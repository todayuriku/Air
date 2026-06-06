import os
import io
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, Response, send_file
from flask_sqlalchemy import SQLAlchemy
import google.generativeai as genai
from dotenv import load_dotenv
from PIL import Image

# グラフ作成用のライブラリ（サーバー環境でエラーを出さないための設定を追加）
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import seaborn as sns
import japanize_matplotlib

# ==========================================
# 1. 環境変数の読み込みと初期設定
# ==========================================
load_dotenv()

app = Flask(__name__)

# Basic認証のパスワード
APP_PASSWORD = os.environ.get("APP_PASSWORD")

# データベースの接続URL（Render仕様の postgres:// を postgresql:// に安全変換）
db_url = os.environ.get("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# データベースの初期化
db = SQLAlchemy(app)

# Gemini APIの初期設定（安定版の構成に修正）
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# ==========================================
# 2. データベースのテーブル設計（CSVの代わり）
# ==========================================
class Inventory(db.Model):
    __tablename__ = 'inventory'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=datetime.now)

class Consumed(db.Model):
    __tablename__ = 'consumed'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    consumed_at = db.Column(db.DateTime, default=datetime.now)

class Purchase(db.Model):
    __tablename__ = 'purchases'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False, default=0)
    purchased_at = db.Column(db.DateTime, default=datetime.now)

# テーブルの自動作成
with app.app_context():
    db.create_all()

# ==========================================
# 3. Basic認証の仕組み
# ==========================================
def check_auth(username, password):
    return password == APP_PASSWORD

def authenticate():
    return Response(
        'パスワードを入力してください', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )

def requires_auth(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# ==========================================
# 4. ルーティング（画面表示と各種機能）
# ==========================================

@app.route('/')
@requires_auth
def index():
    """メイン画面：食材一覧を表示"""
    items = Inventory.query.all()
    # レシピ提案など、前の状態があれば一緒に渡す（初期値はNone）
    return render_template('index.html', items=items, recipe=None)

@app.route('/add', methods=['POST'])
@requires_auth
def add_item():
    """手動で食材を追加する"""
    item_name = request.form.get('name')
    item_quantity = request.form.get('quantity', 1)
    item_price = request.form.get('price', 0)

    if item_name:
        new_item = Inventory(name=item_name, quantity=int(item_quantity))
        db.session.add(new_item)
        
        if int(item_price) > 0:
            new_purchase = Purchase(name=item_name, price=int(item_price))
            db.session.add(new_purchase)

        db.session.commit()
    return redirect(url_for('index'))

@app.route('/consume/<int:item_id>', methods=['POST', 'GET'])
@requires_auth
def consume_item(item_id):
    """食材を消費履歴に移動する"""
    item = Inventory.query.get(item_id)
    if item:
        consumed_record = Consumed(name=item.name, quantity=item.quantity)
        db.session.add(consumed_record)
        db.session.delete(item)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/delete/<int:item_id>', methods=['POST', 'GET'])
@requires_auth
def delete_item(item_id):
    """完全に削除する"""
    item = Inventory.query.get(item_id)
    if item:
        db.session.delete(item)
        db.session.commit()
    return redirect(url_for('index'))

# ==========================================
# ★ 復活機能1：Geminiによるレシート解析
# ==========================================
@app.route('/upload_receipt', methods=['POST'])
@requires_auth
def upload_receipt():
    """アップロードされたレシート画像を解析してDBに登録する"""
    if 'receipt' not in request.files:
        return redirect(url_for('index'))
    
    file = request.files['receipt']
    if file.filename == '':
        return redirect(url_for('index'))
    
    if file:
        # 画像として読み込み
        img = Image.open(file.stream)
        
        # 画像解析に適したモデルを使用
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (
            "このレシート画像から、購入された「食材名」と「価格（数値のみ）」を抽出してください。\n"
            "出力は必ず以下の形式（CSV形式）のみとし、余計な説明は一切省いてください。\n"
            "食材名,価格\n"
            "食材名,価格"
        )
        
        try:
            response = model.generate_content([prompt, img])
            lines = response.text.strip().split('\n')
            
            for line in lines:
                if ',' in line:
                    parts = line.split(',')
                    name = parts[0].strip()
                    try:
                        price = int(parts[1].strip())
                        # 冷蔵庫と購入履歴（食費）の両方に自動登録
                        new_item = Inventory(name=name, quantity=1)
                        new_purchase = Purchase(name=name, price=price)
                        db.session.add(new_item)
                        db.session.add(new_purchase)
                    except ValueError:
                        continue # 数値変換に失敗した行はスキップ
            
            db.session.commit()
        except Exception as e:
            print(f"レシート解析エラー: {e}")
            
    return redirect(url_for('index'))

# ==========================================
# ★ 復活機能2：食費・消費傾向のグラフ生成（動的配信版）
# ==========================================
@app.route('/graph.png')
@requires_auth
def generate_graph():
    """DBのデータからグラフ画像をその場で生成してブラウザに返す（容量を喰わないプロ仕様）"""
    purchases = Purchase.query.all()
    
    fig, ax = plt.subplots(figsize=(8, 4))
    
    if not purchases:
        ax.text(0.5, 0.5, 'データがまだありません', ha='center', va='center', fontsize=14)
    else:
        # グラフデータの集計
        names = [p.name for p in purchases]
        prices = [p.price for p in purchases]
        
        # Seabornで綺麗な棒グラフを作成
        sns.barplot(x=names, y=prices, ax=ax, palette="viridis")
        ax.set_title('食材ごとの購入金額（食費）')
        ax.set_xlabel('食材名')
        ax.set_ylabel('価格 (円)')
        plt.xticks(rotation=45)
    
    plt.tight_layout()
    
    # 画像をディスクに保存せず、メモリ上のバッファに出力
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png')
    img_buf.seek(0)
    plt.close(fig) # メモリ解放
    
    return send_file(img_buf, mimetype='image/png')

# ==========================================
# 復活機能3：GeminiによるAIレシピ提案
# ==========================================
@app.route('/recipe')
@requires_auth
def suggest_recipe():
    items = Inventory.query.all()
    if not items:
        return "冷蔵庫が空です。食材を登録してください。"

    ingredients = ", ".join([item.name for item in items])
    prompt = f"冷蔵庫に以下の食材があります: {ingredients}。これらを使ったおすすめのレシピを1つ提案してください。出力はプレーンテキスト（または基本的な見出し程度）でお願いします。"

    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(prompt)
        recipe = response.text
    except Exception as e:
        recipe = f"エラーが発生しました: {str(e)}"

    return render_template('index.html', items=items, recipe=recipe)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)