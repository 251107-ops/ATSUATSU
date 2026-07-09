import os
import sqlite3
from flask import Flask, render_template, g, redirect, request, session

DATABASE = "nikuman.db"

app = Flask(__name__)
app.secret_key = os.urandom(24) # セッション情報の暗号化に必要な秘密鍵


# --- ルーティング設定 ---

# トップページ（インデックス）
@app.route("/")
def top():
    # セッションにユーザーのメールアドレスがない場合はログイン画面へリダイレクト
    if 'user_email' not in session:
        return redirect('/login')
    
    return render_template('index.html')

# ログイン画面
@app.route("/login", methods=['GET', 'POST'])
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
        
        # 平文（テキストそのまま）でのパスワード一致チェック
        if user_data is not None and user_data['password'] == password:
            session['user_email'] = email  # セッションにメールアドレスを保存（ログイン完了）
            return redirect('/')
        
        error_message = '入力されたメールアドレスもしくはパスワードが誤っています'

    return render_template('login.html', email=email, error_message=error_message)

@app.route("/register1", methods=['GET', 'POST'])
def register1():
    if request.method == 'POST':
        name = request.form.get('name', '')
        email = request.form.get('email', '')
        password = request.form.get('password', '')

        return render_template('register2.html',name=name,email=email,password=password)

    return render_template('register1.html')

@app.route("/register2", methods=['POST'])
def register2():
     # ここにregister2の処理を追加
    name = request.form.get('name', '')
    email = request.form.get('email', '')
    password = request.form.get('password', '')
    grade = request.form.get('grade', '')
    department = request.form.get('department', '')
    introduction = request.form.get('introduction', '')
    icon_path = request.form.get('icon_path', '')

    db = get_db()
    user_check = db.execute("select user_id from users where user_id = ?", (user_id,)).fetchone()
    db.execute(
        "INSERT INTO users (name, email, password, grade, department, introduction, icon_path) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, email, password, grade, department, introduction, icon_path)
    )
    db.commit()
    return redirect('/login')  # 登録完了後にログインページへリダイレクト


# ログアウト処理
@app.route("/logout")
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
@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()



if __name__ == "__main__":
    app.run(debug=True)