# coding=utf-8
import sqlite3
import os
import sys
import datetime
from flask import Flask, request, redirect, url_for, session, g, render_template_string, flash, get_flashed_messages
from werkzeug.security import generate_password_hash, check_password_hash

# ====================================================================
# Flask App Setup & Configuration
# ====================================================================

app = Flask(__name__)
# A secret key is required for session management.
app.secret_key = 'your_secret_key_here'

# ====================================================================
# Database Setup
# ====================================================================

DATABASE = 'database.db'


def get_db():
    """Establishes a connection to the database."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    """Closes the database connection at the end of the request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db():
    """Initializes the database schema with users and demands tables.

    IMPORTANT: If you have updated the schema (e.g., added a new column),
    you must delete the existing 'database.db' file to apply the changes.
    """
    with app.app_context():
        db = get_db()
        # Create a users table if it does not exist.
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0
            );
        ''')
        # Create a demands table for overseas users' needs.
        db.execute('''
            CREATE TABLE IF NOT EXISTS demands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                description TEXT,
                weight REAL,
                destination TEXT NOT NULL,
                expected_fee REAL,
                phone_number TEXT,
                wechat_id TEXT,
                whatsapp_id TEXT,
                post_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        ''')
        # New table to manage orders and their status
        db.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                demand_id INTEGER NOT NULL,
                carrier_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'accepted',
                shipping_address TEXT,
                tracking_number TEXT,
                estimated_arrival_date TEXT,
                flight_number TEXT,
                pickup_location TEXT,
                rating INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (demand_id) REFERENCES demands(id),
                FOREIGN KEY (carrier_id) REFERENCES users(id)
            );
        ''')
        db.commit()

        # Create a super admin account if it does not exist.
        cursor = db.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", ('admin',))
        admin_exists = cursor.fetchone()
        if not admin_exists:
            hashed_password = generate_password_hash('admin_password_123', method='pbkdf2:sha256:260000')
            db.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)",
                       ('admin', hashed_password, 1))
            db.commit()
            print("Super admin account 'admin' created with password 'admin_password_123'")


# Always initialize the database, this will create tables if they don't exist.
init_db()


# ====================================================================
# HTML Templates (embedded as strings for single-file app)
# ====================================================================

# Base HTML structure with Tailwind CSS for styling
def base_html(title, content, messages):
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>带货华人网 - {title}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {{
            font-family: 'Inter', sans-serif;
            @apply bg-gray-100 text-gray-800;
        }}
        .container-fluid {{
            @apply max-w-7xl mx-auto p-4;
        }}
        .table-auto {{
            table-layout: auto;
        }}
        th, td {{
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }}
        th a {{
            display: flex;
            align-items: center;
        }}
        .sort-icon {{
            font-size: 0.8em;
            margin-left: 0.5rem;
        }}
    </style>
</head>
<body class="bg-gray-100 text-gray-800">
    <nav class="bg-white shadow-md mb-8">
        <div class="container-fluid flex justify-between items-center py-4">
            <a href="/" class="text-2xl font-bold text-indigo-600">带货华人网</a>
            {'<div class="flex items-center space-x-4"><span class="text-gray-700">欢迎, ' + session['username'] + '</span><a href="/logout" class="py-1 px-3 bg-red-500 text-white text-sm rounded-full hover:bg-red-600 transition-colors">退出登录</a></div>' if 'username' in session else '<a href="/login" class="py-1 px-3 bg-indigo-500 text-white text-sm rounded-full hover:bg-indigo-600 transition-colors">登录</a>'}
        </div>
    </nav>
    <div class="container-fluid">
        {messages}
        {content}
    </div>
</body>
</html>
"""


def get_flash_messages_html():
    messages = ""
    for category, message in get_flashed_messages(with_categories=True):
        messages += f'<p class="text-center text-red-500 text-sm mt-2">{message}</p>'
    return messages


LOGIN_HTML = """
    <div class="bg-white p-8 rounded-lg shadow-lg w-full max-w-sm sm:max-w-md mx-auto">
        <h1 class="text-3xl font-bold text-center text-indigo-600 mb-6">登录</h1>
        <form method="post" action="/login" class="space-y-4">
            <div>
                <label for="username" class="block text-sm font-medium text-gray-700">用户名</label>
                <input type="text" id="username" name="username" required 
                       class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500">
            </div>
            <div>
                <label for="password" class="block text-sm font-medium text-gray-700">密码</label>
                <input type="password" id="password" name="password" required 
                       class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500">
            </div>
            <button type="submit" 
                    class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">
                登录
            </button>
            <p class="mt-4 text-center text-sm text-gray-600">
                还没有账户？<a href="/register" class="font-medium text-indigo-600 hover:text-indigo-500">点击注册</a>
            </p>
        </form>
    </div>
"""

REGISTER_HTML = """
    <div class="bg-white p-8 rounded-lg shadow-lg w-full max-w-sm sm:max-w-md mx-auto">
        <h1 class="text-3xl font-bold text-center text-indigo-600 mb-6">注册新账户</h1>
        <form method="post" action="/register" class="space-y-4">
            <div>
                <label for="username" class="block text-sm font-medium text-gray-700">用户名</label>
                <input type="text" id="username" name="username" required 
                       class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500">
            </div>
            <div>
                <label for="password" class="block text-sm font-medium text-gray-700">密码</label>
                <input type="password" id="password" name="password" required 
                       class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500">
            </div>
            <button type="submit" 
                    class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">
                注册
            </button>
            <p class="mt-4 text-center text-sm text-gray-600">
                已有账户？<a href="/login" class="font-medium text-indigo-600 hover:text-indigo-500">点击登录</a>
            </p>
        </form>
    </div>
"""

INDEX_HTML = """
    <div class="text-center">
        <div class="flex justify-center space-x-4 mb-8">
            {% if 'username' in session %}
                <a href="/post_demand" class="py-2 px-4 bg-indigo-600 text-white rounded-md shadow-md hover:bg-indigo-700">发布带货需求</a>
            {% else %}
                <a href="/login" class="py-2 px-4 bg-gray-500 text-white rounded-md shadow-md">登录后发布需求</a>
            {% endif %}
        </div>
        <div class="flex-1">
            <h3 class="text-2xl font-semibold mb-4 text-left">所有带货需求</h3>
            <form method="get" action="/" class="mb-4 space-y-2 md:space-y-0 md:space-x-2 md:flex items-center">
                <input type="text" name="item_name" placeholder="按物品名称筛选..." class="px-3 py-2 rounded-md border border-gray-300 w-full md:w-auto flex-1 focus:outline-none focus:ring-2 focus:ring-indigo-500" value="{{ request.args.get('item_name', '') }}">
                <input type="text" name="destination" placeholder="按目的地筛选..." class="px-3 py-2 rounded-md border border-gray-300 w-full md:w-auto flex-1 focus:outline-none focus:ring-2 focus:ring-indigo-500" value="{{ request.args.get('destination', '') }}">
                <input type="text" name="min_weight" placeholder="最小重量 (kg)..." class="px-3 py-2 rounded-md border border-gray-300 w-full md:w-auto focus:outline-none focus:ring-2 focus:ring-indigo-500" value="{{ request.args.get('min_weight', '') }}">
                <input type="text" name="max_weight" placeholder="最大重量 (kg)..." class="px-3 py-2 rounded-md border border-gray-300 w-full md:w-auto focus:outline-none focus:ring-2 focus:ring-indigo-500" value="{{ request.args.get('max_weight', '') }}">
                <button type="submit" class="bg-indigo-500 text-white px-4 py-2 rounded-md hover:bg-indigo-600 w-full md:w-auto">筛选</button>
            </form>
            {% if demands %}
            <div class="overflow-x-auto bg-white rounded-lg shadow-md">
                <table class="table-auto w-full text-sm text-left text-gray-500">
                    <thead class="text-xs text-gray-700 uppercase bg-gray-50">
                        <tr>
                            <th scope="col" class="min-w-0">
                                <a href="?sort=item_name&order={{ 'desc' if request.args.get('sort') == 'item_name' and request.args.get('order') == 'asc' else 'asc' }}{{ '&destination=' + request.args.get('destination', '') }}{{ '&item_name=' + request.args.get('item_name', '') }}{{ '&min_weight=' + request.args.get('min_weight', '') }}{{ '&max_weight=' + request.args.get('max_weight', '') }}">物品名称
                                {% if request.args.get('sort') == 'item_name' %}<span class="sort-icon">{{ '▲' if request.args.get('order') == 'asc' else '▼' }}</span>{% endif %}
                                </a>
                            </th>
                            <th scope="col" class="min-w-0">
                                <a href="?sort=destination&order={{ 'desc' if request.args.get('sort') == 'destination' and request.args.get('order') == 'asc' else 'asc' }}{{ '&destination=' + request.args.get('destination', '') }}{{ '&item_name=' + request.args.get('item_name', '') }}{{ '&min_weight=' + request.args.get('min_weight', '') }}{{ '&max_weight=' + request.args.get('max_weight', '') }}">目的地
                                {% if request.args.get('sort') == 'destination' %}<span class="sort-icon">{{ '▲' if request.args.get('order') == 'asc' else '▼' }}</span>{% endif %}
                                </a>
                            </th>
                            <th scope="col">
                                <a href="?sort=weight&order={{ 'desc' if request.args.get('sort') == 'weight' and request.args.get('order') == 'asc' else 'asc' }}{{ '&destination=' + request.args.get('destination', '') }}{{ '&item_name=' + request.args.get('item_name', '') }}{{ '&min_weight=' + request.args.get('min_weight', '') }}{{ '&max_weight=' + request.args.get('max_weight', '') }}">重量 (kg)
                                {% if request.args.get('sort') == 'weight' %}<span class="sort-icon">{{ '▲' if request.args.get('order') == 'asc' else '▼' }}</span>{% endif %}
                                </a>
                            </th>
                            <th scope="col">运费 (¥)</th>
                            <th scope="col">联系方式</th>
                            <th scope="col" class="min-w-0">发布日期
                                <a href="?sort=post_date&order={{ 'desc' if request.args.get('sort') == 'post_date' and request.args.get('order') == 'asc' else 'asc' }}{{ '&destination=' + request.args.get('destination', '') }}{{ '&item_name=' + request.args.get('item_name', '') }}{{ '&min_weight=' + request.args.get('min_weight', '') }}{{ '&max_weight=' + request.args.get('max_weight', '') }}">
                                {% if request.args.get('sort') == 'post_date' %}<span class="sort-icon">{{ '▲' if request.args.get('order') == 'asc' else '▼' }}</span>{% endif %}
                                </a>
                            </th>
                            <th scope="col">操作</th>
                        </tr>
                    </thead>
                    <tbody>
                    {% for demand in demands %}
                        <tr class="bg-white border-b hover:bg-gray-50">
                            <td class="whitespace-nowrap">{{ '❗' if demand['is_new'] else '' }} {{ demand['item_name'] }}</td>
                            <td>{{ demand['destination'] }}</td>
                            <td>{{ demand['weight'] }}</td>
                            <td>{{ "%.2f"|format(demand['expected_fee']) }}</td>
                            <td>
                                {% if 'username' in session %}
                                <div class="flex flex-col space-y-1">
                                    {% if demand['phone_number'] %}<p class="text-sm text-blue-500">手机: {{ demand['phone_number'] }}</p>{% endif %}
                                    {% if demand['wechat_id'] %}<p class="text-sm text-blue-500">微信: {{ demand['wechat_id'] }}</p>{% endif %}
                                    {% if demand['whatsapp_id'] %}<p class="text-sm text-blue-500">WhatsApp: {{ demand['whatsapp_id'] }}</p>{% endif %}
                                </div>
                                {% else %}
                                <a href="/login" class="text-red-500 hover:underline">登录后查看</a>
                                {% endif %}
                            </td>
                            <td>{{ demand['post_date'].split(' ')[0] }}</td>
                            <td class="space-x-2 whitespace-nowrap">
                                {% if 'username' in session %}
                                    {% if demand['status'] == 'open' %}
                                    <a href="/accept_demand/{{ demand['id'] }}" class="text-sm text-green-600 hover:underline">接受需求</a>
                                    {% else %}
                                    <a href="/order_details/{{ demand['id'] }}" class="text-sm text-blue-600 hover:underline">查看进度</a>
                                    {% endif %}
                                    {% if session['is_admin'] or demand['user_id'] == session['user_id'] %}
                                    <a href="/edit_demand/{{ demand['id'] }}" class="text-sm text-blue-600 hover:underline">编辑</a>
                                    <a href="/delete_demand/{{ demand['id'] }}" class="text-sm text-red-600 hover:underline">删除</a>
                                    {% endif %}
                                {% else %}
                                    <a href="/login" class="text-sm text-gray-500 hover:underline">登录</a>
                                {% endif %}
                            </td>
                        </tr>
                    {% endfor %}
                    </tbody>
                </table>
            </div>
            {% else %}
            <p class="text-center text-gray-500 mt-4">暂无需求发布</p>
            {% endif %}
        </div>
    </div>
"""

POST_DEMAND_HTML = """
    <div class="bg-white p-8 rounded-lg shadow-lg w-full max-w-lg mx-auto">
        <h1 class="text-3xl font-bold text-center text-indigo-600 mb-6">发布带货需求</h1>
        <form method="post" action="/post_demand" class="space-y-4">
            <div>
                <label for="item_name" class="block text-sm font-medium text-gray-700">物品名称</label>
                <input type="text" id="item_name" name="item_name" required 
                       class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm">
            </div>
            <div>
                <label for="description" class="block text-sm font-medium text-gray-700">详细描述</label>
                <textarea id="description" name="description" rows="3" 
                          class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm"></textarea>
            </div>
            <div>
                <label for="weight" class="block text-sm font-medium text-gray-700">预计重量 (kg)</label>
                <input type="number" id="weight" name="weight" step="0.1" required 
                       class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm">
            </div>
            <div>
                <label for="destination" class="block text-sm font-medium text-gray-700">目的地</label>
                <input type="text" id="destination" name="destination" required 
                       class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm">
            </div>
            <div>
                <label for="expected_fee" class="block text-sm font-medium text-gray-700">期望运费 (¥)</label>
                <input type="number" id="expected_fee" name="expected_fee" step="0.01" required 
                       class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm">
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                    <label for="phone_number" class="block text-sm font-medium text-gray-700">手机号</label>
                    <input type="text" id="phone_number" name="phone_number" required 
                           class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm">
                </div>
                <div>
                    <label for="wechat_id" class="block text-sm font-medium text-gray-700">微信号 (可选)</label>
                    <input type="text" id="wechat_id" name="wechat_id" 
                           class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm">
                </div>
                <div>
                    <label for="whatsapp_id" class="block text-sm font-medium text-gray-700">WhatsApp (可选)</label>
                    <input type="text" id="whatsapp_id" name="whatsapp_id" 
                           class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm">
                </div>
            </div>
            <button type="submit" 
                    class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700">
                发布
            </button>
        </form>
    </div>
"""

EDIT_DEMAND_HTML = """
    <div class="bg-white p-8 rounded-lg shadow-lg w-full max-w-lg mx-auto">
        <h1 class="text-3xl font-bold text-center text-indigo-600 mb-6">编辑带货需求</h1>
        <form method="post" class="space-y-4">
            <div>
                <label for="item_name" class="block text-sm font-medium text-gray-700">物品名称</label>
                <input type="text" id="item_name" name="item_name" value="{{ demand.item_name }}" required 
                       class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm">
            </div>
            <div>
                <label for="description" class="block text-sm font-medium text-gray-700">详细描述</label>
                <textarea id="description" name="description" rows="3" 
                          class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm">{{ demand.description }}</textarea>
            </div>
            <div>
                <label for="weight" class="block text-sm font-medium text-gray-700">预计重量 (kg)</label>
                <input type="number" id="weight" name="weight" value="{{ demand.weight }}" step="0.1" required 
                       class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm">
            </div>
            <div>
                <label for="destination" class="block text-sm font-medium text-gray-700">目的地</label>
                <input type="text" id="destination" name="destination" value="{{ demand.destination }}" required 
                       class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm">
            </div>
            <div>
                <label for="expected_fee" class="block text-sm font-medium text-gray-700">期望运费 (¥)</label>
                <input type="number" id="expected_fee" name="expected_fee" value="{{ demand.expected_fee }}" step="0.01" required 
                       class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm">
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                    <label for="phone_number" class="block text-sm font-medium text-gray-700">手机号</label>
                    <input type="text" id="phone_number" name="phone_number" value="{{ demand.phone_number }}" required 
                           class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm">
                </div>
                <div>
                    <label for="wechat_id" class="block text-sm font-medium text-gray-700">微信号 (可选)</label>
                    <input type="text" id="wechat_id" name="wechat_id" value="{{ demand.wechat_id }}" 
                           class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm">
                </div>
                <div>
                    <label for="whatsapp_id" class="block text-sm font-medium text-gray-700">WhatsApp (可选)</label>
                    <input type="text" id="whatsapp_id" name="whatsapp_id" value="{{ demand.whatsapp_id }}" 
                           class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm">
                </div>
            </div>
            <button type="submit" 
                    class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700">
                更新
            </button>
        </form>
    </div>
"""

ORDER_DETAILS_HTML = """
    <div class="flex flex-col md:flex-row gap-8">
        <div class="flex-1">
            <div class="bg-white p-8 rounded-lg shadow-lg">
                <h1 class="text-3xl font-bold text-center text-indigo-600 mb-6">交易详情</h1>
                <div class="space-y-4 text-left text-gray-700">
                    <p><strong>需求物品:</strong> {{ demand['item_name'] }}</p>
                    <p><strong>目的地:</strong> {{ demand['destination'] }}</p>
                    <p><strong>当前状态:</strong> <span class="font-bold text-indigo-600">{{ status_text }}</span></p>
                    {% if order['shipping_address'] %}
                    <p><strong>收货地址:</strong> {{ order['shipping_address'] }}</p>
                    {% endif %}
                    {% if order['tracking_number'] %}
                    <p><strong>快递单号:</strong> {{ order['tracking_number'] }}</p>
                    {% endif %}
                    {% if order['estimated_arrival_date'] %}
                    <p><strong>预计到达日期:</strong> {{ order['estimated_arrival_date'] }}</p>
                    {% endif %}
                    {% if order['flight_number'] %}
                    <p><strong>航班号:</strong> {{ order['flight_number'] }}</p>
                    {% endif %}
                    {% if order['pickup_location'] %}
                    <p><strong>预计取货地址:</strong> {{ order['pickup_location'] }}</p>
                    {% endif %}
                    {% if order['rating'] %}
                    <p><strong>评价星级:</strong> {{ '★' * order['rating'] + '☆' * (5 - order['rating']) }}</p>
                    {% endif %}
                </div>

                <div class="mt-8 space-y-4">
                    {% if user_is_buyer and order['status'] == 'accepted' %}
                        <p class="text-sm text-gray-500">已成功通知帮带者，请等待他们填写收货地址。</p>
                    {% elif user_is_carrier and order['status'] == 'accepted' %}
                        <form method="post" action="/post_shipping_address/{{ order['id'] }}" class="space-y-4">
                            <label for="shipping_address" class="block text-sm font-medium text-gray-700">填写收货地址</label>
                            <textarea id="shipping_address" name="shipping_address" rows="4" required 
                                      class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm"></textarea>
                            <button type="submit" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700">
                                确认地址并通知发布者
                            </button>
                        </form>
                    {% elif user_is_carrier and order['status'] == 'address_submitted' %}
                        <p class="text-sm text-gray-500">已成功通知发布者，请等待他们发货。</p>
                    {% elif user_is_buyer and order['status'] == 'address_submitted' %}
                        <form method="post" action="/post_tracking_number/{{ order['id'] }}" class="space-y-4">
                            <label for="tracking_number" class="block text-sm font-medium text-gray-700">确认地址并输入快递单号</label>
                            <input type="text" id="tracking_number" name="tracking_number" required placeholder="输入快递单号..."
                                class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm">
                            <button type="submit" 
                                class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700">
                                确认下单并通知帮带者
                            </button>
                        </form>
                    {% elif user_is_buyer and order['status'] == 'ordered' %}
                        <p class="text-sm text-gray-500">已通知帮带者，请等待他们确认收货。</p>
                    {% elif user_is_carrier and order['status'] == 'ordered' %}
                        <p class="text-sm text-gray-500">物品已发货，请注意查收。确认收到货后，请填写到达信息。</p>
                        <form method="post" action="/post_arrival_info/{{ order['id'] }}" class="space-y-4 mt-4">
                            <div>
                                <label for="estimated_arrival_date" class="block text-sm font-medium text-gray-700">预计到达日期</label>
                                <input type="date" id="estimated_arrival_date" name="estimated_arrival_date" required class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm">
                            </div>
                            <div>
                                <label for="flight_number" class="block text-sm font-medium text-gray-700">航班号 (可选)</label>
                                <input type="text" id="flight_number" name="flight_number" class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm">
                            </div>
                            <div>
                                <label for="pickup_location" class="block text-sm font-medium text-gray-700">预计取货地址 (可选)</label>
                                <input type="text" id="pickup_location" name="pickup_location" class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm">
                            </div>
                            <button type="submit" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700">
                                确认收货并填写到达信息
                            </button>
                        </form>
                    {% elif user_is_buyer and order['status'] == 'awaiting_pickup' %}
                        <p class="text-sm text-gray-500">帮带者已确认收货，并提供了到达信息。请在收到货后，点击确认完成。</p>
                        <form method="post" action="/complete_order/{{ order['id'] }}" class="space-y-4 mt-4">
                            <div>
                                <label class="block text-sm font-medium text-gray-700">评价帮带者</label>
                                <div class="mt-1 flex items-center space-x-2">
                                    {% for i in range(1, 6) %}
                                        <input type="radio" id="rating-{{ i }}" name="rating" value="{{ i }}" required class="hidden peer">
                                        <label for="rating-{{ i }}" class="text-xl text-gray-400 cursor-pointer peer-checked:text-yellow-400">★</label>
                                    {% endfor %}
                                </div>
                            </div>
                            <button type="submit" 
                                class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700">
                                确认完成并提交评价
                            </button>
                        </form>
                    {% elif order['status'] == 'received' %}
                        <p class="text-center text-green-600 font-bold text-xl">交易已圆满完成！</p>
                    {% endif %}
                </div>
            </div>
        </div>

        <div class="md:w-1/3">
            <div class="bg-white p-8 rounded-lg shadow-lg">
                <h3 class="text-2xl font-bold text-center text-indigo-600 mb-6">交易进度</h3>
                <div class="space-y-4">
                    {% set steps = ['accepted', 'address_submitted', 'ordered', 'awaiting_pickup', 'received'] %}
                    {% for step in steps %}
                        <div class="flex items-center space-x-4">
                            <div class="w-8 h-8 rounded-full flex items-center justify-center 
                                {% if order['status'] == step %}
                                    bg-indigo-600 text-white
                                {% elif steps.index(order['status']) > steps.index(step) %}
                                    bg-green-500 text-white
                                {% else %}
                                    bg-gray-300 text-gray-500
                                {% endif %}
                            ">
                                {{ loop.index }}
                            </div>
                            <span class="font-medium {% if order['status'] == step %}text-indigo-600{% elif steps.index(order['status']) > steps.index(step) %}text-green-500{% else %}text-gray-500{% endif %}">
                                {% if step == 'accepted' %}
                                    需求已接受
                                {% elif step == 'address_submitted' %}
                                    收货地址已确认
                                {% elif step == 'ordered' %}
                                    已下单并寄出
                                {% elif step == 'awaiting_pickup' %}
                                    已确认收货，等待取件
                                {% elif step == 'received' %}
                                    交易已完成
                                {% endif %}
                            </span>
                        </div>
                        {% if not loop.last %}
                        <div class="h-8 w-1 ml-3 
                            {% if steps.index(order['status']) >= loop.index %}
                                bg-green-500
                            {% else %}
                                bg-gray-300
                            {% endif %}
                        "></div>
                        {% endif %}
                    {% endfor %}
                </div>
            </div>
        </div>
    </div>
"""


# ====================================================================
# Flask Routes
# ====================================================================

@app.route('/')
def index():
    """Displays the main dashboard with demands, accessible to all users."""
    db = get_db()

    # Get filter and sort criteria from request arguments
    item_name_filter = request.args.get('item_name', '')
    destination_filter = request.args.get('destination', '')
    min_weight_filter = request.args.get('min_weight', '')
    max_weight_filter = request.args.get('max_weight', '')
    sort_by = request.args.get('sort', 'post_date')
    order = request.args.get('order', 'desc')

    # Build dynamic SQL query with filters
    demand_query = 'SELECT *, (JulianDay(\'now\') - JulianDay(post_date)) < 7 as is_new FROM demands WHERE 1=1'
    demand_params = []

    if item_name_filter:
        demand_query += ' AND item_name LIKE ?'
        demand_params.append(f'%{item_name_filter}%')

    if destination_filter:
        demand_query += ' AND destination LIKE ?'
        demand_params.append(f'%{destination_filter}%')

    if min_weight_filter:
        demand_query += ' AND weight >= ?'
        demand_params.append(min_weight_filter)

    if max_weight_filter:
        demand_query += ' AND weight <= ?'
        demand_params.append(max_weight_filter)

    # Validate and apply sorting
    allowed_sort_fields = ['item_name', 'destination', 'weight', 'post_date']
    if sort_by in allowed_sort_fields:
        demand_query += f' ORDER BY {sort_by}'
        if order.lower() == 'desc':
            demand_query += ' DESC'
        else:
            demand_query += ' ASC'
    else:
        # Default sorting
        demand_query += ' ORDER BY post_date DESC'

    demands = db.execute(demand_query, demand_params).fetchall()

    return render_template_string(
        base_html("带货华人网", render_template_string(INDEX_HTML, username=session.get('username'), demands=demands),
                  get_flash_messages_html())
    )


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles user registration."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        cursor = db.cursor()

        # Check if username already exists
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        user_exists = cursor.fetchone()

        if user_exists:
            flash("该用户名已被占用，请尝试其他用户名。", "error")
            return redirect(url_for('register'))

        # Hash the password for security using a valid method
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256:260000')

        try:
            # Insert the new user into the database
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            db.commit()
            flash("注册成功！请登录。", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("注册失败，请稍后重试。", "error")
            return redirect(url_for('register'))

    return render_template_string(
        base_html("注册新账户", render_template_string(REGISTER_HTML), get_flash_messages_html()))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login and session management."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        cursor = db.cursor()

        # Fetch the user from the database
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()

        # Check if the user exists and the password is correct
        if user and check_password_hash(user['password'], password):
            session['username'] = user['username']
            session['user_id'] = user['id']  # Store user ID in session
            session['is_admin'] = bool(user['is_admin'])  # Store admin status

            # Redirect to index page after successful login
            return redirect(url_for('index'))
        else:
            flash("用户名或密码不正确。", "error")
            return redirect(url_for('login'))

    return render_template_string(base_html("登录", render_template_string(LOGIN_HTML), get_flash_messages_html()))


@app.route('/logout')
def logout():
    """Clears the session and logs the user out."""
    session.pop('username', None)
    session.pop('user_id', None)
    session.pop('is_admin', None)
    return redirect(url_for('login'))


@app.route('/post_demand', methods=['GET', 'POST'])
def post_demand():
    """Handles the posting of a new demand."""
    if 'username' not in session:
        flash("请先登录以发布需求。", "error")
        return redirect(url_for('login'))

    if request.method == 'POST':
        user_id = session['user_id']
        item_name = request.form['item_name']
        description = request.form.get('description', '')
        weight = float(request.form['weight'])
        destination = request.form['destination']
        expected_fee = float(request.form['expected_fee'])
        phone_number = request.form['phone_number']
        wechat_id = request.form.get('wechat_id', '')
        whatsapp_id = request.form.get('whatsapp_id', '')
        post_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db = get_db()
        db.execute(
            'INSERT INTO demands (user_id, item_name, description, weight, destination, expected_fee, phone_number, wechat_id, whatsapp_id, post_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (user_id, item_name, description, weight, destination, expected_fee, phone_number, wechat_id, whatsapp_id,
             post_date))
        db.commit()

        flash("需求发布成功！", "success")
        return redirect(url_for('index'))

    return render_template_string(
        base_html("发布带货需求", render_template_string(POST_DEMAND_HTML), get_flash_messages_html()))


@app.route('/edit_demand/<int:demand_id>', methods=['GET', 'POST'])
def edit_demand(demand_id):
    """Handles editing a demand."""
    if 'username' not in session:
        flash("请先登录。", "error")
        return redirect(url_for('login'))

    db = get_db()
    demand = db.execute('SELECT * FROM demands WHERE id = ?', (demand_id,)).fetchone()

    if not demand:
        flash("需求不存在。", "error")
        return redirect(url_for('index'))

    # Check for user ownership or admin status
    if not session.get('is_admin') and demand['user_id'] != session.get('user_id'):
        flash("您无权编辑此需求。", "error")
        return redirect(url_for('index'))

    # Do not allow editing if the demand has been accepted
    if demand['status'] != 'open':
        flash("此需求已被接受，无法编辑。", "error")
        return redirect(url_for('index'))

    if request.method == 'POST':
        item_name = request.form['item_name']
        description = request.form.get('description', '')
        weight = float(request.form['weight'])
        destination = request.form['destination']
        expected_fee = float(request.form['expected_fee'])
        phone_number = request.form['phone_number']
        wechat_id = request.form.get('wechat_id', '')
        whatsapp_id = request.form.get('whatsapp_id', '')

        db.execute(
            'UPDATE demands SET item_name = ?, description = ?, weight = ?, destination = ?, expected_fee = ?, phone_number = ?, wechat_id = ?, whatsapp_id = ? WHERE id = ?',
            (
            item_name, description, weight, destination, expected_fee, phone_number, wechat_id, whatsapp_id, demand_id))
        db.commit()
        flash("需求更新成功！", "success")
        return redirect(url_for('index'))

    return render_template_string(
        base_html("编辑带货需求", render_template_string(EDIT_DEMAND_HTML, demand=demand), get_flash_messages_html()))


@app.route('/delete_demand/<int:demand_id>', methods=['GET'])
def delete_demand(demand_id):
    """Handles deleting a demand."""
    if 'username' not in session:
        flash("请先登录。", "error")
        return redirect(url_for('login'))

    db = get_db()
    demand = db.execute('SELECT * FROM demands WHERE id = ?', (demand_id,)).fetchone()

    if not demand:
        flash("需求不存在。", "error")
        return redirect(url_for('index'))

    # Check for user ownership or admin status
    if not session.get('is_admin') and demand['user_id'] != session.get('user_id'):
        flash("您无权删除此需求。", "error")
        return redirect(url_for('index'))

    # Do not allow deletion if the demand has been accepted
    if demand['status'] != 'open':
        flash("此需求已被接受，无法删除。", "error")
        return redirect(url_for('index'))

    db.execute('DELETE FROM demands WHERE id = ?', (demand_id,))
    db.commit()
    flash("需求删除成功！", "success")
    return redirect(url_for('index'))


@app.route('/accept_demand/<int:demand_id>')
def accept_demand(demand_id):
    """Initiates the order process by creating a new order and redirecting to shipping address form."""
    if 'username' not in session:
        flash("请先登录以接受需求。", "error")
        return redirect(url_for('login'))

    db = get_db()
    demand = db.execute('SELECT * FROM demands WHERE id = ?', (demand_id,)).fetchone()

    if not demand:
        flash("需求不存在。", "error")
        return redirect(url_for('index'))

    # Check if demand is already accepted
    if demand['status'] != 'open':
        flash("此需求已被接受。", "error")
        return redirect(url_for('index'))

    # Check if the user is accepting their own demand
    if demand['user_id'] == session.get('user_id'):
        flash("您不能接受自己的需求。", "error")
        return redirect(url_for('index'))

    # Create new order entry
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute('INSERT INTO orders (demand_id, carrier_id, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
               (demand_id, session.get('user_id'), 'accepted', now, now))
    db.execute('UPDATE demands SET status = ? WHERE id = ?', ('accepted', demand_id))
    db.commit()

    flash("成功接受需求！请填写收货地址。", "success")
    # Redirect to the new order details page for the user to continue the flow
    order = db.execute('SELECT * FROM orders WHERE demand_id = ? AND carrier_id = ?',
                       (demand_id, session.get('user_id'))).fetchone()
    return redirect(url_for('order_details', order_id=order['id']))


@app.route('/order_details/<int:order_id>', methods=['GET'])
def order_details(order_id):
    """Displays the order details and progress bar."""
    if 'username' not in session:
        flash("请先登录以查看订单详情。", "error")
        return redirect(url_for('login'))

    db = get_db()
    order = db.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()
    if not order:
        order = db.execute('SELECT * FROM orders WHERE demand_id = ?', (order_id,)).fetchone()
        if not order:
            flash("订单不存在。", "error")
            return redirect(url_for('index'))

    demand = db.execute('SELECT * FROM demands WHERE id = ?', (order['demand_id'],)).fetchone()

    if demand['user_id'] != session.get('user_id') and order['carrier_id'] != session.get('user_id'):
        flash("您无权查看此订单。", "error")
        return redirect(url_for('index'))

    status_map = {
        'accepted': '需求已接受',
        'address_submitted': '收货地址已确认',
        'ordered': '已下单并寄出',
        'awaiting_pickup': '已确认收货，等待取件',
        'received': '交易已完成'
    }
    status_text = status_map.get(order['status'], '未知状态')
    user_is_buyer = demand['user_id'] == session.get('user_id')
    user_is_carrier = order['carrier_id'] == session.get('user_id')

    return render_template_string(
        base_html("交易详情", render_template_string(ORDER_DETAILS_HTML,
                                                     order=order,
                                                     demand=demand,
                                                     status_text=status_text,
                                                     user_is_buyer=user_is_buyer,
                                                     user_is_carrier=user_is_carrier), get_flash_messages_html())
    )


@app.route('/post_shipping_address/<int:order_id>', methods=['POST'])
def post_shipping_address(order_id):
    """Handles the buyer's shipping address submission."""
    if 'username' not in session:
        flash("请先登录。", "error")
        return redirect(url_for('login'))

    db = get_db()
    order = db.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()
    demand = db.execute('SELECT * FROM demands WHERE id = ?', (order['demand_id'],)).fetchone()

    if not order or not demand or order['carrier_id'] != session.get('user_id') or order['status'] != 'accepted':
        flash("无效的请求或您无权操作。", "error")
        return redirect(url_for('index'))

    shipping_address = request.form['shipping_address']
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute('UPDATE orders SET shipping_address = ?, status = ?, updated_at = ? WHERE id = ?',
               (shipping_address, 'address_submitted', now, order['id']))
    db.commit()

    # Simulate notification
    print(
        f"Notification: Carrier (ID: {session.get('user_id')}) has submitted shipping address for demand (ID: {demand['id']}).")
    flash("收货地址已确认，已通知发布者。", "success")
    return redirect(url_for('order_details', order_id=order['id']))


@app.route('/post_tracking_number/<int:order_id>', methods=['POST'])
def post_tracking_number(order_id):
    """Handles the buyer's tracking number submission."""
    if 'username' not in session:
        flash("请先登录。", "error")
        return redirect(url_for('login'))

    db = get_db()
    order = db.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()
    demand = db.execute('SELECT * FROM demands WHERE id = ?', (order['demand_id'],)).fetchone()

    if not order or not demand or demand['user_id'] != session.get('user_id') or order['status'] != 'address_submitted':
        flash("无效的请求或您无权操作。", "error")
        return redirect(url_for('index'))

    tracking_number = request.form['tracking_number']
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute('UPDATE orders SET tracking_number = ?, status = ?, updated_at = ? WHERE id = ?',
               (tracking_number, 'ordered', now, order['id']))
    db.commit()

    # Simulate notification
    print(f"Notification: Buyer (ID: {session.get('user_id')}) has posted tracking number for order (ID: {order_id}).")
    flash("快递单号已提交，已通知帮带者。", "success")
    return redirect(url_for('order_details', order_id=order['id']))


@app.route('/post_arrival_info/<int:order_id>', methods=['POST'])
def post_arrival_info(order_id):
    """Handles carrier's submission of estimated arrival info."""
    if 'username' not in session:
        flash("请先登录。", "error")
        return redirect(url_for('login'))

    db = get_db()
    order = db.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()
    if not order or order['carrier_id'] != session.get('user_id') or order['status'] != 'ordered':
        flash("无效的请求或您无权操作。", "error")
        return redirect(url_for('index'))

    estimated_arrival_date = request.form['estimated_arrival_date']
    flight_number = request.form.get('flight_number')
    pickup_location = request.form.get('pickup_location')
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    db.execute(
        'UPDATE orders SET estimated_arrival_date = ?, flight_number = ?, pickup_location = ?, status = ?, updated_at = ? WHERE id = ?',
        (estimated_arrival_date, flight_number, pickup_location, 'awaiting_pickup', now, order['id']))
    db.commit()

    # Simulate notification
    print(f"Notification: Carrier (ID: {session.get('user_id')}) has posted arrival info for order (ID: {order_id}).")
    flash("已成功提交到达信息，请等待需求方确认收货。", "success")
    return redirect(url_for('order_details', order_id=order['id']))


@app.route('/complete_order/<int:order_id>', methods=['POST'])
def complete_order(order_id):
    """Handles the buyer confirming receipt and rating the carrier."""
    if 'username' not in session:
        flash("请先登录。", "error")
        return redirect(url_for('login'))

    db = get_db()
    order = db.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()
    demand = db.execute('SELECT * FROM demands WHERE id = ?', (order['demand_id'],)).fetchone()

    if not order or demand['user_id'] != session.get('user_id') or order['status'] != 'awaiting_pickup':
        flash("无效的请求或您无权操作。", "error")
        return redirect(url_for('index'))

    rating = int(request.form['rating'])
    if not 1 <= rating <= 5:
        flash("无效的评分。", "error")
        return redirect(url_for('order_details', order_id=order['id']))

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute('UPDATE orders SET rating = ?, status = ?, updated_at = ? WHERE id = ?',
               (rating, 'received', now, order['id']))
    db.commit()

    # Simulate notification
    print(f"Notification: Buyer (ID: {session.get('user_id')}) has completed the order and rated the carrier.")
    flash("交易已圆满完成！感谢您的参与。", "success")
    return redirect(url_for('order_details', order_id=order['id']))


# ====================================================================
# Main entry point
# ====================================================================

if __name__ == '__main__':
    # To run this app, save the code as a Python file (e.g., app.py) and run it from your terminal:
    # python app.py
    # The server will start at http://127.0.0.1:5000/
    app.run(debug=True)
