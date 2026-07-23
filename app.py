# --- app.py ---
import os
from flask import Flask, render_template
from flask_socketio import SocketIO, send
from routes.auth import auth
from routes.posts import posts
from routes.skill import skills
from routes.chat import chat, init_chat_events
from routes.category import categories

app = Flask(__name__)

# 💡 修正点: 開発中は固定の文字列にするか、Blueprintを登録する「前」に必ず設定します
app.secret_key = '.secret_key' 

socketio = SocketIO(app, cors_allowed_origins="*")

# Blueprint の登録
app.register_blueprint(auth)
app.register_blueprint(posts)
app.register_blueprint(skills)
app.register_blueprint(chat)
app.register_blueprint(categories)

init_chat_events(socketio)

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

if __name__ == "__main__":
    socketio.run(app, debug=True)