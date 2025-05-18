# Ping and Route Tester

这是一个基于 Flask 的 Web 应用，用于定时执行服务器 Ping 和路由测试。

## 技术栈

- **后端**: Flask, Flask-SQLAlchemy, Flask-Migrate, APScheduler, Requests, ipaddress, pytz, python-dotenv
- **前端**: Jinja2 模板, Bootstrap (推测用于界面)
- **数据库**: SQLite
- **缓存**: Redis (用于IP地理位置信息缓存)

## 功能

- **服务器管理**: 添加、编辑和删除目标服务器。
- **定时测试**: 后台定时对配置的服务器执行 Ping 和 Traceroute 测试。
- **结果查看**: 查看每个服务器的历史 Ping 和 Traceroute 测试结果。
- **报表页面**: 提供测试结果的汇总或可视化报表 (待完善)。
- **API 接口**: 提供获取测试结果的 API 接口。
- **用户认证**: 基于密码的简单登录认证。
- **IP 地理位置**: 尝试获取 Traceroute 跳点IP的地理位置信息，并进行缓存。
- **时区处理**: 支持配置应用的时区。

## 安装与运行

1. **克隆仓库**:
   ```bash
   git clone <仓库地址>
   cd Pting
   ```

2. **创建并激活虚拟环境**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **安装依赖**:
   ```bash
   pip install -r requirements.txt
   ```

4. **配置环境变量**:
   复制 `.env.example` (如果存在) 或手动创建 `.env` 文件在项目根目录，并配置以下变量：
   - `SECRET_KEY`: 用于 Flask Session 的密钥，任意随机字符串。
   - `APP_PASSWORD`: 用于登录应用的密码。
   - `DATABASE_URL`: 数据库连接字符串 (默认为 `sqlite:///site.db`)。
   - `TEST_INTERVAL_SECONDS`: 测试执行间隔，单位秒 (默认为 300)。
   - `TIMEZONE`: 应用使用的时区 (例如：`Asia/Shanghai`, 默认为 `UTC`)。
   - `REDIS_HOST`: Redis 主机地址 (默认为 `localhost`)。
   - `REDIS_PORT`: Redis 端口 (默认为 `6379`)。
   - `REDIS_LOCATION_CACHE_TTL`: IP地理位置缓存的过期时间，单位秒 (默认为 2592000，即 30 天)。

5. **初始化数据库**:
   ```bash
   flask db init
   flask db migrate -m "Initial migration"
   flask db upgrade
   ```
   如果数据库文件 (`site.db`) 已存在，跳过 `flask db init` 和 `flask db migrate`。

6. **运行应用**:
   ```bash
   flask run
   ```
   应用将在默认端口（通常是 5000）启动。

## 项目结构

- `.env`: 环境变量配置文件 (需要手动创建或复制示例)。
- `.gitignore`: Git 忽略文件配置。
- `app.py`: Flask 应用的核心文件。定义应用实例、配置、数据库和 Redis 初始化、用户认证逻辑、路由（页面和API）、测试执行函数、结果解析函数、IP 地理位置获取和缓存逻辑、以及 APScheduler 定时任务。
- `models.py`: 定义 SQLAlchemy 数据模型 (`TargetServer`, `PingResult`, `TracerouteResult`, `TestResult`)，表示数据库中的表结构。
- `requirements.txt`: 列出项目所有 Python 依赖包及其版本。
- `instance/`: Flask 默认的实例文件夹，通常用于存放 SQLite 数据库文件 (`site.db`) 和其他实例相关配置。
- `migrations/`: 由 Flask-Migrate 生成和管理的数据库迁移脚本文件夹。
- `static/`: 存放静态资源文件，如 CSS, JavaScript, 图片等 (前端资源)。
- `templates/`: 存放 Jinja2 模板文件 (`.html` 文件)，用于生成动态网页内容。
- `venv/`: Python 虚拟环境文件夹 (如果在项目根目录创建)。
- `README.md`: 项目自述文件。 