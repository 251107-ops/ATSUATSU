import os
import sqlite3

# Flaskアプリと同じデータベース（nikuman.db）を指定
DB_PATH = os.path.join(os.path.dirname(__file__), "nikuman.db")

def create_tables():
    if not os.path.exists(DB_PATH):
        print(f"エラー: データベースファイルが見つかりません -> {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. rooms テーブルの作成
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            room_id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill_id INTEGER,
            created_by INTEGER,
            is_public INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 既存の rooms テーブルのカラム拡張
    try:
        cursor.execute("ALTER TABLE rooms ADD COLUMN skill_id INTEGER;")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE rooms ADD COLUMN created_by INTEGER;")
    except sqlite3.OperationalError:
        pass
    
    # 2. room_members テーブルの作成
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS room_members (
            room_id INTEGER,
            user_id INTEGER,
            PRIMARY KEY (room_id, user_id),
            FOREIGN KEY (room_id) REFERENCES rooms(room_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
    """)

    # 3. messages テーブルの作成（ここが不足していました）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            room TEXT NOT NULL,
            user_id INTEGER,
            name TEXT NOT NULL,
            content TEXT NOT NULL,
            send_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    conn.commit()
    conn.close()
    print("【成功】messages テーブルの作成・更新が完了しました！")

if __name__ == '__main__':
    create_tables()