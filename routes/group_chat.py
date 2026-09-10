from flask import Blueprint, render_template, redirect, session, request, url_for
from routes.auth import get_db
from flask_socketio import emit, join_room, leave_room
import secrets

group_chat = Blueprint('group_chat', __name__)

# =====================================================================
# 1. グループチャット用ルーティング
# =====================================================================

@group_chat.route('/hub')
def group_chat_hub():
    """チャットハブ画面を表示（選択メニュー）"""
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()
    user_row = db.execute("SELECT name FROM users WHERE user_id = ?", (user_id,)).fetchone()
    user_name = user_row[0] if user_row else "ゲスト"

    return render_template('chat_hub.html', name=user_name)


@group_chat.route('/my-created-group-rooms')
def my_created_group_rooms():
    """自分が作成したグループ（オーナー権限のあるルーム）一覧を表示"""
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()
    
    # 自分が作成者(created_by)になっているグループを取得
    my_groups = db.execute("""
        SELECT gr.group_room_id,
               gr.is_public,
               COALESCE(s.skill_name, '総合交流') AS skill_name,
               (SELECT COUNT(*) FROM group_members WHERE group_room_id = gr.group_room_id) AS total_members
        FROM group_rooms gr
        LEFT JOIN skills s ON gr.skill_id = s.skill_id
        WHERE gr.created_by = ?
    """, (user_id,)).fetchall()

    return render_template('my_created_groups.html', groups=my_groups)


@group_chat.route('/groups')
@group_chat.route('/public-rooms')
def list_groups():
    """公開グループ一覧表示"""
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()
    
    # 公開グループの一覧を取得
    groups = db.execute("""
        SELECT gr.group_room_id,
               s.skill_name,
               (SELECT COUNT(*) FROM group_members WHERE group_room_id = gr.group_room_id) AS total_members
        FROM group_rooms gr
        LEFT JOIN skills s ON gr.skill_id = s.skill_id
        WHERE gr.is_public = 1
    """).fetchall()

    return render_template('public_rooms.html', groups=groups, rooms=groups)


@group_chat.route('/group/create-form')
def show_create_room_form():
    """グループ作成画面を表示 (GET)"""
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()
    skills = db.execute("SELECT skill_id, skill_name FROM skills").fetchall()

    return render_template('project_new.html', skills=skills)


@group_chat.route('/group/create', methods=['POST'])
def create_group():
    """グループの新規作成 (POST)"""
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    skill_id = request.form.get('skill_id')
    is_public = request.form.get('is_public', '1')

    if not skill_id:
        return redirect(url_for('group_chat.show_create_room_form'))

    group_room_id = secrets.token_hex(4)

    db = get_db()
    db.execute("""
        INSERT INTO group_rooms (group_room_id, skill_id, created_by, is_public)
        VALUES (?, ?, ?, ?)
    """, (str(group_room_id), int(skill_id), int(user_id), int(is_public)))

    db.execute("""
        INSERT INTO group_members (group_room_id, user_id, role)
        VALUES (?, ?, 'admin')
    """, (group_room_id, user_id))
    db.commit()

    return redirect(url_for('group_chat.group_chat_room', group_room_id=group_room_id))


@group_chat.route('/group/join', methods=['GET', 'POST'])
@group_chat.route('/group/join/<group_room_id>', methods=['GET', 'POST'])
def join_group(group_room_id=None):
    """グループへの参加手続き"""
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    if not group_room_id:
        group_room_id = request.form.get('group_room_id') or request.args.get('group_room_id')

    if not group_room_id:
        return redirect(url_for('group_chat.list_groups'))

    group_room_id = group_room_id.strip()

    db = get_db()
    group = db.execute("SELECT group_room_id FROM group_rooms WHERE group_room_id = ?", (group_room_id,)).fetchone()
    if not group:
        return "指定されたグループが存在しません。", 404

    already_member = db.execute("""
        SELECT 1 FROM group_members WHERE group_room_id = ? AND user_id = ?
    """, (group_room_id, user_id)).fetchone()

    if not already_member:
        db.execute("""
            INSERT INTO group_members (group_room_id, user_id, role)
            VALUES (?, ?, 'member')
        """, (group_room_id, user_id))
        db.commit()

    return redirect(url_for('group_chat.group_chat_room', group_room_id=group_room_id))


@group_chat.route('/group/room/<group_room_id>')
def group_chat_room(group_room_id):
    """グループチャット画面 (統合レイアウト)"""
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()

    # 1. 現在のグループに参加しているか確認
    is_member = db.execute("""
        SELECT role FROM group_members WHERE group_room_id = ? AND user_id = ?
    """, (group_room_id, user_id)).fetchone()

    if not is_member:
        return redirect(url_for('group_chat.list_groups'))

    session['room'] = group_room_id
    session['group_room_id'] = group_room_id
    session.modified = True

    # 2. 全チャットリスト取得（1on1 + グループ）サイドバー用
    chat_rooms_rows = db.execute('''
        SELECT 
            rm1.room_id AS room_token,
            u.name AS user_name,
            u.icon_path,
            s.skill_name,
            0 AS is_group
        FROM room_members rm1
        JOIN room_members rm2 ON rm1.room_id = rm2.room_id AND rm1.user_id != rm2.user_id
        JOIN users u ON rm2.user_id = u.user_id
        LEFT JOIN rooms r ON rm1.room_id = r.room_id
        LEFT JOIN skills s ON r.skill_id = s.skill_id
        WHERE rm1.user_id = ? AND rm1.hidden = 0

        UNION ALL

        SELECT 
            gr.group_room_id AS room_token,
            COALESCE(s.skill_name, 'グループ') AS user_name,
            NULL AS icon_path,
            s.skill_name,
            1 AS is_group
        FROM group_members gm
        JOIN group_rooms gr ON gm.group_room_id = gr.group_room_id
        LEFT JOIN skills s ON gr.skill_id = s.skill_id
        WHERE gm.user_id = ?
    ''', (user_id, user_id)).fetchall()

    chat_rooms = [{
        'room_token': str(row['room_token']),
        'user_name': row['user_name'],
        'icon_path': row['icon_path'],
        'skill_name': row['skill_name'] if row['skill_name'] else '',
        'is_group': bool(row['is_group'])
    } for row in chat_rooms_rows]

    # 3. 選択中グループのメッセージ履歴（右メイン画面用）
    history_rows = db.execute("""
        SELECT gm.message_id, gm.sender_id, u.name, gm.content, datetime(gm.created_at, 'localtime') AS send_time
        FROM group_messages gm
        JOIN users u ON gm.sender_id = u.user_id
        WHERE gm.group_room_id = ?
        ORDER BY gm.created_at ASC
        LIMIT 50
    """, (group_room_id,)).fetchall()

    history = [{
        'id': row['message_id'],
        'user_id': row['sender_id'],
        'name': row['name'],
        'msg': row['content'],
        'time': row['send_time']
    } for row in history_rows]

    # 4. ヘッダー表示用のグループ名を取得
    target_group = db.execute('''
        SELECT s.skill_name 
        FROM group_rooms gr 
        LEFT JOIN skills s ON gr.skill_id = s.skill_id 
        WHERE gr.group_room_id = ?
    ''', (group_room_id,)).fetchone()
    
    target_user_name = target_group['skill_name'] if target_group and target_group['skill_name'] else 'グループ'

    return render_template(
        'chat.html',
        name=session.get('name', 'User'),
        target_user_name=target_user_name,
        room=group_room_id,
        chats=history,
        user_id=user_id,
        chat_rooms=chat_rooms,
        req_row=None,
        is_reviewed=False
    )


@group_chat.route('/group/leave/<group_room_id>', methods=['POST'])
def leave_group(group_room_id):
    """グループからの脱退処理"""
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()
    db.execute("DELETE FROM group_members WHERE group_room_id = ? AND user_id = ?", (group_room_id, user_id))
    db.commit()

    # メンバーが存在しなくなった場合は自動削除
    member_count = db.execute("SELECT COUNT(*) FROM group_members WHERE group_room_id = ?", (group_room_id,)).fetchone()
    if member_count and member_count[0] == 0:
        db.execute("DELETE FROM group_rooms WHERE group_room_id = ?", (group_room_id,))
        db.execute("DELETE FROM group_messages WHERE group_room_id = ?", (group_room_id,))
        db.commit()

    return redirect(url_for('group_chat.list_groups'))


# =====================================================================
# 🔒 WebSocket イベント（グループチャット用）
# =====================================================================
def init_group_chat_events(socketio):

    @socketio.on('group_joined', namespace='/chat')
    def group_joined(data):
        group_room_id = session.get('group_room_id')
        user_id = session.get('user_id')

        if not user_id or not group_room_id:
            return False

        db = get_db()
        is_member = db.execute("SELECT 1 FROM group_members WHERE group_room_id = ? AND user_id = ?", (group_room_id, user_id)).fetchone()

        if is_member:
            room_key = f"group_{group_room_id}"
            join_room(room_key)
            user_row = db.execute("SELECT name FROM users WHERE user_id = ?", (user_id,)).fetchone()
            real_name = user_row[0] if user_row else "User"
            emit('group_status', {'msg': f"{real_name} がグループに参加しました。"}, to=room_key)
        else:
            return False

    @socketio.on('load_history', namespace='/chat')
    def load_history(data=None):
        group_room_id = session.get('group_room_id') or session.get('room')
        user_id = session.get('user_id')

        if not group_room_id or not user_id:
            return False

        db = get_db()
        is_member = db.execute(
            "SELECT 1 FROM group_members WHERE group_room_id = ? AND user_id = ?", 
            (group_room_id, user_id)
        ).fetchone()

        if not is_member:
            return False

        history_rows = db.execute("""
            SELECT gm.message_id, gm.sender_id, u.name, gm.content, datetime(gm.created_at, 'localtime') AS send_time
            FROM group_messages gm
            JOIN users u ON gm.sender_id = u.user_id
            WHERE gm.group_room_id = ?
            ORDER BY gm.created_at ASC
            LIMIT 50
        """, (group_room_id,)).fetchall()

        formatted_messages = [{
            'id': row['message_id'],
            'user_id': row['sender_id'],
            'name': row['name'],
            'msg': row['content'],
            'time': row['send_time']
        } for row in history_rows]

        emit('load_history_response', {'messages': formatted_messages}, room=request.sid)

    @socketio.on('group_text', namespace='/chat')
    def group_text(data):
        group_room_id = session.get('group_room_id')
        user_id = session.get('user_id')
        msg_content = data.get('msg', '').strip()

        if group_room_id and user_id and msg_content:
            db = get_db()
            is_member = db.execute("SELECT 1 FROM group_members WHERE group_room_id = ? AND user_id = ?", (group_room_id, user_id)).fetchone()
            if not is_member:
                return False

            user_row = db.execute("SELECT name FROM users WHERE user_id = ?", (user_id,)).fetchone()
            real_name = user_row[0] if user_row else "User"

            db.execute("""
                INSERT INTO group_messages (group_room_id, sender_id, content)
                VALUES (?, ?, ?)
            """, (group_room_id, user_id, msg_content))
            db.commit()

            room_key = f"group_{group_room_id}"
            emit('group_message', {'user_id': user_id, 'name': real_name, 'msg': msg_content}, to=room_key)