import os
import json  
import uuid
from datetime import datetime
from flask import Blueprint, render_template, redirect, session, request, jsonify, flash
from werkzeug.utils import secure_filename
from routes.auth import get_db
from routes.projects import fetch_projects

posts = Blueprint('posts', __name__)

# 添付ファイル（画像・PDF）の保存フォルダと許可する拡張子設定
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


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
            (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.post_id AND likes.user_id = ?) AS liked_by_me,
            posts.image_path,
            users.user_id
        FROM posts
        LEFT JOIN users ON posts.user_id = users.user_id
        LEFT JOIN skills ON posts.skill_id = skills.skill_id
        LEFT JOIN categories ON posts.category_id = categories.category_id
        {where_clause}
        {order_by}
    """

    rows = db.execute(query, [user_id] + params).fetchall()

    posts_list = []
    for row in rows:
        posts_list.append({
            'name': row[0] if row[0] else 'ユーザー',
            'department': row[1] if row[1] else '',
            'grade': row[2] if row[2] else '',
            'icon_path': row[3] if row[3] else 'test.png',
            'category_name': row[4] if row[4] else '未設定',
            'skill_name': row[5] if row[5] else '未設定',
            'post_type': row[6],
            'post_text': row[7],
            'post_id': row[8],
            'like_count': row[9] if row[9] else 0,
            'liked_by_me': bool(row[10]),
            'image_path': row[11],
            'user_id': row[12]
        })

    return posts_list

@posts.route("/")
def top():
    if 'user_email' not in session:
        return redirect('/login')

    db = get_db()
    user_id = session.get('user_id')

    # おすすめユーザーの取得
    recommended_users = fetch_recommended_users(db, user_id)

    sort_type = request.args.get('sort', 'new')
    selected_category = request.args.get('category', '')
    selected_grade = request.args.get('grade', '')
    selected_department = request.args.get('department', '')
    search_query = request.args.get('query', '')

    category_data = db.execute("SELECT MIN(category_id) AS category_id, category_name FROM categories GROUP BY category_name ORDER BY category_id").fetchall()
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
    for p in posts_list:
        p['card_type'] = 'skill'

    projects_list = fetch_projects(db, user_id=user_id)

    combined = projects_list + posts_list if sort_type != 'popular' else posts_list + projects_list

    return render_template(
        'top.html',
        recommended_users=recommended_users,
        posts=combined,
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

    recommended_users = fetch_recommended_users(db, user_id)

    return render_template(
        'top.html',
        posts=posts_list,
        recommended_users=recommended_users,
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
                        
                        # 同一スキル・タイプの既存投稿がないかダブルチェック
                        check_exist = db.execute(
                            "SELECT 1 FROM posts WHERE user_id = ? AND skill_id = ? AND post_type = ?",
                            (user_id, skill_id, post_type)
                        ).fetchone()
                        
                        if not check_exist:
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
            ext = os.path.splitext(avatar_file.filename)[1].lower()
            # プロフィールアイコンは画像のみ許容（PDF除外）
            if ext not in {'.png', '.jpg', '.jpeg', '.gif', '.webp'}:
                return jsonify({'message': '対応していない画像形式です'}), 400

            filename = secure_filename(f"user_{user_id}{ext}")
            save_path = os.path.join(UPLOAD_FOLDER, filename)
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
            (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.post_id AND likes.user_id = ?) AS liked_by_me,
            posts.image_path
        FROM posts
        LEFT JOIN skills ON posts.skill_id = skills.skill_id
        LEFT JOIN categories ON posts.category_id = categories.category_id
        WHERE posts.user_id = ?
        ORDER BY posts.post_date DESC
    """, (user_id, user_id)).fetchall()

    my_posts = []
    for row in my_posts_rows:
        my_posts.append({
            'category_name': row[0] if row[0] else '未設定',
            'skill_name': row[1] if row[1] else '未設定',
            'post_type': row[2],
            'post_text': row[3],
            'post_id': row[4],
            'like_count': row[5] if row[5] else 0,
            'liked_by_me': bool(row[6]),
            'image_path': row[7]
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

@posts.route("/posts/<int:post_id>/delete", methods=['POST'])
def delete_post(post_id):
    if 'user_email' not in session:
        return redirect('/login')

    user_id = session.get('user_id')
    db = get_db()

    post = db.execute("SELECT * FROM posts WHERE post_id = ?", (post_id,)).fetchone()
    if not post:
        flash("対象の投稿が見つかりません。", "error")
        return redirect('/profile')

    if post['user_id'] != user_id:
        flash("この投稿を削除する権限がありません。", "error")
        return redirect('/profile')

    active_request = db.execute(
        "SELECT 1 FROM requests WHERE post_id = ? AND status IN ('pending', 'accepted')",
        (post_id,)
    ).fetchone()

    if active_request:
        flash("進行中のリクエストがあるため、この投稿は削除できません。", "error")
        return redirect('/profile')

    db.execute("DELETE FROM likes WHERE post_id = ?", (post_id,))
    db.execute("DELETE FROM posts WHERE post_id = ?", (post_id,))
    db.commit()

    flash("投稿を削除しました。", "success")
    return redirect('/profile')


@posts.route("/posts/<int:post_id>/edit", methods=['GET', 'POST'])
def edit_post(post_id):
    if 'user_email' not in session:
        return redirect('/login')

    user_id = session.get('user_id')
    db = get_db()

    post = db.execute("SELECT * FROM posts WHERE post_id = ?", (post_id,)).fetchone()
    if not post:
        flash("対象の投稿が見つかりません。", "error")
        return redirect('/profile')

    if post['user_id'] != user_id:
        flash("この投稿を編集する権限がありません。", "error")
        return redirect('/profile')

    if request.method == 'POST':
        post_type = request.form.get('post_type', '')
        category_id = request.form.get('category_id', '')
        skill_id = request.form.get('skill_id', '')
        post_text = request.form.get('post_text', '')

        if not skill_id or not post_type or not post_text or not category_id:
            flash("すべてのフィールドを入力してください。", "error")
            return redirect(f'/posts/{post_id}/edit')

        # 自分の他の投稿と同じスキル・タイプで重複していないかチェック（自分自身は除外）
        dup = db.execute("""
            SELECT post_id FROM posts
            WHERE user_id = ? AND skill_id = ? AND post_type = ? AND post_id != ?
        """, (user_id, int(skill_id), post_type, post_id)).fetchone()
        if dup:
            flash("このスキルに関する投稿はすでに存在します。（1つのスキルにつき1つまで）", "error")
            return redirect(f'/posts/{post_id}/edit')

        image_path = post['image_path']
        post_file = request.files.get('post_image')
        if post_file and post_file.filename != '':
            ext = os.path.splitext(post_file.filename)[1].lower()
            if ext in ALLOWED_EXTENSIONS:
                filename = secure_filename(f"post_{uuid.uuid4().hex}{ext}")
                save_path = os.path.join(UPLOAD_FOLDER, filename)
                post_file.save(save_path)
                image_path = f"uploads/{filename}"
            else:
                flash("許可されていないファイル形式です（PNG, JPEG, PDFのみ対応）。", "error")
                return redirect(f'/posts/{post_id}/edit')

        db.execute(
            "UPDATE posts SET post_type = ?, category_id = ?, skill_id = ?, post_text = ?, image_path = ? WHERE post_id = ?",
            (post_type, int(category_id), int(skill_id), post_text, image_path, post_id)
        )
        db.commit()
        flash("投稿を更新しました。", "success")
        return redirect('/profile')

    # GET: 編集フォームの初期値を準備
    raw_categories = db.execute("SELECT category_id, category_name FROM categories ORDER BY category_id").fetchall()
    categories = []
    seen_cat_names = set()
    for c in raw_categories:
        if c['category_name'] and c['category_name'] not in seen_cat_names:
            seen_cat_names.add(c['category_name'])
            categories.append({'category_id': c['category_id'], 'category_name': c['category_name']})

    raw_skills = db.execute("SELECT skill_id, skill_name, category_id FROM skills ORDER BY skill_id").fetchall()
    skills = []
    seen_skills = set()
    for s in raw_skills:
        key = (s['skill_name'], s['category_id'])
        if s['skill_name'] and key not in seen_skills:
            seen_skills.add(key)
            skills.append({
                'skill_id': s['skill_id'],
                'skill_name': s['skill_name'],
                'category_id': s['category_id'] if s['category_id'] is not None else ""
            })

    return render_template('posts.html', categories=categories, skills=skills, preset_type=post['post_type'], edit_post=post)

@posts.route("/posts", methods=['GET', 'POST'])
def create_post():
    db = get_db()
    if 'user_email' not in session:
        return redirect('/login')

    user_id = session.get('user_id')

    if request.method == 'POST':
        post_type = request.form.get('post_type') or request.form.get('type', '')
        category_id = request.form.get('category_id') or request.form.get('category', '')
        skill_id = request.form.get('skill_id') or request.form.get('skill', '')
        post_text = request.form.get('post_text') or request.form.get('content', '')

        if not skill_id or not post_type or not post_text or not category_id:
            return f"すべてのフィールドを入力してください。(type:{post_type}, cat:{category_id}, skill:{skill_id}, text:{post_text})", 400

        # 同じユーザーが同じスキル・タイプで既に投稿していないかチェック
        existing_post = db.execute("""
            SELECT post_id FROM posts 
            WHERE user_id = ? AND skill_id = ? AND post_type = ?
        """, (int(user_id), int(skill_id), post_type)).fetchone()

        if existing_post:
            flash("このスキルに関する投稿はすでに作成されています。（1つのスキルにつき1つまで）")
            return redirect('/posts')

        # 添付ファイル（画像・PDF）のアップロード処理
        # 添付ファイル（画像・PDF）のアップロード処理
        image_path = None
        post_file = request.files.get('post_image')
        if post_file and post_file.filename != '':
            ext = os.path.splitext(post_file.filename)[1].lower()
            if ext in ALLOWED_EXTENSIONS:
                filename = secure_filename(f"post_{uuid.uuid4().hex}{ext}")
                save_path = os.path.join(UPLOAD_FOLDER, filename)
                post_file.save(save_path)
                image_path = f"uploads/{filename}"
            else:
                flash("許可されていないファイル形式です。添付できるのは画像（PNG, JPG, GIF, WEBP）または PDF のみです。")
                return redirect('/posts')

        if user_id:
            post_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            db.execute(
                "INSERT INTO posts (user_id, skill_id, post_type, post_text, image_path, post_date, category_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (int(user_id), int(skill_id), post_type, post_text, image_path, post_date, int(category_id))
            )
            db.commit()
            return redirect('/')

    preset_type = request.args.get('type', '')

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
                (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.post_id AND likes.user_id = ?) AS liked_by_me,
                posts.image_path,
                users.user_id
            FROM posts
            LEFT JOIN users ON posts.user_id = users.user_id
            LEFT JOIN skills ON posts.skill_id = skills.skill_id
            LEFT JOIN categories ON posts.category_id = categories.category_id
            WHERE skills.skill_name LIKE ?
            OR users.department LIKE ?
            OR users.grade LIKE ?
            ORDER BY posts.post_date DESC
        """, (user_id, '%' + search_query + '%', '%' + search_query + '%', '%' + search_query + '%')).fetchall()

        posts_list = []
        for row in rows:
            posts_list.append({
                'name': row[0] if row[0] else 'ユーザー',
                'department': row[1] if row[1] else '',
                'grade': row[2] if row[2] else '',
                'icon_path': row[3] if row[3] else 'test.png',
                'category_name': row[4] if row[4] else '未設定',
                'skill_name': row[5] if row[5] else '未設定',
                'post_type': row[6],
                'post_text': row[7],
                'post_id': row[8],
                'like_count': row[9] if row[9] else 0,
                'liked_by_me': bool(row[10]),
                'image_path': row[11],
                'user_id': row[12]
            })
        return render_template('top.html', posts=posts_list, active_tab='all', search_query=search_query)

    return redirect('/')

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
            (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.post_id AND likes.user_id = ?) AS liked_by_me,
            posts.image_path,
            users.user_id
        FROM posts
        LEFT JOIN users ON posts.user_id = users.user_id
        LEFT JOIN skills ON posts.skill_id = skills.skill_id
        LEFT JOIN categories ON posts.category_id = categories.category_id
        WHERE posts.post_id IN (
            SELECT likes.post_id FROM likes WHERE likes.user_id = ?
        )
        ORDER BY posts.post_date DESC
    """, (user_id, user_id)).fetchall()

    posts_list = []
    for row in rows:
        posts_list.append({
            'name': row[0] if row[0] else 'ユーザー',
            'department': row[1] if row[1] else '',
            'grade': row[2] if row[2] else '',
            'icon_path': row[3] if row[3] else 'test.png',
            'category_name': row[4] if row[4] else '未設定',
            'skill_name': row[5] if row[5] else '未設定',
            'post_type': row[6],
            'post_text': row[7],
            'post_id': row[8],
            'like_count': row[9] if row[9] else 0,
            'liked_by_me': bool(row[10]),
            'image_path': row[11],
            'user_id': row[12]
        })
    return render_template('like_page.html', posts=posts_list)


@posts.route("/users/<int:user_id>")
def other_profile(user_id):
    if 'user_email' not in session:
        return redirect('/login')

    my_user_id = session.get('user_id')

    # 自分自身の場合は自分のプロフィールへ
    if user_id == my_user_id:
        return redirect('/profile')

    # データベース接続（SQLite）
    db = get_db()

    # ユーザー情報の取得
    user_row = db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()

    if not user_row:
        return "ユーザーが見つかりません", 404

    # fetchone() の結果を辞書形式に変換
    user = dict(user_row) if user_row else None

    # 教える/学ぶスキルの取得（posts テーブル経由）
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

    # ★ 【修正箇所】相手の投稿一覧の取得（いいね数と自分がいいね済みかのフラグを結合）
    user_posts_rows = db.execute("""
        SELECT 
            p.*, 
            c.category_name, 
            s.skill_name,
            COALESCE(l.like_count, 0) AS like_count,
            CASE WHEN my_l.post_id IS NOT NULL THEN 1 ELSE 0 END AS liked_by_me
        FROM posts p
        LEFT JOIN categories c ON p.category_id = c.category_id
        LEFT JOIN skills s ON p.skill_id = s.skill_id
        -- 各投稿のいいね合計数を集計して結合
        LEFT JOIN (
            SELECT post_id, COUNT(*) AS like_count 
            FROM likes 
            GROUP BY post_id
        ) l ON p.post_id = l.post_id
        -- ログイン中の自分がいいねしているか判定するために結合
        LEFT JOIN likes my_l ON p.post_id = my_l.post_id AND my_l.user_id = ?
        WHERE p.user_id = ?
        ORDER BY p.post_date DESC
    """, (my_user_id, user_id)).fetchall()
    
    user_posts = [dict(row) for row in user_posts_rows]

    # 評価（平均値と件数）の取得
    review_stats = db.execute("""
        SELECT AVG(rating) AS avg_rating, COUNT(*) AS review_count 
        FROM reviews 
        WHERE reviewee_id = ?
    """, (user_id,)).fetchone()

    # 評価コメント（レビュー本文一覧）の取得
    reviews_rows = db.execute("""
        SELECT r.rating, r.comment, r.created_at, u.name AS reviewer_name
        FROM reviews r
        JOIN users u ON r.reviewer_id = u.user_id
        WHERE r.reviewee_id = ?
        ORDER BY r.created_at DESC
    """, (user_id,)).fetchall()
    reviews = [dict(row) for row in reviews_rows]

    return render_template(
        'other_profile.html',
        user=user,
        skills_teach=skills_teach,
        skills_learn=skills_learn,
        user_posts=user_posts,
        review_stats=review_stats,
        reviews=reviews
    )

# --- ★ 追加: おすすめユーザー取得用の共通関数 ---
def fetch_recommended_users(db, current_user_id):
    if not current_user_id:
        return []

    # 1. 自分が投稿した「学びたい」スキルIDを『すべて』取得
    skills_rows = db.execute("""
        SELECT DISTINCT skill_id 
        FROM posts 
        WHERE user_id = ? AND post_type = '学びたい' AND skill_id IS NOT NULL AND skill_id != ''
    """, (current_user_id,)).fetchall()

    my_learn_skills = [row['skill_id'] if isinstance(row, dict) else row[0] for row in skills_rows]

    if not my_learn_skills:
        return []

    placeholders = ','.join(['?'] * len(my_learn_skills))

    sql = f"""
        SELECT DISTINCT
            u.user_id,
            u.name,
            u.department,
            u.grade,
            u.icon_path,
            s.skill_name AS matched_skill
        FROM posts p
        JOIN users u ON p.user_id = u.user_id
        JOIN skills s ON p.skill_id = s.skill_id
        WHERE p.post_type = '教えたい'
          AND p.skill_id IN ({placeholders})
          AND p.user_id != ?
        LIMIT 5
    """

    params = tuple(my_learn_skills) + (current_user_id,)
    
    recommended_users = db.execute(sql, params).fetchall()
    return recommended_users

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

    recommended_users = fetch_recommended_users(db, user_id)

    return render_template(
        'top.html',
        posts=posts_list,
        recommended_users=recommended_users,
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
@posts.route("/like/<int:post_id>", methods=["POST"])
def like_post(post_id):
    if 'user_email' not in session:
        return jsonify({
            "success": False,
            "message": "ログインしてください"
        }), 401

    user_id = session.get('user_id')
    db = get_db()

    # 投稿が存在するか確認
    post = db.execute(
        "SELECT post_id FROM posts WHERE post_id = ?",
        (post_id,)
    ).fetchone()

    if not post:
        return jsonify({
            "success": False,
            "message": "投稿が見つかりません"
        }), 404

    # すでにいいねしているか確認
    like = db.execute(
        """
        SELECT 1
        FROM likes
        WHERE post_id = ? AND user_id = ?
        """,
        (post_id, user_id)
    ).fetchone()

    if like:
        # いいね解除
        db.execute(
            """
            DELETE FROM likes
            WHERE post_id = ? AND user_id = ?
            """,
            (post_id, user_id)
        )
        is_liked = False

    else:
        # いいね追加
        db.execute(
            """
            INSERT INTO likes (post_id, user_id)
            VALUES (?, ?)
            """,
            (post_id, user_id)
        )
        is_liked = True

    db.commit()

    # いいね数を取得
    like_count = db.execute(
        """
        SELECT COUNT(*)
        FROM likes
        WHERE post_id = ?
        """,
        (post_id,)
    ).fetchone()[0]

    return jsonify({
        "success": True,
        "post_id": post_id,
        "like_count": like_count,
        "is_liked": is_liked
    })   

@posts.route("/posts/likes", methods=["POST"])
def like_post_alias():
    post_id = request.form.get('post_id') or (request.get_json(silent=True) or {}).get('post_id')
    if not post_id:
        return jsonify({"success": False, "message": "post_idが必要です"}), 400
    return like_post(int(post_id))