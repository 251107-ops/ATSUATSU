import os
import sqlite3
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from flask import Blueprint, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

ph = PasswordHasher()

DATABASE = os.path.join(os.path.dirname(__file__), '..', 'nikuman.db')

# 💡 routesフォルダ内に置く場合は template_folder の指定が必要です
auth = Blueprint('auth', __name__, template_folder='../templates')
auth.secret_key = os.urandom(24)  # セッション情報の暗号化に必要な秘密鍵


# --- ルーティング設定 ---


# ログイン画面
@auth.route('/login', methods=['GET', 'POST'])
def login():
    error_message = ''
    email = ''

    if request.method == 'POST':
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        name = request.form.get('name', '')

        db = get_db()
        # データベースから該当するメールアドレスのユーザー情報を取得
        user_data = db.execute(
            'SELECT user_id, name, email, password FROM users WHERE email = ?',
            [email],
        ).fetchone()

        # ⭕ ハッシュ化されたパスワードの検証
        if user_data:
            try:
                if ph.verify(user_data['password'], password):
                    session.clear()

                    session['user_email'] = email  # セッションにメールアドレスを保存（ログイン完了）
                    session['user_id'] = user_data['user_id']  # セッションにユーザーIDを保存
                    session['name'] = user_data['name']  # セッションにユーザー名を保存（Chat用）
                    session['room'] = None

                    session.modified = True
                    return redirect('/')
            except (VerifyMismatchError, InvalidHashError):
                pass

        error_message = '入力されたメールアドレスもしくはパスワードが誤っています'

    return render_template(
        'login.html', email=email, error_message=error_message
    )


# 新規登録 1ページ目
@auth.route('/register1', methods=['GET', 'POST'])
def register1():
    if request.method == 'POST':
        name = request.form.get('name', '')
        email = request.form.get('email', '')
        password = request.form.get('password', '')

        # ⭕ method='sha256' を削除（自動で最新の安全なアルゴリズムが使われます）
        pass_hash = ph.hash(password)
        return render_template(
            'register2.html', name=name, email=email, password=pass_hash
        )

    return render_template('register1.html')


# 新規登録 2ページ目
@auth.route('/register2', methods=['POST'])
def register2():
    name = request.form.get('name', '')
    email = request.form.get('email', '')
    password = request.form.get(
        'password', ''
    )  # 1ページ目から引き継いだハッシュ化済みパスワード
    grade = request.form.get('grade', '')
    department = request.form.get('department', '')
    introduction = request.form.get('introduction', '')

    # ★ 学年のデータ整形（「2年」→「2」に変換して保存）
    if grade:
        grade = grade.replace('年', '').strip()

    db = get_db()
    user_check = db.execute(
        'SELECT email FROM users WHERE email = ?', (email,)
    ).fetchone()

    if not user_check:
        # まずユーザーを登録し、自動採番されたuser_idを取得する
        cursor = db.execute(
            'INSERT INTO users (name, email, password, grade, department,'
            ' introduction, icon_path) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (name, email, password, grade, department, introduction, ''),
        )
        db.commit()
        new_user_id = cursor.lastrowid

        # アイコン画像が送信されていれば保存する
        icon_file = request.files.get('icon')
        if icon_file and icon_file.filename:
            allowed_ext = {'.png', '.jpg', '.jpeg', '.gif'}
            ext = os.path.splitext(icon_file.filename)[1].lower()

            if ext in allowed_ext:
                filename = secure_filename(f'user_{new_user_id}{ext}')
                upload_dir = os.path.join('static', 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                save_path = os.path.join(upload_dir, filename)
                icon_file.save(save_path)

                icon_path = f'uploads/{filename}'
                db.execute(
                    'UPDATE users SET icon_path = ? WHERE user_id = ?',
                    (icon_path, new_user_id),
                )
                db.commit()

        return redirect('/login')  # 登録完了後にログインページへリダイレクト
    else:
        error_message = 'このデータは既に登録されています'
        return render_template(
            'register1.html',
            error_message=error_message,
            name=name,
            email=email,
            password=password,
        )


# ログアウト処理
@auth.route('/logout')
def logout():
    session.clear()  # セッションからユーザー情報を削除（ログアウト）
    return redirect('/login')


# ★ 自分のプロフィール画面表示
@auth.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    db = get_db()

    # ユーザー情報の取得
    user = db.execute(
        'SELECT user_id, name, email, grade, department, introduction, icon_path FROM users WHERE user_id = ?',
        (user_id,)
    ).fetchone()

    # 教えたいスキル
    skills_teach = db.execute(
        '''
        SELECT DISTINCT s.skill_name
        FROM posts p
        JOIN skills s ON p.skill_id = s.skill_id
        WHERE p.user_id = ? AND p.post_type = '教えたい'
        ''',
        (user_id,)
    ).fetchall()

    # 学びたいスキル
    skills_learn = db.execute(
        '''
        SELECT DISTINCT s.skill_name
        FROM posts p
        JOIN skills s ON p.skill_id = s.skill_id
        WHERE p.user_id = ? AND p.post_type = '学びたい'
        ''',
        (user_id,)
    ).fetchall()

    # 自分の投稿
    my_posts = db.execute(
        '''
        SELECT p.*, s.skill_name, c.category_name,
               (SELECT COUNT(*) FROM likes WHERE post_id = p.post_id) AS like_count,
               EXISTS(SELECT 1 FROM likes WHERE post_id = p.post_id AND user_id = ?) AS liked_by_me
        FROM posts p
        JOIN skills s ON p.skill_id = s.skill_id
        JOIN categories c ON p.category_id = c.category_id
        WHERE p.user_id = ?
        ORDER BY p.post_date DESC
        ''',
        (user_id, user_id)
    ).fetchall()

    # レビュー統計情報
    avg_rating_val = db.execute(
        'SELECT AVG(rating) FROM reviews WHERE reviewee_id = ?',
        (user_id,)
    ).fetchone()[0] or 0

    review_count = db.execute(
        'SELECT COUNT(*) FROM reviews WHERE reviewee_id = ?',
        (user_id,)
    ).fetchone()[0] or 0

    review_stats = {
        'avg_rating': round(avg_rating_val, 1),
        'review_count': review_count
    }

    return render_template(
        'profile.html',
        user=user,
        skills_teach=skills_teach,
        skills_learn=skills_learn,
        my_posts=my_posts,
        review_stats=review_stats
    )


# ★ 自分のプロフィール編集画面・更新処理
@auth.route('/profile_edit', methods=['GET', 'POST'])
def profile_edit():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    db = get_db()

    if request.method == 'POST':
        name = request.form.get('name', '')
        grade = request.form.get('grade', '')
        department = request.form.get('department', '')
        introduction = request.form.get('introduction', '')

        # ★ 学年のデータ整形（「2年」等の入力から「年」を取り除き「2」にしてDB保存）
        if grade:
            grade = str(grade).replace('年', '').strip()

        # 画像ファイルのアップロード処理
        icon_file = request.files.get('icon')
        if icon_file and icon_file.filename:
            allowed_ext = {'.png', '.jpg', '.jpeg', '.gif'}
            ext = os.path.splitext(icon_file.filename)[1].lower()

            if ext in allowed_ext:
                filename = secure_filename(f'user_{user_id}{ext}')
                upload_dir = os.path.join('static', 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                save_path = os.path.join(upload_dir, filename)
                icon_file.save(save_path)

                icon_path = f'uploads/{filename}'
                db.execute('UPDATE users SET icon_path = ? WHERE user_id = ?', (icon_path, user_id))

        # 基本情報の更新
        db.execute(
            '''
            UPDATE users
            SET name = ?, grade = ?, department = ?, introduction = ?
            WHERE user_id = ?
            ''',
            (name, grade, department, introduction, user_id)
        )
        db.commit()

        # セッション情報の更新
        session['name'] = name

        return redirect('/profile')

    user = db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
    return render_template('profile_edit.html', user=user)


@auth.route('/change-password', methods=['GET', 'POST'])
def change_password():
    error_message = ''
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        password_confirm = request.form.get('password_confirm', '')

        db = get_db()
        user_data = db.execute(
            'SELECT password FROM users WHERE user_id=?', (user_id,)
        ).fetchone()

        current_valid = False

        if user_data:
            try:
                current_valid = ph.verify(
                    user_data['password'], current_password
                )
            except (VerifyMismatchError, InvalidHashError):
                current_valid = False

        if not current_valid:
            error_message = 'Current password is incorrect.'

        elif new_password != password_confirm:
            error_message = 'New passwords do not match.'

        elif not new_password.strip():
            error_message = 'New password cannot be empty.'
        else:
            new_pass_hash = ph.hash(new_password)
            db.execute(
                'UPDATE users set password = ? WHERE user_id = ?',
                (new_pass_hash, user_id),
            )
            db.commit()
            return redirect('/profile')
    return render_template('settings.html', error_message=error_message)


# データベース接続関数
def connect_db():
    rv = sqlite3.connect(DATABASE, timeout=20.0)
    rv.row_factory = sqlite3.Row  # カラム名でのデータ取得を可能にする設定
    return rv


# データベースインスタンスの取得
def get_db():
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db


def init_db():
    db = connect_db()

    db.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            request_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id      INTEGER NOT NULL REFERENCES posts(post_id),
            requester_id INTEGER NOT NULL REFERENCES users(user_id),
            receiver_id  INTEGER NOT NULL REFERENCES users(user_id),
            room_id      TEXT REFERENCES rooms(room_id),
            status       TEXT NOT NULL DEFAULT 'pending',
            created_at   TEXT DEFAULT (datetime('now','localtime')),
            updated_at   TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(user_id),
            type        TEXT NOT NULL,
            related_id  INTEGER,
            is_read     INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            review_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id  INTEGER NOT NULL UNIQUE REFERENCES requests(request_id),
            reviewer_id INTEGER NOT NULL REFERENCES users(user_id),
            reviewee_id INTEGER NOT NULL REFERENCES users(user_id),
            rating      INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
            comment     TEXT,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );
    """)

    db.commit()
    db.close()


@auth.teardown_app_request
def close_db(error):
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()


# 他人のプロフィール画面表示
@auth.route('/profile/<int:user_id>')
def view_other_profile(user_id):
    if 'user_id' not in session:
        return redirect('/login')

    if session['user_id'] == user_id:
        return redirect('/profile')

    db = get_db()
    
    # 1. ユーザー基本情報の取得
    user = db.execute(
        'SELECT user_id, name, email, grade, department, introduction, icon_path FROM users WHERE user_id = ?',
        (user_id,)
    ).fetchone()

    if not user:
        return render_template('404.html'), 404

    # 2. 教えたいスキルの取得
    skills_teach = db.execute(
        '''
        SELECT DISTINCT s.skill_name
        FROM posts p
        JOIN skills s ON p.skill_id = s.skill_id
        WHERE p.user_id = ? AND p.post_type = '教えたい'
        ''',
        (user_id,)
    ).fetchall()

    # 3. 学びたいスキルの取得
    skills_learn = db.execute(
        '''
        SELECT DISTINCT s.skill_name
        FROM posts p
        JOIN skills s ON p.skill_id = s.skill_id
        WHERE p.user_id = ? AND p.post_type = '学びたい'
        ''',
        (user_id,)
    ).fetchall()

    # 4. 投稿一覧の取得
    user_posts = db.execute(
        '''
        SELECT p.*, s.skill_name, c.category_name,
               (SELECT COUNT(*) FROM likes WHERE post_id = p.post_id) AS like_count,
               EXISTS(SELECT 1 FROM likes WHERE post_id = p.post_id AND user_id = ?) AS liked_by_me
        FROM posts p
        JOIN skills s ON p.skill_id = s.skill_id
        JOIN categories c ON p.category_id = c.category_id
        WHERE p.user_id = ?
        ORDER BY p.post_date DESC
        ''',
        (session['user_id'], user_id)
    ).fetchall()

    # 5. レビュー情報の取得
    reviews = db.execute(
        '''
        SELECT r.*, u.name AS reviewer_name, u.icon_path AS reviewer_icon
        FROM reviews r
        JOIN users u ON r.reviewer_id = u.user_id
        WHERE r.reviewee_id = ?
        ORDER BY r.created_at DESC
        ''',
        (user_id,)
    ).fetchall()

    avg_rating_val = db.execute(
        'SELECT AVG(rating) FROM reviews WHERE reviewee_id = ?',
        (user_id,)
    ).fetchone()[0] or 0

    review_stats = {
        'avg_rating': round(avg_rating_val, 1),
        'review_count': len(reviews)
    }

    return render_template(
        'other_profile.html',
        user=user,
        skills_teach=skills_teach,
        skills_learn=skills_learn,
        user_posts=user_posts,
        reviews=reviews,
        review_stats=review_stats
    )