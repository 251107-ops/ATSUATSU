import os
import secrets
import uuid
from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_socketio import emit, join_room, leave_room
from routes.auth import get_db

chat = Blueprint('chat', __name__)

# ---------------------------------------------------------------------
# 画像アップロード設定
# ---------------------------------------------------------------------
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    )


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

    if existing_room:
        return str(existing_room['room_id'])

    cursor = db.execute(
        """
        INSERT INTO rooms (skill_id, is_public, created_by) 
        VALUES (?, 0, ?)
    """,
        (skill_id, user1_id),
    )

    new_room_id = cursor.lastrowid

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
# 0.5 画像アップロード API
# =====================================================================
@chat.route('/upload-image', methods=['POST'])
def upload_image():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': '認証が必要です'}), 401

    if 'image' not in request.files:
        return jsonify({'error': 'ファイルが添付されていません'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'ファイルが選択されていません'}), 400

    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        new_filename = f'{uuid.uuid4().hex}.{ext}'
        save_path = os.path.join(UPLOAD_FOLDER, new_filename)

        file.save(save_path)

        image_url = url_for('static', filename=f'uploads/{new_filename}')
        return jsonify({'image_url': image_url})

    return jsonify({'error': '許可されていない画像形式です'}), 400


# =====================================================================
# 1. チャットハブへのルーティング
# =====================================================================
@chat.route('/chat', methods=['GET', 'POST'])
def chat_hub():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    session['room'] = None
    session.modified = True

    db = get_db()
    user_row = db.execute(
        'SELECT name FROM users WHERE user_id = ?', (user_id,)
    ).fetchone()
    name = user_row['name'] if user_row else session.get('name', 'User')

    # 👥 サイドバー用：自分が参加しているチャットルーム一覧を取得
    chat_rooms_rows = db.execute(
        """
        SELECT 
            rm1.room_id AS room_token,
            u.name AS user_name,
            u.icon_path,
            s.skill_name
        FROM room_members rm1
        JOIN room_members rm2 ON rm1.room_id = rm2.room_id AND rm1.user_id != rm2.user_id
        JOIN users u ON rm2.user_id = u.user_id
        LEFT JOIN rooms r ON rm1.room_id = r.room_id
        LEFT JOIN skills s ON r.skill_id = s.skill_id
        WHERE rm1.user_id = ?
    """,
        (user_id,),
    ).fetchall()

    chat_rooms = []
    for row in chat_rooms_rows:
        chat_rooms.append({
            'room_token': str(row['room_token']),
            'user_name': row['user_name'],
            'icon_path': row['icon_path'],
            'skill_name': row['skill_name'] if row['skill_name'] else '',
        })

    # chat.html へ必要なデータを全て渡して描画
    return render_template(
        'chat.html',
        name=name,
        chat_rooms=chat_rooms,
        room=None,
        chats=[],
        user_id=user_id,
    )


# =====================================================================
# 2. チャットルーム画面 (厳格なメンバーシップ検証 ＆ 履歴取得)
# =====================================================================
@chat.route('/chat/room/<string:room_id>')
def chat_room(room_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()

    is_member = db.execute(
        """
        SELECT 1 FROM room_members WHERE room_id = ? AND user_id = ?
    """,
        (room_id, user_id),
    ).fetchone()

    if not is_member:
        session['room'] = None
        session.modified = True
        return redirect(url_for('.chat_hub'))

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

    # 📥 過去ログの取得
    history_rows = db.execute(
        """
        SELECT id, user_id, name, content, datetime(send_at, 'localtime') AS send_time
        FROM messages
        WHERE room = ?
        ORDER BY send_at ASC
        LIMIT 50
    """,
        (room_id,),
    ).fetchall()

    history = []
    for row in history_rows:
        history.append({
            'id': row['id'],
            'user_id': row['user_id'],
            'name': row['name'],
            'content': row['content'],
            'time': row['send_time'],
        })

    # 👥 サイドバー用：自分が参加しているチャットルームと相手の情報一覧を取得
    chat_rooms_rows = db.execute(
        """
        SELECT 
            rm1.room_id AS room_token,
            u.name AS user_name,
            u.icon_path,
            s.skill_name
        FROM room_members rm1
        JOIN room_members rm2 ON rm1.room_id = rm2.room_id AND rm1.user_id != rm2.user_id
        JOIN users u ON rm2.user_id = u.user_id
        LEFT JOIN rooms r ON rm1.room_id = r.room_id
        LEFT JOIN skills s ON r.skill_id = s.skill_id
        WHERE rm1.user_id = ?
    """,
        (user_id,),
    ).fetchall()

    chat_rooms = []
    target_user_name = None  # ヘッダー用の相手の名前

    for row in chat_rooms_rows:
        token_str = str(row['room_token'])
        chat_rooms.append({
            'room_token': token_str,
            'user_name': row['user_name'],
            'icon_path': row['icon_path'],
            'skill_name': row['skill_name'] if row['skill_name'] else '',
        })
        # 現在開いているルームの相手の名前を保持
        if token_str == str(room_id):
            target_user_name = row['user_name']

    # ★ 修正ポイント: room_id の型キャスト対応 ＆ SQLの条件調整
    # room_id が文字列か数値かどちらでも対応できるように CAST して比較します
    req_row = db.execute(
        """
        SELECT request_id, status, requester_id, receiver_id,
               requester_completed, receiver_completed
        FROM requests
        WHERE CAST(room_id AS TEXT) = CAST(? AS TEXT)
          AND (requester_id = ? OR receiver_id = ?)
        """,
        (room_id, user_id, user_id),
    ).fetchone()

    # dict化して確実にJinja2でプロパティ参照できるように対応
    if req_row:
        req_row = dict(req_row)

    return render_template(
        'chat.html',
        name=name,
        target_user_name=target_user_name, # 追加：相手の名前
        room=room_id,
        chats=history,
        user_id=user_id,
        req_row=req_row,
        chat_rooms=chat_rooms,
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
            return (
                'アクセス権限がありません。このルームはプライベートです。',
                403,
            )

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

            req_status = db.execute(
                'SELECT status FROM requests WHERE room_id = ?', (room,)
            ).fetchone()
            if req_status and req_status['status'] == 'completed':
                print(
                    f'[WS TEXT REJECTED] room {room} は終了済みのため送信できません。'
                )
                return False

            user_row = db.execute(
                'SELECT name FROM users WHERE user_id = ?', (user_id,)
            ).fetchone()
            real_name = user_row['name'] if user_row else 'User'

            # メッセージ保存と ID の獲得
            cursor = db.execute(
                """
                INSERT INTO messages (room, user_id, name, content) 
                VALUES (?, ?, ?, ?)
            """,
                (room, user_id, real_name, msg_content),
            )
            msg_id = cursor.lastrowid
            db.commit()

            # ID・ユーザーIDを付与して全クライアントへ配信
            emit(
                'message',
                {
                    'id': msg_id,
                    'user_id': user_id,
                    'msg': f'{real_name}: {msg_content}',
                },
                to=room,
            )

    # 🗑️ メッセージ削除イベント
    @socketio.on('delete_message', namespace='/chat')
    def delete_message(data):
        room = session.get('room')
        user_id = session.get('user_id')
        msg_id = data.get('msg_id')

        if room and user_id and msg_id:
            db = get_db()
            # 送信者本人のメッセージかつ現在属しているルームのメッセージか検証して削除
            cursor = db.execute(
                'DELETE FROM messages WHERE id = ? AND user_id = ? AND room ='
                ' ?',
                (msg_id, user_id, room),
            )
            db.commit()

            if cursor.rowcount > 0:
                print(
                    '[WS DELETE Success] Msg ID:'
                    f' {msg_id} deleted by User: {user_id}'
                )
                # ルーム全員の端末の画面から削除する通知を送信
                emit('message_deleted', {'msg_id': msg_id}, to=room)

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


# =====================================================================
# ヘッダーの「チャット」ボタン用のリダイレクト処理
# =====================================================================
@chat.route('/chat_index')
def chat_index():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()

    # ユーザーが参加している直近のルームを1件取得
    latest_room = db.execute(
        '''
        SELECT room_id 
        FROM room_members 
        WHERE user_id = ? 
        ORDER BY room_id DESC 
        LIMIT 1
    ''',
        (user_id,),
    ).fetchone()

    # 参加しているルームがあればその画面へ、なければチャットハブ（未選択画面など）へ
    if latest_room:
        return redirect(
            url_for('chat.chat_room', room_id=latest_room['room_id'])
        )
    else:
        return redirect(url_for('chat.chat_hub'))


# =====================================================================
# サイドバーからのチャット削除（ルーム退出）処理
# =====================================================================
@chat.route('/chat/room/<string:room_id>/leave', methods=['POST'])
def leave_room_action(room_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()

    # 1. room_members から自分を削除
    db.execute(
        'DELETE FROM room_members WHERE room_id = ? AND user_id = ?',
        (room_id, user_id),
    )
    db.commit()

    # 2. もしルーム内にメンバーが誰もいなくなったらルーム自体も削除
    member_count = db.execute(
        'SELECT COUNT(*) AS count FROM room_members WHERE room_id = ?',
        (room_id,),
    ).fetchone()

    if member_count and member_count['count'] == 0:
        db.execute('DELETE FROM rooms WHERE room_id = ?', (room_id,))
        db.execute('DELETE FROM messages WHERE room = ?', (room_id,))
        db.commit()

    # 削除後は他のチャット画面（または一覧インデックス）へリダイレクト
    return redirect(url_for('chat.chat_index'))


# =====================================================================
# HTTP送信時のフォールバック処理（必要に応じて使用）
# =====================================================================
@chat.route('/chat/send', methods=['POST'])
def send_message():
    db = get_db()
    room_id = request.form.get('room_id')
    message_text = request.form.get('message')

    # ルームの状態を確認
    room = db.execute("SELECT status FROM requests WHERE room_id = ?", (room_id,)).fetchone()

    # チャットが終了している場合は送信を拒否
    if room and room['status'] == 'completed':
        return jsonify({'error': 'このチャットは既に終了しています'}), 400

    return jsonify({'status': 'ok'})