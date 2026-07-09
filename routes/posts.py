from flask import Blueprint, render_template, redirect, session
from routes.auth import get_db

posts = Blueprint('posts', __name__)

@posts.route("/")
def top():
    if 'user_email' not in session:
        return redirect('/login')

    db = get_db()
    result = db.execute("""
        SELECT
            users.username, users.department, users.grade, users.profile_photo,
            categories.name AS category_name,
            skills.skill_name,
            posts.type, posts.body
        FROM posts
        JOIN users ON posts.user_id = users.user_id
        JOIN skills ON posts.skill_id = skills.skill_id
        JOIN categories ON skills.category_id = categories.category_id
        ORDER BY posts.created_at DESC
    """).fetchall()

    return render_template('index.html', posts=result)