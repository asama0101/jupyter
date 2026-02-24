# CLAUDE.md — ネットワーク機器コマンド収集ツール 要求仕様書

## 概要

踏み台サーバ経由でCisco・Juniper等のネットワーク機器にtelnet/SSHで接続し、コマンドを実行して結果を取得するツール。JupyterノートブックとCLI（コマンドライン）の両方で動作する。

---

## ユーザー

- ネットワークエンジニア（技術レベル：高）
- Jupyterノートブック上での作業確認と、CLIでの自動化・定期実行の両用途で使用する

---

## アーキテクチャ方針

- コアロジックはPythonライブラリとして実装し、Jupyter・CLIの両方から呼び出せるようにする
- Jupyter用：ノートブック内でimportして使用。出力はセル内に整形表示
- CLI用：コマンドラインから実行可能なエントリーポイントを提供

---

## 接続仕様

### 踏み台サーバへの接続
- プロトコル：telnet / SSH（両方サポート）
- 認証：パスワード認証のみ

### ネットワーク機器への接続
- プロトコル：telnet / SSH（両方サポート）
- 認証：パスワード認証のみ
- 対応メーカー：Cisco、Juniper、その他メーカー（設定ファイルで機器タイプを指定）
- Cisco特有：enable（特権モード）への昇格をサポート。enableパスワードは設定ファイルで管理

### 接続フロー
- 踏み台サーバは**1台以上の複数台経由**をサポートする
- 踏み台を順番にホップしながら最終的にネットワーク機器へ到達する

```
ローカル → 踏み台1（telnet or SSH）→ 踏み台2（telnet or SSH）→ … → ネットワーク機器（telnet or SSH）
```

- 踏み台が1台のみの場合も同じ設定構造で記述できる（リストの要素を1つにするだけ）
- 各踏み台で個別にプロトコル・認証情報を設定できる

---

## 設定ファイル仕様

設定ファイルはYAML形式。接続先管理とコマンド定義は**別ファイル**に分離する。

### 1. 接続先設定ファイル（例：`hosts.yaml`）

```yaml
# 踏み台サーバはリスト形式で定義（上から順に経由する）
bastions:
  - name: bastion-1
    host: 192.168.0.1
    port: 22
    protocol: ssh   # ssh or telnet
    username: user1
    password: pass1

  - name: bastion-2
    host: 10.10.0.1
    port: 23
    protocol: telnet
    username: user2
    password: pass2

devices:
  - name: core-sw-01
    host: 10.0.0.1
    port: 23
    protocol: telnet   # ssh or telnet
    vendor: cisco
    username: admin
    password: pass
    enable_password: enablepass  # Cisco専用（不要な場合は省略）

  - name: edge-router-01
    host: 10.0.0.2
    port: 22
    protocol: ssh
    vendor: juniper
    username: admin
    password: pass
```

### 2. コマンド定義ファイル（例：`commands.yaml`）

```yaml
commands:
  - name: show_version
    command: "show version"
    vendor: cisco      # 特定ベンダー向け（省略時は全ベンダー共通）
    keywords:
      - word: "Version"
        color: "blue"
      - word: "Uptime"
        color: "green"

  - name: show_interfaces
    command: "show interfaces"
    keywords:
      - word: "down"
        color: "red"
      - word: "up"
        color: "green"

  - name: show_route
    command: "show ip route"
    vendor: cisco
    # keywordsを省略した場合はハイライトなし

  - name: show_route_juniper
    command: "show route"
    vendor: juniper
```

### 3. レビュー定義ファイル（例：`review_points.yaml`）

```yaml
review_points:
  - name: show_version
    points:
      - "JUNOSバージョンが想定通りであることを確認する"
      - "稼働時間(uptime)が著しく短くないことを確認する（直近の再起動有無）"
      - "Kernelバージョンに既知の脆弱性・不具合がないことを確認する"

  - name: show_interfaces
    points:
      - "Link downのインタフェースが想定外でないことを確認する"
      - "Admin upかつLink downの組み合わせがある場合は要調査"
      - "不明なインタフェースが追加・削除されていないことを確認する"

  - name: show_route
    points:
      - "経路数が想定通りであることを確認する"
      - "デフォルトルートの有無を確認する"
      - "意図しない経路の追加・消失がないことを確認する"

  - name: show_bgp_summary
    points:
      - "BGPセッションが全てEstablishedになっていることを確認する"
      - "Idle / Active状態のピアがある場合は障害として要調査"
      - "受信・送信経路数が想定通りであることを確認する"
```

---

## 機能要件

### 1. コマンド実行
- 指定した機器に対して、コマンド定義ファイルのコマンドを順次実行する
- 設定変更コマンド（config系）も実行可能とする
- Ciscoのenable昇格が必要な場合、コマンド実行前に自動でenableモードに移行する
- 実行ログ（接続開始・完了・エラー）を標準エラー出力またはログファイルに出力する

### 2. 出力保存
- プロンプト+コマンドとコマンドの実行結果をテキストファイルとして保存する
- 保存先ディレクトリ・ファイル名は以下の形式：
  ```
  outputs/{device_name}/{YYYYMMDD_HHMMSS}/{command_name}.txt
  ```

### 3. 差分表示
- 今回の実行結果と指定した日時の保存したファイルを比較し、差分をdiff形式で表示する
- 差分はターミナル/Jupyterの両方で確認できる形式で出力する
- 差分がない場合は「変更なし」と表示する

### 4. Jupyter向け表示
- コマンド出力結果をセル内に表示する
- 差分はハイライト付きで表示する（追加行：緑、削除行：赤）
- レビュー定義ファイルの確認観点（points:）を表示する
- ログインとコマンド実行の間にYes/Noの確認を挟む

### 5. CLI向け表示
- コマンド出力結果を標準出力に表示する
- 差分はunified diff形式でターミナルに表示する
- 実行ログ（接続開始・完了・エラー）を標準エラー出力またはログファイルに出力する
- ログインとコマンド実行の間にYes/Noの確認を挟む

### 6. エラー処理
- 接続失敗・認証エラーが発生した場合は**処理を止める**（後続機器への実行もしない）
- エラー内容（機器名・エラー種別・メッセージ）を明示する

---

## 非機能要件

- 複数機器への一括並列実行は**対象外**（順次・単機器実行のみ）
- パスワード等の認証情報はYAMLファイルで管理（将来的な環境変数対応は考慮しておく）
- Python 3.8以上を対象とする
- 依存ライブラリ：
    - `netmiko`（telnet/SSH）`PyYAML`、`difflib`は使用可能
    - `telnetlib` or `telnetlib3`（telnet）は使用不可

---

## ディレクトリ構成（想定）

```
project/
├── CLAUDE.md               # 本仕様書
├── configs/
│   ├── hosts.yaml          # 接続先設定
│   ├── commands.yaml       # コマンド定義
│   └── review_points.yaml  # レビュー定義
├── src/
│   ├── __init__.py
│   ├── connector.py        # 踏み台・機器への接続処理
│   ├── executor.py         # コマンド実行処理
│   ├── output.py           # 出力保存・差分表示
│   └── config.py           # 設定ファイル読み込み
├── main.py                 # CLIエントリーポイント
├── main.ipynb              # Jupyter使用例ノートブック
├── execution.log           # 実行ログ
└── outputs/                # コマンド出力保存先
    └── {device_name}/
        └── {YYYYMMDD_HHMMSS}/
            └── {command_name}.txt
```

---

## CLIインターフェース（想定）

```bash
# 指定した機器に全コマンドを実行（コマンドファイルの指定も可能）
python cli.py --host core-sw-01

# 差分表示モード
python cli.py --host core-sw-01 --diff "YYYYMMDD_HHMMSS"

# 出力保存先を指定
python cli.py --host core-sw-01 --output-dir /var/log/netcollector
```

---

## Jupyter使用例（想定）

```python
from netcollector import NetCollector

nc = NetCollector(hosts_file="hosts.yaml", commands_file="commands.yaml")

# 接続・実行
result = nc.run(device="core-sw-01")

# 出力表示（整形）
result.show()

# 差分表示
result.diff()
```

---

## 将来拡張の考慮事項（実装対象外・設計時に意識する）

- 認証情報の環境変数・Vaultからの取得
- 複数機器への一括実行
- 定期実行（cronやスケジューラ連携）
- テキストパース（TextFSM / NTC Templates）による構造化出力
- Jupyter向け表示のキーワード箇所ハイライト化
    - `keywords` は省略可能。省略した場合はハイライトなし
    - `color` には色名（`red` / `green` / `blue` / `yellow` / `orange` 等）を指定する
    - キーワードの大文字・小文字は区別しない（case-insensitive）

