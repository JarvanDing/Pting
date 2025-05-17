from flask import Flask, render_template, request, redirect, url_for, session, flash, get_flashed_messages, jsonify
from flask_migrate import Migrate
import subprocess
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import time
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import requests
import redis

# 从 models.py 导入 db 对象和模型
from models import db, TargetServer, PingResult, TracerouteResult, TestResult

from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

app = Flask(__name__)
# 从环境变量中获取 SECRET_KEY
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'a_default_secret_key_if_not_set')
# 配置数据库 URI，从环境变量 DATABASE_URL 获取，如果未设置则使用默认值
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///site.db')
# 设置为 False 可以减少内存消耗，但在开发时可以开启以便于调试
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 从环境变量获取测试间隔，如果未设置或无效，默认为 300 秒  
TEST_INTERVAL_SECONDS = int(os.getenv('TEST_INTERVAL_SECONDS', 300)) if os.getenv('TEST_INTERVAL_SECONDS', '').isdigit() else 300

# Redis 配置
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_LOCATION_CACHE_TTL = int(os.getenv('REDIS_LOCATION_CACHE_TTL', 2592000)) # 默认一个月

migrate = Migrate(app, db)

# 初始化 Redis 客户端
try:
    redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    # 测试连接
    redis_client.ping()
    print("Redis 连接成功！")
except redis.exceptions.ConnectionError as e:
    print(f"Redis 连接失败: {e}")
    redis_client = None # 如果连接失败，将客户端设置为 None

# 将 db 对象与 Flask 应用绑定
db.init_app(app)

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
    """新的主页 - 报表页面"""
    # 获取所有服务器列表，用于筛选
    servers = TargetServer.query.all()
    # 这里将是报表页面的逻辑，暂时先渲染一个空的模板
    return render_template('reports.html', servers=servers)

@app.route('/manage_servers')
@login_required
def manage_servers():
    """服务器管理页面，显示所有服务器并提供管理链接"""
    # 从数据库中获取所有 TargetServer 记录
    servers = TargetServer.query.all()
    # 将获取到的数据传递给模板
    return render_template('manage_servers.html', servers=servers)

@app.route('/login', methods=['GET', 'POST'])
def login():
    # 检查是否已经登录，如果已登录则重定向到主页
    if is_authenticated():
        return redirect(url_for('index'))

    if request.method == 'POST':
        # 获取表单数据
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
        return redirect(url_for('manage_servers'))
    
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
        return redirect(url_for('manage_servers'))

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
    return redirect(url_for('manage_servers'))

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

    # 处理 Traceroute 结果并添加地理位置或私有IP标识
    processed_traceroute_results = []
    for result in traceroute_results:
        processed_data = {'raw': result}
        
        # 优先使用带地理位置的结构化数据
        if result.traceroute_hops_with_location:
            # 为每个跳点的详情添加 display_location 字段
            processed_hops = []
            for hop in result.traceroute_hops_with_location:
                processed_details = []
                for detail in hop['details']:
                    # 复制 detail 字典以避免修改原始数据
                    processed_detail = detail.copy()
                    # 如果没有 location 数据，且 IP 是私有 IP，则设置 display_location
                    if not processed_detail.get('location') and processed_detail.get('ip') and is_private_ip(processed_detail['ip']):
                         processed_detail['display_location'] = '局域网'
                    processed_details.append(processed_detail)
                processed_hops.append({'hop_number': hop['hop_number'], 'details': processed_details})
                
            processed_data['processed_hops_with_location'] = processed_hops # 存储在新的键下
        elif result.result_output:
             # 如果没有结构化数据，但有原始输出，则解析原始输出作为回退
             processed_data['parsed'] = parse_traceroute_output(result.result_output)
             # 对于回退的解析结果，也可以检查私有 IP
             if processed_data['parsed']:
                 fallback_processed_hops = []
                 for hop in processed_data['parsed']:
                     fallback_processed_details = []
                     for detail in hop['details']:
                          fallback_processed_detail = detail.copy()
                          if fallback_processed_detail.get('ip') and is_private_ip(fallback_processed_detail['ip']):
                               fallback_processed_detail['display_location'] = '局域网'
                          fallback_processed_details.append(fallback_processed_detail)
                     fallback_processed_hops.append({'hop_number': hop['hop_number'], 'details': fallback_processed_details})
                 processed_data['fallback_processed_hops'] = fallback_processed_hops # 存储回退的处理数据


        processed_traceroute_results.append(processed_data)


    # 渲染模板并传递数据
    return render_template('view_results.html', server=server, ping_results=parsed_ping_results, traceroute_results=processed_traceroute_results) # 传递处理后的数据

@app.route('/api/results/<string:test_type>', defaults={'server_id': None})
@app.route('/api/results/<int:server_id>/<string:test_type>')
@login_required
def api_results(server_id, test_type):
    """提供测试结果的 API 接口"""
    if test_type not in ['ping', 'traceroute']:
        return jsonify({'error': '无效的测试类型'}), 400

    if test_type == 'ping':
        # 从 PingResult 表中查询数据
        query = PingResult.query.order_by(PingResult.test_time.desc())
        if server_id is not None:
            query = query.filter_by(target_server_id=server_id)
            
        results = query.all()

        # 格式化 Ping 结果
        formatted_results = []
        for result in results:
            formatted_results.append({
                'id': result.id,
                'server_id': result.target_server_id,
                'test_time': result.test_time.isoformat(), # Format datetime as ISO string
                'raw_output': result.raw_output,
                'packets_transmitted': result.packets_transmitted,
                'packets_received': result.packets_received,
                'packet_loss_percent': result.packet_loss_percent,
                'min_rtt_ms': result.min_rtt_ms,
                'avg_rtt_ms': result.avg_rtt_ms,
                'max_rtt_ms': result.max_rtt_ms,
            })

    elif test_type == 'traceroute':
        # 从 TracerouteResult 表中查询数据
        query = TracerouteResult.query.order_by(TracerouteResult.test_time.desc())
        if server_id is not None:
            query = query.filter_by(target_server_id=server_id)
            
        results = query.all()

        # 格式化 Traceroute 结果
        formatted_results = []
        for result in results:
             # TracerouteResult 的 processed_hops_with_location 字段已经包含了处理后的数据
             # 只需要直接返回即可
             formatted_results.append({
                 'id': result.id,
                 'server_id': result.target_server_id,
                 'test_time': result.test_time.isoformat(),
                 'raw_output': result.raw_output,
                 'processed_hops': result.processed_hops_with_location # 直接使用存储的结构化数据
             })

    return jsonify(formatted_results)

def is_private_ip(ip_address):
    """检查一个 IPv4 地址是否属于私有网络范围"""
    if not ip_address or ip_address == 'N/A' or ip_address == '*':
        return False

    try:
        parts = list(map(int, ip_address.split('.')))
        if len(parts) != 4:
            return False # 非法的 IPv4 地址格式
        
        # 10.0.0.0/8
        if parts[0] == 10:
            return True
        # 172.16.0.0/12
        if parts[0] == 172 and 16 <= parts[1] <= 31:
            return True
        # 192.168.0.0/16
        if parts[0] == 192 and parts[1] == 168:
            return True
        # 环回地址
        if ip_address == '127.0.0.1':
            return True
            
    except ValueError:
        # 处理部分不是整数的情况
        return False

    return False

def get_ip_location(ip_address):
    """使用 ip-api.com 获取 IP 地址的地理位置信息"""
    if ip_address == 'N/A' or ip_address == '*':
        return None
    
    # 检查是否为环回地址
    if ip_address == '127.0.0.1':
        return None

    # 检查是否为私有 IPv4 地址范围 (手动检查)
    parts = list(map(int, ip_address.split('.'))) if '.' in ip_address else None
    
    if parts and len(parts) == 4:
        # 10.0.0.0/8
        if parts[0] == 10:
            print(f"跳过私有 IP 的位置查询: {ip_address}")
            return None
        # 172.16.0.0/12
        if parts[0] == 172 and 16 <= parts[1] <= 31:
             print(f"跳过私有 IP 的位置查询: {ip_address}")
             return None
        # 192.168.0.0/16
        if parts[0] == 192 and parts[1] == 168:
             print(f"跳过私有 IP 的位置查询: {ip_address}")
             return None
    # 注意: 为了简化，这里不检查 IPv6 私有地址范围 (ULA, link-local)
    # 且 traceroute -n 主要返回 IPv4 地址。

    # 如果不是已知的私有/环回 IP，则继续进行 API 调用
    api_url = f"http://ip-api.com/json/{ip_address}"
    try:
        response = requests.get(api_url, timeout=5) # 为 API 请求添加超时
        response.raise_for_status() # 对于不良状态码抛出异常
        data = response.json()
        if data.get('status') == 'success':
            # 返回相关的地理位置数据
            return {
                'country': data.get('country'),
                'city': data.get('city'),
                'lat': data.get('lat'),
                'lon': data.get('lon')
            }
        else:
            # API 返回的状态不是 success (例如，fail, limited)
            print(f"IP 地理位置 API 返回状态: {data.get('status')}，IP: {ip_address}。消息: {data.get('message')}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"获取 IP {ip_address} 的位置时出错: {e}")
        return None
    except json.JSONDecodeError:
         print(f"解码 IP {ip_address} 的 JSON 响应时出错")
         return None
    except Exception as e:
        print(f"获取 IP {ip_address} 的地理位置时发生未知错误: {e}")
        return None

def get_cached_or_fetch_location(ip_address):
    """
    从 Redis 缓存获取 IP 地址的地理位置信息，如果缓存中没有或已过期，则调用外部 API 获取并存入缓存。
    """
    if not redis_client:
        print("Redis 客户端未初始化，跳过缓存。直接调用 API 获取位置。")
        return get_ip_location(ip_address) # 如果 Redis 未连接，回退到直接调用 API

    # 检查是否为私有 IP，如果是则不进行查询
    if is_private_ip(ip_address):
        # print(f"IP {ip_address} 是私有 IP，跳过位置查询和缓存。")
        return None # 私有 IP 不查询也不缓存

    cache_key = f"ip_location:{ip_address}"
    try:
        # 尝试从 Redis 获取缓存数据
        cached_data = redis_client.get(cache_key)
        if cached_data:
            # print(f"从 Redis 缓存获取到 IP {ip_address} 的位置信息。")
            return json.loads(cached_data) # 缓存命中，返回解析后的 JSON 数据

        # 缓存未命中或已过期，调用外部 API
        # print(f"Redis 缓存未命中或已过期，为 IP {ip_address} 调用外部 API 获取位置。")
        location_data = get_ip_location(ip_address)

        if location_data:
            # 将获取到的位置信息存入 Redis 缓存
            redis_client.set(cache_key, json.dumps(location_data), ex=REDIS_LOCATION_CACHE_TTL)
            # print(f"已将 IP {ip_address} 的位置信息存入 Redis 缓存，过期时间: {REDIS_LOCATION_CACHE_TTL} 秒。")
            return location_data
        else:
            # 如果 API 没有返回有效位置数据，也可以选择在 Redis 中标记一下，避免短时间内重复请求失败的 IP
            # 例如，设置一个很短的过期时间，表示最近尝试过但失败了
            # redis_client.set(cache_key, json.dumps({'status': 'failed'}), ex=60) # 标记失败 60 秒
            return None # API 未返回有效数据

    except redis.exceptions.RedisError as e:
        print(f"Redis 操作出错 ({e.__class__.__name__}): {e}")
        # Redis 操作失败时，回退到直接调用 API
        return get_ip_location(ip_address)
    except json.JSONDecodeError:
        print(f"解码 Redis 缓存数据时出错 for IP {ip_address}")
        # 解码失败也回退到直接调用 API
        return get_ip_location(ip_address)
    except Exception as e:
        print(f"get_cached_or_fetch_location 发生未知错误 for IP {ip_address}: {e}")
        return get_ip_location(ip_address)

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
    """执行所有目标服务器的 Ping 和 Traceroute 测试并保存结果到新的表中"""
    # 需要在应用上下文中执行数据库操作
    with app.app_context():
        servers = TargetServer.query.all()
        
        # 使用线程池并发执行测试
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_server = {}
            # 提交每个服务器的 ping 和 traceroute 任务
            for server in servers:
                ping_future = executor.submit(run_ping_test, server.hostname)
                traceroute_future = executor.submit(run_traceroute_test, server.hostname)
                future_to_server[ping_future] = (server, 'ping')
                future_to_server[traceroute_future] = (server, 'traceroute')

            # 处理已完成的任务结果
            for future in as_completed(future_to_server):
                server, test_type = future_to_server[future]
                try:
                    output = future.result()
                    
                    if test_type == 'ping':
                        # 解析 Ping 输出并保存到 PingResult 表
                        parsed_data = parse_ping_output(output)
                        new_ping_result = PingResult( # 使用新的 PingResult 模型
                            target_server_id=server.id,
                            raw_output=output,
                            packets_transmitted=parsed_data.get('packets_transmitted'),
                            packets_received=parsed_data.get('packets_received'),
                            # 将百分比字符串转换为浮点数（如果可能）
                            packet_loss_percent=float(parsed_data.get('packet_loss', '0%').strip('%')) if 'packet_loss' in parsed_data and parsed_data['packet_loss'] != 'N/A' else None,
                            # 将 RTT 字符串转换为浮点数（如果可能）
                            min_rtt_ms=float(parsed_data.get('min_rtt', 'N/A').split(' ')[0]) if 'min_rtt' in parsed_data and parsed_data['min_rtt'] != 'N/A' else None,
                            avg_rtt_ms=float(parsed_data.get('avg_rtt', 'N/A').split(' ')[0]) if 'avg_rtt' in parsed_data and parsed_data['avg_rtt'] != 'N/A' else None,
                            max_rtt_ms=float(parsed_data.get('max_rtt', 'N/A').split(' ')[0]) if 'max_rtt' in parsed_data and parsed_data['max_rtt'] != 'N/A' else None
                        )
                        db.session.add(new_ping_result)
                        print(f"完成 {test_type} 测试 for {server.hostname}，结果已保存到 PingResult。")

                    elif test_type == 'traceroute':
                        # 解析 Traceroute 输出并处理地理位置，保存到 TracerouteResult 表
                        parsed_hops = parse_traceroute_output(output)
                        hops_with_location = []
                        
                        # 使用另一个线程池或同步方式处理地理位置查询，调用缓存函数
                        # 这里为简化，直接在当前循环中调用缓存函数（它内部会处理缓存和 API 调用）
                        # 如果需要进一步优化 API 调用速率，可以在这里加入小的延时或更复杂的异步处理
                        
                        for hop in parsed_hops:
                            hop_data = {'hop_number': hop['hop_number'], 'details': []}
                            for detail in hop['details']:
                                ip = detail.get('ip')
                                location_data = None
                                if ip and ip != 'N/A' and ip != '*':
                                     # 调用缓存函数获取地理位置
                                     # 注意：get_cached_or_fetch_location 内部已处理私有 IP 和 API 调用
                                     location_data = get_cached_or_fetch_location(ip)

                                # 将详情与地理位置数据组合
                                combined_detail = detail.copy()
                                if location_data:
                                    combined_detail['location'] = location_data
                                # else: # 如果没有获取到位置，保留原始 detail 或添加标识（is_private_ip 已在缓存函数内处理）
                                     # if is_private_ip(ip): # 如果是私有 IP，可以显式添加标识，不过前端处理也行
                                          # combined_detail['display_location'] = '局域网'
                                
                                hop_data['details'].append(combined_detail)
                            hops_with_location.append(hop_data)
                        
                        new_traceroute_result = TracerouteResult( # 使用新的 TracerouteResult 模型
                            target_server_id=server.id,
                            raw_output=output,
                            processed_hops_with_location=hops_with_location # 保存结构化数据
                        )
                        db.session.add(new_traceroute_result)
                        print(f"完成 {test_type} 测试 for {server.hostname}，结果已保存到 TracerouteResult。")

                except Exception as exc:
                    print(f'{server.hostname} 的 {test_type} 测试产生异常: {exc}')
                    # 处理异常: 根据测试类型创建包含错误消息的结果到对应的表中
                    if test_type == 'ping':
                        new_ping_result = PingResult(
                            target_server_id=server.id,
                            raw_output=f"测试异常: {exc}",
                            # 其他结构化字段为 None
                        )
                        db.session.add(new_ping_result)
                    elif test_type == 'traceroute':
                         new_traceroute_result = TracerouteResult(
                              target_server_id=server.id,
                              raw_output=f"测试异常: {exc}",
                              processed_hops_with_location=None # 错误时无结构化数据
                         )
                         db.session.add(new_traceroute_result)


        # 提交所有测试结果到数据库
        db.session.commit()
        print("所有测试任务完成并保存结果。")

# 初始化 APScheduler
scheduler = BackgroundScheduler()

# 配置周期性任务 (任务将在调度器启动时添加)
# 我们将调度器启动逻辑移到 __main__ 块中，以防止在调试模式下重复启动。
# if not scheduler.running:
#     # 防止在调试模式下添加重复任务
#     if not app.debug or not scheduler.get_jobs():
#         # 使用配置的测试间隔
#         scheduler.add_job(func=perform_tests, trigger="interval", seconds=TEST_INTERVAL_SECONDS)
#         scheduler.start()

if __name__ == '__main__':
    # 确保调度器仅在主进程中启动，当 debug=True 时
    # WERKZEUG_RUN_MAIN 环境变量由 Flask 的重载器在重载进程中设置
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        # 配置周期性任务
        # 在添加任务前检查任务是否已存在 (在某些场景下 main 块可能多次执行)
        if not scheduler.get_jobs():
             scheduler.add_job(func=perform_tests, trigger="interval", seconds=TEST_INTERVAL_SECONDS)
             print(f"定时任务 '{perform_tests.__name__}' 已添加到调度器，间隔 {TEST_INTERVAL_SECONDS} 秒。") # 添加打印确认任务已添加

        # 启动调度器
        if not scheduler.running:
            try:
                scheduler.start()
                print("APScheduler 已启动。") # 添加打印确认调度器已启动
            except Exception as e:
                print(f"启动 APScheduler 失败: {e}") # 打印启动失败信息

    # 在实际生产环境中，debug=True 需要关闭
    # 从环境变量 FLASK_DEBUG 获取调试模式，默认为 True
    debug_mode = os.getenv('FLASK_DEBUG', 'True').lower() in ['true', '1']
    print("Flask 应用运行在 debug={} 模式。".format(debug_mode)) # 添加打印确认调试模式
    # 将打印时间间隔的语句放在 app.run() 之前
    print("自动执行定时任务的时间间隔设置为:", TEST_INTERVAL_SECONDS, "秒") # Moved this line

    app.run(debug=debug_mode) # This line blocks until server stops