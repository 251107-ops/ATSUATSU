import traceback
from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from routes.auth import get_db
from routes.chat import create_chat_room

requests_bp = Blueprint('requests', __name__)


# POST /requests -- 新規リクエスト送信
@requests_bp.route('/requests', methods=['POST'])
def send_request():
    user_id = session.get('user_id')
    post_id = request.form.get('post_id')
    if not post_id and request.is_json:
        data = request.get_json()
        post_id = data.get('post_id') if data else None

    if not user_id:
        flash('ログインが必要です。')
        return redirect('/login')

    if not post_id:
        flash('投稿IDが見つかりません。')
        return redirect('/')

    db = get_db()

    try:
        post = db.execute(
            'SELECT * FROM posts WHERE post_id = ?', (post_id,)
        ).fetchone()

        if not post:
            flash('該当の投稿が存在しません。')
            return redirect('/')

        receiver_id = (
            post['user_id']
            if 'user_id' in post.keys()
            else post.get('poster_id')
        )

        if str(user_id) == str(receiver_id):
            flash('自分の投稿にはリクエストを送れません。')
            return redirect('/')

        existing = db.execute(
            """
            SELECT request_id FROM requests 
            WHERE requester_id = ? 
              AND CAST(post_id AS TEXT) = CAST(? AS TEXT) 
              AND status IN ('pending', 'accepted')
            """,
            (user_id, post_id),
        ).fetchone()

        if existing:
            flash(
                'すでにこの投稿にリクエストを送信しています。相手の承認をお待ちください。'
            )
            return redirect('/')

        db.execute(
            """
            INSERT INTO requests (requester_id, receiver_id, post_id, status)
            VALUES (?, ?, ?, 'pending')
            """,
            (user_id, receiver_id, post_id),
        )

        db.execute(
            """
            INSERT INTO notifications (user_id, type)
            VALUES (?, 'new_request')
            """,
            (receiver_id,),
        )

        db.commit()
        flash('リクエストを送信しました！')
        return redirect('/requests')

    except Exception as e:
        db.rollback()
        print('========== [ERROR DETAILED TRACEBACK] ==========')
        traceback.print_exc()
        print('=================================================')
        flash(f'送信に失敗しました: {e}')
        return redirect('/')


# GET /requests -- リクエスト一覧表示
@requests_bp.route('/requests', methods=['GET'])
def list_requests():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()

    received = db.execute(
        """
        SELECT 
            r.*, 
            u.name AS requester_name, 
            p.post_text, 
            rm.room_id
        FROM requests r
        JOIN users u ON r.requester_id = u.user_id
        JOIN posts p ON r.post_id = p.post_id
        LEFT JOIN room_members rm ON rm.user_id = r.requester_id
        WHERE r.receiver_id = ?
        ORDER BY r.request_id DESC
        """,
        (user_id,),
    ).fetchall()

    sent = db.execute(
        """
        SELECT 
            r.*, 
            u.name AS receiver_name, 
            p.post_text, 
            rm.room_id
        FROM requests r
        JOIN users u ON r.receiver_id = u.user_id
        JOIN posts p ON r.post_id = p.post_id
        LEFT JOIN room_members rm ON rm.user_id = r.receiver_id
        WHERE r.requester_id = ?
        ORDER BY r.request_id DESC
        """,
        (user_id,),
    ).fetchall()

    return render_template('request_list.html', received=received, sent=sent)


# POST /requests/<id>/accept -- 承認
@requests_bp.route('/requests/<int:req_id>/accept', methods=['POST'])
def accept_request(req_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()

    try:
        req = db.execute(
            'SELECT * FROM requests WHERE request_id = ? AND receiver_id = ?',
            (req_id, user_id),
        ).fetchone()

        if not req:
            flash('権限がないか、リクエストが存在しません。')
            return redirect('/requests')

        room_id = create_chat_room(req['requester_id'], req['receiver_id'])

        db.execute(
            "UPDATE requests SET status = 'accepted' WHERE request_id = ?",
            (req_id,),
        )

        db.execute(
            """
            INSERT INTO notifications (user_id, type)
            VALUES (?, 'request_accepted')
            """,
            (req['requester_id'],),
        )

        db.commit()
        return redirect(url_for('chat.chat_room', room_id=room_id))

    except Exception as e:
        db.rollback()
        print('========== [ACCEPT ERROR TRACEBACK] ==========')
        traceback.print_exc()
        print('=============================================')
        flash(f'承認処理に失敗しました: {e}')
        return redirect('/requests')


# POST /requests/<id>/decline -- 拒否
@requests_bp.route('/requests/<int:req_id>/decline', methods=['POST'])
def decline_request(req_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()
    req = db.execute(
        'SELECT * FROM requests WHERE request_id = ? AND receiver_id = ?',
        (req_id, user_id),
    ).fetchone()

    if req:
        db.execute(
            "UPDATE requests SET status = 'declined' WHERE request_id = ?",
            (req_id,),
        )

        db.execute(
            """
            INSERT INTO notifications (user_id, type)
            VALUES (?, 'request_declined')
            """,
            (req['requester_id'],),
        )
        db.commit()

    return redirect('/requests')


# POST /requests/<id>/complete -- 完了
@requests_bp.route('/requests/<int:req_id>/complete', methods=['POST'])
def complete_request(req_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()

    try:
        req = db.execute(
            'SELECT * FROM requests WHERE request_id = ?', (req_id,)
        ).fetchone()

        if not req or (
            str(req['requester_id']) != str(user_id)
            and str(req['receiver_id']) != str(user_id)
        ):
            flash('この操作を行う権限がありません。')
            return redirect('/requests')

        db.execute(
            "UPDATE requests SET status = 'completed' WHERE request_id = ?",
            (req_id,),
        )

        target_user = (
            req['receiver_id']
            if str(req['requester_id']) == str(user_id)
            else req['requester_id']
        )

        db.execute(
            """
            INSERT INTO notifications (user_id, type)
            VALUES (?, 'request_completed')
            """,
            (target_user,),
        )

        db.commit()
        flash('チャットを終了し、リクエストを完了しました。')
        return redirect('/requests')

    except Exception as e:
        db.rollback()
        print('========== [COMPLETE ERROR TRACEBACK] ==========')
        traceback.print_exc()
        print('=================================================')
        flash(f'完了処理に失敗しました: {e}')
        return redirect('/requests')


# GET /notifications -- 通知一覧（送信者の名前と room_id を取得）
@requests_bp.route('/notifications', methods=['GET'])
def list_notifications():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()

    # ★ room_members を結合して 該当チャットルームの room_id も同時に取得
    notifications = db.execute(
        """
        SELECT 
            n.*,
            u.name AS sender_name,
            rm.room_id
        FROM notifications n
        LEFT JOIN requests r ON (
            (n.type = 'new_request' AND r.receiver_id = n.user_id) OR
            (n.type IN ('request_accepted', 'request_completed', 'request_declined') AND r.requester_id = n.user_id)
        )
        LEFT JOIN users u ON u.user_id = (
            CASE 
                WHEN n.type = 'new_request' THEN r.requester_id
                ELSE r.receiver_id
            END
        )
        LEFT JOIN room_members rm ON rm.user_id = n.user_id 
            AND rm.room_id IN (SELECT room_id FROM room_members WHERE user_id = u.user_id)
        WHERE n.user_id = ?
        GROUP BY n.rowid
        ORDER BY n.rowid DESC
        """,
        (user_id,),
    ).fetchall()

    db.execute(
        'UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0',
        (user_id,),
    )
    db.commit()

    return render_template('notifications.html', notifications=notifications)