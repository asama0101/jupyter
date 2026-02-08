# ディレクトリ構成

```
project_name/
├── data/
│   ├── raw/
│   ├── interim/
│   └── processed/
├── lib/                    # 共通自作関数（.py）
│   └── rsync_utils.py      # `rsync`で差分データをダウンロードする関数
├── param/
│   ├── config/
│   └── cmd/
├── results/                # ダウンロードファイルの保存先
├── vault/
├── .gitignore              # data/ や vault/ をGit管理から外す設定
├── README.md               # プロジェクトの目的、実行方法のメモ
└── 01_rsync-download.ipynb # `rsync_utils.py`を呼び出し、任意の場所からファイルダウンロードするnotebook

```