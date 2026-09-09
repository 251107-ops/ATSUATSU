from flask import Blueprint, render_template, redirect, session
from routes.auth import get_db

notifications_bp = Blueprint('notifications_bp', __name__)


@notifications_bp.route('/notifications')
def list_notifications():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()

    # ⭕ rev.review_id が存在するかどうかで has_reviewed フラグ（1 or 0）を作成
    # 💡 プロジェクト機能の通知(new_project_request / project_request_accepted /
    #    project_request_declined)にも対応するため project_requests / projects を条件付きJOINで追加。
    #    related_id の意味が type によって異なる点に注意:
    #      - new_project_request          → related_id = project_requests.request_id
    #      - project_request_accepted/declined → related_id = projects.project_id
    rows = db.execute("""
        SELECT
            n.notification_id, n.type, n.related_id, n.is_read, n.created_at,
            r.request_id, r.status, r.room_id,
            requester.name AS requester_name,
            receiver.name AS receiver_name,
            s.skill_name, p.post_type,
            CASE WHEN rev.review_id IS NOT NULL THEN 1 ELSE 0 END AS has_reviewed,
            pr.request_id AS project_request_id,
            pr.status AS project_request_status,
            proj.project_id AS project_id,
            proj.project_name AS project_name,
            proj.group_room_id AS group_room_id,
            applicant.name AS applicant_name
        FROM notifications n
        LEFT JOIN requests r ON n.related_id = r.request_id
        LEFT JOIN posts p ON r.post_id = p.post_id
        LEFT JOIN skills s ON p.skill_id = s.skill_id
        LEFT JOIN users requester ON r.requester_id = requester.user_id
        LEFT JOIN users receiver ON r.receiver_id = receiver.user_id
        LEFT JOIN reviews rev ON rev.request_id = r.request_id AND rev.reviewer_id = ?
        LEFT JOIN project_requests pr
            ON n.type = 'new_project_request' AND n.related_id = pr.request_id
        LEFT JOIN projects proj
            ON (n.type = 'new_project_request' AND pr.project_id = proj.project_id)
            OR (n.type IN ('project_request_accepted', 'project_request_declined')
                AND n.related_id = proj.project_id)
        LEFT JOIN users applicant ON pr.applicant_id = applicant.user_id
        WHERE n.user_id = ?
        ORDER BY n.created_at DESC
    """, (user_id, user_id)).fetchall()

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
        elif row['type'] == 'completion_pending':
            item['message'] = f"{row['requester_name'] if row['status'] else ''}チャット終了の申請が届いています。あなたも「チャット終了」を押すと完了します"
        elif row['type'] == 'new_review':
            item['message'] = f"「{row['skill_name']}」のセッションについて評価が届きました"
        elif row['type'] == 'awaiting_review':
            item['message'] = f"「{row['skill_name']}」のセッションが完了しました。評価をお願いします"
        elif row['type'] == 'awaiting_review_teacher':
            item['message'] = f"「{row['skill_name']}」のセッションが完了しました。{row['requester_name']}さんからの評価をお待ちください"
        elif row['type'] == 'new_project_request':
            # 💡 異常系対応: 通知が残っている間にプロジェクトが削除されるとproject_nameがNoneになるため、
            #    「None」がそのまま画面に出ないようフォールバックする
            proj_name = row['project_name'] or '削除されたプロジェクト'
            applicant_name = row['applicant_name'] or '不明なユーザー'
            item['message'] = f"{applicant_name}さんから「{proj_name}」への参加申請が届きました"
        elif row['type'] == 'project_request_accepted':
            proj_name = row['project_name'] or '削除されたプロジェクト'
            item['message'] = f"「{proj_name}」への参加申請が承認されました！グループチャットに参加できます"
        elif row['type'] == 'project_request_declined':
            proj_name = row['project_name'] or '削除されたプロジェクト'
            item['message'] = f"「{proj_name}」への参加申請はお断りされました"
        else:
            item['message'] = "通知があります"
        
        notifications.append(item)

    # 一覧を開いたタイミングで既読にする
    db.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0", (user_id,))
    db.commit()

    return render_template('notifications.html', notifications=notifications)