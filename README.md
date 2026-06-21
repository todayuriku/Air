
# AiR - スマート冷蔵庫管理アプリ 

AiR（エアー）は、家庭の冷蔵庫の在庫をスマートに管理し、日々の食費や消費傾向を可視化するWebアプリケーションです。最新の生成AIを活用したレシート読み取りやレシピ提案機能も搭載しています。

## 主な機能

* **在庫管理**
    * 食材ごとの数量、賞味期限、保存状態（未開封・冷凍など）を管理。
    * 消費期限が近いものを自動でハイライト表示（安全・注意・期限切れ等）。
* **AIレシート解析**
    * スマートフォンのカメラ等で撮影したレシート画像をアップロードするだけで、AI（Gemini 2.5 Flash）が自動で「食品・食材」のみを抽出し、在庫と食費履歴に一括登録します。
* **AIレシピ提案**
    * 現在の冷蔵庫の在庫状況をもとに、AIが作れるレシピを3つ提案。「買い物なし」「時短」「期限が近い物から消費」などの条件指定も可能です。
* **グラフ・統計ダッシュボード**
    * 自炊（レシート）と外食の支出比較グラフ（先月/今月、年間推移）。
    * よく消費する食材のトップ5ランキング（グラム、パックなどの単位別）。

## 技術スタック

* **Backend:** Python 3, Flask, SQLAlchemy
* **Database:** Neon (Serverless PostgreSQL)
* **AI / LLM:** Google Gemini API (`google-genai` SDK / `gemini-2.5-flash` モデル)
* **Data Visualization:** Matplotlib, Seaborn
* **Frontend:** HTML5, CSS3, Vanilla JavaScript
* **Hosting:** Render

## 主要なディレクトリ構成

```text
project/
├── flask_app.py        # アプリケーションのメインロジック
├── requirements.txt    # 依存ライブラリ一覧
├── static/
│   ├── css/            # スタイルシート
│   ├── js/             # フロントエンドのスクリプト
│   ├── images/         # アイコン画像等のアセット
│   └── fonts/          # グラフ描画用の日本語フォント (NotoSansJP-Regular.ttf)
└── templates/
    └── index.html      # メイン画面のHTMLテンプレート
```

## 環境構築と起動方法
**1 リポジトリのクローン**
```bash
git clone [https://github.com/yourusername/AiR.git](https://github.com/yourusername/AiR.git)
cd AiR
```
**2 依存パッケージをインストールする**
```bash
pip install -r requirements.txt
  ```
**3 プロジェクトルートに .env ファイルを作成し、以下の環境変数を設定します。**
```Ini, TOML
GEMINI_API_KEY=your_google_gemini_api_key
# Neonのデータベース接続URLを登録
DATABASE_URL=postgresql://your_neon_database_url
APP_PASSWORD=your_basic_auth_password
```
**4 アプリケーションを起動します。**
```bash
python flask_app.py
```
**5 ブラウザで http://localhost:5000 にアクセスします。**

## Renderへのデプロイ
このアプリケーションは Render でのホスティングに最適化されています。

**1 Renderのダッシュボードから Web Service を新規作成し、GitHubリポジトリを連携します。**

**2 2Environment Variables に以下の3つを設定します。**
* GEMINI_API_KEY
* DATABASE_URL (Neonの接続文字列)
* APP_PASSWORD

**3 Start Command を以下のように設定します。**
```bash
gunicorn flask_app:app --bind 0.0.0.0:$PORT
```
**4 デプロイを実行します。**

