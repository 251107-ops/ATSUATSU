from flask import Blueprint, render_template, redirect, session
from routes.auth import get_db

notifications_bp = Blueprint('notifications_bp', __name__)


@notifications_bp.route('/notifications')
def list_notifications():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()

    rows = db.execute("""
        SELECT
            n.notification_id, n.type, n.related_id, n.is_read, n.created_at,
            r.request_id, r.status, r.room_id,
            requester.name AS requester_name,
            receiver.name AS receiver_name,
            s.skill_name, p.post_type
        FROM notifications n
        LEFT JOIN requests r ON n.related_id = r.request_id
        LEFT JOIN posts p ON r.post_id = p.post_id
        LEFT JOIN skills s ON p.skill_id = s.skill_id
        LEFT JOIN users requester ON r.requester_id = requester.user_id
        LEFT JOIN users receiver ON r.receiver_id = receiver.user_id
        WHERE n.user_id = ?
        ORDER BY n.created_at DESC
    """, (user_id,)).fetchall()

    notifications = []
    for row in rows:
        item = dict(row)
        if row['type'] == 'new_request':
            item['message'] = f"{row['requester_name']}さんから「{row['skill_name']}」（{row['post_type']}）への申し込みが届きました"
        elif row['type'] == 'request_accepted':
            item['message'] = f"{row['receiver_name']}さんが「{row['skill_name']}」への申し込みを承認しました"
        elif row['type'] == 'request_declined':
            item['message'] = f"{row['receiver_name']}さんが「{row['skill_name']}」への申し込みをお断りしました"
        elif row['type'] == 'session_completed':
            item['message'] = f"{row['requester_name']}さんとの「{row['skill_name']}」のセッションが完了しました"
        else:
            item['message'] = "通知があります"
        notifications.append(item)

    # 一覧を開いたタイミングで既読にする
    db.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0", (user_id,))
    db.commit()

    return render_template('notifications.html', notifications=notifications)