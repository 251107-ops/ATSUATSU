from flask import Blueprint, render_template, redirect, session, request
from routes.auth import get_db

posts = Blueprint('posts', __name__)

@posts.route("/")
def top():
    if 'user_email' not in session:
        return redirect('/login')

    db = get_db()
    rows = db.execute("""
        SELECT
            users.name, users.department, users.grade, users.icon_path,
            skills.skill_name,
            posts.post_type, posts.post_text
        FROM posts
        JOIN users ON posts.user_id = users.user_id
        JOIN skills ON posts.skill_id = skills.skill_id
    """).fetchall()

    posts_list = []
    for row in rows:
        posts_list.append({
            'name': row[0],
            'department': row[1],
            'grade': row[2],
            'icon_path': row[3] if row[3] else 'img/default-avatar.png',
            'skill_name': row[4],
            'post_type': row[5],
            'post_text': row[6],
            'category_name': 'スキル',
            'favorite_count': 0       
        })
    return render_template('top.html', posts=posts_list)

# @posts.route("/profile_edit")
# def profile_edit(): 
#     return render_template('profile_edit.html')

@posts.route("/profile", methods=['GET', 'POST'])
def profile():
    if 'user_email' not in session:
        return redirect('/login')

    user_email = session['user_email']
    db = get_db()
    row = db.execute("SELECT name, email, department, grade, introduction, icon_path FROM users WHERE email = ?", (user_email,)).fetchone()
    if row:
        user = {
            'name': row[0],
            'email': row[1],
            'department': row[2],
            'grade': row[3],
            'introduction': row[4],
            'icon_path': row[5]
        }
    return render_template('profile.html', user=user)

@posts.route("/profile_edit", methods=['GET', 'POST'])
def profile_edit():
    if 'user_email' not in session:
        return redirect('/login')

    user_email = session['user_email']
    db = get_db()
    row = db.execute("SELECT name, email, department, grade, introduction, icon_path FROM users WHERE email = ?", (user_email,)).fetchone()

    if row:
        user = {
            'name': row[0],
            'email': row[1],
            'department': row[2],
            'grade': row[3],
            'introduction': row[4],
            'icon_path': row[5]
        }

    return render_template('profile_edit.html', user=user)

@posts.route("/profile/edit", methods=['GET', 'POST'])
def edit_profile():
    if 'user_email' not in session:
        return redirect('/login')

    user_email = session['user_email']
    db = get_db()

    if request.method == 'POST':
        name = request.form.get('name', '')
        department = request.form.get('department', '')
        grade = request.form.get('grade', '')
        introduction = request.form.get('introduction', '')

        db.execute(
            "UPDATE users SET name = ?, department = ?, grade = ?, introduction = ? WHERE email = ?",
            (name, department, grade, introduction, user_email)
        )
        db.commit()
        return redirect('/profile')

    # user = db.execute("SELECT name, email, department, grade, introduction FROM users WHERE email = ?", (user_email,)).fetchone()
    # return render_template('profile.html', user=user)

# @posts.route("/top")
# def home():

#     return render_template('top.html')

@posts.route("/posts", methods=['GET', 'POST'])
def create_post():
    db = get_db()
    if 'user_email' not in session:
        return redirect('/login')

    if request.method == 'POST':
        # フォームからデータを取得
        skill_id = request.form.get('skill_id', '')
        post_type = request.form.get('post_type', '')
        post_text = request.form.get('post_text', '')

        if not skill_id or not post_type or not post_text:
            return "すべてのフィールドを入力してください", 400
        
        user_id = session.get('user_id')


        if user_id and skill_id:
            db.execute(
                "INSERT INTO posts (user_id, skill_id, post_type, post_text) VALUES (?, ?, ?, ?)",
                (session['user_id'], skill_id, post_type, post_text)
            )
            db.commit()
            return redirect('/')
    skills = db.execute("SELECT skill_id, skill_name FROM skills").fetchall()
    return render_template('posts.html', skills=skills)