# coding=utf-8
import sqlite3
import os
import sys
import datetime
import json
from flask import Flask, request, redirect, url_for, session, g, render_template, flash, get_flashed_messages
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# ====================================================================
# Flask App Setup & Configuration
# ====================================================================

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


# ====================================================================
# Database Setup
# ====================================================================

DATABASE = 'database.db'


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''
                   CREATE TABLE IF NOT EXISTS users
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       username
                       TEXT
                       UNIQUE
                       NOT
                       NULL,
                       password
                       TEXT
                       NOT
                       NULL,
                       is_admin
                       INTEGER
                       DEFAULT
                       0,
                       is_locked
                       INTEGER
                       DEFAULT
                       0,
                       expiry_date
                       TEXT,
                       post_count
                       INTEGER
                       DEFAULT
                       0,
                       accepted_count
                       INTEGER
                       DEFAULT
                       0,
                       last_rating
                       INTEGER,
                       UNIQUE
                   (
                       username
                   )
                       );
                   ''')
        db.execute('''
                   CREATE TABLE IF NOT EXISTS listings
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       user_id
                       INTEGER
                       NOT
                       NULL,
                       data
                       TEXT,
                       post_date
                       TEXT
                       NOT
                       NULL,
                       status
                       TEXT
                       NOT
                       NULL
                       DEFAULT
                       'open',
                       FOREIGN
                       KEY
                   (
                       user_id
                   ) REFERENCES users
                   (
                       id
                   )
                       );
                   ''')
        db.execute('''
                   CREATE TABLE IF NOT EXISTS settings
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       site_name
                       TEXT
                       DEFAULT
                       '通用网站平台',
                       registration_enabled
                       INTEGER
                       DEFAULT
                       1,
                       fields_definition
                       TEXT
                       DEFAULT
                       '[]'
                   );
                   ''')
        db.commit()

        cursor = db.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", ('admin',))
        admin_exists = cursor.fetchone()
        if not admin_exists:
            hashed_password = generate_password_hash('admin_password_123', method='pbkdf2:sha256:260000')
            db.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)",
                       ('admin', hashed_password, 1))
            db.commit()
            print("Super admin account 'admin' created with password 'admin_password_123'")

        cursor.execute("SELECT id FROM settings")
        settings_exist = cursor.fetchone()
        if not settings_exist:
            db.execute("INSERT INTO settings (site_name, registration_enabled, fields_definition) VALUES (?, ?, ?)",
                       ('通用网站平台', 1, json.dumps([
                           {"name": "field_name_1", "label": "字段1", "type": "text", "required": True},
                           {"name": "field_name_2", "label": "字段2", "type": "number", "required": False},
                           {"name": "field_name_3", "label": "字段3", "type": "textarea", "required": False}
                       ])))
            db.commit()
            print("Site settings initialized with registration enabled and default fields.")


init_db()


# ====================================================================
# HTML Templates
# ====================================================================

def get_settings():
    db = get_db()
    settings = db.execute('SELECT * FROM settings WHERE id = 1').fetchone()
    if settings:
        settings = dict(settings)
        settings['fields_definition'] = json.loads(settings['fields_definition'])
    return settings


# ====================================================================
# Flask Routes
# ====================================================================

@app.route('/')
def index():
    db = get_db()
    settings = get_settings()

    fields_definition = settings['fields_definition']
    fields_to_display = [f for f in fields_definition]
    fields_to_filter = [f for f in fields_to_display if f['type'] not in ['textarea', 'file']]

    query = "SELECT id, user_id, data, post_date, status FROM listings WHERE 1=1"
    params = []

    for field in fields_to_filter:
        filter_value = request.args.get(field['name'])
        if filter_value:
            query += f" AND json_extract(data, '$.{field['name']}') LIKE ?"
            params.append(f'%{filter_value}%')

    sort_by = request.args.get('sort')
    order = request.args.get('order', 'desc')

    if sort_by:
        query += f" ORDER BY json_extract(data, '$.{sort_by}') {order.upper()}"
    else:
        query += " ORDER BY post_date DESC"

    listings = db.execute(query, params).fetchall()

    listings_processed = []
    for listing in listings:
        listing = dict(listing)
        listing['data'] = json.loads(listing['data'])
        listings_processed.append(listing)

    return render_template('index.html',
                           listings=listings_processed,
                           fields_to_display=fields_to_display,
                           fields_to_filter=fields_to_filter,
                           settings=settings
                           )


@app.route('/register', methods=['GET', 'POST'])
def register():
    db = get_db()
    settings = get_settings()
    if not settings or not settings['registration_enabled']:
        flash("注册功能已关闭。", "error")
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cursor = db.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        user_exists = cursor.fetchone()

        if user_exists:
            flash("该用户名已被占用，请尝试其他用户名。", "error")
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256:260000')

        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            db.commit()
            flash("注册成功！请登录。", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("注册失败，请稍后重试。", "error")
            return redirect(url_for('register'))

    return render_template('register.html', settings=settings)


@app.route('/login', methods=['GET', 'POST'])
def login():
    settings = get_settings()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        cursor = db.cursor()

        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password'], password):
            if user['is_locked']:
                flash("您的账号已被锁定，请联系管理员。", "error")
                return redirect(url_for('login'))
            if user['expiry_date'] and datetime.datetime.now().strftime("%Y-%m-%d") > user['expiry_date']:
                flash("您的账号已过期，请联系管理员。", "error")
                return redirect(url_for('login'))

            session['username'] = user['username']
            session['user_id'] = user['id']
            session['is_admin'] = bool(user['is_admin'])

            return redirect(url_for('index'))
        else:
            flash("用户名或密码不正确。", "error")
            return redirect(url_for('login'))

    return render_template('login.html', settings=settings)


@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('user_id', None)
    session.pop('is_admin', None)
    return redirect(url_for('login'))


@app.route('/post_demand', methods=['GET', 'POST'])
def post_demand():
    if 'username' not in session:
        flash("请先登录以发布内容。", "error")
        return redirect(url_for('login'))

    settings = get_settings()
    fields = settings['fields_definition']

    if request.method == 'POST':
        user_id = session['user_id']
        post_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        listing_data = {}
        for field in fields:
            if field['type'] == 'file':
                file = request.files.get(field['name'])
                if field['required'] and (not file or file.filename == ''):
                    flash(f"字段 '{field['label']}' 是必填的。", "error")
                    return redirect(url_for('post_demand'))
                if file and allowed_file(file.filename):
                    filename = f"{user_id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(file.filename)}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    listing_data[field['name']] = filename
                else:
                    listing_data[field['name']] = None
            else:
                listing_data[field['name']] = request.form.get(field['name'])

        db = get_db()
        db.execute('INSERT INTO listings (user_id, data, post_date) VALUES (?, ?, ?)',
                   (user_id, json.dumps(listing_data), post_date))
        db.commit()

        flash("发布成功！", "success")
        return redirect(url_for('index'))

    return render_template('post_demand.html', fields=fields, settings=settings)


@app.route('/edit_demand/<int:demand_id>', methods=['GET', 'POST'])
def edit_demand(demand_id):
    if 'username' not in session:
        flash("请先登录。", "error")
        return redirect(url_for('login'))

    db = get_db()
    demand = db.execute('SELECT * FROM listings WHERE id = ?', (demand_id,)).fetchone()

    if not demand:
        flash("内容不存在。", "error")
        return redirect(url_for('index'))

    if not session.get('is_admin') and demand['user_id'] != session.get('user_id'):
        flash("您无权编辑此内容。", "error")
        return redirect(url_for('index'))

    if demand['status'] != 'open' and not session.get('is_admin'):
        flash("此内容已被接受，无法编辑。", "error")
        return redirect(url_for('index'))

    settings = get_settings()
    fields = settings['fields_definition']
    demand_data = json.loads(demand['data'])

    if request.method == 'POST':
        listing_data = {}
        for field in fields:
            if field['type'] == 'file':
                file = request.files.get(field['name'])
                if file and allowed_file(file.filename):
                    filename = f"{demand_id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(file.filename)}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    listing_data[field['name']] = filename
                else:
                    listing_data[field['name']] = demand_data.get(field['name'])
            else:
                listing_data[field['name']] = request.form.get(field['name'])

        db.execute('UPDATE listings SET data = ? WHERE id = ?',
                   (json.dumps(listing_data), demand_id))
        db.commit()
        flash("内容更新成功！", "success")
        return redirect(url_for('index'))

    return render_template('edit_demand.html', demand_data=demand_data, fields=fields, settings=settings)


@app.route('/delete_demand/<int:demand_id>', methods=['GET'])
def delete_demand(demand_id):
    if 'username' not in session:
        flash("请先登录。", "error")
        return redirect(url_for('login'))

    db = get_db()
    demand = db.execute('SELECT * FROM listings WHERE id = ?', (demand_id,)).fetchone()

    if not demand:
        flash("内容不存在。", "error")
        return redirect(url_for('index'))

    if not session.get('is_admin') and demand['user_id'] != session.get('user_id'):
        flash("您无权删除此内容。", "error")
        return redirect(url_for('index'))

    if demand['status'] != 'open' and not session.get('is_admin'):
        flash("此内容已被接受，无法删除。", "error")
        return redirect(url_for('index'))

    db.execute('DELETE FROM listings WHERE id = ?', (demand_id,))
    db.commit()
    flash("内容删除成功！", "success")
    return redirect(url_for('index'))


@app.route('/view_details/<int:demand_id>')
def view_details(demand_id):
    db = get_db()
    demand = db.execute('SELECT * FROM listings WHERE id = ?', (demand_id,)).fetchone()

    if not demand:
        flash("内容不存在。", "error")
        return redirect(url_for('index'))

    demand_data = json.loads(demand['data'])
    settings = get_settings()
    fields = settings['fields_definition']

    return render_template('view_details.html', demand=demand, demand_data=demand_data, fields=fields,
                           settings=settings)


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/admin_panel', methods=['GET', 'POST'])
def admin_panel():
    if not session.get('is_admin'):
        flash("您无权访问此页面。", "error")
        return redirect(url_for('index'))

    db = get_db()
    users = db.execute('SELECT * FROM users').fetchall()
    settings = get_settings()

    return render_template('admin.html', users=users, settings=settings)


@app.route('/admin/set_site_name', methods=['POST'])
def set_site_name():
    if not session.get('is_admin'):
        flash("您无权执行此操作。", "error")
        return redirect(url_for('index'))

    site_name = request.form['site_name']
    if not site_name:
        flash("网站名称不能为空。", "error")
        return redirect(url_for('admin_panel'))

    db = get_db()
    db.execute('UPDATE settings SET site_name = ? WHERE id = 1', (site_name,))
    db.commit()

    flash(f"网站名称已更新为 '{site_name}'。", "success")
    return redirect(url_for('admin_panel'))


@app.route('/admin/toggle_registration', methods=['POST'])
def toggle_registration():
    if not session.get('is_admin'):
        flash("您无权执行此操作。", "error")
        return redirect(url_for('index'))

    db = get_db()
    settings = get_settings()

    new_status = 1 if not settings or not settings['registration_enabled'] else 0
    db.execute('UPDATE settings SET registration_enabled = ? WHERE id = 1', (new_status,))
    db.commit()

    flash(f"注册功能已{'开启' if new_status else '关闭'}。", "success")
    return redirect(url_for('admin_panel'))


@app.route('/admin/toggle_lock/<int:user_id>')
def toggle_lock(user_id):
    if not session.get('is_admin'):
        flash("您无权执行此操作。", "error")
        return redirect(url_for('index'))

    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user or user['is_admin']:
        flash("无效用户或无法锁定管理员账号。", "error")
        return redirect(url_for('admin_panel'))

    new_status = 0 if user['is_locked'] else 1
    db.execute('UPDATE users SET is_locked = ? WHERE id = ?', (new_status, user_id))
    db.commit()

    flash(f"用户 {user['username']} 账号已{'解锁' if user['is_locked'] else '锁定'}。", "success")
    return redirect(url_for('admin_panel'))


@app.route('/admin/set_expiry/<int:user_id>', methods=['POST'])
def set_expiry(user_id):
    if not session.get('is_admin'):
        flash("您无权执行此操作。", "error")
        return redirect(url_for('index'))

    expiry_date = request.form['expiry_date']
    if not expiry_date:
        flash("请选择有效的日期。", "error")
        return redirect(url_for('admin_panel'))

    db = get_db()
    db.execute('UPDATE users SET expiry_date = ? WHERE id = ?', (expiry_date, user_id))
    db.commit()

    flash(f"用户有效期已设置为 {expiry_date}。", "success")
    return redirect(url_for('admin_panel'))


@app.route('/admin/delete_user/<int:user_id>')
def delete_user(user_id):
    if not session.get('is_admin'):
        flash("您无权执行此操作。", "error")
        return redirect(url_for('index'))

    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user or user['is_admin']:
        flash("无效用户或无法删除管理员账号。", "error")
        return redirect(url_for('admin_panel'))

    db.execute('DELETE FROM users WHERE id = ?', (user_id,))
    db.commit()

    flash(f"用户 {user['username']} 已被删除。", "success")
    return redirect(url_for('admin_panel'))


@app.route('/admin/update_fields', methods=['POST'])
def update_fields():
    if not session.get('is_admin'):
        flash("您无权执行此操作。", "error")
        return redirect(url_for('index'))

    new_fields = []
    i = 0
    while True:
        field_name = request.form.get(f'field_name_{i}')
        if not field_name:
            break

        field_label = request.form.get(f'field_label_{i}')
        field_type = request.form.get(f'field_type_{i}')
        field_required = request.form.get(f'field_required_{i}') == 'on'

        new_fields.append({
            "name": field_name,
            "label": field_label,
            "type": field_type,
            "required": field_required
        })
        i += 1

    db = get_db()
    db.execute('UPDATE settings SET fields_definition = ? WHERE id = 1', (json.dumps(new_fields),))
    db.commit()

    flash("动态字段已更新！", "success")
    return redirect(url_for('admin_panel'))


# ====================================================================
# Main entry point
# ====================================================================

if __name__ == '__main__':
    app.run(debug=True)
