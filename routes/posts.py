import os
from datetime import datetime
from flask import Blueprint, render_template, redirect, session, request, jsonify
from werkzeug.utils import secure_filename
from routes.auth import get_db

posts = Blueprint('posts', __name__)


@posts.route("/")
def top():
    if 'user_email' not in session:
        return redirect('/login')

    sort_type = request.args.get('sort', 'new')

    if sort_type == 'popular':
        order_by = "ORDER BY like_count DESC, posts.post_date"
    else:
        order_by = "ORDER BY posts.post_date DESC"

    db = get_db()
    query = f"""
        SELECT
            users.name, users.department, users.grade, users.icon_path,
            skills.skill_name,
            posts.post_type, posts.post_text, posts.post_id,
            (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.post_id) AS like_count
        FROM posts
        JOIN users ON posts.user_id = users.user_id
        JOIN skills ON posts.skill_id = skills.skill_id
        {order_by}
    """

    rows = db.execute(query).fetchall()

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
            'post_id': row[7],
            'category_name': 'スキル',
            'like_count': row[8] if row[8] else 0
        })
    return render_template('top.html', posts=posts_list, active_tab='all', active_sort=sort_type)


@posts.route("/top/learn")
def top_learn():
    if 'user_email' not in session:
        return redirect('/login')

    db = get_db()
    rows = db.execute("""
        SELECT
            users.name, users.department, users.grade, users.icon_path,
            skills.skill_name,
            posts.post_type, posts.post_text, posts.post_id,
            (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.post_id) AS like_count
        FROM posts
        JOIN users ON posts.user_id = users.user_id
        JOIN skills ON posts.skill_id = skills.skill_id
        WHERE posts.post_type = '学びたい'
        ORDER BY posts.post_date DESC
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
            'post_id': row[7],
            'category_name': 'スキル',
            'like_count': row[8] if row[8] else 0
        })
    return render_template('top.html', posts=posts_list, active_tab='learn')


@posts.route("/top/teach")
def top_teach():
    if 'user_email' not in session:
        return redirect('/login')

    db = get_db()
    rows = db.execute("""
        SELECT
            users.name, users.department, users.grade, users.icon_path,
            skills.skill_name,
            posts.post_type, posts.post_text, posts.post_id,
            (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.post_id) AS like_count
        FROM posts
        JOIN users ON posts.user_id = users.user_id
        JOIN skills ON posts.skill_id = skills.skill_id
        WHERE posts.post_type = '教えたい'
        ORDER BY posts.post_date DESC
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
            'post_id': row[7],
            'category_name': 'スキル',
            'like_count': row[8] if row[8] else 0
        })
    return render_template('top.html', posts=posts_list, active_tab='teach')


@posts.route("/profile", methods=['GET', 'POST'])
def profile():
    if 'user_email' not in session:
        return redirect('/login')

    user_email = session['user_email']
    user_id = session.get('user_id')
    db = get_db()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        department = request.form.get('department', '')
        grade = request.form.get('grade', '')
        introduction = request.form.get('bio', '')

        if not name:
            return jsonify({'message': '名前を入力してください'}), 400

        # アイコン画像の保存処理
        icon_path = None
        avatar_file = request.files.get('avatar')
        if avatar_file and avatar_file.filename:
            allowed_ext = {'.png', '.jpg', '.jpeg', '.gif'}
            ext = os.path.splitext(avatar_file.filename)[1].lower()
            if ext not in allowed_ext:
                return jsonify({'message': '対応していない画像形式です'}), 400

            filename = secure_filename(f"user_{user_id}{ext}")
            upload_dir = os.path.join('static', 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            save_path = os.path.join(upload_dir, filename)
            avatar_file.save(save_path)

            # DBに保存するパスは url_for('static', ...) が使える相対パスにする
            icon_path = f"uploads/{filename}"

        if icon_path:
            db.execute(
                "UPDATE users SET name = ?, department = ?, grade = ?, introduction = ?, icon_path = ? WHERE email = ?",
                (name, department, grade, introduction, icon_path, user_email)
            )
        else:
            db.execute(
                "UPDATE users SET name = ?, department = ?, grade = ?, introduction = ? WHERE email = ?",
                (name, department, grade, introduction, user_email)
            )
        db.commit()

        return jsonify({'message': 'プロフィールを保存しました'}), 200

    # ↓ GET時の表示処理
    row = db.execute(
        "SELECT name, email, department, grade, introduction, icon_path FROM users WHERE email = ?",
        (user_email,)
    ).fetchone()

    user = None
    if row:
        user = {
            'name': row[0],
            'email': row[1],
            'department': row[2],
            'grade': row[3],
            'introduction': row[4],
            'icon_path': row[5]
        }

    teach_rows = db.execute("""
        SELECT DISTINCT skills.skill_id, skills.skill_name 
        FROM posts
        JOIN skills ON posts.skill_id = skills.skill_id
        WHERE posts.user_id = ? AND posts.post_type = '教えたい'
    """, (user_id,)).fetchall()
    skills_teach = [{'skill_id': r[0], 'skill_name': r[1]} for r in teach_rows]

    learn_rows = db.execute("""
        SELECT DISTINCT skills.skill_id, skills.skill_name 
        FROM posts
        JOIN skills ON posts.skill_id = skills.skill_id
        WHERE posts.user_id = ? AND posts.post_type = '学びたい'
    """, (user_id,)).fetchall()
    skills_learn = [{'skill_id': r[0], 'skill_name': r[1]} for r in learn_rows]

    return render_template('profile.html', user=user, skills_teach=skills_teach, skills_learn=skills_learn)


@posts.route("/profile_edit", methods=['GET', 'POST'])
def profile_edit():
    if 'user_email' not in session:
        return redirect('/login')

    user_email = session['user_email']
    db = get_db()
    row = db.execute(
        "SELECT name, email, department, grade, introduction, icon_path FROM users WHERE email = ?",
        (user_email,)
    ).fetchone()

    user = None
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

    return redirect('/profile')


@posts.route("/posts", methods=['GET', 'POST'])
def create_post():
    db = get_db()
    if 'user_email' not in session:
        return redirect('/login')

    if request.method == 'POST':
        skill_id = request.form.get('skill_id', '')
        post_type = request.form.get('post_type', '')
        post_text = request.form.get('post_text', '')

        if not skill_id or not post_type or not post_text:
            return "すべてのフィールドを入力してください", 400

        user_id = session.get('user_id')

        if user_id and skill_id:
            post_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            db.execute(
                "INSERT INTO posts (user_id, skill_id, post_type, post_text, post_date) VALUES (?, ?, ?, ?, ?)",
                (user_id, skill_id, post_type, post_text, post_date)
            )
            db.commit()
            return redirect('/')

    skills = db.execute("SELECT skill_id, skill_name FROM skills").fetchall()
    return render_template('posts.html', skills=skills)


@posts.route("/posts/search", methods=['GET', 'POST'])
def search_posts():
    if 'user_email' not in session:
        return redirect('/login')

    db = get_db()
    search_query = request.args.get('query', '')

    if search_query:
        rows = db.execute("""
            SELECT
                users.name, users.department, users.grade, users.icon_path,
                skills.skill_name,
                posts.post_type, posts.post_text, posts.post_id,
                (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.post_id) AS like_count
            FROM posts
            JOIN users ON posts.user_id = users.user_id
            JOIN skills ON posts.skill_id = skills.skill_id
            WHERE skills.skill_name LIKE ?
            OR users.department LIKE ?
            OR users.grade LIKE ?
            ORDER BY posts.post_date DESC
        """, ('%' + search_query + '%', '%' + search_query + '%', '%' + search_query + '%')).fetchall()

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
                'post_id': row[7],
                'category_name': 'スキル',
                'like_count': row[8] if row[8] else 0
            })
        return render_template('top.html', posts=posts_list, active_tab='all', search_query=search_query)

    return redirect('/')


@posts.route("/posts/likes", methods=['POST'])
def like_post():
    if 'user_email' not in session:
        return redirect('/login')

    post_id = request.form.get('post_id')
    user_id = session.get('user_id')
    if not post_id or not user_id:
        return redirect('/')
    db = get_db()

    existing_like = db.execute(
        "SELECT 1 FROM likes WHERE user_id = ? AND post_id = ?", (user_id, post_id)
    ).fetchone()

    if existing_like:
        db.execute("DELETE FROM likes WHERE user_id = ? AND post_id = ?", (user_id, post_id))
    else:
        db.execute("INSERT INTO likes (user_id, post_id) VALUES (?, ?)", (user_id, post_id))

    db.commit()
    return redirect(request.referrer or '/')


@posts.route("/likes/page", methods=["GET"])
def get_like():
    if 'user_email' not in session:
        return redirect('/login')

    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    db = get_db()
    rows = db.execute("""
        SELECT
            users.name, users.department, users.grade, users.icon_path,
            skills.skill_name,
            posts.post_type, posts.post_text, posts.post_id,
            (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.post_id) AS like_count
        FROM posts
        JOIN users ON posts.user_id = users.user_id
        JOIN skills ON posts.skill_id = skills.skill_id
        WHERE posts.post_id IN (
            SELECT likes.post_id FROM likes WHERE likes.user_id = ?
        )
        ORDER BY posts.post_date DESC
    """, (user_id,)).fetchall()

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
            'post_id': row[7],
            'category_name': 'スキル',
            'like_count': row[8] if row[8] else 0
        })
    return render_template('like_page.html', posts=posts_list)