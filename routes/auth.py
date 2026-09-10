import os
import random
import sqlite3
from datetime import datetime, timedelta
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from flask import Blueprint, g, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

ph = PasswordHasher()

DATABASE = os.path.join(os.path.dirname(__file__), '..', 'nikuman.db')

auth = Blueprint('auth', __name__, template_folder='../templates')


# --- データベース接続管理 ---

def connect_db():
    rv = sqlite3.connect(DATABASE, timeout=20.0)
    rv.row_factory = sqlite3.Row
    return rv


def get_db():
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db


@auth.teardown_app_request
def close_db(error):
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()


def init_db():
    db = connect_db()
    try:
        db.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                request_id          INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id             INTEGER NOT NULL REFERENCES posts(post_id),
                requester_id        INTEGER NOT NULL REFERENCES users(user_id),
                receiver_id         INTEGER NOT NULL REFERENCES users(user_id),
                room_id             TEXT REFERENCES rooms(room_id),
                status              TEXT NOT NULL DEFAULT 'pending',
                requester_completed INTEGER NOT NULL DEFAULT 0,
                receiver_completed  INTEGER NOT NULL DEFAULT 0,
                created_at          TEXT DEFAULT (datetime('now','localtime')),
                updated_at          TEXT DEFAULT (datetime('now','localtime'))
            )
        """)

        for col in ["requester_completed", "receiver_completed"]:
            try:
                db.execute(f"ALTER TABLE requests ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")
            except sqlite3.OperationalError:
                pass

        db.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL REFERENCES users(user_id),
                type            TEXT NOT NULL,
                related_id      INTEGER,
                is_read         INTEGER NOT NULL DEFAULT 0,
                created_at      TEXT DEFAULT (datetime('now','localtime'))
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
                skill_name  TEXT,
                post_type   TEXT,
                created_at  TEXT DEFAULT (datetime('now','localtime'))
            );
        """)

        for col in ["skill_name", "post_type"]:
            try:
                db.execute(f"ALTER TABLE reviews ADD COLUMN {col} TEXT")
            except sqlite3.OperationalError:
                pass

        db.commit()
    finally:
        db.close()


# --- ルーティング設定 ---

# ログイン画面
@auth.route('/login', methods=['GET', 'POST'])
def login():
    error_message = ''
    email = ''

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        db = get_db()
        user_data = db.execute(
            'SELECT user_id, name, email, password FROM users WHERE email = ?',
            (email,),
        ).fetchone()

        if user_data:
            try:
                if ph.verify(user_data['password'], password):
                    session.clear()
                    session['user_email'] = email
                    session['user_id'] = user_data['user_id']
                    session['name'] = user_data['name']
                    session['room'] = None
                    session.modified = True
                    return redirect('/')
            except (VerifyMismatchError, InvalidHashError):
                pass

        error_message = '入力されたメールアドレスもしくはパスワードが誤っています'

    return render_template('login.html', email=email, error_message=error_message)


# 新規登録 1ページ目
@auth.route('/register1', methods=['GET', 'POST'])
def register1():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        pass_hash = ph.hash(password)
        return render_template(
            'register2.html', name=name, email=email, password=pass_hash
        )

    return render_template('register1.html')


# 新規登録 2ページ目
@auth.route('/register2', methods=['POST'])
def register2():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    grade = request.form.get('grade', '')
    department = request.form.get('department', '').strip()
    introduction = request.form.get('introduction', '').strip()

    if grade:
        grade = grade.replace('年', '').strip()

    db = get_db()
    user_check = db.execute(
        'SELECT email FROM users WHERE email = ?', (email,)
    ).fetchone()

    if not user_check:
        cursor = db.execute(
            'INSERT INTO users (name, email, password, grade, department, introduction, icon_path) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (name, email, password, grade, department, introduction, ''),
        )
        db.commit()
        new_user_id = cursor.lastrowid

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

        return redirect('/login')
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
    session.clear()
    return redirect('/login')


# パスワード変更
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
                current_valid = ph.verify(user_data['password'], current_password)
            except (VerifyMismatchError, InvalidHashError):
                current_valid = False

        if not current_valid:
            error_message = '現在のパスワードが正しくありません。'
        elif new_password != password_confirm:
            error_message = '新しいパスワードが一致しません。'
        elif not new_password.strip():
            error_message = '新しいパスワードを入力してください。'
        else:
            new_pass_hash = ph.hash(new_password)
            db.execute(
                'UPDATE users set password = ? WHERE user_id = ?',
                (new_pass_hash, user_id),
            )
            db.commit()
            return redirect('/profile')

    return render_template('settings.html', error_message=error_message)


# 他人のプロフィール画面表示
@auth.route('/profile/<int:user_id>')
def view_other_profile(user_id):
    if 'user_id' not in session:
        return redirect('/login')

    if session['user_id'] == user_id:
        return redirect('/profile')

    db = get_db()

    user = db.execute(
        'SELECT user_id, name, email, grade, department, introduction, icon_path FROM users WHERE user_id = ?',
        (user_id,)
    ).fetchone()

    if not user:
        return render_template('404.html'), 404

    skills_teach = db.execute(
        '''
        SELECT DISTINCT s.skill_name
        FROM posts p
        JOIN skills s ON p.skill_id = s.skill_id
        WHERE p.user_id = ? AND p.post_type = '教えたい'
        ''',
        (user_id,)
    ).fetchall()

    skills_learn = db.execute(
        '''
        SELECT DISTINCT s.skill_name
        FROM posts p
        JOIN skills s ON p.skill_id = s.skill_id
        WHERE p.user_id = ? AND p.post_type = '学びたい'
        ''',
        (user_id,)
    ).fetchall()

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


# --- パスワード再設定フロー ---

@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    error_message = ''

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        db = get_db()

        user = db.execute(
            'SELECT user_id FROM users WHERE email = ?', (email,)
        ).fetchone()

        if user:
            otp_code = f"{random.randint(0, 999999):06d}"
            expiration = datetime.now() + timedelta(minutes=10)

            db.execute(
                'UPDATE users SET reset_token = ?, token_expiration = ? WHERE email = ?',
                (otp_code, expiration, email)
            )
            db.commit()

            return render_template('show_code.html', email=email, otp_code=otp_code)
        else:
            error_message = '指定されたメールアドレスのアカウントは見つかりませんでした。'

    return render_template('forgot_password.html', error_message=error_message)


@auth.route('/enter-code', methods=['POST'])
def enter_code():
    email = request.form.get('email', '').strip()
    return render_template('verify_code.html', email=email)


@auth.route('/verify-code', methods=['POST'])
def verify_code():
    email = request.form.get('email', '').strip()
    code = request.form.get('code', '').strip()

    db = get_db()
    user = db.execute(
        'SELECT user_id, token_expiration FROM users WHERE email = ? AND reset_token = ?',
        (email, code)
    ).fetchone()

    if not user:
        return render_template(
            'verify_code.html',
            email=email,
            error_message='認証コードが正しくないか、メールアドレスが一致しません。'
        )

    expiration = user['token_expiration']
    if isinstance(expiration, str):
        expiration = datetime.strptime(expiration.split('.')[0], '%Y-%m-%d %H:%M:%S')

    if datetime.now() > expiration:
        return render_template(
            'verify_code.html',
            email=email,
            error_message='認証コードの有効期限（10分）が切れています。最初からやり直してください。'
        )

    return render_template('reset_password.html', user_id=user['user_id'])


@auth.route('/reset-password', methods=['POST'])
def reset_password():
    user_id = request.form.get('user_id', '')
    new_password = request.form.get('password', '')
    password_confirm = request.form.get('password_confirm', '')

    if not new_password.strip():
        return render_template('reset_password.html', user_id=user_id, error_message='新しいパスワードを入力してください。')

    if new_password != password_confirm:
        return render_template('reset_password.html', user_id=user_id, error_message='パスワードが一致しません。')

    db = get_db()
    new_pass_hash = ph.hash(new_password)

    db.execute(
        'UPDATE users SET password = ?, reset_token = NULL, token_expiration = NULL WHERE user_id = ?',
        (new_pass_hash, user_id)
    )
    db.commit()

    return redirect('/login')