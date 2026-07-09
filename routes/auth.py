import os
import sqlite3
from flask import Blueprint, render_template, g, redirect, request, session
from werkzeug.security import generate_password_hash, check_password_hash
from argon2 import PasswordHasher
ph = PasswordHasher()

DATABASE = os.path.join(os.path.dirname(__file__), "..", "nikuman.db")

# 💡 routesフォルダ内に置く場合は template_folder の指定が必要です
auth = Blueprint('auth', __name__, template_folder='../templates')
auth.secret_key = os.urandom(24) # セッション情報の暗号化に必要な秘密鍵


# --- ルーティング設定 ---

# ログイン画面
@auth.route("/login", methods=['GET', 'POST'])
def login():
    error_message = ''
    email = ''

    if request.method == 'POST':
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        
        db = get_db()
        # データベースから該当するメールアドレスのユーザー情報を取得
        user_data = db.execute(
            "SELECT email, password FROM users WHERE email = ?", [email]
        ).fetchone()
        
        # ⭕ ハッシュ化されたパスワードの検証
        if user_data is not None and ph.verify(user_data['password'], password):
            session['user_email'] = email  # セッションにメールアドレスを保存（ログイン完了）
            return redirect('/')
        
        error_message = '入力されたメールアドレスもしくはパスワードが誤っています'

    return render_template('login.html', email=email, error_message=error_message)

# 新規登録 1ページ目
@auth.route("/register1", methods=['GET', 'POST'])
def register1():
    if request.method == 'POST':
        name = request.form.get('name', '')
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        
        # ⭕ method='sha256' を削除（自動で最新の安全なアルゴリズムが使われます）
        pass_hash = ph.hash(password)
        return render_template('register2.html', name=name, email=email, password=pass_hash)

    return render_template('register1.html')

# 新規登録 2ページ目
@auth.route("/register2", methods=['POST'])
def register2():
    name = request.form.get('name', '')
    email = request.form.get('email', '')
    password = request.form.get('password', '') # 1ページ目から引き継いだハッシュ化済みパスワード
    grade = request.form.get('grade', '')
    department = request.form.get('department', '')
    introduction = request.form.get('introduction', '')
    icon_path = request.form.get('icon_path', '')

    db = get_db()
    user_check = db.execute("SELECT email FROM users WHERE email = ?", (email,)).fetchone()
    
    if not user_check:
        db.execute(
            "INSERT INTO users (name, email, password, grade, department, introduction, icon_path) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, email, password, grade, department, introduction, icon_path)
        )
        db.commit()
        return redirect('/login')  # 登録完了後にログインページへリダイレクト
    else:
        error_message = '入力されたデータにはエラーがあります'
    return render_template('register1.html', error_message=error_message, name=name, email=email, password=password)


# ログアウト処理
@auth.route("/logout")
def logout():
    session.pop('user_email', None)  # セッションからユーザー情報を削除（ログアウト）
    return redirect('/login')


# データベース接続関数
def connect_db():
    rv = sqlite3.connect(DATABASE)
    rv.row_factory = sqlite3.Row # カラム名でのデータ取得を可能にする設定
    return rv

# データベースインスタンスの取得
def get_db():
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db

# リクエスト終了時に自動でデータベースを閉じる
@auth.teardown_appcontext
def close_db(error):
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()