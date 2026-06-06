import os
import re
import urllib.parse
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
# ★AIライブラリ（最新版）
from google import genai
from PIL import Image
import io
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Basic認証
APP_PASSWORD = os.environ.get("APP_PASSWORD", "3823")

@app.before_request
def basic_auth():
    if request.endpoint and request.endpoint != 'static':
        auth = request.authorization
        if not auth or auth.password != APP_PASSWORD:
            return Response('パスワードを入力してください。\n', 401, {'WWW-Authenticate': 'Basic realm="AiR Login"'})

# データベース設定 (Neon)
db_url = os.environ.get("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ★グラフのデザイン・フォント設定
sns.set_theme(style="whitegrid", rc={"axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False})

# 用意したフォントファイルを相対パスで読み込む
FONT_PATH = os.path.join('static', 'fonts', 'NotoSansJP-VariableFont_wght.ttf')
try:
    if os.path.exists(FONT_PATH):
        font_manager = matplotlib.font_manager.FontManager()
        font_manager.addfont(FONT_PATH) # フォントを強制的にリストへ追加
        prop = matplotlib.font_manager.FontProperties(fname=FONT_PATH)
        matplotlib.rcParams['font.family'] = prop.get_name()
        print(f"フォント読み込み成功: {prop.get_name()}")
    else:
        print(f"警告: フォントファイルが見つかりません - {FONT_PATH}")
except Exception as e:
    print(f"フォント読み込みエラー: {e}")

# Gemini API設定 (最新版)
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# --- データベースのテーブル定義 ---
class Inventory(db.Model):
    __tablename__ = 'inventory'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.String(50), nullable=False)
    unit = db.Column(db.String(20))
    category = db.Column(db.String(50))
    exp_date = db.Column(db.String(20))
    status = db.Column(db.String(20))
    memo = db.Column(db.Text)

class FoodMaster(db.Model):
    __tablename__ = 'food_master'
    name = db.Column(db.String(100), primary_key=True)
    yomi = db.Column(db.String(100))
    exp_days = db.Column(db.Integer)
    unit = db.Column(db.String(20))
    category = db.Column(db.String(50))

class Consumed(db.Model):
    __tablename__ = 'consumed'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20))
    category = db.Column(db.String(50))
    price = db.Column(db.Float, default=0)
    calories = db.Column(db.Float, default=0)
    consumed_date = db.Column(db.String(20))

class Purchase(db.Model):
    __tablename__ = 'purchases'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20))
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Float)
    price = db.Column(db.Float)
    type = db.Column(db.String(20))

with app.app_context():
    db.create_all()

# --- データアクセス関数 ---
def load_inventory():
    records = Inventory.query.all()
    return [{
        'name': r.name, 'quantity': r.quantity, 'unit': r.unit,
        'category': r.category, 'exp_date': r.exp_date, 'status': r.status, 'memo': r.memo or ''
    } for r in records]

def get_master_foods():
    records = FoodMaster.query.all()
    master = {}
    for r in records:
        master[r.name] = {'exp_days': r.exp_days, 'unit': r.unit, 'category': r.category}
    return master

def save_inventory(items_dict_list):
    Inventory.query.delete()
    for item in items_dict_list:
        new_item = Inventory(
            name=item['name'], quantity=item['quantity'], unit=item['unit'],
            category=item['category'], exp_date=item['exp_date'],
            status=item['status'], memo=item.get('memo', '')
        )
        db.session.add(new_item)
    db.session.commit()

def save_consumed(item):
    new_consumed = Consumed(
        name=item['name'],
        quantity=float(item['quantity']),
        unit=item.get('unit', ''),
        category=item.get('category', ''),
        consumed_date=datetime.now().strftime('%Y/%m/%d %H:%M')
    )
    db.session.add(new_consumed)
    db.session.commit()

def get_expense_summary():
    this_month_total = 0.0
    last_month_total = 0.0
    today = datetime.now()
    this_month_str = today.strftime('%Y/%m')
    last_month_str = (today.replace(day=1) - timedelta(days=1)).strftime('%Y/%m')
    
    records = Purchase.query.all()
    for row in records:
        try:
            date_str = row.date
            price = float(row.price)
            if date_str.startswith(this_month_str):
                this_month_total += price
            elif date_str.startswith(last_month_str):
                last_month_total += price
        except: pass
    return int(this_month_total), int(last_month_total)

def get_row_type(row):
    if row.type: return row.type
    return 'receipt'

def create_expense_chart(period='comparison'):
    today = datetime.now()
    this_month_str = today.strftime('%Y/%m')
    last_month_str = (today.replace(day=1) - timedelta(days=1)).strftime('%Y/%m')
    this_year_str = today.strftime('%Y/') 
    
    records = Purchase.query.all()
    if not records: return None

    fig, ax = plt.subplots(figsize=(6, 4))

    if period == 'comparison':
        this_receipt, this_manual, last_receipt, last_manual = 0.0, 0.0, 0.0, 0.0
        for row in records:
            try:
                date_str = row.date
                price = float(row.price)
                rtype = get_row_type(row)
                if date_str.startswith(this_month_str):
                    if rtype == 'manual': this_manual += price
                    else: this_receipt += price
                elif date_str.startswith(last_month_str):
                    if rtype == 'manual': last_manual += price
                    else: last_receipt += price
            except: pass
                
        if (this_receipt + this_manual) == 0 and (last_receipt + last_manual) == 0:
            plt.close(fig)
            return None
            
        labels = ['先月', '今月']
        receipt_vals = [last_receipt, this_receipt]
        manual_vals = [last_manual, this_manual]
        title = '先月と今月の食費比較'
        
        ax.bar(labels, receipt_vals, label='自炊 (レシート)', color='#7B8FF7', width=0.5, alpha=0.9)
        ax.bar(labels, manual_vals, bottom=receipt_vals, label='外食・その他', color='#FFB74D', width=0.5, alpha=0.9)

    elif period == 'year':
        data_dict = defaultdict(lambda: {'receipt': 0.0, 'manual': 0.0})
        for row in records:
            try:
                date_str = row.date
                if not date_str.startswith(this_year_str): continue
                price = float(row.price)
                rtype = get_row_type(row)
                month = date_str[5:7] 
                data_dict[month][rtype] += price
            except: pass
                
        if not data_dict: 
            plt.close(fig)
            return None
        
        labels_sorted = sorted(data_dict.keys())
        receipt_vals = [data_dict[k]['receipt'] for k in labels_sorted]
        manual_vals = [data_dict[k]['manual'] for k in labels_sorted]
        display_labels = [f"{int(l)}月" for l in labels_sorted]
        title = f'{today.year}年の食費推移' 
        
        ax.bar(display_labels, receipt_vals, label='自炊 (レシート)', color='#7B8FF7', alpha=0.9)
        ax.bar(display_labels, manual_vals, bottom=receipt_vals, label='外食・その他', color='#FFB74D', alpha=0.9)
        ax.tick_params(axis='x', rotation=45)
    
    ax.set_title(title, fontsize=14, fontweight='bold', pad=25, loc='left')
    ax.set_ylabel('金額 (円)', fontsize=11, color='#555555')
    ax.set_xlabel('')
    ax.tick_params(colors='#444444')
    ax.legend(fontsize=10, loc='lower right', bbox_to_anchor=(1.0, 1.02), ncol=2, frameon=False, borderaxespad=0)
    
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=120)
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img_b64

def create_ranking_charts(period='this_month'):
    today = datetime.now()
    this_month_str = today.strftime('%Y/%m')
    last_month_str = (today.replace(day=1) - timedelta(days=1)).strftime('%Y/%m')
    this_year_str = today.strftime('%Y/') 
    
    records = Consumed.query.all()
    if not records:
        return {"g": None, "pack": None, "other": None}
        
    consumption = defaultdict(float)
    for row in records:
        try:
            date_str = row.consumed_date
            if period == 'this_month':
                if not date_str.startswith(this_month_str): continue
            elif period == 'last_month':
                if not date_str.startswith(last_month_str): continue
            elif period == 'year':
                if not date_str.startswith(this_year_str): continue

            name = row.name
            unit = row.unit
            consumption[(name, unit)] += float(row.quantity)
        except: pass
            
    groups = {'g': [], 'pack': [], 'other': []}
    for (name, unit), qty in consumption.items():
        if unit == 'g' or unit == 'ｇ':
            groups['g'].append((name, qty))
        elif unit in ['袋', 'パック', '箱']:
            groups['pack'].append((name, qty))
        else:
            groups['other'].append((name, qty))
            
    res = {}
    palettes = {'g': 'crest', 'pack': 'flare', 'other': 'Blues_d'}
    
    for key, lst in groups.items():
        if not lst:
            res[key] = None
            continue
            
        lst.sort(key=lambda x: x[1], reverse=True)
        lst = lst[:5]
        
        names = [x[0] for x in lst]
        qtys = [x[1] for x in lst]
        title_suffix = 'グラム' if key=='g' else '袋/パック/箱' if key=='pack' else 'その他'
        
        fig, ax = plt.subplots(figsize=(5, 3))
        sns.barplot(x=qtys, y=names, hue=names, palette=palettes[key], legend=False, ax=ax)
        
        ax.set_title(f"消費トップ5 ({title_suffix})", fontsize=12, fontweight='bold', pad=10)
        ax.set_xlabel('累計消費量', fontsize=10, color='#666666')
        ax.set_ylabel('')
        ax.tick_params(colors='#555555')
        for label in ax.get_yticklabels():
            label.set_fontweight('bold')
            label.set_color('#333333')
            
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=120)
        buf.seek(0)
        res[key] = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        
    return res

# --- ルーティング ---
@app.route('/')
def index():
    master_foods = get_master_foods()
    items = load_inventory()
    grouped = {}
    today = datetime.now().date()

    for idx, item in enumerate(items):
        name = item['name']
        qty = float(item['quantity'])
        if qty <= 0: continue
        if name not in grouped:
            grouped[name] = {
                'name': name, 'quantity': 0, 'unit': item['unit'],
                'category': item.get('category', 'その他'),
                'status': item.get('status', '未開封'), 'exp_dates': [],
                'memo': item.get('memo', ''),
                'added_order': idx
            }
        grouped[name]['quantity'] += qty
        grouped[name]['exp_dates'].append(item['exp_date'])
        if item.get('memo'):
            grouped[name]['memo'] = item['memo']
        grouped[name]['added_order'] = max(grouped[name]['added_order'], idx)
        
    display_items = []
    for data in grouped.values():
        data['exp_dates'].sort()
        best_exp = data['exp_dates'][0]
        data['exp_date'] = best_exp

        try:
            exp_dt = datetime.strptime(best_exp, '%Y/%m/%d').date()
            diff = (exp_dt - today).days
            if diff < 0:
                data['exp_status'] = 'expired'  
            elif diff <= 1:
                data['exp_status'] = 'urgent'    
            elif diff <= 3:
                data['exp_status'] = 'warning'    
            else:
                data['exp_status'] = 'safe'      
        except Exception:
            data['exp_status'] = 'safe'

        q = data['quantity']
        data['quantity'] = int(q) if q.is_integer() else round(q, 1)
        display_items.append(data)
        
    display_items.sort(key=lambda x: x['exp_date'])
    
    # 修正: JSが読み取れる形式（JSON文字列）に変換して渡す
    unit_map = {name: info['unit'] for name, info in master_foods.items()}
    unit_map_json = json.dumps(unit_map, ensure_ascii=False)
    
    expense_chart = create_expense_chart('comparison')
    ranking_charts = create_ranking_charts('this_month')
    this_month_total, last_month_total = get_expense_summary()
            
    return render_template(
        'index.html',
        items=display_items,
        master_foods=list(master_foods.keys()),
        unit_map=unit_map_json,
        expense_chart=expense_chart,
        ranking_charts=ranking_charts,
        this_month_total=this_month_total,
        last_month_total=last_month_total
    )

@app.route('/add', methods=['POST'])
def add_item():
    master_foods = get_master_foods()
    name = request.form.get('item_name')
    qty = float(request.form.get('quantity', 0))
    food_info = master_foods.get(name, {'exp_days': 3, 'unit': '個', 'category': 'その他'})
    expire_date = (datetime.now() + timedelta(days=food_info['exp_days'])).strftime('%Y/%m/%d')
    items = load_inventory()
    qty_str = str(int(qty)) if qty.is_integer() else str(qty)
    items.append({
        'name': name, 'quantity': qty_str, 'unit': food_info['unit'],
        'category': food_info['category'], 'exp_date': expire_date, 'status': '未開封', 'memo': ''
    })
    save_inventory(items)
    return redirect(url_for('index'))

@app.route('/scan_receipt', methods=['POST'])
def scan_receipt():
    master_foods = get_master_foods()
    if 'receipt_image' not in request.files:
        return jsonify({'error': '画像が見つかりません'}), 400
        
    file = request.files['receipt_image']
    img = Image.open(file.stream)
    master_list_str = ", ".join(master_foods.keys())
    
    prompt = f"""
    このレシート画像から、購入した「食品・食材」のみを抽出してください。（日用品は除外）
    【重要ルール】
    1. 固有の商品名やブランド名は、一般的な食材名に変換してください。（例：「シャウエッセン」→「ウインナー」）
    2. 表記揺れを防ぐため、必ず以下の【マスター食材リスト】に存在する名前と「完全に一致」させて出力してください。リストに該当しない場合は、最も近い一般的な食材名にしてください。
    3. レシートの中には、食材名だけではなく商品名で登録されている場合もあるため、その場合は商品名から食材を推察して出力してください。

    【マスター食材リスト】:
    {master_list_str}

    以下のJSONフォーマットの配列で出力してください。JSON以外の文章は絶対に含めないでください。
    [
      {{"name": "食材名(推察・変換後)", "qty": 数量(数字), "price": 金額(数字), "original_name": "レシートに印字されているそのままの商品名"}}
    ]
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[img, prompt]
        )
        
        raw_text = response.text.strip()
        start = raw_text.find('[')
        end = raw_text.rfind(']') + 1
        if start == -1 or end == 0:
            return jsonify({'error': '解析結果が不正です'}), 500
            
        parsed_items = json.loads(raw_text[start:end])
        results = []
        for item in parsed_items:
            name = item.get('name', '不明な食材')
            original_name = item.get('original_name', name)
            qty = item.get('qty', 1)
            price = item.get('price', 0)
            
            matched_name = name
            for m_name in master_foods.keys():
                if m_name == name:
                    matched_name = m_name
                    break
                elif m_name in name or name in m_name:
                    matched_name = m_name
            
            memo = ""
            if original_name and original_name != '不明な食材':
                memo = f"レシート表示：{original_name}"
                    
            results.append({
                'name': matched_name,
                'quantity': qty,
                'price': price,
                'unit': master_foods.get(matched_name, {}).get('unit', '個'),
                'memo': memo
            })
            
        return jsonify({'items': results})
    except Exception as e:
        print("AIエラー:", e)
        return jsonify({'error': '読み取りに失敗しました。もう一度お試しください。'}), 500

@app.route('/add_multiple', methods=['POST'])
def add_multiple():
    master_foods = get_master_foods()
    data = request.get_json()
    items_to_add = data.get('items', [])
    inventory = load_inventory()
    
    for item in items_to_add:
        name = item['name']
        qty = float(item['quantity'])
        price = float(item.get('price', 0))
        memo = item.get('memo', '')
        
        food_info = master_foods.get(name, {'exp_days': 3, 'unit': '個', 'category': 'その他'})
        expire_date = (datetime.now() + timedelta(days=food_info['exp_days'])).strftime('%Y/%m/%d')
        qty_str = str(int(qty)) if qty.is_integer() else str(qty)
        
        inventory.append({
            'name': name, 'quantity': qty_str, 'unit': food_info['unit'],
            'category': food_info['category'], 'exp_date': expire_date, 'status': '未開封', 'memo': memo
        })
        
        new_purchase = Purchase(
            date=datetime.now().strftime('%Y/%m/%d %H:%M'),
            name=name, quantity=qty, price=price, type='receipt'
        )
        db.session.add(new_purchase)
        
    save_inventory(inventory)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/add_manual_expense', methods=['POST'])
def add_manual_expense():
    expense_date_str = request.form.get('expense_date')
    expense_name = request.form.get('expense_name', '外食・その他')
    try: price = float(request.form.get('price', 0))
    except ValueError: price = 0
        
    if price > 0:
        if expense_date_str:
            date_val = expense_date_str.replace('-', '/') + ' 12:00'
        else:
            date_val = datetime.now().strftime('%Y/%m/%d %H:%M')

        new_purchase = Purchase(
            date=date_val, name=expense_name, quantity=1, price=price, type='manual'
        )
        db.session.add(new_purchase)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/api/get_chart/<period>')
def get_chart(period):
    chart_base64 = create_expense_chart(period)
    return jsonify({'chart': chart_base64})

@app.route('/api/get_ranking_chart/<period>')
def get_ranking_chart(period):
    charts = create_ranking_charts(period)
    return jsonify(charts)

@app.route('/reset_inventory', methods=['POST'])
def reset_inventory():
    Inventory.query.delete()
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/reset_history', methods=['POST'])
def reset_history():
    Consumed.query.delete()
    Purchase.query.delete()
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/update_status/<string:name>')
def update_status(name):
    items = load_inventory()
    target_items = [i for i in items if i['name'] == name]
    if target_items:
        current = target_items[0].get('status', '未開封')
        status_cycle = ['未開封', '半分', 'あと少し', '冷凍']
        if current not in status_cycle: current = '未開封'
        new_status = status_cycle[(status_cycle.index(current) + 1) % len(status_cycle)]
        for item in target_items:
            item['status'] = new_status
        save_inventory(items)
    return redirect(url_for('index'))

@app.route('/update/<string:name>/<string:mode>/<amount>')
def update_item(name, mode, amount):
    items = load_inventory()
    try: amount = float(amount)
    except ValueError: return redirect(url_for('index'))

    target_items = [i for i in items if i['name'] == name]
    if mode == 'plus':
        if target_items:
            target_items.sort(key=lambda x: x['exp_date'], reverse=True)
            new_qty = float(target_items[0]['quantity']) + amount
            target_items[0]['quantity'] = str(int(new_qty)) if new_qty.is_integer() else str(round(new_qty, 1))
    elif mode == 'minus':
        target_items.sort(key=lambda x: x['exp_date'])
        amount_left = amount
        for item in target_items:
            if amount_left <= 0: break
            qty = float(item['quantity'])
            if qty > 0:
                sub = min(qty, amount_left)
                new_qty = qty - sub
                item['quantity'] = str(int(new_qty)) if new_qty.is_integer() else str(round(new_qty, 1))
                amount_left -= sub
    items = [i for i in items if float(i['quantity']) > 0]
    save_inventory(items)
    return redirect(url_for('index'))

@app.route('/consume', methods=['POST'])
def consume_item():
    name = request.form.get('item_name')
    try: consume_amount = float(request.form.get('consume_amount', 0))
    except ValueError: consume_amount = 0
    if consume_amount <= 0: return redirect(url_for('index'))
    items = load_inventory()
    target_items = [i for i in items if i['name'] == name]
    if not target_items: return redirect(url_for('index'))
    target_items.sort(key=lambda x: x['exp_date'])
    amount_left_to_consume = consume_amount
    actual_consumed = 0
    for item in target_items:
        if amount_left_to_consume <= 0: break
        qty = float(item['quantity'])
        if qty > 0:
            sub = min(qty, amount_left_to_consume)
            new_qty = qty - sub
            item['quantity'] = str(int(new_qty)) if new_qty.is_integer() else str(round(new_qty, 1))
            amount_left_to_consume -= sub
            actual_consumed += sub
    if actual_consumed > 0:
        save_consumed({'name': name, 'quantity': actual_consumed, 'unit': target_items[0]['unit'], 'category': target_items[0].get('category', 'その他')})
    items = [i for i in items if float(i['quantity']) > 0]
    save_inventory(items)
    return redirect(url_for('index'))

@app.route('/delete/<string:name>')
def delete_item(name):
    items = load_inventory()
    items = [i for i in items if i['name'] != name]
    save_inventory(items)
    return redirect(url_for('index'))

@app.route('/ask_ai', methods=['POST'])
def ask_ai():
    data = request.get_json()
    mode = data.get('mode', 'strict')
    prioritize = data.get('prioritize', False)
    time = data.get('time', 'quick')
    items = load_inventory()
    
    if not items: return jsonify({"answer": "在庫がありません。"}), 200
    
    inv_text = ", ".join([f"{i['name']}({i['quantity']}{i['unit']}, 期限:{i['exp_date']})" for i in items])
    
    prompt = f"""あなたは家庭料理の専門家です。在庫と条件から、日常的で作りやすい料理を3つ提案してください。
【現在の在庫】: {inv_text}
【条件】: 買い物:{'在庫のみ' if mode == 'strict' else '買い足しOK'}, 期限優先:{'あり' if prioritize else 'なし'}, スタイル:{'時短' if time == 'quick' else '本格'}
【出力ルール（厳守）】:
- 挨拶や余計な解説は禁止。以下のフォーマットのみ出力。
- 料理名は、クックパッドなどで検索しやすい一般的な名称（例：「牛肉と野菜のコンソメスープ」）にすること。「〜の旨味を凝縮した」などの気取った表現や、長すぎる修飾語は絶対に使用しない。

**料理名**
調理時間: 〇分
買い足すもの: 〇〇
"""
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        
        dish_names = re.findall(r'\*\*(.*?)\*\*', response.text)
        links = [{"name": n, "url": f"https://www.google.com/search?q={urllib.parse.quote(n + ' レシピ')}"} for n in dish_names]
        return jsonify({"answer": response.text, "links": links})
    except Exception as e:
        print("AIエラー:", e)
        return jsonify({"answer": "AIエラーが発生しました。"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)