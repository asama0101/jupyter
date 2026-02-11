# rsync ファイル同期プロジェクト

## 概要

リモートサーバから特定のファイルを `rsync` を用いて取得する自動化ツールです。
SSH鍵が登録できない環境でも動作するよう、`pexpect` によるパスワード自動入力をサポートしています。また、`--itemize-changes` オプションにより、**実際にダウンロードされたファイルのみ**をログに記録します。

## ディレクトリ構成

```text
project_name/
├── data/                   # 各種データ格納（未使用）
│   ├── raw/                # 転送後の一次データ
│   ├── interim/            # 中間処理データ
│   └── processed/          # 最終処理データ
├── lib/                    # 自作ライブラリ
│   ├── rsync_utils.py      # 同期処理本体（CLI実行対応）
│   └── logger_config.py    # 共通ロギング設定
├── param/                  # パラメータ・外部コマンド設定（未使用）
│   ├── config/             # 設定テンプレート
│   └── cmd/                # 外部コマンドテンプレート
├── results/                # 実行結果、集計レポート等
├── vault/                  # 機密情報（config.json 等を格納：Git除外）
├── .gitignore              # data/ や vault/ を管理対象外に設定
├── README.md               # 本ドキュメント
├── 01_rsync-download.ipynb # 手動実行・疎通確認用Notebook
└── run_sync.sh             # CRON用実行スクリプト

```

---

## 実行方法

### 1. Jupyter Notebook からの実行

`01_rsync-download.ipynb` を開き、各セルを順に実行してください。

* **セル1**: モジュールのインポートと環境確認
* **セル2**: `vault/config.json` の読み込み（ファイルがない場合は自動で雛形を作成し停止します）
* **セル3**: 同期の実行と結果確認

### 2. コマンドライン（CLI）からの直接実行

`lib/rsync_utils.py` は、単体で実行することも可能です。`vault/config.json` を参照するように `__main__` ブロックを記述しています。

```bash
# プロジェクトルートへ移動
$ cd /home/jupyter_projects/download-files/

# PYTHONPATHにlibを追加して実行
$ export PYTHONPATH=$PYTHONPATH:$(pwd)/lib
$ python3 lib/rsync_utils.py

```

---

## CRON による定期実行設定

サーバーで毎日決まった時間に自動実行する場合の設定例です。

### 1. 実行用シェルスクリプトの作成

環境変数のパスを通すため、ラッパースクリプト（例: `run_sync.sh`）を作成することをお勧めします。

```bash
#!/bin/bash
# 目的：環境変数を設定し、同期スクリプトを安全に実行する
# 使い方：sh run_sync.sh または crontabから呼び出し

PROJECT_DIR="/home/jupyter_projects/download-files"
cd $PROJECT_DIR

# PYTHONPATHの設定（自作モジュールの場所を教える）
export PYTHONPATH=$PYTHONPATH:$PROJECT_DIR/lib

# 実行（標準出力とエラーをログに流す）
/usr/bin/python3 lib/rsync_utils.py >> $PROJECT_DIR/result/cron_shell.log 2>&1

```

### 2. crontab への登録

```bash
$ crontab -e

```

以下の1行を末尾に追加（例：毎日深夜 02:00 に実行）

```text
00 02 * * * /bin/bash /home/jupyter_projects/download-files/run_sync.sh

```

---

## モジュール仕様

### `lib/rsync_utils.py`

#### `rsync_pull(conf)`

* **目的**: 設定辞書に基づき `rsync` を実行し、新規ダウンロードファイルのみを抽出してログに記録する。
* **使い方**: インポートして辞書形式の設定を渡す。
* **引数**:
* `conf` (dict): `REMOTE_USER`, `REMOTE_HOST`, `PASSWORD`, `SRC_DIR`, `DEST_DIR`, `BW_LIMIT`, `EXT_FILTER` 等を含む。


* **返り値**:
* `str`: 実行結果メッセージ（成功時は "Success: ..."、失敗時は "Error: ..."）。



---

## セキュリティ上の注意

* **vault/** フォルダにはパスワードが含まれるため、絶対に Git 等のリポジトリにコミットしないことを推奨します。
* `.gitignore` に以下の記述があることを確認してください：
```text
vault/
data/
__pycache__/

```
