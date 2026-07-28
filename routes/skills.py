from flask import Blueprint, render_template, redirect, session, request
from routes.auth import get_db

skills = Blueprint('skills', __name__)


@skills.route("/skill_edit", methods=['GET', 'POST'])
def add_skill():
    if 'user_email' not in session:
        return redirect('/login')

    db = get_db()
    skill_name = request.form.get('skill_name', '').strip()

    if skill_name:
        db.execute(
            "INSERT INTO skills (skill_name) VALUES (?)",
            (skill_name,)
        )
        db.commit()

    return redirect('/posts')


@skills.route("/skill", methods=["GET"])
def skill_list():
    if 'user_email' not in session:
        return redirect('/login')

    db = get_db()
    skill_rows = db.execute("SELECT skill_name FROM skills").fetchall()
    return render_template('profile.html', skills=skill_rows)