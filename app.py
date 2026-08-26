# --- app.py ---
import os
from routes.auth import get_db
from flask import Flask, render_template, session
from flask_socketio import SocketIO, send
from routes.auth import auth
from routes.posts import posts
from routes.skill import skill
from routes.chat import chat, init_chat_events
from routes.category import categories
from routes.requests import requests_bp

app = Flask(__name__)

# 💡 修正点: 開発中は固定の文字列にするか、Blueprintを登録する「前」に必ず設定します
app.secret_key = '.secret_key' 

socketio = SocketIO(app, cors_allowed_origins="*")

# Blueprint の登録
app.register_blueprint(auth)
app.register_blueprint(posts)
app.register_blueprint(skill)
app.register_blueprint(chat)
app.register_blueprint(categories)
app.register_blueprint(requests_bp)

init_chat_events(socketio)

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

if __name__ == "__main__":
    socketio.run(app, debug=True)
    # app.py などに追記
@app.context_processor
def inject_notifications():
    user_id = session.get('user_id')
    if not user_id:
        return dict(unread_count=0)
    
    db = get_db()
    # is_read = 0 (未読) の通知数をカウント
    row = db.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
        (user_id,)
    ).fetchone()
    
    unread_count = row[0] if row else 0
    return dict(unread_count=unread_count)