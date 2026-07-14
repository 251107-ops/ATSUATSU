from flask import Blueprint, render_template, redirect, session, request
from routes.auth import get_db

categories = Blueprint('categories', __name__)

# @categories.route("/categories")
# def category_list():
#     if 'user_email' not in session:
#         return redirect('/login')

#     db = get_db()
#     categories = db.execute("SELECT * FROM categories").fetchall()
#     return render_template('category_list.html', categories=categories)

# @categories.route("categories", methods=['GET', 'POST'])
# def add_category():
#     if 'user_email' not in session:
#         return redirect('/login')

#     if request.method == 'POST':
#         category_name = request.form.get('category_name', '')
#         db = get_db()
#         db.execute("INSERT INTO categories (name) VALUES (?)", (category_name,))
#         db.commit()
#         return redirect('/categories')

#     return render_template('add_category.html')