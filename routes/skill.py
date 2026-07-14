from flask import Blueprint, render_template, redirect, session, request
from routes.auth import get_db

skills = Blueprint('skills', __name__)

@skills.route("/skill_edit", methods=['GET', 'POST'])
def add_skill():
    if 'user_email' not in session:
        return redirect('/login')

    user_email = session['user_email']
    db = get_db()
    result = db.execute("INSERT INTO skills (skill_name) VALUES (?)", (request.form.get('skill_name'),)).fetchall()

    return render_template('profile_edit.html', user=user)
