# ディレクトリ構成

```
project_name/
├── data/              # データ管理
│   ├── raw/           # 元データ（絶対に変更しない / 読み取り専用）
│   ├── interim/       # 中間処理（掃除中・変換中のデータ）
│   └── processed/     # 加工済みデータ（分析にそのまま使える完成品）
├── lib/               # 共通自作関数（.py）
│   ├── __init__.py    # パッケージとして認識させるためのファイル
│   ├── data_loader.py # サーバー接続やデータ読み込み関数
│   └── utils.py       # グラフ描画や便利な汎用関数
├── param/             # 分析設定（パラメータ、列名の定義、YAML等）
│   ├── config/        # パラメータファイルの保存先
│   └── cmd/           # コマンドファイルの保存先
├── result/            # 成果物（グラフ、図、最終レポート、提出用CSV）
├── vault/             # アクセス先のサーバー情報、IP、認証情報
├── .gitignore         # data/ や vault/ をGit管理から外す設定
├── README.md          # プロジェクトの目的、実行方法のメモ
├── 1.0-data-cleaning.ipynb
├── 2.0-exploration.ipynb
└── 3.0-modeling.ipynb

```