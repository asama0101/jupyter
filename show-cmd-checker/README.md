# ネットワーク機器ログ自動収集・解析プロジェクト

## 概要

ネットワーク機器への一括コマンド実行、および確認観点に基づいたインタラクティブなHTMLレポートの生成を自動化するツールです。
踏み台経由の `SSH/Telnet` 接続による実機操作をサポートし、セルフチェックを効率化します。

## ディレクトリ構成

```text
project_name/
├── data/              # データ管理
│   ├── raw/           # 元データ（絶対に変更しない / 読み取り専用）
│   ├── interim/       # 中間処理（掃除中・変換中のデータ）
│   └── processed/     # 加工済みデータ（分析にそのまま使える完成品）
├── lib/               # 共通自作関数（.py）
│   ├── login_utils.py # サーバー接続やログイン管理関数
│   └── exe_utils.py   # コマンド実行やレポート生成関数
├── param/             # 分析設定
│   ├── config/        # パラメータファイルの保存先（device.json等）
│   └── cmd/           # コマンドファイルの保存先（commands.txt等）
├── result/            # 成果物（エビデンス、最終レポート、HTML）
├── vault/             # アクセス先のサーバー情報、IP、認証情報
├── .gitignore         # data/ や vault/ をGit管理から外す設定
├── README.md          # プロジェクトの目的、実行方法のメモ
└── 01_log-checker.ipynb

```

### 各ディレクトリの説明

* **data/**: ネットワーク機器から取得したログや、解析対象のファイルを管理します。
* **lib/**: 接続、コマンド実行、HTML整形などのロジックをモジュール化。
* **param/**: 実行したいコマンド定義（`commands.txt`）などを管理。
* **vault/**: 接続先の生IPやパスワードを格納。Git管理から除外。
* **result/**: 実行の都度生成される証跡ログ（.log）や、HTMLレポートが蓄積。

---

## 前提条件 (Prerequisites)

* **Python環境**: Python 3.8 以上
* **必要ライブラリ**:
```bash
pip install netmiko ipython

```


* **ネットワーク疎通**: 実行端末から踏み台サーバへのポート到達性（SSH:22 / Telnet:23等）があること。

---

## 準備手順 (Setup)

実行前に以下の3つのステップを完了させてください。

### 1. 接続先情報の定義 (`vault/device.json`)

`param/config/` ではなく `vault/` 内に作成します。踏み台とターゲットの情報を記述してください。

```json
{
  "jump-server": {
    "device_type": "generic_termserver",
    "host": "192.168.x.x",
    "username": "user",
    "password": "password"
  },
  "target-01": {
    "device_type": "juniper_junos",
    "host": "172.20.x.x",
    "username": "admin",
    "password": "password"
  }
}

```

### 2. 実行コマンドの定義 (`param/cmd/commands.txt`)

`コマンド ;; 確認観点 ;; ハイライトキーワード` の形式で定義します。

```text
show version ;; OSバージョンの確認 ;; 18.2R1.9
show route summary ;; hiddenルートがないことを確認 ;; 0 hidden

```

### 3. 環境の初期化

初回実行前に `result/` ディレクトリが存在することを確認してください（存在しない場合は自動作成されますが、Git管理用に `.gitkeep` 等を置くことを推奨します）。

---

## 実行方法 (Usage)

1. **Notebookの起動**: `01_log-checker.ipynb` を Jupyter 上で開きます。
2. **変数設定**: セル内で `TARGET_NAME` を `device.json` で定義したキー名（例: `"target-01"`）に書き換えます。
3. **一括実行**: 「Run All Cells」をクリックします。
* 踏み台へのログイン、ターゲットへのJump、コマンド実行が順次行われます。


4. **結果確認**:
* Jupyter上に表示されるHTMLレポートでセルフチェックを実施。
* 保存用ファイルは `result/report_[ターゲット名]_[日時].html` として出力されます。



---

## セキュリティ・制限事項

* **Git Security**: `vault/` フォルダは機密情報を含むため、絶対にコミットしないでください。
* **Log Size**: ログ出力が極端に多いコマンド（`show log` 等）は、解析用HTMLの動作を重くする可能性があります。必要に応じて `grep` 等で絞り込んだコマンドを定義してください。
