import os
from flask import Flask
# routes フォルダの auth.py から auth（Blueprint）をインポート
from routes.auth import auth
from routes.posts import posts
from routes.skills import skills

app = Flask(__name__)

# 🔑 セッション（cookie）の暗号化に必要な鍵はここで設定します
app.secret_key = os.urandom(24)

# 🔌 ここで Blueprint をアプリケーション本体に登録（合体！）
app.register_blueprint(auth)
app.register_blueprint(posts)
app.register_blueprint(skills)

if __name__ == "__main__":
    app.run(debug=True)