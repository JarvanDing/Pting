from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

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

@app.route('/')
def index():
    # 从数据库中获取所有 TargetServer 记录
    servers = TargetServer.query.all()
    # 将获取到的数据传递给模板
    return render_template('index.html', servers=servers)

if __name__ == '__main__':
    # 在实际生产环境中，debug=True 需要关闭
    app.run(debug=True) 