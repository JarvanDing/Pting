from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    # 暂定返回一个简单的模板，后续再完善
    return render_template('index.html')

if __name__ == '__main__':
    # 在实际生产环境中，debug=True 需要关闭
    app.run(debug=True) 