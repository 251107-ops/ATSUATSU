import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "nikuman.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for col in ["skill_name TEXT", "post_type TEXT"]:
        col_name = col.split()[0]
        try:
            cursor.execute(f"ALTER TABLE reviews ADD COLUMN {col};")
            print(f"{col_name} を追加しました")
        except sqlite3.OperationalError:
            print(f"{col_name} は既に存在します")

    # 既存レビューのバックフィル（投稿がまだ残っているものだけ現在の情報で埋める）
    cursor.execute("""
        UPDATE reviews
        SET skill_name = (
            SELECT s.skill_name
            FROM requests r
            JOIN posts p ON r.post_id = p.post_id
            JOIN skills s ON p.skill_id = s.skill_id
            WHERE r.request_id = reviews.request_id
        ),
        post_type = (
            SELECT p.post_type
            FROM requests r
            JOIN posts p ON r.post_id = p.post_id
            WHERE r.request_id = reviews.request_id
        )
        WHERE skill_name IS NULL
    """)
    conn.commit()
    conn.close()
    print("reviewsテーブルのバックフィルが完了しました")

if __name__ == '__main__':
    migrate()