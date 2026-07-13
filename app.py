import os
import json
import sqlite3
from flask import Flask, render_template, g, redirect, request, session, jsonify

DATABASE = "nikuman.db"

app = Flask(__name__)
# 開発をスムーズにするため、秘密鍵を固定値にすることをおすすめします（再起動ごとの強制ログアウトを防ぐため）
app.secret_key = os.urandom(24) 


# ==========================================================================
# --- ルーティング設定 ---
# ==========================================================================

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


# 新規登録 画面1
@app.route("/register1", methods=['GET', 'POST'])
def register1():
    if request.method == 'POST':
        name = request.form.get('name', '')
        email = request.form.get('email', '')
        password = request.form.get('password', '')

        return render_template('register2.html', name=name, email=email, password=password)

    return render_template('register1.html')


# 新規登録 処理2
@app.route("/register2", methods=['POST'])
def register2():
    name = request.form.get('name', '')
    email = request.form.get('email', '')
    password = request.form.get('password', '')
    grade = request.form.get('grade', '')
    department = request.form.get('department', '')
    introduction = request.form.get('introduction', '')
    icon_path = request.form.get('icon_path', '')

    db = get_db()
    
    # 【修正】未定義の user_id ではなく、email で重複チェックを行うように修正
    user_check = db.execute("SELECT email FROM users WHERE email = ?", (email,)).fetchone()
    if user_check is not None:
        return "このメールアドレスは既に登録されています。", 400

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


# プロフィール編集画面の表示と更新
@app.route("/profile", methods=['GET', 'POST'])
def profile():
    # ログインチェック
    if 'user_email' not in session:
        if request.method == 'POST':
            return jsonify({'message': 'セッションが切れました。再ログインしてください'}), 401
        return redirect('/login')
        
    email = session['user_email']
    db = get_db()

    # --------------------------------------------------
    # POST: JavaScript(fetch)からの非同期保存処理
    # --------------------------------------------------
    if request.method == 'POST':
        try:
            # フォームから送信されたデータを取得
            name = request.form.get('name', '')
            grade = request.form.get('grade', '')
            department = request.form.get('department', '')
            introduction = request.form.get('bio', '')  # HTMLのtextareaのname="bio"
            
            # JavaScriptからJSON文字列として送られてくるスキル配列をパース
            teach_skills_json = request.form.get('teachSkills', '[]')
            learn_skills_json = request.form.get('learnSkills', '[]')
            teach_skills_list = json.loads(teach_skills_json)
            learn_skills_list = json.loads(learn_skills_json)

            # 画像ファイルの取得（送られてきている場合）
            avatar_file = request.files.get('avatar')
            icon_path = None
            if avatar_file and avatar_file.filename != '':
                icon_path = f"/static/img/{avatar_file.filename}"

            # データベースのユーザー情報を更新
            if icon_path:
                db.execute(
                    """
                    UPDATE users 
                    SET name = ?, grade = ?, department = ?, introduction = ?, icon_path = ?
                    WHERE email = ?
                    """,
                    (name, grade, department, introduction, icon_path, email)
                )
            else:
                db.execute(
                    """
                    UPDATE users 
                    SET name = ?, grade = ?, department = ?, introduction = ? 
                    WHERE email = ?
                    """,
                    (name, grade, department, introduction, email)
                )
            
            db.commit()

            # JavaScript側の fetch が正常終了と判定できるようJSONを返す
            return jsonify({'message': 'プロフィールを保存しました！'})

        except Exception as e:
            print(f"Error: {e}")
            return jsonify({'message': 'サーバー側でエラーが発生しました'}), 500

    # --------------------------------------------------
    # GET: 画面表示処理
    # --------------------------------------------------
    
    # 現在のユーザー情報を取得
    user = db.execute(
        "SELECT name, email, grade, department, introduction, icon_path FROM users WHERE email = ?", 
        [email]
    ).fetchone()

    # スキルデータの取得（※現在は仮の初期データ。必要に応じてテーブルからSQLで取得してください）
    teach_skills = ["Python", "HTML/CSS"]
    learn_skills = ["データサイエンス", "UI/UXデザイン"]

    # CSRFトークン用の仮関数（HTML側で csrf_token() を呼んでいるため）
    def dummy_csrf_token():
        return "dummy_token_string"

    return render_template(
        'profile.html', 
        user=user, 
        teach_skills=teach_skills, 
        learn_skills=learn_skills,
        csrf_token=dummy_csrf_token  # HTML側のエラーを防ぐために渡しています
    )


# ==========================================================================
# --- データベース共通処理（重複を排除し1つに統合） ---
# ==========================================================================

# データベース接続関数
def connect_db():
    rv = sqlite3.connect(DATABASE)
    rv.row_factory = sqlite3.Row  # カラム名でのデータ取得を可能にする設定
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