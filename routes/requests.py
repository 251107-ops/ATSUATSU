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

    if request.method == 'POST':
        post_id = request.form.get('post_id')
        if not post_id:
            return "post_idが必要です", 400

        post = db.execute("SELECT user_id FROM posts WHERE post_id = ?", (post_id,)).fetchone()
        if not post:
            return "対象の投稿が見つかりません", 404

        receiver_id = post['user_id']
        if receiver_id == user_id:
            return "自分の投稿にはリクエストできません", 400

        # 同じ投稿に対して pending/accepted 中のリクエストが既にあれば二重送信を防ぐ
        existing = db.execute("""
            SELECT 1 FROM requests
            WHERE post_id = ? AND requester_id = ? AND status IN ('pending', 'accepted')
        """, (post_id, user_id)).fetchone()

        if not existing:
            cursor = db.execute("""
                INSERT INTO requests (post_id, requester_id, receiver_id, status)
                VALUES (?, ?, ?, 'pending')
            """, (post_id, user_id, receiver_id))
            db.commit()

            db.execute("""
                INSERT INTO notifications (user_id, type, related_id)
                VALUES (?, 'new_request', ?)
            """, (receiver_id, cursor.lastrowid))
            db.commit()

        return redirect(url_for('.list_requests'))

    # ↓ GET: 自分が送った/受けたリクエストを両方取得
    sent = db.execute("""
        SELECT r.request_id, r.status, r.room_id, r.created_at,
               u.name AS partner_name, s.skill_name, p.post_type
        FROM requests r
        JOIN posts p ON r.post_id = p.post_id
        JOIN skills s ON p.skill_id = s.skill_id
        JOIN users u ON r.receiver_id = u.user_id
        WHERE r.requester_id = ?
        ORDER BY r.created_at DESC
    """, (user_id,)).fetchall()

    received = db.execute("""
        SELECT r.request_id, r.status, r.room_id, r.created_at,
               u.name AS partner_name, s.skill_name, p.post_type
        FROM requests r
        JOIN posts p ON r.post_id = p.post_id
        JOIN skills s ON p.skill_id = s.skill_id
        JOIN users u ON r.requester_id = u.user_id
        WHERE r.receiver_id = ?
        ORDER BY r.created_at DESC
    """, (user_id,)).fetchall()

    return render_template('request_list.html', sent=sent, received=received)


# =====================================================================
# 2. リクエストの承諾（受信側のみ） → ルーム自動作成
# =====================================================================
@requests_bp.route('/requests/<int:request_id>/accept', methods=['POST'])
def accept_request(request_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()
    req = db.execute("SELECT * FROM requests WHERE request_id = ?", (request_id,)).fetchone()

    if not req:
        return "リクエストが見つかりません", 404
    if req['receiver_id'] != user_id:
        return "このリクエストを承諾する権限がありません", 403
    if req['status'] != 'pending':
        return redirect(url_for('.list_requests'))

    post = db.execute("SELECT skill_id FROM posts WHERE post_id = ?", (req['post_id'],)).fetchone()

    room_id = secrets.token_hex(4)
    db.execute(
        "INSERT INTO rooms (room_id, skill_id, is_public, created_by) VALUES (?, ?, 0, ?)",
        (room_id, post['skill_id'], user_id)
    )
    db.execute("INSERT INTO room_members (room_id, user_id) VALUES (?, ?)", (room_id, req['requester_id']))
    db.execute("INSERT INTO room_members (room_id, user_id) VALUES (?, ?)", (room_id, req['receiver_id']))
    db.execute("""
        UPDATE requests SET status = 'accepted', room_id = ?, updated_at = datetime('now','localtime')
        WHERE request_id = ?
    """, (room_id, request_id))
    db.commit()

    db.execute("""
        INSERT INTO notifications (user_id, type, related_id) VALUES (?, 'request_accepted', ?)
    """, (req['requester_id'], request_id))
    db.commit()

    return redirect(url_for('chat.chat_room', room_id=room_id))


# =====================================================================
# 3. リクエストの拒否（受信側のみ）
# =====================================================================
@requests_bp.route('/requests/<int:request_id>/decline', methods=['POST'])
def decline_request(request_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()
    req = db.execute("SELECT * FROM requests WHERE request_id = ?", (request_id,)).fetchone()

    if not req:
        return "リクエストが見つかりません", 404
    if req['receiver_id'] != user_id:
        return "このリクエストを拒否する権限がありません", 403
    if req['status'] != 'pending':
        return redirect(url_for('.list_requests'))

    db.execute("""
        UPDATE requests SET status = 'declined', updated_at = datetime('now','localtime')
        WHERE request_id = ?
    """, (request_id,))
    db.commit()

    db.execute("""
        INSERT INTO notifications (user_id, type, related_id) VALUES (?, 'request_declined', ?)
    """, (req['requester_id'], request_id))
    db.commit()

    return redirect(url_for('.list_requests'))


# =====================================================================
# 4. セッション完了（申し込んだ側=requesterのみ）
# =====================================================================
@requests_bp.route('/requests/<int:request_id>/complete', methods=['POST'])
def complete_request(request_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()
    req = db.execute("SELECT * FROM requests WHERE request_id = ?", (request_id,)).fetchone()

    if not req:
        return "リクエストが見つかりません", 404
    if req['requester_id'] != user_id:
        return "セッション完了にできるのは申し込んだ本人のみです", 403
    if req['status'] != 'accepted':
        return redirect(url_for('.list_requests'))

    db.execute("""
        UPDATE requests SET status = 'completed', updated_at = datetime('now','localtime')
        WHERE request_id = ?
    """, (request_id,))
    db.commit()

    db.execute("""
        INSERT INTO notifications (user_id, type, related_id) VALUES (?, 'session_completed', ?)
    """, (req['receiver_id'], request_id))
    db.commit()

    # レビュー機能がまだ無いので、いったん一覧に戻す
    return redirect(url_for('.list_requests'))
