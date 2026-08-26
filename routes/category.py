from flask import Blueprint, render_template, redirect, session, request
from routes.auth import get_db

categories = Blueprint('categories', __name__)

@categories.route("/categories")
def category_list():
    if 'user_email' not in session:
        return redirect('/login')

    user_email = session['user_email']
    db = get_db()
    category_rows = db.execute("SELECT * FROM categories").fetchall()
    return render_template('top.html', categories=category_rows)

@categories.route("/categories-add", methods=['GET', 'POST'])
def add_category():
    if 'user_email' not in session:
        return redirect('/login')
    
    user_email = session['user_email']

    if request.method == 'POST':
        category_name = request.form.get('category_name', '')
        db = get_db()
        db.execute("INSERT INTO categories (category_name) VALUES (?)", (category_name,))
        db.commit()
        return redirect('/posts')

    return render_template('posts.html')