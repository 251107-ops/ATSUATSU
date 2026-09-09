from flask import Blueprint, render_template, redirect, session, request, flash, url_for
from routes.auth import get_db

# Blueprint名を skill に設定
skill = Blueprint('skill', __name__)

@skill.route("/skill_edit", methods=['POST'])
def add_skill():
    # ログインチェック
    if 'user_email' not in session:
        return redirect('/login')

    category_id = request.form.get('category_id')
    skill_name = request.form.get('skill_name', '').strip()

    # 入力値の必須チェック
    if not category_id or not skill_name:
        flash('カテゴリとスキル名を入力してください。')
        return redirect('/posts')

    db = get_db()

    try:
        # 1. 重複チェック（同じカテゴリ内に同名のスキルがあるか確認）
        # 大文字・小文字を区別せず比較したい場合は LOWER(skill_name) = LOWER(?) を使用
        existing_skill = db.execute(
            "SELECT skill_id FROM skills WHERE category_id = ? AND LOWER(skill_name) = LOWER(?)",
            (category_id, skill_name)
        ).fetchone()

        if existing_skill:
            flash(f'「{skill_name}」はすでにこのカテゴリに登録されています。')
            return redirect('/posts')

        # 2. DBへの挿入処理（category_id と skill_name の両方を保存）
        db.execute(
            "INSERT INTO skills (category_id, skill_name) VALUES (?, ?)",
            (category_id, skill_name)
        )
        db.commit()
        flash(f'新しいスキル「{skill_name}」を追加しました！')

    except Exception as e:
        print(f"DB登録エラー: {e}")
        db.rollback()
        flash('スキルの登録中にエラーが発生しました。')

    # 処理完了後、投稿画面に戻る
    return redirect('/posts')


@skill.route("/skill", methods=["GET"])
def skill_list():
    if 'user_email' not in session:
        return redirect('/login')

    db = get_db()
    skill_rows = db.execute("SELECT skill_name FROM skills").fetchall()
    return render_template('profile.html', skills=skill_rows)