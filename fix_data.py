import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "nikuman.db")

def fix():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # accepted なのに room_members にいないリクエストを探して追加
    requests = cursor.execute("SELECT requester_id, receiver_id FROM requests WHERE status = 'accepted'").fetchall()
    
    for req in requests:
        req_id, rec_id = req[0], req[1]
        
        # ルーム作成
        cursor.execute("INSERT INTO rooms (created_by) VALUES (?)", (rec_id,))
        room_id = cursor.lastrowid
        
        # メンバー追加
        cursor.execute("INSERT OR IGNORE INTO room_members (room_id, user_id) VALUES (?, ?)", (room_id, req_id))
        cursor.execute("INSERT OR IGNORE INTO room_members (room_id, user_id) VALUES (?, ?)", (room_id, rec_id))
        print(f"Room {room_id} created for users {req_id} and {rec_id}")

    conn.commit()
    conn.close()
    print("データ修復が完了しました！")

if __name__ == '__main__':
    fix()