# CLAUDE.md — リモートファイル転送ツール 要求仕様書

## プロジェクト概要

SCPプロトコルを用いてリモートサーバーとのファイルアップロード・ダウンロードを行う Python ツール。
JupyterNotebook とコマンドライン（CLI）の両環境で動作する。

---

## 対象ユーザー

- エンジニア（CLI操作に慣れている）

---

## 動作環境

| 環境 | 対応内容 |
|------|----------|
| CLI | `python scp_tool.py upload ...` / `python scp_tool.py download ...` |
| Jupyter Notebook | Python モジュールとして import して関数呼び出し |

---

## 接続仕様

- **プロトコル**: SCP（Secure Copy Protocol）
- **認証方式**: パスワード認証
- **接続情報**: ホスト名、ポート番号（デフォルト22）、ユーザー名、パスワード

---

## 機能要件

### 1. ファイルダウンロード

- リモートサーバーから指定ファイル・ディレクトリをローカルへ転送
- 複数ファイルの一括ダウンロード対応
- ディレクトリの再帰的ダウンロード対応
- ワイルドカード・パターン指定対応（例: `*.csv`, `data_2024_*`）

### 2. ファイルアップロード

- ローカルから指定ファイル・ディレクトリをリモートサーバーへ転送
- 複数ファイルの一括アップロード対応
- ディレクトリの再帰的アップロード対応
- ワイルドカード・パターン指定対応

### 3. チェックサム検証（整合性確認）

- 転送前後にファイルのチェックサム（SHA-256）を計算・比較
- 不一致の場合はエラーとして報告

### 4. 転送ログの保存

- 転送日時、方向（upload/download）、ファイルパス、サイズ、結果（成功/失敗）、チェックサム結果をログファイルに記録
- ログは追記形式。ログファイルパスは設定で変更可能（デフォルト: `transfer.log`）

### 5. 転送完了後の通知

- 転送完了時（成功・失敗問わず）にコンソールへサマリーを出力
- Jupyter 環境では HTML/テーブル形式でサマリーを表示（`IPython.display` 利用）

---

## 非機能要件

- **依存ライブラリ**: `netmiko`（SCP/SSH）
- **進捗表示**: `tqdm` は使用不可。独自の進捗出力（標準出力へのシンプルなテキスト表示）で実装すること
- **Python バージョン**: 3.9 以上
- **エラーハンドリング**: 接続失敗・認証失敗・ファイル不存在・チェックサム不一致をそれぞれ明確な例外・エラーメッセージで報告
- **セキュリティ**: パスワードはコード内にハードコードせず、設定ファイル・環境変数・引数から取得

---

## インターフェース仕様

### 設定ファイル（`config.yaml`）

リモートサーバーごとにデフォルト値を定義する。CLI実行時にプロファイル名を指定することで、対応するデフォルト値が自動適用される。

```yaml
profiles:
  production:
    host: prod.example.com
    port: 22
    user: deploy
    remote_base: /var/data/
    local_base: ./downloads/
    log: ./logs/transfer_prod.log
    checksum: true

  staging:
    host: stg.example.com
    port: 2222
    user: admin
    remote_base: /tmp/data/
    local_base: ./staging/
    log: ./logs/transfer_stg.log
    checksum: false

default_profile: staging
```

### CLI

プロファイルのデフォルト値を使いつつ、個別オプションで上書き可能。

```bash
# プロファイルを指定してダウンロード（デフォルト値を使用）
python scp_tool.py download \
  --profile production \
  --remote "*.csv"

# オプションで個別上書き
python scp_tool.py download \
  --profile production \
  --remote "/path/to/remote/*.csv" \
  --local "./custom_dir/" \
  --port 2222 \
  --log "./custom.log" \
  --no-checksum

# アップロード
python scp_tool.py upload \
  --profile staging \
  --local "./data_*.csv"
```

**CLIオプション一覧（すべてオプション、設定ファイルのデフォルト値で補完）:**

| オプション | 説明 | デフォルト |
|------------|------|------------|
| `--profile` | 使用するプロファイル名 | `config.yaml` の `default_profile` |
| `--host` | 接続先ホスト | プロファイルの値 |
| `--port` | ポート番号 | プロファイルの値（未指定時: 22） |
| `--user` | ユーザー名 | プロファイルの値 |
| `--password` | パスワード（未指定時は対話入力） | — |
| `--remote` | リモートパス（ワイルドカード可） | プロファイルの `remote_base` |
| `--local` | ローカルパス | プロファイルの `local_base` |
| `--log` | ログファイルパス | プロファイルの値 |
| `--no-checksum` | チェックサム検証をスキップ | プロファイルの `checksum` |
| `--config` | 設定ファイルパス | `./config.yaml` |

### Python API（Jupyter 向け）

```python
from scp_tool import SCPClient

client = SCPClient(host="example.com", user="admin", password="secret")

# ダウンロード
client.download(remote="/data/*.csv", local="./output/")

# アップロード
client.upload(local="./data/*.csv", remote="/uploads/")
```

---

## ログフォーマット

```
2024-01-15 12:34:56 | DOWNLOAD | /remote/data.csv -> ./local/data.csv | 2.3MB | SUCCESS | SHA256: abc123...
2024-01-15 12:35:10 | UPLOAD   | ./local/report.pdf -> /remote/report.pdf | 512KB | FAILED  | ConnectionError
```

---

## ディレクトリ構成（想定）

```
scp_tool/
├── scp_tool.py        # CLI エントリーポイント
├── client.py          # SCPClient クラス
├── checksum.py        # チェックサム処理
├── logger.py          # ログ管理
├── config.py          # 設定ファイル読み込み・プロファイル管理
├── config.yaml        # サーバープロファイル設定（要編集）
├── transfer.log       # 転送ログ（自動生成）
├── requirements.txt
└── README.md
```

---

## 開発上の注意事項（Claude へ）

- CLI と Jupyter の両方で動作するため、`if __name__ == "__main__":` で CLI 処理を分離し、コアロジックは必ず関数・クラスとして切り出すこと
- Jupyter 環境の検出には `IPython.get_ipython()` を使用する
- 進捗表示は `tqdm` を使わず、標準出力への簡易テキスト（例: `[3/10] uploading data_003.csv...`）で実装すること。Jupyter環境では `IPython.display` を使ってインプレース更新する
- SCP接続には `netmiko` を使用すること（`paramiko` は使用しない）
- 設定ファイルは `PyYAML` で読み込み、プロファイルのデフォルト値と CLI 引数をマージする（CLI引数が優先）
- パスワードが引数にも設定ファイルにも存在しない場合は `getpass` で対話入力を求めること
- パスワードを含む接続情報はログに記録しないこと
- `config.yaml` はサンプルとして `config.yaml.example` をリポジトリに含め、実際の `config.yaml` は `.gitignore` に追加すること
