# net_collector

踏み台サーバ経由でCisco・Juniperなどのネットワーク機器にtelnet/SSHで接続し、
コマンドを実行して結果を収集・保存・差分表示するツールです。

## 機能

- **マルチホップ接続**: telnet/SSHの踏み台を複数経由して機器に接続
- **コマンド実行**: YAMLで定義したコマンドを順次実行・保存
- **差分表示**: 過去の実行結果との差分をハイライト表示
- **Jupyter対応**: キーワードハイライト付きHTML表示 + 確認観点表示
- **CLI対応**: `python main.py` でコマンドライン実行

## ディレクトリ構成

```
net_collector/
├── CLAUDE.md               # 要求仕様書
├── README.md               # 本ファイル
├── requirements.txt        # 依存パッケージ
├── main.py                 # CLIエントリーポイント
├── main.ipynb              # Jupyter使用例ノートブック
├── execution.log           # 実行ログ
├── configs/
│   ├── hosts.yaml          # 接続先設定（踏み台・機器）
│   ├── commands.yaml       # コマンド定義
│   └── review_points.yaml  # レビュー確認観点定義
├── src/
│   ├── __init__.py         # NetCollector クラス（Jupyter向け）
│   ├── config.py           # 設定ファイル読み込み
│   ├── connector.py        # 接続管理（Telnet/SSH チェーン）
│   ├── executor.py         # コマンド実行
│   └── output.py           # 出力保存・差分表示
└── outputs/                # コマンド出力保存先
    └── {device_name}/
        └── {YYYYMMDD_HHMMSS}/
            └── {command_name}.txt
```

## セットアップ

### 仮想環境の有効化

```bash
source /opt/jupyter/venv/bin/activate
```

### 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

## 設定ファイルの編集

### `configs/hosts.yaml` — 接続先設定

```yaml
bastions:
  - name: bastion-1
    host: 192.168.3.23
    port: 23
    protocol: telnet   # ssh or telnet
    username: sysope
    password: "P!ssw0rd1234"

devices:
  - name: vmx1
    host: 172.20.20.2
    port: 22
    protocol: ssh
    vendor: juniper    # cisco / juniper / generic
    username: admin
    password: "admin@123"
```

### `configs/commands.yaml` — コマンド定義

```yaml
commands:
  - name: show_version
    command: "show version"
    vendor: juniper    # 省略時は全ベンダー共通
    keywords:
      - word: "JUNOS"
        color: "blue"
```

## 実行方法

### CLI

```bash
# 仮想環境を有効化
source /opt/jupyter/venv/bin/activate

# 機器にコマンドを実行して保存
python main.py --host vmx1

# 差分表示モード（指定タイムスタンプとの比較）
python main.py --host vmx1 --diff 20260223_100000

# 出力先を指定
python main.py --host vmx1 --output-dir /var/log/netcollector

# 確認プロンプトをスキップ（自動化向け）
python main.py --host vmx1 --no-confirm
```

### Jupyter ノートブック

```bash
# ノートブックサーバを起動
jupyter notebook main.ipynb
```

```python
from src import NetCollector

nc = NetCollector(
    hosts_file="configs/hosts.yaml",
    commands_file="configs/commands.yaml",
    review_file="configs/review_points.yaml",
)

# 接続・実行（Yes/No 確認あり）
result = nc.run(device="vmx1")

# 結果を表示（キーワードハイライト + 確認観点）
result.show()

# 差分表示（直前の保存データと比較）
result.diff()

# 特定タイムスタンプと比較
result.diff("20260223_100000")
```

## 接続方式

| 踏み台プロトコル | 機器プロトコル | 実装 |
|---|---|---|
| SSH のみ | SSH / Telnet | Paramiko ProxyJump + Netmiko |
| Telnet あり | SSH / Telnet | ソケットベース対話セッション |

## 対応機器

| vendor 設定値 | 機器タイプ |
|---|---|
| `juniper` | Juniper JunOS（vMX 等） |
| `cisco` | Cisco IOS / IOS-XE |
| `generic` | その他汎用機器 |
