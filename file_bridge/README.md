# file_bridge — SCP ファイル転送ツール

SCP プロトコルを使ってリモートサーバーとのファイル転送を行う Python ツールです。
CLI（コマンドライン）と Jupyter Notebook の両環境で動作します。

---

## 特徴

- **ダウンロード / アップロード** — ワイルドカード（`*.csv` 等）と再帰的ディレクトリ転送に対応
- **チェックサム検証** — 転送前後に SHA-256 ハッシュを比較し、整合性を保証
- **転送ログ** — 日時・ファイルパス・サイズ・結果・チェックサムをファイルに記録
- **Jupyter 対応** — HTML テーブル形式のサマリーをノートブック内に表示
- **プロファイル管理** — `config.yaml` に複数サーバーの設定を定義し、名前で切り替え

---

## 動作環境

| 項目 | 要件 |
|------|------|
| Python | 3.9 以上 |
| 依存ライブラリ | `netmiko >= 4.0.0`, `PyYAML >= 6.0` |
| 対応環境 | CLI / Jupyter Notebook |
| プロトコル | SCP（Secure Copy Protocol）|
| 認証方式 | パスワード認証 |

---

## インストール

```bash
pip install -r requirements.txt
```

> **仮想環境を使用している場合:**
> ```bash
> # 例：既存の venv を使用
> /opt/jupyter/venv/bin/pip install -r requirements.txt
> ```

---

## セットアップ

### 1. 設定ファイルを作成

サンプルをコピーして編集します。

```bash
cp config.yaml.example config.yaml
```

`config.yaml`（`git` 管理外・編集必須）:

```yaml
profiles:
  myserver:
    host: 192.168.1.100      # リモートサーバーの IP またはホスト名
    port: 22                  # SSH ポート番号
    user: username            # SSH ユーザー名
    password: "your_password" # パスワード（省略時は環境変数・対話入力）
    remote_base: /data/       # リモートのデフォルトディレクトリ
    local_base: ./downloads/  # ローカルのデフォルトディレクトリ
    log: ./logs/transfer.log  # 転送ログファイルのパス
    checksum: true            # SHA-256 チェックサム検証を有効にするか

default_profile: myserver
```

> **セキュリティ:** `config.yaml` は `.gitignore` に登録済みです。
> パスワードは設定ファイルの代わりに環境変数 `SCP_PASSWORD` でも指定できます。

```bash
export SCP_PASSWORD="your_password"
```

---

## 使い方

### CLI

```bash
# プロファイルを使ってダウンロード
python3 main.py download --profile myserver --remote "/data/*.csv"

# ローカル保存先を指定
python3 main.py download --profile myserver \
  --remote "/data/*.csv" \
  --local "./output/"

# チェックサム検証をスキップ
python3 main.py download --profile myserver \
  --remote "/data/large_file.bin" \
  --no-checksum

# アップロード（ワイルドカード対応）
python3 main.py upload --profile myserver \
  --local "./reports/*.pdf" \
  --remote "/uploads/"

# プロファイルを使わずに直接指定
python3 main.py download \
  --host 192.168.1.100 --user admin --password "pass" \
  --remote "/data/file.txt" --local "./downloads/"
```

**CLI オプション一覧:**

| オプション | 説明 | デフォルト |
|------------|------|------------|
| `--profile` | 使用するプロファイル名 | `default_profile` の値 |
| `--host` | 接続先ホスト | プロファイルの値 |
| `--port` | SSH ポート番号 | プロファイルの値（未指定時: 22）|
| `--user` | ユーザー名 | プロファイルの値 |
| `--password` | パスワード | 環境変数 `SCP_PASSWORD` → 対話入力 |
| `--remote` | リモートパス（ワイルドカード可）| プロファイルの `remote_base` |
| `--local` | ローカルパス | プロファイルの `local_base` |
| `--log` | ログファイルパス | プロファイルの `log` |
| `--no-checksum` | SHA-256 検証をスキップ | プロファイルの `checksum` |
| `--config` | 設定ファイルパス | `./config.yaml` |

### Jupyter Notebook

```python
from src.client import SCPClient

# クライアントを作成
client = SCPClient(
    host="192.168.1.100",
    user="username",
    password="your_password",
    port=22,
    log_file="./logs/transfer.log",
    use_checksum=True,
)

# ダウンロード（ワイルドカード対応）
results = client.download(remote="/data/*.csv", local="./output/")

# アップロード
results = client.upload(local="./reports/*.pdf", remote="/uploads/")

# 結果の確認
for r in results:
    status = "✓" if r["success"] else "✗"
    print(f"{status} {r.get('remote', r.get('local'))}")
```

Jupyter 環境では転送完了後に HTML テーブル形式のサマリーが自動表示されます。

---

## ディレクトリ構成

```
file_bridge/
├── main.py            # CLI エントリーポイント（python3 main.py で起動）
├── main.ipynb         # Jupyter Notebook 版エントリーポイント
├── config.yaml        # 実際の接続設定（.gitignore 対象・要作成）
├── config.yaml.example # 設定ファイルのテンプレート（Git 管理対象）
├── requirements.txt   # 依存ライブラリ
├── .gitignore
├── README.md
└── src/               # ソースコードパッケージ
    ├── __init__.py    # パッケージ定義（SCPClient をエクスポート）
    ├── client.py      # SCPClient クラス
    ├── checksum.py    # SHA-256 チェックサム計算・検証
    ├── logger.py      # 転送ログ管理（TransferLogger / TransferRecord）
    ├── config.py      # 設定ファイル読み込みとプロファイル管理
    └── cli.py         # CLI コマンド定義（argparse）
```

自動生成されるディレクトリ（初回実行時に作成）:

```
file_bridge/
├── downloads/         # ダウンロードファイルの保存先（デフォルト）
└── logs/
    └── transfer.log   # 転送ログ
```

---

## 転送ログ

`logs/transfer.log` に以下の形式で追記されます。

```
2026-02-23 14:50:01 | DOWNLOAD | /remote/data.csv -> downloads/data.csv | 1.1KB | SUCCESS | SHA256: 9fa61f73...
2026-02-23 14:50:02 | UPLOAD   | ./local/report.pdf -> /remote/report.pdf | 512KB | FAILED  | Connection reset by peer
```

| フィールド | 説明 |
|-----------|------|
| 日時 | `YYYY-MM-DD HH:MM:SS` 形式 |
| 方向 | `DOWNLOAD` または `UPLOAD` |
| パス | `転送元 -> 転送先` |
| サイズ | ファイルサイズ（B / KB / MB / GB）|
| 結果 | `SUCCESS` または `FAILED` |
| チェックサム | SHA-256 ハッシュ または エラーメッセージ |

---

## エラーと対処法

| エラー | 原因 | 対処法 |
|--------|------|--------|
| `Authentication failed` | パスワードが間違っている | `--password` または `SCP_PASSWORD` を確認 |
| `Connection timed out` | ホストに到達できない | `--host` と `--port` を確認 |
| `FileNotFoundError` | リモート/ローカルにファイルが存在しない | パスとワイルドカードを確認 |
| `チェックサム不一致` | 転送中にデータ破損 | 再転送を実行 |
| `KeyError: プロファイルが見つかりません` | `--profile` 名が誤っている | `config.yaml` のプロファイル名を確認 |

---

## セキュリティ注意事項

- **パスワードをコード内にハードコードしないでください。**
- `config.yaml` には実際のパスワードを記載できますが、Git にコミットしないよう `.gitignore` に登録済みです。
- パスワードの管理には環境変数 `SCP_PASSWORD` の使用を推奨します。
- SSH ホストの公開鍵が変わった場合は接続に失敗します（中間者攻撃の防止）。

---

## ライセンス

MIT License
