import os
import re
import urllib.parse
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
import google.generativeai as genai
from PIL import Image
import io
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict
from dotenv import load_dotenv

# ==========================================
# 1. 初期設定とデータベース接続
# ==========================================
load_dotenv()

app = Flask(__name__)

# Basic認証のパスワード（Renderの環境変数から取得、未設定時は元の '3823'）
APP_PASSWORD = os.environ.get("APP_PASSWORD", "3823")

@app.before_request
def basic_auth():
    if request.endpoint and request.endpoint != 'static':
        auth = request.authorization
        if not auth or auth.password != APP_PASSWORD:
            return Response('パスワードを入力してください。\n', 401, {'WWW-Authenticate': 'Basic realm="AiR Login"'})

# データベース接続設定
db_url = os.environ.get("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

sns.set_theme(style="whitegrid", rc={"axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False})
# japanize_matplotlibの代わりに、一般的な日本語フォントを直接指定する安全な方法
plt.rcParams['font.family'] = ['sans-serif']
plt.rcParams['font.sans-serif'] = ['Hiragino Maru Gothic Pro', 'Yu Gothic', 'Meiryo', 'Takao', 'IPAexGothic', 'IPAPGothic', 'Noto Sans CJK JP']

# Gemini API設定
# Gemini API設定
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
# ==========================================
# 2. データベースのテーブル定義（CSVの代わり）
# ==========================================

class Inventory(db.Model):
    __tablename__ = 'inventory'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.String(50), nullable=False) # CSVの仕様に合わせString型
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

# ==========================================
# 3. データアクセス関数（DB仕様に書き換え）
# ==========================================

def load_inventory():
    records = Inventory.query.all()
    # CSV時代と同じ辞書のリスト形式にして返す（既存ロジックを壊さないため）
    return [{
        'id': r.id, 'name': r.name, 'quantity': r.quantity, 'unit': r.unit,
        'category': r.category, 'exp_date': r.exp_date, 'status': r.status, 'memo': r.memo or ''
    } for r in records]

def get_master_foods():
    records = FoodMaster.query.all()
    master = {}
    for r in records:
        master[r.name] = {'exp_days': r.exp_days, 'unit': r.unit, 'category': r.category}
    return master

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
        sns.barplot(x=qtys, y=names, palette=palettes[key], ax=ax)
        
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

# ==========================================
# 4. ルーティング（変更なし、保存処理のみDB対応）
# ==========================================

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
    unit_map = {name: info['unit'] for name, info in master_foods.items()}
    
    expense_chart = create_expense_chart('comparison') 
    ranking_charts = create_ranking_charts('this_month')
    this_month_total, last_month_total = get_expense_summary()

    unique_categories = ['乳・卵', '肉類', '野菜', '魚介類', '大豆製品', '調味料', '飲料', '加工食品', 'その他']
    unique_units = list(set(info['unit'] for info in master_foods.values()))
    if not unique_units:
        unique_units = ['個', 'g', '袋', '本', 'パック', '箱']
            
    return render_template(
        'index.html', 
        items=display_items, 
        master_foods=master_foods.keys(), 
        unit_map=unit_map,
        expense_chart=expense_chart,
        ranking_charts=ranking_charts,
        this_month_total=this_month_total,
        last_month_total=last_month_total,
        unique_categories=unique_categories,
        unique_units=unique_units
    )

@app.route('/add', methods=['POST'])
def add_item():
    master_foods = get_master_foods()
    name = request.form.get('item_name')
    qty = float(request.form.get('quantity', 0))
    food_info = master_foods.get(name, {'exp_days': 3, 'unit': '個', 'category': 'その他'})
    expire_date = (datetime.now() + timedelta(days=food_info['exp_days'])).strftime('%Y/%m/%d')
    qty_str = str(int(qty)) if qty.is_integer() else str(qty)
    
    new_item = Inventory(
        name=name, quantity=qty_str, unit=food_info['unit'],
        category=food_info['category'], exp_date=expire_date, status='未開封', memo=''
    )
    db.session.add(new_item)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/scan_receipt', methods=['POST'])
def scan_receipt():
    master_foods = get_master_foods()
    if 'receipt_image' not in request.files:
        return jsonify({'error': '画像が見つかりません'}), 400
        
    file = request.files['receipt_image']
    img = Image.open(file.stream)
    
    master_list_str = ", ".join(master_foods.keys())
    master_units_str = ", ".join(set(info['unit'] for info in master_foods.values()))
    
    prompt = f"""
    このレシート画像から、購入した「食品・食材」のみを抽出してください。（日用品は除外）
    
    【重要ルール】
    1. 固有の商品名やブランド名は、一般的な食材名に変換してください。（例：「シャウエッセン」→「ウインナー」）
    2. 以下の【マスター食材リスト】に存在する名前と「完全に一致」させて出力してください。
    3. 【マスター食材リスト】に該当しない全く新しい食材の場合は、is_newをtrueにし、以下のリストから最も適切な「単位」と「カテゴリ」を選び、一般的な「賞味期限（日数）」「ふりがな」を推測してください。
    【単位リスト】: {master_units_str if master_units_str else '個, g, 袋, 本, パック, 箱'}
    【カテゴリリスト】: 乳・卵, 肉類, 野菜, 魚介類, 大豆製品, 調味料, 飲料, 加工食品, その他

    【マスター食材リスト】:
    {master_list_str}

    以下のJSONフォーマットの配列で出力してください。JSON以外の文章は絶対に含めないでください。
    [
      {{"name": "食材名", "qty": 数量, "price": 金額, "original_name": "印字名", "is_new": true, "yomi": "ふりがな", "exp_days": 推測日数, "unit": "推測単位", "category": "推測カテゴリ"}}
    ]
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content([img, prompt])
        
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
            is_matched = False
            for m_name in master_foods.keys():
                if m_name == name or m_name in name or name in m_name:
                    matched_name = m_name
                    is_matched = True
                    break
            
            if not is_matched and item.get('is_new'):
                yomi = item.get('yomi', name)
                exp_days = int(item.get('exp_days', 3))
                unit = item.get('unit', '個')
                category = item.get('category', 'その他')
                
                # 新しい食材をマスターDBに登録
                new_master = FoodMaster(name=name, yomi=yomi, exp_days=exp_days, unit=unit, category=category)
                db.session.merge(new_master) # 既に存在する場合は上書き
                db.session.commit()
                
                master_foods[name] = {'exp_days': exp_days, 'unit': unit, 'category': category}
                matched_name = name
            
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
    
    for item in items_to_add:
        name = item['name']
        qty = float(item['quantity'])
        price = float(item.get('price', 0))
        memo = item.get('memo', '') 
        
        food_info = master_foods.get(name, {'exp_days': 3, 'unit': '個', 'category': 'その他'})
        expire_date = (datetime.now() + timedelta(days=food_info['exp_days'])).strftime('%Y/%m/%d')
        qty_str = str(int(qty)) if qty.is_integer() else str(qty)
        
        new_item = Inventory(
            name=name, quantity=qty_str, unit=food_info['unit'],
            category=food_info['category'], exp_date=expire_date, status='未開封', memo=memo
        )
        db.session.add(new_item)
        
        new_purchase = Purchase(
            date=datetime.now().strftime('%Y/%m/%d %H:%M'),
            name=name, quantity=qty, price=price, type='receipt'
        )
        db.session.add(new_purchase)
        
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

@app.route('/add_master', methods=['POST'])
def add_master():
    name = request.form.get('master_name')
    yomi = request.form.get('master_yomi')
    try: exp_days = int(request.form.get('master_exp_days', 3))
    except: exp_days = 3
    unit = request.form.get('master_unit', '個')
    category = request.form.get('master_category', 'その他')
    
    if name:
        new_master = FoodMaster(name=name, yomi=yomi, exp_days=exp_days, unit=unit, category=category)
        db.session.merge(new_master)
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
    items = Inventory.query.filter_by(name=name).all()
    if items:
        current = items[0].status
        status_cycle = ['未開封', '半分', 'あと少し', '冷凍']
        if current not in status_cycle: current = '未開封'
        new_status = status_cycle[(status_cycle.index(current) + 1) % len(status_cycle)]
        
        for item in items: 
            item.status = new_status
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/update/<string:name>/<string:mode>/<amount>')
def update_item(name, mode, amount):
    try: amount = float(amount)
    except ValueError: return redirect(url_for('index'))

    items = Inventory.query.filter_by(name=name).all()
    
    if mode == 'plus':
        if items:
            items.sort(key=lambda x: x.exp_date, reverse=True)
            new_qty = float(items[0].quantity) + amount
            items[0].quantity = str(int(new_qty)) if new_qty.is_integer() else str(round(new_qty, 1))
    elif mode == 'minus':
        items.sort(key=lambda x: x.exp_date)
        amount_left = amount
        for item in items:
            if amount_left <= 0: break
            qty = float(item.quantity)
            if qty > 0:
                sub = min(qty, amount_left)
                new_qty = qty - sub
                item.quantity = str(int(new_qty)) if new_qty.is_integer() else str(round(new_qty, 1))
                amount_left -= sub

    # 数量が0以下のものを削除
    Inventory.query.filter(Inventory.quantity <= '0').delete(synchronize_session=False)
    Inventory.query.filter(Inventory.quantity == '0.0').delete(synchronize_session=False)
    db.session.commit()
    
    return redirect(url_for('index'))

@app.route('/consume', methods=['POST'])
def consume_item():
    name = request.form.get('item_name')
    try: consume_amount = float(request.form.get('consume_amount', 0))
    except ValueError: consume_amount = 0
    if consume_amount <= 0: return redirect(url_for('index'))
    
    items = Inventory.query.filter_by(name=name).all()
    if not items: return redirect(url_for('index'))
    
    items.sort(key=lambda x: x.exp_date)
    amount_left_to_consume = consume_amount
    actual_consumed = 0
    
    for item in items:
        if amount_left_to_consume <= 0: break
        qty = float(item.quantity)
        if qty > 0:
            sub = min(qty, amount_left_to_consume)
            new_qty = qty - sub
            item.quantity = str(int(new_qty)) if new_qty.is_integer() else str(round(new_qty, 1))
            amount_left_to_consume -= sub
            actual_consumed += sub
            
    if actual_consumed > 0:
        save_consumed({'name': name, 'quantity': actual_consumed, 'unit': items[0].unit, 'category': items[0].category or 'その他'})
        
    Inventory.query.filter(Inventory.quantity <= '0').delete(synchronize_session=False)
    Inventory.query.filter(Inventory.quantity == '0.0').delete(synchronize_session=False)
    db.session.commit()
    
    return redirect(url_for('index'))

@app.route('/delete/<string:name>')
def delete_item(name):
    Inventory.query.filter_by(name=name).delete()
    db.session.commit()
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
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        dish_names = re.findall(r'\*\*(.*?)\*\*', response.text)
        links = [{"name": n, "url": f"https://www.google.com/search?q={urllib.parse.quote(n + ' レシピ')}"} for n in dish_names]
        return jsonify({"answer": response.text, "links": links})
    except:
        return jsonify({"answer": "AIエラーが発生しました。"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
