# --- app.py ---
import os
from flask import Flask, render_template
from flask_socketio import SocketIO, send
from routes.auth import auth
from routes.posts import posts
from routes.skill import skill
from routes.chat import chat, init_chat_events
from routes.category import categories
from routes.auth import get_db

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

init_chat_events(socketio)

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

with app.app_context():
    db = get_db()
    db.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY AUTOINCREMENT, 
        name TEXT NOT NULL UNIQUE, email TEXT NOT NULL UNIQUE, password TEXT NOT NULL, grade TEXT NOT NULL, department TEXT NOT NULL, 
        introduction TEXT, icon_path TEXT)''')
    db.execute('''CREATE TABLE IF NOT EXISTS  posts (post_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, skill_id INTEGER NOT NULL, post_type TEXT NOT NULL, 
        post_text TEXT NOT NULL, post_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, category_id INTEGER NOT NULL, 
        FOREIGN KEY(user_id) REFERENCES users(user_id),  FOREIGN KEY(skill_id) REFERENCES skills(skill_id), FOREIGN KEY(category_id) REFERENCES categories(category_id))''')
    db.execute('''CREATE TABLE IF NOT EXISTS skills (skill_id INTEGER PRIMARY KEY AUTOINCREMENT, skill_name TEXT NOT NULL, category_id INTEGER NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS categories (category_id INTEGER PRIMARY KEY AUTOINCREMENT, category_name TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS likes (user_id INTEGER NOT NULL, post_id INTEGER NOT NULL, PRIMARY KEY (user_id, post_id), FOREIGN KEY (user_id) REFERENCES users(user_id), FOREIGN KEY (post_id) REFERENCES posts(post_id))''')
    db.commit()

if __name__ == "__main__":
    socketio.run(app, debug=True)