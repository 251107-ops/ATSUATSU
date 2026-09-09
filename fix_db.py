import os
import sqlite3

# プロジェクト内の .db ファイルを自動探索して更新するスクリプト
current_dir = os.path.dirname(os.path.abspath(__file__))

db_files = []
for root, dirs, files in os.walk(current_dir):
    # .venv などの仮想環境フォルダは除外
    if '.venv' in root:
        continue
    for file in files:
        if file.endswith('.db') or file.endswith('.sqlite') or file.endswith('.sqlite3'):
            db_files.append(os.path.join(root, file))

if not db_files:
    print("DBファイルが見つかりませんでした。ファイル名を確認してください。")
else:
    for db_path in db_files:
        print(f"対象DB: {db_path}")
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # テーブルが存在するか確認
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
            if cursor.fetchone():
                try:
                    cursor.execute("ALTER TABLE users ADD COLUMN reset_token TEXT;")
                    print("  -> reset_token カラムを追加しました")
                except sqlite3.OperationalError:
                    print("  -> reset_token はすでに追加されています")

                try:
                    cursor.execute("ALTER TABLE users ADD COLUMN token_expiration DATETIME;")
                    print("  -> token_expiration カラムを追加しました")
                except sqlite3.OperationalError:
                    print("  -> token_expiration はすでに追加されています")

                conn.commit()
            conn.close()
        except Exception as e:
            print(f"  -> エラーが発生しました: {e}")

print("完了しました。")