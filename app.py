from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import subprocess
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import time
import os

app = Flask(__name__)
# 配置数据库 URI，'sqlite:///site.db' 表示在应用根目录创建一个名为 site.db 的文件
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
# 设置为 False 可以减少内存消耗，但在开发时可以开启以便于调试
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

class TargetServer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # hostname 可以存储域名或IP地址
    hostname = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return f"TargetServer('{self.hostname}', '{self.description}')"

class TestResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    target_server_id = db.Column(db.Integer, db.ForeignKey('target_server.id'), nullable=False)
    test_type = db.Column(db.String(50), nullable=False) # e.g., 'ping', 'traceroute'
    test_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    result_output = db.Column(db.Text, nullable=True)

    # 定义与 TargetServer 的关系
    server = db.relationship('TargetServer', backref=db.backref('results', lazy=True))

    def __repr__(self):
        return f"TestResult('{self.server.hostname}', '{self.test_type}', '{self.test_time}')"

@app.route('/')
def index():
    # 从数据库中获取所有 TargetServer 记录
    servers = TargetServer.query.all()
    # 将获取到的数据传递给模板
    return render_template('index.html', servers=servers)

@app.route('/add_server', methods=['GET', 'POST'])
def add_server():
    if request.method == 'POST':
        # 获取表单数据
        hostname = request.form.get('hostname')
        description = request.form.get('description')
        
        # 创建新的 TargetServer 实例
        new_server = TargetServer(hostname=hostname, description=description)
        
        # 添加到数据库会话并保存
        db.session.add(new_server)
        db.session.commit()
        
        # 重定向到主页或服务器列表页
        return redirect(url_for('index'))
    
    # GET 请求时显示表单
    return render_template('add_server.html')

@app.route('/edit_server/<int:server_id>', methods=['GET', 'POST'])
def edit_server(server_id):
    # 根据 ID 从数据库获取服务器，如果不存在则返回 404 错误
    server = TargetServer.query.get_or_404(server_id)

    if request.method == 'POST':
        # 更新服务器信息
        server.hostname = request.form.get('hostname')
        server.description = request.form.get('description')
        
        # 提交保存到数据库
        db.session.commit()
        
        # 重定向到主页
        return redirect(url_for('index'))

    # GET 请求时显示编辑表单
    return render_template('edit_server.html', server=server)

@app.route('/delete_server/<int:server_id>', methods=['POST'])
def delete_server(server_id):
    # 根据 ID 从数据库获取服务器，如果不存在则返回 404 错误
    server = TargetServer.query.get_or_404(server_id)
    
    # 从数据库中删除服务器
    db.session.delete(server)
    db.session.commit()
    
    # 重定向到主页
    return redirect(url_for('index'))

@app.route('/results/<int:server_id>')
def view_results(server_id):
    # 根据 ID 从数据库获取服务器，如果不存在则返回 404 错误
    server = TargetServer.query.get_or_404(server_id)
    
    # 获取该服务器的所有测试结果，按时间倒序排序
    all_results = TestResult.query.filter_by(target_server_id=server.id).order_by(TestResult.test_time.desc()).all()

    # 将结果按测试类型分开
    ping_results = [r for r in all_results if r.test_type == 'ping']
    traceroute_results = [r for r in all_results if r.test_type == 'traceroute']

    # 渲染模板并传递数据
    return render_template('view_results.html', server=server, ping_results=ping_results, traceroute_results=traceroute_results)

def run_ping_test(hostname, count=4):
    """执行 Ping 测试并返回结果字符串"""
    try:
        # 构建 ping 命令，-c 指定次数
        command = ['ping', '-c', str(count), hostname]
        # 执行命令并捕获输出
        # capture_output=True 捕获 stdout 和 stderr
        # text=True 将输出解码为文本
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        # 如果命令执行失败 (例如，主机不可达)
        return f"Ping 测试失败: {e.stderr}"
    except FileNotFoundError:
        return "错误: 未找到 ping 命令。请确保已安装 ping。"
    except Exception as e:
        return f"发生未知错误: {e}"

def run_traceroute_test(hostname):
    """执行 Traceroute 测试并返回结果字符串"""
    try:
        # 构建 traceroute 命令，-n 避免反向 DNS 查询，加快速度
        # 在某些系统上可能是 traceroute，在其他系统上可能是 tracert (Windows)
        # 我们先尝试 traceroute
        command = ['traceroute', '-n', hostname]
        # 执行命令并捕获输出
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=60)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Traceroute 测试失败: {e.stderr}"
    except FileNotFoundError:
        return "错误: 未找到 traceroute 命令。请确保已安装 traceroute。"
    except subprocess.TimeoutExpired:
        return "Traceroute 测试超时。"
    except Exception as e:
        return f"发生未知错误: {e}"

def perform_tests():
    """执行所有目标服务器的 Ping 和 Traceroute 测试并保存结果"""
    # 需要在应用上下文中执行数据库操作
    with app.app_context():
        servers = TargetServer.query.all()
        for server in servers:
            print(f"正在测试服务器: {server.hostname}")
            
            # 执行 Ping 测试
            ping_output = run_ping_test(server.hostname)
            new_ping_result = TestResult(
                target_server_id=server.id,
                test_type='ping',
                result_output=ping_output
            )
            db.session.add(new_ping_result)
            
            # 执行 Traceroute 测试
            traceroute_output = run_traceroute_test(server.hostname)
            new_traceroute_result = TestResult(
                target_server_id=server.id,
                test_type='traceroute',
                result_output=traceroute_output
            )
            db.session.add(new_traceroute_result)
        
        # 提交所有测试结果
        db.session.commit()
        print("测试完成并保存结果。")

# 初始化 APScheduler
scheduler = BackgroundScheduler()

# 添加定时任务，例如每 5 分钟执行一次测试
# 使用 'interval' 触发器，seconds=300 表示 300 秒，即 5 分钟
# 你可以根据需求调整间隔
scheduler.add_job(func=perform_tests, trigger='interval', seconds=300, id='periodic_tests')

if __name__ == '__main__':
    # 在运行应用前启动调度器
    # 仅在主进程中启动调度器，避免在调试模式下重复启动
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        scheduler.start()
        print("调度器已启动")

    # 在实际生产环境中，debug=True 需要关闭
    app.run(debug=True) 