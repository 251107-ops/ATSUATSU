from flask import Blueprint, render_template, redirect, session, request, url_for
from routes.auth import get_db

reviews_bp = Blueprint('reviews_bp', __name__)


@reviews_bp.route('/reviews/new/<int:request_id>', methods=['GET', 'POST'])
def new_review(request_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()
    req = db.execute("SELECT * FROM requests WHERE request_id = ?", (request_id,)).fetchone()

    if not req:
        return "リクエストが見つかりません", 404
    if req['requester_id'] != user_id:
        return "この評価を投稿する権限がありません", 403
    if req['status'] != 'completed':
        return "このリクエストはまだ評価できません", 400

    existing = db.execute("SELECT 1 FROM reviews WHERE request_id = ?", (request_id,)).fetchone()
    if existing:
        return redirect(url_for('requests_bp.list_requests'))

    if request.method == 'POST':
        rating = request.form.get('rating', '')
        comment = request.form.get('comment', '').strip()

        if not rating or not rating.isdigit() or not (1 <= int(rating) <= 5):
            return "評価（星1〜5）を選択してください", 400

        db.execute("""
            INSERT INTO reviews (request_id, reviewer_id, reviewee_id, rating, comment)
            VALUES (?, ?, ?, ?, ?)
        """, (request_id, req['requester_id'], req['receiver_id'], int(rating), comment))

        db.execute("""
            UPDATE requests SET status = 'reviewed', updated_at = datetime('now','localtime')
            WHERE request_id = ?
        """, (request_id,))
        db.commit()

        db.execute("""
            INSERT INTO notifications (user_id, type, related_id) VALUES (?, 'new_review', ?)
        """, (req['receiver_id'], request_id))
        db.commit()

        return redirect(url_for('requests_bp.list_requests'))

    # GET: フォームに出す相手の名前・スキル名を取得
    info = db.execute("""
        SELECT u.name AS partner_name, s.skill_name, p.post_type
        FROM requests r
        JOIN posts p ON r.post_id = p.post_id
        JOIN skills s ON p.skill_id = s.skill_id
        JOIN users u ON r.receiver_id = u.user_id
        WHERE r.request_id = ?
    """, (request_id,)).fetchone()

    return render_template('review_new.html', req=req, info=info)

@reviews_bp.route('/profile/reviews')
def list_reviews():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()

    reviews = db.execute("""
        SELECT comment, created_at
        FROM reviews
        WHERE reviewee_id = ?
        ORDER BY created_at DESC
    """, (user_id,)).fetchall()

    stats = db.execute("""
        SELECT AVG(rating) AS avg_rating, COUNT(*) AS review_count
        FROM reviews WHERE reviewee_id = ?
    """, (user_id,)).fetchone()

    return render_template('review_list.html', reviews=reviews, stats=stats)