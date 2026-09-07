import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "nikuman.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE room_members ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0;")
        print("hidden を追加しました")
    except sqlite3.OperationalError:
        print("hidden は既に存在します")
    conn.commit()
    conn.close()

if __name__ == '__main__':
    migrate()