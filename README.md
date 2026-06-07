
# AiR - スマート冷蔵庫管理アプリ 

AiR（エアー）は、家庭の冷蔵庫の在庫をスマートに管理し、日々の食費や消費傾向を可視化するWebアプリケーションです。最新の生成AIを活用したレシート読み取りやレシピ提案機能も搭載しています。

##主な機能

* **在庫管理**
    * 食材ごとの数量、賞味期限、保存状態（未開封・冷凍など）を管理。
    * 消費期限が近いものを自動でハイライト表示（安全・注意・期限切れ等）。
* **🧾 AIレシート解析**
    * スマートフォンのカメラ等で撮影したレシート画像をアップロードするだけで、AI（Gemini 2.5 Flash）が自動で「食品・食材」のみを抽出し、在庫と食費履歴に一括登録します。
* **AIレシピ提案**
    * 現在の冷蔵庫の在庫状況をもとに、AIが作れるレシピを3つ提案。「買い物なし」「時短」などの条件指定も可能です。
* **グラフ・統計ダッシュボード**
    * 自炊（レシート）と外食の支出比較グラフ（先月/今月、年間推移）。
    * よく消費する食材のトップ5ランキング（グラム、パックなどの単位別）。
* **食材マスター管理**
    * よく使う食材の名前、ふりがな、デフォルトの賞味期限、単位、カテゴリをマスターとして管理。五十音順やカテゴリ順でのソートが可能です。

##技術スタック

* **Backend:** Python 3, Flask, SQLAlchemy
* **Database:** Neon (Serverless PostgreSQL)
* **AI / LLM:** Google Gemini API (`google-genai` SDK / `gemini-2.5-flash` モデル)
* **Data Visualization:** Matplotlib, Seaborn
* **Frontend:** HTML5, CSS3, Vanilla JavaScript
* **Hosting:** Render

## 📁 主要なディレクトリ構成

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
1 リポジトリのクローン
git clone [https://github.com/yourusername/AiR.git](https://github.com/yourusername/AiR.git)
cd AiR
2 依存パッケージをインストールする
pip install -r requirements.txt



