import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "nikuman.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for col in ["requester_completed", "receiver_completed"]:
        try:
            cursor.execute(f"ALTER TABLE requests ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0;")
            print(f"{col} を追加しました")
        except sqlite3.OperationalError:
            print(f"{col} は既に存在します")
    conn.commit()
    conn.close()

if __name__ == '__main__':
    migrate()
