import secrets
from flask import Blueprint, redirect, render_template, request, session, url_for
from flask_socketio import emit, join_room, leave_room
from routes.auth import get_db

chat = Blueprint('chat', __name__)


# =====================================================================
# 0. 他Blueprint（requests.pyなど）から呼べる共通ルーム作成関数
# =====================================================================
def create_chat_room(user1_id, user2_id, skill_id=None):
    """リクエスト承認時などに2人間のプライベートルームを作成または取得する共通関数"""
    db = get_db()

    # 既にこの2人だけのルームが存在するか確認
    existing_room = db.execute(
        """
        SELECT rm1.room_id 
        FROM room_members rm1
        JOIN room_members rm2 ON rm1.room_id = rm2.room_id
        JOIN rooms r ON rm1.room_id = r.room_id
        WHERE rm1.user_id = ? AND rm2.user_id = ? AND r.is_public = 0
    """,
        (user1_id, user2_id),
    ).fetchone()

    # ★ 修正: カラム名 'room_id' を指定して安全に取得
    if existing_room:
        return str(existing_room['room_id'])

    # 1. room_id を指定せず INSERT し、自動採番（AUTOINCREMENT）させる
    cursor = db.execute(
        """
        INSERT INTO rooms (skill_id, is_public, created_by) 
        VALUES (?, 0, ?)
    """,
        (skill_id, user1_id),
    )

    # 自動生成された数値IDを取得
    new_room_id = cursor.lastrowid

    # 2. 生成された room_id を使ってメンバー登録
    db.execute(
        'INSERT INTO room_members (room_id, user_id) VALUES (?, ?)',
        (new_room_id, user1_id),
    )
    db.execute(
        'INSERT INTO room_members (room_id, user_id) VALUES (?, ?)',
        (new_room_id, user2_id),
    )
    db.commit()

    return str(new_room_id)


# =====================================================================
# 1. チャットハブへのルーティング
# =====================================================================
@chat.route('/chat', methods=['GET', 'POST'])
def chat_hub():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    # 💡 ユーザー切り替え時の不正アクセスを防ぐため、アクティブなルームセッションを完全にクリア
    session['room'] = None
    session.modified = True

    db = get_db()
    user_row = db.execute(
        'SELECT name FROM users WHERE user_id = ?', (user_id,)
    ).fetchone()
    name = user_row['name'] if user_row else session.get('name', 'User')

    return render_template('chat_hub.html', name=name)


# =====================================================================
# 2. チャットルーム画面 (厳格なメンバーシップ検証 ＆ 履歴取得)
# =====================================================================
@chat.route('/chat/room/<string:room_id>')
def chat_room(room_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()

    # 🔒 安全対策: 現在ログインしているユーザーが本当にこのルームのメンバーかDBで最終確認
    is_member = db.execute(
        """
        SELECT 1 FROM room_members WHERE room_id = ? AND user_id = ?
    """,
        (room_id, user_id),
    ).fetchone()

    # メンバーではない場合、ハブ画面へ強制リダイレクト
    if not is_member:
        session['room'] = None
        session.modified = True
        return redirect(url_for('.chat_hub'))

    # 検証成功後、セッションに正しいルームIDを設定
    session['room'] = room_id
    session.modified = True

    user_row = db.execute(
        'SELECT name FROM users WHERE user_id = ?', (user_id,)
    ).fetchone()
    name = user_row['name'] if user_row else session.get('name', 'User')

    print(
        f'[HTTP ACCESS] VERIFIED - User: {name} (ID: {user_id}) entering Room:'
        f' {room_id}'
    )

    # 📥 メッセージ履歴の取得
    history_rows = db.execute(
        """
        SELECT name, content, datetime(send_at, 'localtime') AS send_time
        FROM messages
        WHERE room = ?
        ORDER BY send_at ASC
        LIMIT 50
    """,
        (room_id,),
    ).fetchall()

    history = []
    for row in history_rows:
        history.append(
            {'name': row['name'], 'content': row['content'], 'time': row['send_time']}
        )

    return render_template(
        'chat.html', name=name, room=room_id, chats=history, user_id=user_id
    )


# =====================================================================
# 3. 公開ルームの作成
# =====================================================================
@chat.route('/create-public-room/<int:skill_id>', methods=['GET', 'POST'])
def create_public_room(skill_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()
    invitation_code = secrets.token_hex(4)

    # ルームを公開設定 (is_public = 1) で作成
    db.execute(
        """
        INSERT INTO rooms (room_id, skill_id, is_public, created_by) 
        VALUES (?, ?, 1, ?)
    """,
        (invitation_code, skill_id, user_id),
    )
    db.execute(
        'INSERT INTO room_members (room_id, user_id) VALUES (?, ?)',
        (invitation_code, user_id),
    )
    db.commit()

    return redirect(url_for('.chat_room', room_id=invitation_code))


# =====================================================================
# 3.5. 非公開ルームの作成
# =====================================================================
@chat.route('/create-private-room/<int:skill_id>', methods=['GET', 'POST'])
def create_private_room(skill_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()
    invitation_code = secrets.token_hex(4)

    # ルームを非公開設定 (is_public = 0) で作成
    db.execute(
        """
        INSERT INTO rooms (room_id, skill_id, is_public, created_by) 
        VALUES (?, ?, 0, ?)
    """,
        (invitation_code, skill_id, user_id),
    )
    db.execute(
        'INSERT INTO room_members (room_id, user_id) VALUES (?, ?)',
        (invitation_code, user_id),
    )
    db.commit()

    return redirect(url_for('.chat_room', room_id=invitation_code))


# =====================================================================
# 4. プライベートルームへの参加手続き
# =====================================================================
@chat.route('/private-room', methods=['POST'])
def join_private_room():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    code = request.form.get('room_code', '').strip()
    if not code:
        return 'Please enter a valid room code.', 400

    db = get_db()

    room_exists = db.execute(
        'SELECT room_id FROM rooms WHERE room_id = ?', (code,)
    ).fetchone()
    if not room_exists:
        return 'This room code does not exist or has expired.', 404

    already_member = db.execute(
        """
        SELECT 1 FROM room_members WHERE room_id = ? AND user_id = ?
    """,
        (code, user_id),
    ).fetchone()

    if not already_member:
        db.execute(
            'INSERT INTO room_members (room_id, user_id) VALUES (?, ?)',
            (code, user_id),
        )
        db.commit()

    return redirect(url_for('.chat_room', room_id=code))


# =====================================================================
# 5. 公開ルーム一覧の表示
# =====================================================================
@chat.route('/public-rooms')
def list_public_rooms():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()
    rooms = db.execute("""
        SELECT rooms.room_id, skills.skill_name, 
               (SELECT COUNT(*) FROM room_members WHERE room_id = rooms.room_id) AS total_members
        FROM rooms 
        LEFT JOIN skills ON rooms.skill_id = skills.skill_id
        WHERE rooms.is_public = 1
    """).fetchall()

    return render_template('public_rooms.html', rooms=rooms)


# =====================================================================
# 6. ルームへのアクセス確認
# =====================================================================
@chat.route('/access-room/<string:room_id>')
def access_room(room_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()
    room_data = db.execute(
        'SELECT is_public FROM rooms WHERE room_id = ?', (room_id,)
    ).fetchone()
    if not room_data:
        return 'The requested room does not exist.', 404

    if room_data['is_public'] == 1:
        already_member = db.execute(
            """
            SELECT 1 FROM room_members WHERE room_id = ? AND user_id = ?
        """,
            (room_id, user_id),
        ).fetchone()

        if not already_member:
            db.execute(
                'INSERT INTO room_members (room_id, user_id) VALUES (?, ?)',
                (room_id, user_id),
            )
            db.commit()
    else:
        is_invited = db.execute(
            """
            SELECT 1 FROM room_members WHERE room_id = ? AND user_id = ?
        """,
            (room_id, user_id),
        ).fetchone()
        if not is_invited:
            return 'アクセス権限がありません。このルームはプライベートです。', 403

    return redirect(url_for('.chat_room', room_id=room_id))


# =====================================================================
# 7. ルーム作成フォームの表示
# =====================================================================
@chat.route('/create-room-form')
def show_create_room_form():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()
    skills = db.execute('SELECT skill_id, skill_name FROM skills').fetchall()

    return render_template('create_room.html', skills=skills)


# =====================================================================
# 8. 自分で作成したルームを表示する
# =====================================================================
@chat.route('/my-created-rooms')
def list_my_created_rooms():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()

    created_rooms = db.execute(
        """
        SELECT rooms.room_id, skills.skill_name, 
               (SELECT COUNT(*) FROM room_members WHERE room_id = rooms.room_id) AS total_members
        FROM rooms 
        LEFT JOIN skills ON rooms.skill_id = skills.skill_id
        WHERE rooms.created_by = ?
    """,
        (user_id,),
    ).fetchall()

    return render_template('public_rooms.html', rooms=created_rooms)


# =====================================================================
# 9. 参加したルームを表示する
# =====================================================================
@chat.route('/my-room-access')
def list_my_room_access():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()

    access_rooms = db.execute(
        """
        SELECT rooms.room_id, rooms.is_public, rooms.created_by, skills.skill_name, 
               (SELECT COUNT(*) FROM room_members WHERE room_id = rooms.room_id) AS total_members
        FROM rooms 
        INNER JOIN room_members ON rooms.room_id = room_members.room_id
        LEFT JOIN skills ON rooms.skill_id = skills.skill_id
        WHERE room_members.user_id = ?
    """,
        (user_id,),
    ).fetchall()

    return render_template('my_rooms.html', access_rooms=access_rooms)


# =====================================================================
# 🔒 WebSocket イベント設定
# =====================================================================
def init_chat_events(socketio):

    @socketio.on('joined', namespace='/chat')
    def joined(message):
        room = session.get('room')
        user_id = session.get('user_id')

        if not user_id or not room:
            print('[WS REJECTED] セッション情報が見つかりません。')
            return False

        db = get_db()
        is_member = db.execute(
            'SELECT 1 FROM room_members WHERE room_id = ? AND user_id = ?',
            (room, user_id),
        ).fetchone()

        if is_member:
            join_room(room)
            user_row = db.execute(
                'SELECT name FROM users WHERE user_id = ?', (user_id,)
            ).fetchone()
            real_name = user_row['name'] if user_row else 'User'
            print(f'[WS VERIFIED] User {real_name} joined room {room}')
            emit('status', {'msg': f'{real_name} が入室しました。'}, to=room)
        else:
            print(
                f'[WS SECURITY BREACH] 不正な接続をブロックしました。ユーザーID {user_id}'
                f' はルーム {room} のメンバーではありません。'
            )
            return False

    @socketio.on('text', namespace='/chat')
    def text(message):
        room = session.get('room')
        user_id = session.get('user_id')
        msg_content = message.get('msg', '').strip()

        if room and user_id and msg_content:
            db = get_db()
            is_member = db.execute(
                'SELECT 1 FROM room_members WHERE room_id = ? AND user_id = ?',
                (room, user_id),
            ).fetchone()
            if not is_member:
                print(
                    f'[WS TEXT REJECTED] ユーザーID {user_id} はルーム {room}'
                    ' への発言権限がありません。'
                )
                return False

            user_row = db.execute(
                'SELECT name FROM users WHERE user_id = ?', (user_id,)
            ).fetchone()
            real_name = user_row['name'] if user_row else 'User'

            db.execute(
                """
                INSERT INTO messages (room, user_id, name, content) 
                VALUES (?, ?, ?, ?)
            """,
                (room, user_id, real_name, msg_content),
            )
            db.commit()

            emit('message', {'msg': f'{real_name}: {msg_content}'}, to=room)

    @socketio.on('left', namespace='/chat')
    def left(message):
        room = session.get('room')
        user_id = session.get('user_id')
        if room and user_id:
            db = get_db()
            user_row = db.execute(
                'SELECT name FROM users WHERE user_id = ?', (user_id,)
            ).fetchone()
            real_name = user_row['name'] if user_row else 'Someone'
            leave_room(room)
            emit('status', {'msg': f'{real_name} が退室しました。'}, to=room)