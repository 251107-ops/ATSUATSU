from flask import Blueprint, render_template, redirect, session, request
from routes.auth import get_db

# Blueprint名を skill に変更
skill = Blueprint('skill', __name__)


@skill.route("/skill_edit", methods=['POST'])  # POST専用
def add_skill():
    if 'user_email' not in session:
        return redirect('/login')

    if request.method == 'POST':
        db = get_db()
        skill_name = request.form.get('skill_name', '').strip()
        category_id = request.form.get('category_id')
        skill_id = request.form.get('skill_id', '')

        if skill_name:
            try:
                # DBへの挿入処理
                db.execute(
                    "INSERT INTO skills (skill_name) VALUES (?,?)",
                    (skill_name,category_id)
                )
                db.commit()
            except Exception as e:
                print(f"DB登録エラー: {e}")
                db.rollback()

    # 処理が終わったら投稿ページ（/posts）へ戻る
    return redirect('/posts')


@skill.route("/skill", methods=["GET"])
def skill_list():
    if 'user_email' not in session:
        return redirect('/login')

    db = get_db()
    skill_rows = db.execute("SELECT skill_name FROM skills").fetchall()
    return render_template('profile.html', skills=skill_rows)