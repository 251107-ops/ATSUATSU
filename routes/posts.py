from flask import Blueprint, render_template, redirect, session
from routes.auth import get_db

posts = Blueprint('posts', __name__)

@posts.route("/")
def top():
    if 'user_email' not in session:
        return redirect('/login')

    db = get_db()
    result = db.execute("SELECT name, email, department, grade, introduction, icon_path FROM users").fetchall()
    # result = [dict(row) for row in result]

    return render_template('top.html', posts=result)


@posts.route("/profile")
def profile():
    if 'user_email' not in session:
        return redirect('/login')

    user_email = session['user_email']
    db = get_db()
    user = db.execute("SELECT name, email, department, grade, introduction, icon_path FROM users WHERE email = ?", (user_email,)).fetchone()

    return render_template('profile.html', user=user)