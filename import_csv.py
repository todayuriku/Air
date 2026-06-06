import csv
import os
from flask_app import app, db, FoodMaster

def import_master_data():
    filename = 'food_master.csv'
    
    if not os.path.exists(filename):
        print(f"エラー: {filename} が見つかりません。同じフォルダにあるか確認してください。")
        return

    # アプリの裏側（Neonデータベース）に接続して作業を開始
    with app.app_context():
        with open(filename, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)  # 1行目（ヘッダー）を飛ばす
            
            count = 0
            for row in reader:
                # 列が5つ（名前,読み,日数,単位,カテゴリ）ある行だけを処理
                if len(row) >= 5:
                    name = row[0]
                    yomi = row[1]
                    try:
                        exp_days = int(row[2])
                    except ValueError:
                        exp_days = 3
                    unit = row[3]
                    category = row[4]

                    # 既に登録されているかチェック（重複防止）
                    existing = FoodMaster.query.get(name)
                    if not existing:
                        new_food = FoodMaster(name=name, yomi=yomi, exp_days=exp_days, unit=unit, category=category)
                        db.session.add(new_food)
                        count += 1
        
        # 最後に一気に保存
        db.session.commit()
        print(f"🎉 大成功！ {count} 件の食材データをNeonに学習させました！")

if __name__ == '__main__':
    import_master_data()