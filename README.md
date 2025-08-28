# 通用网站平台

这是一个基于 Flask、SQLite 和 Tailwind CSS 的轻量级通用网站平台。它提供了一个动态可配置的发布系统，用户可以注册、登录并发布内容，管理员则可以灵活地管理字段、用户和网站设置。

-----

## 核心功能

  * **用户管理**：
      * 用户注册和登录。
      * 管理员可以锁定、解锁和删除用户。
      * 为用户设置账户有效期。
  * **动态发布系统**：
      * 管理员可以**动态添加、修改和删除发布字段**（例如：文本、数字、文件等）。
      * 用户根据管理员设定的字段进行发布。
      * 主页根据字段定义动态生成筛选和排序功能。
  * **权限控制**：
      * 区分普通用户和管理员权限。
      * 管理员拥有独立的后台管理面板，可以控制网站名称、注册功能、用户和动态字段。
      * 普通用户只能管理自己的发布内容。
  * **安全与日志**：
      * 使用 `pbkdf2:sha256` 算法加密存储用户密码。
      * 记录关键的用户操作历史（例如：登录、发布、管理员操作）。
  * **文件上传**：
      * 支持文件字段类型，并将上传的文件安全地存储在服务器上。

-----

## 技术栈

  * **后端框架**：[Flask](https://flask.palletsprojects.com/)
  * **数据库**：[SQLite3](https://docs.python.org/3/library/sqlite3.html) (轻量级，无需额外配置)
  * **前端框架**：[Tailwind CSS](https://tailwindcss.com/) (用于快速构建美观的界面)
  * **Python 库**：`werkzeug`, `sqlite3`, `json`, `datetime` 等

-----

## 部署与运行

1.  **克隆仓库**：
    将所有代码文件（`app.py`、`templates/`、`static/`）放在同一个文件夹中。

2.  **安装依赖**：
    如果你还没有安装 Flask 和 Werkzeug，请使用 pip 安装它们：

    ```bash
    pip install Flask
    pip install werkzeug
    ```

    这个项目没有其他复杂的依赖。

3.  **初始化数据库**：
    首次运行 `app.py` 时，它会自动创建 `database.db` 文件，并初始化 `users`, `listings`, `settings` 和 `history` 表。同时，会自动创建一个名为 `admin` 的超级管理员账户，密码为 `admin_password_123`。

4.  **运行应用**：
    在命令行中进入项目目录，然后运行：

    ```bash
    python app.py
    ```

    如果一切顺利，你将看到类似 `Running on http://127.0.0.1:5000` 的输出。

-----

## 路由说明

  * `/`：主页，显示所有已发布的列表，并提供筛选和排序功能。
  * `/register`：新用户注册页面。
  * `/login`：用户登录页面。
  * `/logout`：用户退出登录。
  * `/post_demand`：用户发布新内容。
  * `/edit_demand/<string:demand_id>`：编辑指定内容的页面。
  * `/delete_demand/<string:demand_id>`：删除指定内容。
  * `/view_details/<string:demand_id>`：查看内容详情。
  * `/admin_panel`：**管理员后台**，管理所有用户和网站设置。
  * `/admin/update_fields`：用于保存动态字段的表单提交路由。
  * `/history`：查看操作历史记录。
  * `/uploads/<filename>`：处理文件上传和下载。

-----

## 管理员初始设置

1.  运行应用后，访问 `http://127.0.0.1:5000/login`。
2.  使用默认管理员账户登录：
      * **用户名**：`admin`
      * **密码**：`admin_password_123`
3.  登录后，点击导航栏中的“**管理员后台**”链接，进入管理面板。
4.  在管理面板中，你可以修改网站名称、开启/关闭注册功能、管理动态字段、查看和管理所有用户。
