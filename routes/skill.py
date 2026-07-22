from flask import Blueprint, render_template, redirect, session, request
from routes.auth import get_db

skills = Blueprint('skills', __name__)

@skills.route("/skill_edit", methods=['GET', 'POST'])
def add_skill():
    if 'user_email' not in session:
        return redirect('/login')

    user_email = session['user_email']
    db = get_db()
    result = db.execute("INSERT INTO skills (skill_name) VALUES (?)", (request.form.get('skill_name'),))
    db.commit()

    return render_template('posts.html')

@skills.route("/skill", methods=["GET"])
def skill_list():
    if 'user_email' not in session:
        return redirect('/login')

    user_email = session['user_email']
    user_id = session.get('user_id')
    db = get_db()
    
    
    user_row = db.execute(
        "SELECT name, email, department, grade, introduction, icon_path FROM users WHERE email = ?", 
        (user_email,)
    ).fetchone()
    
    user = None
    if user_row:
        user = {
            'name': user_row[0],
            'email': user_row[1],
            'department': user_row[2],
            'grade': user_row[3],
            'introduction': user_row[4],
            'icon_path': user_row[5]
        }


    learn_data = db.execute("""
        SELECT DISTINCT skills.skill_id, skills.skill_name 
        FROM posts
        JOIN skills ON posts.skill_id = skills.skill_id
        WHERE posts.user_id = ? AND posts.post_type = '学びたい'
    """, (user_id,)).fetchall()
    
    skills_learn = [{'skill_id': row[0], 'skill_name': row[1]} for row in learn_data]

    
    teach_data = db.execute("""
        SELECT DISTINCT skills.skill_id, skills.skill_name 
        FROM posts
        JOIN skills ON posts.skill_id = skills.skill_id
        WHERE posts.user_id = ? AND posts.post_type = '教えたい'
    """, (user_id,)).fetchall()
    
    skills_teach = [{'skill_id': row[0], 'skill_name': row[1]} for row in teach_data]

    
    return render_template('profile.html', user=user, skills_learn=skills_learn, skills_teach=skills_teach)
