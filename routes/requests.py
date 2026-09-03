import traceback
import secrets
from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from routes.auth import get_db
from routes.chat import create_chat_room

requests_bp = Blueprint('requests_bp', __name__)


# =====================================================================
# 1. POST /requests -- 新規リクエスト送信（非同期/同期 両対応）
# =====================================================================
@requests_bp.route('/requests', methods=['POST'])
def send_request():
    user_id = session.get('user_id')
    
    # JSON・Form両方のリクエスト形式に対応
    post_id = request.form.get('post_id')
    if not post_id and request.is_json:
        data = request.get_json()
        post_id = data.get('post_id') if data else None

    # 非同期通信（fetch）判定フラグ
    is_async = request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if not user_id:
        if is_async:
            return jsonify({'success': False, 'message': 'ログインが必要です。'}), 401
        flash('ログインが必要です。')
        return redirect('/login')

    if not post_id:
        if is_async:
            return jsonify({'success': False, 'message': '投稿IDが見つかりません。'}), 400
        flash('投稿IDが見つかりません。')
        return redirect(url_for('.list_requests'))

    db = get_db()

    try:
        post = db.execute(
            'SELECT * FROM posts WHERE post_id = ?', (post_id,)
        ).fetchone()

        if not post:
            if is_async:
                return jsonify({'success': False, 'message': '該当の投稿が存在しません。'}), 404
            flash('該当の投稿が存在しません。')
            return redirect(url_for('.list_requests'))

        receiver_id = (
            post['user_id']
            if 'user_id' in post.keys()
            else post.get('poster_id')
        )

        if str(user_id) == str(receiver_id):
            if is_async:
                return jsonify({
                    'success': False, 
                    'message': '自分の投稿にはリクエストを送れません。',
                    'reason': 'own_post'
                    }), 400
            flash('自分の投稿にはリクエストを送れません。')
            return redirect(url_for('.list_requests'))

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
            msg = 'すでにこの投稿にリクエストを送信しています。'
            if is_async:
                return jsonify({'success': False, 'message': msg,'reason': 'duplicate'}), 400
            flash(msg)
            return redirect(url_for('.list_requests'))

        # リクエスト登録
        cursor = db.execute(
            """
            INSERT INTO requests (requester_id, receiver_id, post_id, status)
            VALUES (?, ?, ?, 'pending')
            """,
            (user_id, receiver_id, post_id),
        )

        # 通知登録
        db.execute(
            """
            INSERT INTO notifications (user_id, type, related_id)
            VALUES (?, 'new_request', ?)
            """,
            (receiver_id, cursor.lastrowid),
        )

        db.commit()

        if is_async:
            return jsonify({'success': True, 'message': 'リクエストを送信しました！'})
        
        flash('リクエストを送信しました！')
        return redirect(url_for('.list_requests'))

    except Exception as e:
        db.rollback()
        print('========== [ERROR DETAILED TRACEBACK] ==========')
        traceback.print_exc()
        print('=================================================')
        if is_async:
            return jsonify({'success': False, 'message': f'送信に失敗しました: {e}'}), 500
        flash(f'送信に失敗しました: {e}')
        return redirect(url_for('.list_requests'))


# =====================================================================
# 2. GET /requests -- リクエスト一覧表示
# =====================================================================
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
               r.requester_completed, r.receiver_completed,
               u.name AS partner_name, s.skill_name, p.post_type
        FROM requests r
        JOIN posts p ON r.post_id = p.post_id
        JOIN skills s ON p.skill_id = s.skill_id
        JOIN users u ON r.receiver_id = u.user_id
        WHERE r.requester_id = ?
        ORDER BY r.created_at DESC
    """, (user_id,)).fetchall()

    # 自分が受け取ったリクエストを取得
    received = db.execute("""
        SELECT r.request_id, r.status, r.room_id, r.created_at,
               r.requester_completed, r.receiver_completed,
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
# 3. リクエストの承諾（受信側のみ） → ルーム自動作成
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

    cursor = db.execute(
        "INSERT INTO rooms (skill_id, is_public, created_by) VALUES (?, 0, ?)",
        (post['skill_id'], user_id)
    )
    room_id = cursor.lastrowid

    db.execute("INSERT INTO room_members (room_id, user_id) VALUES (?, ?)", (room_id, req['requester_id']))
    db.execute("INSERT INTO room_members (room_id, user_id) VALUES (?, ?)", (room_id, req['receiver_id']))
    db.execute("""
        UPDATE requests SET status = 'accepted', room_id = ?, updated_at = datetime('now','localtime')
        WHERE request_id = ?
    """, (room_id, request_id))

    db.execute("""
        INSERT INTO notifications (user_id, type, related_id) VALUES (?, 'request_accepted', ?)
    """, (req['requester_id'], request_id))
    db.commit()

    return redirect(url_for('chat.chat_room', room_id=room_id))
    
# =====================================================================
# 4. リクエストの拒否（受信側のみ）
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

    db.execute("""
        INSERT INTO notifications (user_id, type, related_id) VALUES (?, 'request_declined', ?)
    """, (req['requester_id'], request_id))
    db.commit()

    return redirect(url_for('.list_requests'))


# =====================================================================
# 5. セッション完了（申し込んだ側=requesterのみ）
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

    if user_id == req['requester_id']:
        my_col = 'requester_completed'
        partner_id = req['receiver_id']
    elif user_id == req['receiver_id']:
        my_col = 'receiver_completed'
        partner_id = req['requester_id']
    else:
        return "このセッションの当事者ではありません", 403

    if req['status'] != 'accepted':
        return redirect(url_for('chat.chat_room', room_id=req['room_id']))

    db.execute(f"UPDATE requests SET {my_col} = 1, updated_at = datetime('now','localtime') WHERE request_id = ?",
               (request_id,))
    db.commit()

    updated = db.execute("SELECT * FROM requests WHERE request_id = ?", (request_id,)).fetchone()

    if updated['requester_completed'] == 1 and updated['receiver_completed'] == 1:
        # 両者合意 → completed に確定
        db.execute(
            "UPDATE requests SET status = 'completed', updated_at = datetime('now','localtime') WHERE request_id = ?",
            (request_id,)
        )
        # 教えてる側（receiver）にも「評価待ち」を通知
        db.execute(
            "INSERT INTO notifications (user_id, type, related_id) VALUES (?, 'awaiting_review_teacher', ?)",
            (req['receiver_id'], request_id)
        )
        db.execute(
            "INSERT INTO notifications (user_id, type, related_id) VALUES (?, 'awaiting_review', ?)",
            (req['requester_id'], request_id))

        db.commit()

        # requesterが最後に押した場合だけ評価画面へ、receiverならリクエスト一覧へ
        if user_id == req['requester_id']:
            return redirect(url_for('reviews_bp.new_review', request_id=request_id))
        else:
            return redirect(url_for('.list_requests'))
    else:
        # まだ片方だけ → 相手に「あなたも押してください」通知
        db.execute(
            "INSERT INTO notifications (user_id, type, related_id) VALUES (?, 'completion_pending', ?)",
            (partner_id, request_id)
        )
        db.commit()
        return redirect(url_for('.list_requests'))