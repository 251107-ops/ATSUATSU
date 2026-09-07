from flask import Blueprint, render_template, redirect, session, request, url_for, flash
from routes.auth import get_db

reviews_bp = Blueprint('reviews_bp', __name__)


@reviews_bp.route('/reviews/new/<int:request_id>', methods=['GET', 'POST'])
def new_review(request_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()
    
    req = db.execute("""
        SELECT * FROM requests 
        WHERE request_id = ? OR room_id = ?
    """, (request_id, str(request_id))).fetchone()

    # ⭕ 画面遷移（テキスト返却）せず flash メッセージを出して一覧へ戻す
    if not req:
        flash('指定されたリクエストが見つかりませんでした。', 'error')
        return redirect(url_for('requests_bp.list_requests'))

    current_user_id = int(user_id)
    requester_id = int(req['requester_id'])
    receiver_id = int(req['receiver_id'])

    if current_user_id not in (requester_id, receiver_id):
        flash('この評価を投稿する権限がありません。', 'error')
        return redirect(url_for('requests_bp.list_requests'))

    if req['status'] != 'completed':
        flash('このリクエストはまだ評価できません。', 'error')
        return redirect(url_for('requests_bp.list_requests'))

    reviewer_id = current_user_id
    reviewee_id = receiver_id if current_user_id == requester_id else requester_id

    existing = db.execute("""
        SELECT 1 FROM reviews 
        WHERE request_id = ? AND reviewer_id = ?
    """, (req['request_id'], reviewer_id)).fetchone()
    
    if existing:
        flash('このセッションは既に評価済みです。', 'info')
        return redirect(url_for('requests_bp.list_requests'))

    # 評価対象（相手）とスキル情報を取得
    # ★ ここで取れる skill_name / post_type を「評価時点のスナップショット」として使う
    info = db.execute("""
        SELECT u.name AS partner_name, s.skill_name, p.post_type
        FROM requests r
        LEFT JOIN posts p ON r.post_id = p.post_id
        LEFT JOIN skills s ON p.skill_id = s.skill_id
        JOIN users u ON u.user_id = ?
        WHERE r.request_id = ?
    """, (reviewee_id, req['request_id'])).fetchone()

    if request.method == 'POST':
        rating = request.form.get('rating', '')
        comment = request.form.get('comment', '').strip()

        # ⭕ 評価（星）が未選択などのバリデーションエラー時
        # ページ遷移せず flash メッセージを表示し、入力内容を維持して同じ画面を再描画
        if not rating or not rating.isdigit() or not (1 <= int(rating) <= 5):
            flash('評価（星1〜5）を選択してください。', 'error')
            return render_template('review_new.html', req=req, info=info, comment=comment)

        db.execute("""
            INSERT INTO reviews (request_id, reviewer_id, reviewee_id, rating, comment, skill_name, post_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            req['request_id'], reviewer_id, reviewee_id, int(rating), comment,
            info['skill_name'] if info else None,
            info['post_type'] if info else None
        ))

        db.execute("""
            UPDATE requests SET status = 'reviewed', updated_at = datetime('now','localtime')
            WHERE request_id = ?
        """, (req['request_id'],))
        
        db.execute("""
            INSERT INTO notifications (user_id, type, related_id) VALUES (?, 'new_review', ?)
        """, (reviewee_id, req['request_id']))
        
        db.commit()

        flash('評価を送信しました！', 'success')
        return redirect(url_for('requests_bp.list_requests'))

    return render_template('review_new.html', req=req, info=info)


@reviews_bp.route('/profile/reviews')
def list_reviews():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()

    # ★ posts / skills を経由しなくなったので、投稿が消えても影響を受けない
    reviews = db.execute("""
        SELECT comment, created_at, skill_name, post_type
        FROM reviews
        WHERE reviewee_id = ?
        ORDER BY created_at DESC
    """, (user_id,)).fetchall()

    stats = db.execute("""
        SELECT AVG(rating) AS avg_rating, COUNT(*) AS review_count
        FROM reviews WHERE reviewee_id = ?
    """, (user_id,)).fetchone()

    return render_template('review_list.html', reviews=reviews, stats=stats)