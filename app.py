# --- app.py ---
import os
from flask import Flask, render_template, session
from flask_socketio import SocketIO, send
from routes.posts import posts
from routes.skill import skill
from routes.chat import chat, init_chat_events
from routes.category import categories
from routes.auth import auth, get_db, init_db
from routes.requests import requests_bp
from routes.notifications import notifications_bp
from routes.reviews import reviews_bp

app = Flask(__name__)

# :bulb: 修正点: 開発中は固定の文字列にするか、Blueprintを登録する「前」に必ず設定します
app.secret_key = '.secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Blueprint の登録
app.register_blueprint(auth)
app.register_blueprint(posts)
app.register_blueprint(skill)
app.register_blueprint(chat)
app.register_blueprint(categories)
app.register_blueprint(requests_bp)
app.register_blueprint(notifications_bp)
app.register_blueprint(reviews_bp)

init_chat_events(socketio)
init_db() 

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
    db.execute('''CREATE TABLE IF NOT EXISTS skills (skill_id INTEGER PRIMARY KEY AUTOINCREMENT, skill_name TEXT NOT NULL, category_id INTEGER NOT NULL , FOREIGN KEY(category_id) REFERENCES categories(category_id), UNIQUE (skill_name, category_id))''')
    db.execute('''CREATE TABLE IF NOT EXISTS categories (category_id INTEGER PRIMARY KEY AUTOINCREMENT, category_name TEXT NOT NULL UNIQUE)''')
    db.execute('''CREATE TABLE IF NOT EXISTS likes (user_id INTEGER NOT NULL, post_id INTEGER NOT NULL, PRIMARY KEY (user_id, post_id), FOREIGN KEY (user_id) REFERENCES users(user_id), FOREIGN KEY (post_id) REFERENCES posts(post_id))''')
    # requests テーブルの作成（既存のテーブルがある場合は削除して再作成）
    db.execute('''CREATE TABLE IF NOT EXISTS rooms (
        room_id INTEGER PRIMARY KEY AUTOINCREMENT,
        skill_id INTEGER,
        created_by INTEGER,
        is_public INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    # room_members テーブルの作成（既存のテーブルがある場合は削除して再作成）
    db.execute('''CREATE TABLE IF NOT EXISTS room_members (
        room_id INTEGER,
        user_id INTEGER,
        PRIMARY KEY (room_id, user_id),
        FOREIGN KEY (room_id) REFERENCES rooms(room_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id))''')
    # messages テーブルの作成（既存のテーブルがある場合は削除して再作成）
    db.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_id INTEGER,
        room TEXT,
        user_id INTEGER,
        name TEXT NOT NULL,
        content TEXT NOT NULL,
        send_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    db.execute('''INSERT OR IGNORE INTO categories (category_name) VALUES
        ('IT・PCスキル'),
        ('語学'),
        ('学業・研究'),
        ('就活・キャリア'),
        ('趣味・アート'),
        ('スポーツ・運動'),
        ('ライフスタイル'),
        ('その他')''')
    db.execute('''INSERT OR IGNORE INTO skills (skill_name, category_id)
        SELECT 'Python', category_id FROM categories WHERE category_name = 'IT・PCスキル' UNION ALL
        SELECT 'Excel', category_id FROM categories WHERE category_name = 'IT・PCスキル' UNION ALL
        SELECT '動画編集', category_id FROM categories WHERE category_name = 'IT・PCスキル' UNION ALL
        SELECT '英会話', category_id FROM categories WHERE category_name = '語学' UNION ALL
        SELECT '中国語', category_id FROM categories WHERE category_name = '語学' UNION ALL
        SELECT 'TOEIC対策', category_id FROM categories WHERE category_name = '語学' UNION ALL
        SELECT 'レポート執筆', category_id FROM categories WHERE category_name = '学業・研究' UNION ALL
        SELECT '統計・データ分析', category_id FROM categories WHERE category_name = '学業・研究' UNION ALL
        SELECT '卒論の進め方', category_id FROM categories WHERE category_name = '学業・研究' UNION ALL
        SELECT 'ES添削', category_id FROM categories WHERE category_name = '就活・キャリア' UNION ALL
        SELECT '面接対策', category_id FROM categories WHERE category_name = '就活・キャリア' UNION ALL
        SELECT '業界研究', category_id FROM categories WHERE category_name = '就活・キャリア' UNION ALL
        SELECT 'イラスト', category_id FROM categories WHERE category_name = '趣味・アート' UNION ALL
        SELECT '写真撮影', category_id FROM categories WHERE category_name = '趣味・アート' UNION ALL
        SELECT 'ギター', category_id FROM categories WHERE category_name = '趣味・アート' UNION ALL
        SELECT '筋トレ', category_id FROM categories WHERE category_name = 'スポーツ・運動' UNION ALL
        SELECT 'テニス', category_id FROM categories WHERE category_name = 'スポーツ・運動' UNION ALL
        SELECT 'ランニング', category_id FROM categories WHERE category_name = 'スポーツ・運動' UNION ALL
        SELECT '料理', category_id FROM categories WHERE category_name = 'ライフスタイル' UNION ALL
        SELECT 'ヨガ', category_id FROM categories WHERE category_name = 'ライフスタイル' UNION ALL
        SELECT '一人暮らし術', category_id FROM categories WHERE category_name = 'ライフスタイル' UNION ALL
        SELECT 'なんでも相談', category_id FROM categories WHERE category_name = 'その他' UNION ALL
        SELECT '恋愛相談', category_id FROM categories WHERE category_name = 'その他' UNION ALL
        SELECT 'その他スキル', category_id FROM categories WHERE category_name = 'その他'
    ''')
    db.commit()

@app.context_processor
def inject_unread_notifications():
    if 'user_id' in session:
        db = get_db()
        count = db.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
            (session['user_id'],)
        ).fetchone()[0]
        return {'unread_notifications': count}
    return {'unread_notifications': 0}


@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


if __name__ == "__main__":
    socketio.run(app, debug=True)