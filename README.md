# ディレクトリ構成

```
project_name/
├── data/
│   ├── raw/
│   ├── interim/       # 中間処理データ
│   └── processed/
├── notebooks/         # 役割ごとに番号を振る
│   ├── 1.0-data-cleaning.ipynb
│   ├── 2.0-exploration.ipynb
│   └── 3.0-modeling.ipynb
├── src/               # 共通で使う自作関数（.py）を置く
│   ├── __init__.py
│   ├── data_loader.py
│   └── utils.py
├── outputs/           # グラフやモデルの保存先
│   ├── figures/       # 可視化結果（png等）
│   └── models/        # 学習済みモデル（pkl等）
├── .gitignore         # data/などをGit管理から外す
└── README.md
```