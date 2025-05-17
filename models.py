from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import JSON

db = SQLAlchemy()

class TargetServer(db.Model):
    # 服务器ID，主键
    id = db.Column(db.Integer, primary_key=True)
    # 主机名或IP地址，唯一且不能为空
    hostname = db.Column(db.String(100), unique=True, nullable=False)
    # 服务器描述，可以为空
    description = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return f"TargetServer('{self.hostname}', '{self.description}')"

# Ping 结果模型
class PingResult(db.Model):
    # Ping结果ID，主键
    id = db.Column(db.Integer, primary_key=True)
    # 目标服务器ID，外键关联 TargetServer
    target_server_id = db.Column(db.Integer, db.ForeignKey('target_server.id'), nullable=False)
    # 测试时间，默认为当前UTC时间
    test_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # 原始Ping命令输出
    raw_output = db.Column(db.Text, nullable=True)

    # 结构化Ping数据字段
    # 发送的包数量
    packets_transmitted = db.Column(db.Integer, nullable=True)
    # 接收的包数量
    packets_received = db.Column(db.Integer, nullable=True)
    # 丢包率（百分比）
    packet_loss_percent = db.Column(db.Float, nullable=True)
    # 最小RTT（毫秒）
    min_rtt_ms = db.Column(db.Float, nullable=True)
    # 平均RTT（毫秒）
    avg_rtt_ms = db.Column(db.Float, nullable=True)
    # 最大RTT（毫秒）
    max_rtt_ms = db.Column(db.Float, nullable=True)

    # 与 TargetServer 的关系
    server = db.relationship('TargetServer', backref=db.backref('ping_results', lazy=True))

    def __repr__(self):
        return f"PingResult('{self.server.hostname}', '{self.test_time}')"

# Traceroute 结果模型
class TracerouteResult(db.Model):
    # Traceroute结果ID，主键
    id = db.Column(db.Integer, primary_key=True)
    # 目标服务器ID，外键关联 TargetServer
    target_server_id = db.Column(db.Integer, db.ForeignKey('target_server.id'), nullable=False)
    # 测试时间，默认为当前UTC时间
    test_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # 原始Traceroute命令输出
    raw_output = db.Column(db.Text, nullable=True)

    # 存储带地理位置信息的结构化跳数数据
    processed_hops_with_location = db.Column(db.JSON, nullable=True)

    # 与 TargetServer 的关系
    server = db.relationship('TargetServer', backref=db.backref('traceroute_results', lazy=True))

    def __repr__(self):
        return f"TracerouteResult('{self.server.hostname}', '{self.test_time}')"

# 通用测试结果模型 (可能已废弃，但保留注释)
class TestResult(db.Model):
    # 测试结果ID，主键
    id = db.Column(db.Integer, primary_key=True)
    # 目标服务器ID，外键关联 TargetServer
    target_server_id = db.Column(db.Integer, db.ForeignKey('target_server.id'), nullable=False)
    # 测试类型（例如：'ping', 'traceroute'）
    test_type = db.Column(db.String(50), nullable=False)
    # 测试时间，默认为当前UTC时间
    test_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # Ping测试的原始输出 (此字段可能已由 PingResult 模型取代)
    result_output = db.Column(db.Text, nullable=True)
    # Traceroute测试的原始输出 (此字段可能已由 TracerouteResult 模型取代)
    traceroute_output = db.Column(db.Text, nullable=True)
    # 存储带地理位置信息的结构化traceroute结果 (此字段可能已由 TracerouteResult 模型取代)
    traceroute_hops_with_location = db.Column(db.JSON, nullable=True)

    # 定义与 TargetServer 的关系
    server = db.relationship('TargetServer', backref=db.backref('results', lazy=True))

    def __repr__(self):
        return f"TestResult('{self.server.hostname}', '{self.test_type}', '{self.test_time}')" 