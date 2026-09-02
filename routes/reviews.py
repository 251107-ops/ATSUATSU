from flask import Blueprint, render_template, redirect, session, request, url_for
from routes.auth import get_db

reviews_bp = Blueprint('reviews_bp', __name__)


@reviews_bp.route('/reviews/new/<int:request_id>', methods=['GET', 'POST'])
def new_review(request_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()
    
    # 1. request_id または room_id のどちらが渡されても取得できるように検索
    req = db.execute("""
        SELECT * FROM requests 
        WHERE request_id = ? OR room_id = ?
    """, (request_id, str(request_id))).fetchone()

    if not req:
        return "リクエストが見つかりません", 404

    # 2. 型を int に揃え、申請者(requester_id)・受領者(receiver_id)の双方を許可
    current_user_id = int(user_id)
    requester_id = int(req['requester_id'])
    receiver_id = int(req['receiver_id'])

    if current_user_id not in (requester_id, receiver_id):
        return "この評価を投稿する権限がありません", 403

    if req['status'] != 'completed':
        return "このリクエストはまだ評価できません", 400

    # 3. 評価する側（自分）と評価される側（相手）のIDを自動判定
    reviewer_id = current_user_id
    reviewee_id = receiver_id if current_user_id == requester_id else requester_id

    # 重複評価の防止チェック
    existing = db.execute("""
        SELECT 1 FROM reviews 
        WHERE request_id = ? AND reviewer_id = ?
    """, (req['request_id'], reviewer_id)).fetchone()
    
    if existing:
        return redirect(url_for('requests_bp.list_requests'))

    if request.method == 'POST':
        rating = request.form.get('rating', '')
        comment = request.form.get('comment', '').strip()

        if not rating or not rating.isdigit() or not (1 <= int(rating) <= 5):
            return "評価（星1〜5）を選択してください", 400

        # 動的に特定した reviewer_id, reviewee_id を登録
        db.execute("""
            INSERT INTO reviews (request_id, reviewer_id, reviewee_id, rating, comment)
            VALUES (?, ?, ?, ?, ?)
        """, (req['request_id'], reviewer_id, reviewee_id, int(rating), comment))

        db.execute("""
            UPDATE requests SET status = 'reviewed', updated_at = datetime('now','localtime')
            WHERE request_id = ?
        """, (req['request_id'],))
        
        db.execute("""
            INSERT INTO notifications (user_id, type, related_id) VALUES (?, 'new_review', ?)
        """, (reviewee_id, req['request_id']))
        
        db.commit()

        return redirect(url_for('requests_bp.list_requests'))

    # GET: 評価対象（相手）の情報とスキルを取得
    info = db.execute("""
        SELECT u.name AS partner_name, s.skill_name, p.post_type
        FROM requests r
        LEFT JOIN posts p ON r.post_id = p.post_id
        LEFT JOIN skills s ON p.skill_id = s.skill_id
        JOIN users u ON u.user_id = ?
        WHERE r.request_id = ?
    """, (reviewee_id, req['request_id'])).fetchone()

    return render_template('review_new.html', req=req, info=info)


@reviews_bp.route('/profile/reviews')
def list_reviews():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()

    reviews = db.execute("""
        SELECT rv.comment, rv.created_at, s.skill_name
        FROM reviews rv
        JOIN requests r ON rv.request_id = r.request_id
        LEFT JOIN posts p ON r.post_id = p.post_id
        LEFT JOIN skills s ON p.skill_id = s.skill_id
        WHERE rv.reviewee_id = ?
        ORDER BY rv.created_at DESC
    """, (user_id,)).fetchall()

    stats = db.execute("""
        SELECT AVG(rating) AS avg_rating, COUNT(*) AS review_count
        FROM reviews WHERE reviewee_id = ?
    """, (user_id,)).fetchone()

    return render_template('review_list.html', reviews=reviews, stats=stats)