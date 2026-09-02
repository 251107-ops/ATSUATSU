# check_request.py
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "nikuman.db")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# ① requestsテーブルの列一覧を確認（マイグレーションが効いているか）
print("=== requestsテーブルの列一覧 ===")
cols = conn.execute("PRAGMA table_info(requests)").fetchall()
for c in cols:
    print(c['name'])

print()

# ② 実際のrequests行を全部確認
print("=== requestsの中身 ===")
rows = conn.execute("SELECT * FROM requests").fetchall()
for r in rows:
    print(dict(r))

conn.close()