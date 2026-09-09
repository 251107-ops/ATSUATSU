import secrets
from flask import Blueprint, render_template, redirect, session, request, flash, url_for, jsonify
from routes.auth import get_db

projects_bp = Blueprint('projects_bp', __name__)


def fetch_projects(db, user_id=None):
    """プロジェクト募集カード一覧を取得（top.htmlのcards構造に合わせた辞書で返す）
    カテゴリはprojectsに持たせず、選択したスキルが属するcategoryをそのまま表示に使う"""
    rows = db.execute("""
        SELECT
            p.project_id, p.project_name, p.description, p.recruit_count, p.status,
            p.group_room_id,
            u.user_id, u.name, u.department, u.grade, u.icon_path,
            s.skill_name,
            c.category_name
        FROM projects p
        JOIN users u ON p.owner_user_id = u.user_id
        JOIN skills s ON p.skill_id = s.skill_id
        LEFT JOIN categories c ON s.category_id = c.category_id
        WHERE p.status = 'recruiting'
        ORDER BY p.created_at DESC
    """).fetchall()

    projects_list = []
    for row in rows:
        current_members = db.execute(
            "SELECT COUNT(*) FROM group_members WHERE group_room_id = ?", (row['group_room_id'],)
        ).fetchone()[0]

        already_applied = False
        if user_id:
            already_applied = bool(db.execute(
                "SELECT 1 FROM project_requests WHERE project_id = ? AND applicant_id = ? AND status = 'pending'",
                (row['project_id'], user_id)
            ).fetchone())

        already_member = False
        if user_id:
            already_member = bool(db.execute(
                "SELECT 1 FROM group_members WHERE group_room_id = ? AND user_id = ?",
                (row['group_room_id'], user_id)
            ).fetchone())

        projects_list.append({
            'card_type': 'project',
            'project_id': row['project_id'],
            'project_name': row['project_name'],
            'description': row['description'],
            'recruit_count': row['recruit_count'],
            'current_members': current_members,
            'category_name': row['category_name'] if row['category_name'] else '未設定',
            'skill_name': row['skill_name'],
            'name': row['name'],
            'department': row['department'],
            'grade': row['grade'],
            'icon_path': row['icon_path'],
            'user_id': row['user_id'],
            'is_owner': (user_id == row['user_id']),
            'already_applied': already_applied,
            'already_member': already_member,
        })
    return projects_list


@projects_bp.route('/project/new', methods=['GET', 'POST'])
def new_project():
    """ルーム作成を統合したプロジェクト作成画面"""
    if 'user_email' not in session:
        return redirect('/login')

    user_id = session.get('user_id')
    db = get_db()

    if request.method == 'POST':
        project_name = request.form.get('project_name', '').strip()
        description = request.form.get('description', '').strip()
        recruit_count = request.form.get('recruit_count', '2')
        skill_id = request.form.get('skill_id', '')
        is_public = 1 if request.form.get('is_public', 'public') == 'public' else 0

        if not project_name or not description or not skill_id:
            flash("すべての項目を入力してください。")
            return redirect('/project/new')

        skill_id = int(skill_id)

        # 個人のスキルカードと同じルール：同一ユーザー×同一スキルの重複プロジェクトは不可
        existing = db.execute(
            "SELECT 1 FROM projects WHERE owner_user_id = ? AND skill_id = ?",
            (user_id, skill_id)
        ).fetchone()
        if existing:
            flash("このスキルに関するプロジェクトはすでに作成されています。（1つのスキルにつき1つまで）")
            return redirect('/project/new')

        # グループルームを先に作成
        group_room_id = secrets.token_hex(4)
        db.execute(
            "INSERT INTO group_rooms (group_room_id, skill_id, created_by, is_public) VALUES (?, ?, ?, ?)",
            (group_room_id, skill_id, user_id, is_public)
        )
        db.execute(
            "INSERT INTO group_members (group_room_id, user_id, role) VALUES (?, ?, 'owner')",
            (group_room_id, user_id)
        )

        db.execute("""
            INSERT INTO projects (owner_user_id, project_name, description, skill_id, recruit_count, group_room_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, project_name, description, skill_id, int(recruit_count), group_room_id))

        db.commit()
        flash("プロジェクトを作成しました。")
        return redirect('/')

    categories = db.execute("SELECT category_id, category_name FROM categories ORDER BY category_id").fetchall()
    skills = db.execute("SELECT skill_id, skill_name, category_id FROM skills ORDER BY skill_id").fetchall()

    return render_template('project_new.html', categories=categories, skills=skills)


@projects_bp.route('/projects')
def project_top():
    """プロジェクト募集カードのみのトップ画面"""
    if 'user_email' not in session:
        return redirect('/login')

    db = get_db()
    user_id = session.get('user_id')
    projects_list = fetch_projects(db, user_id=user_id)

    return render_template('project_top.html', posts=projects_list)


@projects_bp.route('/project/apply', methods=['POST'])
def apply_project():
    user_id = session.get('user_id')
    is_async = request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if not user_id:
        if is_async:
            return jsonify({'success': False, 'message': 'ログインが必要です。'}), 401
        return redirect('/login')

    project_id = request.form.get('project_id')
    if not project_id:
        if is_async:
            return jsonify({'success': False, 'message': 'プロジェクトIDが見つかりません。'}), 400
        flash('プロジェクトIDが見つかりません。')
        return redirect('/')

    db = get_db()
    project = db.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()

    if not project:
        msg = '該当のプロジェクトが存在しません。'
        if is_async:
            return jsonify({'success': False, 'message': msg}), 404
        flash(msg)
        return redirect('/')

    if project['owner_user_id'] == user_id:
        msg = '自分のプロジェクトには申請できません。'
        if is_async:
            return jsonify({'success': False, 'message': msg, 'reason': 'own_project'}), 400
        flash(msg)
        return redirect('/')

    already_member = db.execute(
        "SELECT 1 FROM group_members WHERE group_room_id = ? AND user_id = ?",
        (project['group_room_id'], user_id)
    ).fetchone()
    if already_member:
        msg = 'すでにこのプロジェクトに参加しています。'
        if is_async:
            return jsonify({'success': False, 'message': msg, 'reason': 'already_member'}), 400
        flash(msg)
        return redirect('/')

    existing = db.execute("""
        SELECT 1 FROM project_requests
        WHERE project_id = ? AND applicant_id = ? AND status = 'pending'
    """, (project_id, user_id)).fetchone()
    if existing:
        msg = 'すでにこのプロジェクトに参加申請を送信しています。'
        if is_async:
            return jsonify({'success': False, 'message': msg, 'reason': 'duplicate'}), 400
        flash(msg)
        return redirect('/')

    cursor = db.execute("""
        INSERT INTO project_requests (project_id, applicant_id, status)
        VALUES (?, ?, 'pending')
    """, (project_id, user_id))

    db.execute("""
        INSERT INTO notifications (user_id, type, related_id)
        VALUES (?, 'new_project_request', ?)
    """, (project['owner_user_id'], cursor.lastrowid))

    db.commit()

    msg = 'プロジェクト参加申請を送信しました！'
    if is_async:
        return jsonify({'success': True, 'message': msg})
    flash(msg)
    return redirect('/')


@projects_bp.route('/project/request/<int:request_id>/accept', methods=['POST'])
def accept_project_request(request_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()
    req = db.execute("""
        SELECT pr.*, p.group_room_id, p.recruit_count, p.owner_user_id, p.project_name, p.project_id
        FROM project_requests pr
        JOIN projects p ON pr.project_id = p.project_id
        WHERE pr.request_id = ?
    """, (request_id,)).fetchone()

    if not req:
        return "申請が見つかりません", 404
    if req['owner_user_id'] != user_id:
        return "この申請を承認する権限がありません", 403
    if req['status'] != 'pending':
        return redirect(url_for('.project_top'))

    current_members = db.execute(
        "SELECT COUNT(*) FROM group_members WHERE group_room_id = ?", (req['group_room_id'],)
    ).fetchone()[0]

    if current_members >= req['recruit_count']:
        flash("募集人数に達しているため承認できません。")
        return redirect(url_for('.project_top'))

    db.execute(
        "INSERT OR IGNORE INTO group_members (group_room_id, user_id, role) VALUES (?, ?, 'member')",
        (req['group_room_id'], req['applicant_id'])
    )
    db.execute(
        "UPDATE project_requests SET status = 'accepted', updated_at = datetime('now','localtime') WHERE request_id = ?",
        (request_id,)
    )

    # 定員に達したら募集を締め切る
    new_count = current_members + 1
    if new_count >= req['recruit_count']:
        db.execute("UPDATE projects SET status = 'full' WHERE project_id = ?", (req['project_id'],))

    db.execute("""
        INSERT INTO notifications (user_id, type, related_id) VALUES (?, 'project_request_accepted', ?)
    """, (req['applicant_id'], req['project_id']))
    db.commit()

    # TODO: なりまつさんのグループチャット画面のroute名が確定したらここを差し替える
    # 例: return redirect(url_for('group_chat.room', group_room_id=req['group_room_id']))
    flash(f"承認しました。グループチャット「{req['project_name']}」に追加されました。")
    return redirect(url_for('.project_top'))


@projects_bp.route('/project/request/<int:request_id>/decline', methods=['POST'])
def decline_project_request(request_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()
    req = db.execute("""
        SELECT pr.*, p.owner_user_id FROM project_requests pr
        JOIN projects p ON pr.project_id = p.project_id
        WHERE pr.request_id = ?
    """, (request_id,)).fetchone()

    if not req:
        return "申請が見つかりません", 404
    if req['owner_user_id'] != user_id:
        return "この申請を拒否する権限がありません", 403
    if req['status'] != 'pending':
        return redirect(url_for('.project_top'))

    db.execute(
        "UPDATE project_requests SET status = 'declined', updated_at = datetime('now','localtime') WHERE request_id = ?",
        (request_id,)
    )
    db.execute("""
        INSERT INTO notifications (user_id, type, related_id) VALUES (?, 'project_request_declined', ?)
    """, (req['applicant_id'], req['project_id']))
    db.commit()

    return redirect(url_for('.project_top'))