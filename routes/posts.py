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