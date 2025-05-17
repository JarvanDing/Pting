from flask import Flask, render_template, request, redirect, url_for, session, flash, get_flashed_messages
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import subprocess
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import time
import os
import re

from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

app = Flask(__name__)
# 从环境变量中获取 SECRET_KEY
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
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

# 简单的登录验证函数
def is_authenticated():
    return 'authenticated' in session and session['authenticated']

# 要求登录的装饰器
def login_required(view):
    from functools import wraps
    @wraps(view)
    def wrapped_view(**kwargs):
        if not is_authenticated():
            flash('请先登录以访问此页面。', 'warning')
            return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view

@app.route('/')
@login_required
def index():
    # 从数据库中获取所有 TargetServer 记录
    servers = TargetServer.query.all()
    # 将获取到的数据传递给模板
    return render_template('index.html', servers=servers)

@app.route('/login', methods=['GET', 'POST'])
def login():
    # 检查是否已经登录，如果已登录则重定向到主页
    if is_authenticated():
        return redirect(url_for('index'))

    if request.method == 'POST':
        password = request.form.get('password')
        # 从环境变量中获取设置的密码
        correct_password = os.environ.get('APP_PASSWORD')
        
        if password == correct_password:
            # 密码正确，设置 session 并重定向到主页
            session['authenticated'] = True
            flash('登录成功！', 'success')
            return redirect(url_for('index'))
        else:
            # 密码错误，显示错误消息
            flash('密码错误，请重试。', 'danger')

    # GET 请求或密码错误时显示登录表单
    return render_template('login.html')

@app.route('/logout')
def logout():
    # 移除 session 中的认证标志
    session.pop('authenticated', None)
    flash('您已退出登录。', 'info')
    return redirect(url_for('login'))

@app.route('/add_server', methods=['GET', 'POST'])
@login_required
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
@login_required
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
@login_required
def delete_server(server_id):
    # 根据 ID 从数据库获取服务器，如果不存在则返回 404 错误
    server = TargetServer.query.get_or_404(server_id)
    
    # 从数据库中删除服务器
    db.session.delete(server)
    db.session.commit()
    
    # 重定向到主页
    return redirect(url_for('index'))

@app.route('/results/<int:server_id>')
@login_required
def view_results(server_id):
    # 根据 ID 从数据库获取服务器，如果不存在则返回 404 错误
    server = TargetServer.query.get_or_404(server_id)
    
    # 获取该服务器的所有测试结果，按时间倒序排序
    all_results = TestResult.query.filter_by(target_server_id=server.id).order_by(TestResult.test_time.desc()).all()

    # 将结果按测试类型分开
    ping_results = [r for r in all_results if r.test_type == 'ping']
    traceroute_results = [r for r in all_results if r.test_type == 'traceroute']

    # 解析 Ping 结果
    parsed_ping_results = []
    for result in ping_results:
        parsed_data = parse_ping_output(result.result_output)
        # 将原始结果和解析后的数据一起存储，方便在模板中访问
        parsed_ping_results.append({'raw': result, 'parsed': parsed_data})

    # 解析 Traceroute 结果
    parsed_traceroute_results = []
    for result in traceroute_results:
        parsed_data = parse_traceroute_output(result.result_output)
        # 将原始结果和解析后的数据一起存储，方便在模板中访问
        parsed_traceroute_results.append({'raw': result, 'parsed': parsed_data})

    # 渲染模板并传递数据
    return render_template('view_results.html', server=server, ping_results=parsed_ping_results, traceroute_results=parsed_traceroute_results)

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

def parse_ping_output(output):
    """解析 Ping 命令输出并提取关键信息"""
    stats = {
        'packets_transmitted': 0,
        'packets_received': 0,
        'packet_loss': 'N/A',
        'min_rtt': 'N/A',
        'avg_rtt': 'N/A',
        'max_rtt': 'N/A',
    }

    if not output:
        return stats

    # 尝试匹配丢包率信息
    loss_match = re.search(r'(\d+)% packet loss', output)
    if loss_match:
        stats['packet_loss'] = f"{loss_match.group(1)}%"

    # 尝试匹配发送和接收的包数量
    packets_match = re.search(r'(\d+) packets transmitted, (\d+) packets received', output)
    if packets_match:
        stats['packets_transmitted'] = int(packets_match.group(1))
        stats['packets_received'] = int(packets_match.group(2))

    # 尝试匹配 RTT 统计信息 (min/avg/max)
    rtt_match = re.search(r'rtt min/avg/max/mdev = (\d+\.?\d+)/(\d+\.?\d+)/(\d+\.?\d+)/\d+\.?\d+ ms', output)
    if rtt_match:
        stats['min_rtt'] = f"{rtt_match.group(1)} ms"
        stats['avg_rtt'] = f"{rtt_match.group(2)} ms"
        stats['max_rtt'] = f"{rtt_match.group(3)} ms"

    return stats

def parse_traceroute_output(output):
    """解析 Traceroute 命令输出并提取关键信息"""
    hops = []
    if not output:
        return hops

    # 按行分割输出
    lines = output.strip().split('\n')

    # 遍历每一行，跳过头部信息
    # 头部信息通常是 "traceroute to example.com (x.x.x.x), 30 hops max, 60 byte packets"
    # 实际的跳信息从第二行或第三行开始，具体取决于输出格式
    # 我们尝试从包含跳数 (数字) 开头的行开始解析
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 尝试匹配以数字开头的行 (跳数)
        hop_match = re.match(r'^\s*(\d+)\s+(.*)', line)
        if hop_match:
            hop_number = int(hop_match.group(1))
            hop_data_str = hop_match.group(2)

            # 解析跳的详细信息 (IP/域名, 延迟)
            # 格式可能像 "hostname (IP)  time1 ms  time2 ms ..." 或 "IP  time1 ms ..." 或 "* * *"
            details = []
            current_detail = {}
            parts = hop_data_str.split()

            i = 0
            while i < len(parts):
                part = parts[i]
                if part == '*':
                    details.append({'host': '*', 'ip': 'N/A', 'rtt': 'N/A'})
                    # 如果是 *, 跳过接下来的 * *
                    while i + 1 < len(parts) and parts[i+1] == '*':
                         i += 1
                elif part.endswith('ms'):
                     # 匹配延迟，通常前面是数字
                     if i > 0 and parts[i-1].replace('.', '', 1).isdigit():
                          details.append({'host': current_detail.get('host', 'N/A'), 'ip': current_detail.get('ip', 'N/A'), 'rtt': f"{parts[i-1]} {part}"})
                          current_detail = {} # 重置 detail for next entry
                          i += 1 # 跳过 ms
                     else:
                          # 如果格式不符合预期，作为原始部分处理
                          details.append({'host': 'N/A', 'ip': 'N/A', 'rtt': part})

                elif re.match(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', part):
                    # 匹配 IP 地址
                    current_detail['ip'] = part
                    current_detail['host'] = part # 默认主机名就是IP

                elif part.endswith(')'):
                    # 匹配主机名 (IP) 格式
                    if i > 0 and parts[i-1].endswith('('):
                         host_name = parts[i-2] if i > 1 else 'N/A' # 主机名在括号前
                         ip_address = part.strip('()')
                         current_detail['host'] = host_name
                         current_detail['ip'] = ip_address
                         i += 1 # 跳过 )
                    else:
                        # 如果格式不符合预期，作为原始部分处理
                        current_detail['host'] = part
                        current_detail['ip'] = 'N/A' # 无法确定IP

                else:
                    # 处理其他可能的文本部分，例如域名
                    if 'host' not in current_detail or current_detail['host'] == 'N/A':
                         current_detail['host'] = part


                i += 1

            # 将当前跳的信息添加到 hops 列表中
            # 由于一个跳可能有多个探测的延迟结果，我们将它们都添加到 details 中
            hops.append({'hop_number': hop_number, 'details': details})

    return hops

def perform_tests():
    """执行所有目标服务器的 Ping 和 Traceroute 测试并保存结果"""
    # 需要在应用上下文中执行数据库操作
    with app.app_context():
        servers = TargetServer.query.all()
        for server in servers:
            print(f"正在测试服务器: {server.hostname}")
            
            # 执行 Ping 测试
            ping_output = run_ping_test(server.hostname)
            # 可以选择在这里解析 Ping 结果并存储结构化数据，或者在展示时解析
            # 暂定在展示时解析，这里只保存原始输出
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