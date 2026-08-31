import os
import json  
from datetime import datetime
from flask import Blueprint, render_template, redirect, session, request, jsonify
from werkzeug.utils import secure_filename
from routes.auth import get_db

posts = Blueprint('posts', __name__)


def fetch_posts(db, category_id="", post_type="", search_query="", sort_type="new", grade="", department="", user_id=None):

    conditions = []
    params = []  

    if category_id:
        conditions.append("posts.category_id = ?")
        params.append(category_id)

    if post_type:
        conditions.append("posts.post_type = ?")
        params.append(post_type)

    if grade:
        conditions.append("users.grade = ?")
        params.append(grade)

    if department:
        conditions.append("users.department = ?")
        params.append(department)

    if search_query:
        conditions.append("(skills.skill_name LIKE ? OR users.department LIKE ? OR users.grade LIKE ?)")
        search_pattern = f"%{search_query}%"
        params.extend([search_pattern, search_pattern, search_pattern])

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    if sort_type == 'popular':
        order_by = "ORDER BY like_count DESC, posts.post_date DESC"
    else:
        order_by = "ORDER BY posts.post_date DESC"

    query = f"""
        SELECT
            users.name,
            users.department,
            users.grade,
            users.icon_path,
            categories.category_name,
            skills.skill_name,
            posts.post_type, posts.post_text, posts.post_id,
            (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.post_id) AS like_count,
            (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.post_id AND likes.user_id = ?) AS liked_by_me
        FROM posts
        JOIN users ON posts.user_id = users.user_id
        JOIN skills ON posts.skill_id = skills.skill_id
        JOIN categories ON posts.category_id = categories.category_id
        {where_clause}
        {order_by}
    """

    rows = db.execute(query, [user_id] + params).fetchall()

    posts_list = []
    for row in rows:
        posts_list.append({
            'name': row[0],
            'department': row[1],
            'grade': row[2],
            'icon_path': row[3] if row[3] else 'img/default-avatar.png',
            'category_name': row[4],
            'skill_name': row[5],
            'post_type': row[6],
            'post_text': row[7],
            'post_id': row[8],
            'like_count': row[9] if row[9] else 0,
            'liked_by_me': bool(row[10])
        })

    return posts_list


@posts.route("/")
def top():
    if 'user_email' not in session:
        return redirect('/login')

    db = get_db()
    user_id = session.get('user_id')
    sort_type = request.args.get('sort', 'new')
    selected_category = request.args.get('category', '')
    selected_grade = request.args.get('grade', '')
    selected_department = request.args.get('department', '')
    search_query = request.args.get('query', '')

    category_data = db.execute("SELECT * FROM categories").fetchall()
    grade_data = db.execute("SELECT DISTINCT grade FROM users WHERE grade IS NOT NULL AND grade != ''").fetchall()
    department_data = db.execute("SELECT DISTINCT department FROM users WHERE department IS NOT NULL AND department != ''").fetchall()

    posts_list = fetch_posts(
        db,
        category_id=selected_category,
        grade=selected_grade,
        department=selected_department,
        search_query=search_query,
        sort_type=sort_type,
        user_id=user_id
    )

    return render_template(
        'top.html',
        posts=posts_list,
        active_tab='all',
        active_sort=sort_type,
        categories=category_data,
        grades=grade_data,
        selected_grade=selected_grade,
        selected_category=selected_category,
        departments=department_data,
        selected_department=selected_department,
        search_query=search_query
    )


@posts.route("/top/learn")
def top_learn():
    if 'user_email' not in session:
        return redirect('/login')

    db = get_db()
    user_id = session.get('user_id')
    sort_type = request.args.get('sort', 'new')
    selected_category = request.args.get('category', '')
    selected_grade = request.args.get('grade', '')
    selected_department = request.args.get('department', '')
    search_query = request.args.get('query', '')

    category_data = db.execute("SELECT * FROM categories").fetchall()
    grade_data = db.execute("SELECT DISTINCT grade FROM users WHERE grade IS NOT NULL AND grade != ''").fetchall()
    department_data = db.execute("SELECT DISTINCT department FROM users WHERE department IS NOT NULL AND department != ''").fetchall()

    posts_list = fetch_posts(
        db,
        category_id=selected_category,
        post_type='学びたい',
        grade=selected_grade,
        department=selected_department,
        search_query=search_query,
        sort_type=sort_type,
        user_id=user_id
    )

    return render_template(
        'top.html',
        posts=posts_list,
        active_tab='learn',
        active_sort=sort_type,
        categories=category_data,
        selected_category=selected_category,
        grades=grade_data,
        selected_grade=selected_grade,
        departments=department_data,
        selected_department=selected_department,
        search_query=search_query
    )


@posts.route("/top/teach")
def top_teach():
    if 'user_email' not in session:
        return redirect('/login')

    db = get_db()
    user_id = session.get('user_id')
    sort_type = request.args.get('sort', 'new')
    selected_category = request.args.get('category', '')
    selected_grade = request.args.get('grade', '')
    selected_department = request.args.get('department', '')
    search_query = request.args.get('query', '')

    category_data = db.execute("SELECT * FROM categories").fetchall()
    grade_data = db.execute("SELECT DISTINCT grade FROM users WHERE grade IS NOT NULL AND grade != ''").fetchall()
    department_data = db.execute("SELECT DISTINCT department FROM users WHERE department IS NOT NULL AND department != ''").fetchall()

    posts_list = fetch_posts(
        db,
        category_id=selected_category,
        post_type='教えたい',
        grade=selected_grade,
        department=selected_department,
        search_query=search_query,
        sort_type=sort_type,
        user_id=user_id
    )

    return render_template(
        'top.html',
        posts=posts_list,
        active_tab='teach',
        active_sort=sort_type,
        categories=category_data,
        selected_category=selected_category,
        grades=grade_data,
        selected_grade=selected_grade,
        departments=department_data,
        selected_department=selected_department,
        search_query=search_query
    )


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
        introduction = request.form.get('bio') or request.form.get('introduction', '')

        if not name:
            return jsonify({'message': '名前を入力してください'}), 400

        teach_skills_json = request.form.get('teachSkills', '[]')
        learn_skills_json = request.form.get('learnSkills', '[]')

        try:
            teach_skill_names = json.loads(teach_skills_json)
            learn_skill_names = json.loads(learn_skills_json)
        except json.JSONDecodeError:
            teach_skill_names = []
            learn_skill_names = []

        def sync_skills(post_type, skill_names):
            current_rows = db.execute("""
                SELECT skills.skill_id, skills.skill_name
                FROM posts JOIN skills ON posts.skill_id = skills.skill_id
                WHERE posts.user_id = ? AND posts.post_type = ?
            """, (user_id, post_type)).fetchall()
            current_names = {row[1]: row[0] for row in current_rows}

            for name_ in skill_names:
                if name_ not in current_names:
                    skill_row = db.execute("SELECT skill_id, category_id FROM skills WHERE skill_name = ?", (name_,)).fetchone()
                    if skill_row:
                        skill_id = skill_row[0]
                        skill_category_id = skill_row[1]
                        db.execute(
                            "INSERT INTO posts (user_id, skill_id, post_type, post_text, post_date, category_id) VALUES (?, ?, ?, ?, ?, ?)",
                            (user_id, skill_id, post_type, '', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), skill_category_id)
                        )

            for name_, skill_id in current_names.items():
                if name_ not in skill_names:
                    db.execute(
                        "DELETE FROM posts WHERE user_id = ? AND skill_id = ? AND post_type = ?",
                        (user_id, skill_id, post_type)
                    )

        sync_skills('教えたい', teach_skill_names)
        sync_skills('学びたい', learn_skill_names)

        icon_path = None
        avatar_file = request.files.get('avatar') or request.files.get('icon')
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

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'message': 'プロフィールを保存しました'}), 200
        else:
            return redirect('/profile')

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

    review_stats = db.execute("""
        SELECT AVG(rating) AS avg_rating, COUNT(*) AS review_count
        FROM reviews WHERE reviewee_id = ?
    """, (user_id,)).fetchone()

    learn_rows = db.execute("""
        SELECT DISTINCT skills.skill_id, skills.skill_name 
        FROM posts
        JOIN skills ON posts.skill_id = skills.skill_id
        WHERE posts.user_id = ? AND posts.post_type = '学びたい'
    """, (user_id,)).fetchall()
    skills_learn = [{'skill_id': r[0], 'skill_name': r[1]} for r in learn_rows]

    my_posts_rows = db.execute("""
        SELECT
            categories.category_name,
            skills.skill_name,
            posts.post_type, posts.post_text, posts.post_id,
            (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.post_id) AS like_count,
            (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.post_id AND likes.user_id = ?) AS liked_by_me
        FROM posts
        JOIN skills ON posts.skill_id = skills.skill_id
        JOIN categories ON posts.category_id = categories.category_id
        WHERE posts.user_id = ?
        ORDER BY posts.post_date DESC
    """, (user_id, user_id)).fetchall()

    my_posts = []
    for row in my_posts_rows:
        my_posts.append({
            'category_name': row[0],
            'skill_name': row[1],
            'post_type': row[2],
            'post_text': row[3],
            'post_id': row[4],
            'like_count': row[5] if row[5] else 0,
            'liked_by_me': bool(row[6])
        })

    return render_template('profile.html', user=user, skills_teach=skills_teach, skills_learn=skills_learn, my_posts=my_posts, review_stats=review_stats)


@posts.route("/profile_edit", methods=['GET', 'POST'])
def profile_edit():
    if 'user_email' not in session:
        return redirect('/login')

    user_email = session['user_email']
    user_id = session.get('user_id')
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

    teach_rows = db.execute("""
        SELECT DISTINCT skills.skill_id, skills.skill_name 
        FROM posts
        JOIN skills ON posts.skill_id = skills.skill_id
        WHERE posts.user_id = ? AND posts.post_type = '教えたい'
    """, (user_id,)).fetchall()
    teach_skills = [{'skill_id': r[0], 'skill_name': r[1]} for r in teach_rows]

    learn_rows = db.execute("""
        SELECT DISTINCT skills.skill_id, skills.skill_name 
        FROM posts
        JOIN skills ON posts.skill_id = skills.skill_id
        WHERE posts.user_id = ? AND posts.post_type = '学びたい'
    """, (user_id,)).fetchall()
    learn_skills = [{'skill_id': r[0], 'skill_name': r[1]} for r in learn_rows]

    return render_template('profile_edit.html', user=user, teach_skills=teach_skills, learn_skills=learn_skills)


@posts.route("/posts", methods=['GET', 'POST'])
def create_post():
    db = get_db()
    if 'user_email' not in session:
        return redirect('/login')

    if request.method == 'POST':
        skill_id = request.form.get('skill_id', '')
        post_type = request.form.get('post_type', '')
        post_text = request.form.get('post_text', '')
        category_id = request.form.get('category_id', '')

        if not skill_id or not post_type or not post_text or not category_id:
            return "すべてのフィールドを入力してください", 400

        user_id = session.get('user_id')

        if user_id and skill_id and category_id:
            post_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            db.execute(
                "INSERT INTO posts (user_id, skill_id, post_type, post_text, post_date, category_id) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, skill_id, post_type, post_text, post_date, category_id)
            )
            db.commit()
            return redirect('/')

    preset_type = request.args.get('type', '')

    # カテゴリ一覧の取得と整形
    raw_categories = db.execute("SELECT category_id, category_name FROM categories ORDER BY category_id").fetchall()
    categories = []
    seen_cat_names = set()
    for c in raw_categories:
        try:
            c_id = c['category_id']
            c_name = c['category_name']
        except (TypeError, IndexError):
            c_id = c[0]
            c_name = c[1]

        if c_name and c_name not in seen_cat_names:
            seen_cat_names.add(c_name)
            categories.append({
                'category_id': c_id,
                'category_name': c_name
            })

    # スキル一覧の取得と整形
    raw_skills = db.execute("SELECT skill_id, skill_name, category_id FROM skills ORDER BY skill_id").fetchall()
    skills = []
    seen_skills = set()
    for s in raw_skills:
        try:
            s_id = s['skill_id']
            s_name = s['skill_name']
            s_cat_id = s['category_id']
        except (TypeError, IndexError):
            s_id = s[0]
            s_name = s[1]
            s_cat_id = s[2]

        key = (s_name, s_cat_id)
        if s_name and key not in seen_skills:
            seen_skills.add(key)
            skills.append({
                'skill_id': s_id,
                'skill_name': s_name,
                'category_id': s_cat_id if s_cat_id is not None else ""
            })

    return render_template('posts.html', categories=categories, skills=skills, preset_type=preset_type)


@posts.route("/posts/search", methods=['GET', 'POST'])
def search_posts():
    if 'user_email' not in session:
        return redirect('/login')

    db = get_db()
    user_id = session.get('user_id')
    search_query = request.args.get('query', '')

    if search_query:
        rows = db.execute("""
            SELECT
                users.name, users.department, users.grade, users.icon_path,
                categories.category_name,
                skills.skill_name,
                posts.post_type, posts.post_text, posts.post_id,
                (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.post_id) AS like_count,
                (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.post_id AND likes.user_id = ?) AS liked_by_me
            FROM posts
            JOIN users ON posts.user_id = users.user_id
            JOIN skills ON posts.skill_id = skills.skill_id
            JOIN categories ON posts.category_id = categories.category_id
            WHERE skills.skill_name LIKE ?
            OR users.department LIKE ?
            OR users.grade LIKE ?
            ORDER BY posts.post_date DESC
        """, (user_id, '%' + search_query + '%', '%' + search_query + '%', '%' + search_query + '%')).fetchall()

        posts_list = []
        for row in rows:
            posts_list.append({
                'name': row[0],
                'department': row[1],
                'grade': row[2],
                'icon_path': row[3] if row[3] else 'img/default-avatar.png',
                'category_name': row[4],
                'skill_name': row[5],
                'post_type': row[6],
                'post_text': row[7],
                'post_id': row[8],
                'like_count': row[9] if row[9] else 0,
                'liked_by_me': bool(row[10])
            })
        return render_template('top.html', posts=posts_list, active_tab='all', search_query=search_query)

    return redirect('/')


@posts.route("/posts/likes", methods=['POST'])
def like_post():
    if 'user_email' not in session:
        return jsonify({'error': 'unauthorized'}), 401

    post_id = request.form.get('post_id')
    user_id = session.get('user_id')
    if not post_id or not user_id:
        return jsonify({'error': 'invalid request'}), 400

    db = get_db()
    existing_like = db.execute(
        "SELECT 1 FROM likes WHERE user_id = ? AND post_id = ?", (user_id, post_id)
    ).fetchone()

    if existing_like:
        db.execute("DELETE FROM likes WHERE user_id = ? AND post_id = ?", (user_id, post_id))
        liked = False
    else:
        db.execute("INSERT INTO likes (user_id, post_id) VALUES (?, ?)", (user_id, post_id))
        liked = True

    db.commit()
    return jsonify({'liked': liked})


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
            categories.category_name,
            skills.skill_name,
            posts.post_type, posts.post_text, posts.post_id,
            (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.post_id) AS like_count,
            (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.post_id AND likes.user_id = ?) AS liked_by_me
        FROM posts
        JOIN users ON posts.user_id = users.user_id
        JOIN skills ON posts.skill_id = skills.skill_id
        JOIN categories ON posts.category_id = categories.category_id
        WHERE posts.post_id IN (
            SELECT likes.post_id FROM likes WHERE likes.user_id = ?
        )
        ORDER BY posts.post_date DESC
    """, (user_id, user_id)).fetchall()
    posts_list = []
    for row in rows:
        posts_list.append({
            'name': row[0],
            'department': row[1],
            'grade': row[2],
            'icon_path': row[3] if row[3] else 'img/default-avatar.png',
            'category_name': row[4],
            'skill_name': row[5],
            'post_type': row[6],
            'post_text': row[7],
            'post_id': row[8],
            'like_count': row[9] if row[9] else 0,
            'liked_by_me': bool(row[10])
        })
    return render_template('like_page.html', posts=posts_list)