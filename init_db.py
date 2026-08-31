import os
import sqlite3

# auth.py と同じパス（nikuman.db）を指定
DB_PATH = os.path.join(os.path.dirname(__file__), "nikuman.db")

def init_chat_tables():
    if not os.path.exists(DB_PATH):
        print(f"エラー: DBファイルが見つかりません -> {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # rooms テーブルの作成（初回作成用）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            room_id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill_id INTEGER,
            is_public INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 既に rooms テーブルが存在する場合のために skill_id カラムを追加
    try:
        cursor.execute("ALTER TABLE rooms ADD COLUMN skill_id INTEGER;")
        print("rooms テーブルに skill_id カラムを追加しました。")
    except sqlite3.OperationalError:
        # すでに skill_id カラムが存在する場合は無視
        pass

    # room_members テーブルの作成
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS room_members (
            room_id INTEGER,
            user_id INTEGER,
            PRIMARY KEY (room_id, user_id),
            FOREIGN KEY (room_id) REFERENCES rooms(room_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
    """)

    conn.commit()
    conn.close()
    print("【成功】nikuman.db の更新が完了しました！")

if __name__ == '__main__':
    init_chat_tables()