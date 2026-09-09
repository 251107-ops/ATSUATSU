# migrate_projects.py
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "nikuman.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ==========================================
    # グループチャット用テーブル（メンバー提供分と同一定義、IF NOT EXISTSなので二重実行しても安全）
    # ==========================================
    cursor.execute('''CREATE TABLE IF NOT EXISTS group_rooms (
        group_room_id TEXT PRIMARY KEY,
        skill_id INTEGER NOT NULL REFERENCES skills(skill_id) ON DELETE CASCADE,
        created_by INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        is_public INTEGER DEFAULT 1
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS group_members (
        group_room_id TEXT NOT NULL REFERENCES group_rooms(group_room_id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        role TEXT DEFAULT 'member',
        joined_at TEXT DEFAULT (datetime('now','localtime')),
        PRIMARY KEY (group_room_id, user_id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS group_messages (
        message_id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_room_id INTEGER NOT NULL REFERENCES group_rooms(group_room_id) ON DELETE CASCADE,
        sender_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        content TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )''')

    # ==========================================
    # プロジェクト機能用テーブル（新設計：スキルは単一、募集カード情報を保持）
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            project_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_user_id  INTEGER NOT NULL REFERENCES users(user_id),
            project_name   TEXT NOT NULL,
            description    TEXT NOT NULL,
            skill_id       INTEGER NOT NULL REFERENCES skills(skill_id),
            recruit_count  INTEGER NOT NULL DEFAULT 2,
            group_room_id  TEXT NOT NULL REFERENCES group_rooms(group_room_id),
            status         TEXT NOT NULL DEFAULT 'recruiting',
            created_at     TEXT DEFAULT (datetime('now','localtime'))
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_requests (
            request_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id   INTEGER NOT NULL REFERENCES projects(project_id),
            applicant_id INTEGER NOT NULL REFERENCES users(user_id),
            status       TEXT NOT NULL DEFAULT 'pending',
            created_at   TEXT DEFAULT (datetime('now','localtime')),
            updated_at   TEXT DEFAULT (datetime('now','localtime'))
        );
    """)

    conn.commit()
    conn.close()
    print("projects関連テーブル（v2・group_rooms連携版）の作成が完了しました")

if __name__ == '__main__':
    migrate()