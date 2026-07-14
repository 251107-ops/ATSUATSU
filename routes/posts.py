from flask import Blueprint, render_template, redirect, session, request
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