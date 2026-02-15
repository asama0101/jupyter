
# プロジェクト名：Provisioning Automation System

本システムは、FITELnetルータ等のネットワーク機器に対し、加入者情報（Subscriber）および帯域制御（Traffic Manager/Shaper）の設定を自動反映するためのプロフェッショナルなプロビジョニング・パッケージです。

---

## 1. プロジェクト構造

「責務の分離」を重視し、コード、設定、データ、ログを明確に分けたディレクトリ構成です。

```text
.
├── main_provisioning.sh       # 【メイン】エントリーポイント（全体制御）
├── lib/                       # 【ライブラリ】機能別スクリプト群
│   ├── utils.sh               # 共通基盤（ログ出力、プロジェクトルート特定）
│   ├── remote_fetch.sh        # 外部同期（sync/copyモード対応）
│   ├── scp_transfer.sh        # ルータとのファイル送受信（非対話認証）
│   ├── csv_merge.sh           # CSV統合（ヘッダー削除、.gz自動判別）
│   ├── generate_tm_config.sh  # Config生成（カスコン形式→ルータ形式）
│   ├── fitelnet_api.py        # Python共通APIクラス
│   ├── exec_cmd.py            # コマンド実行エンジン（引数による上書き対応）
│   └── apply_config.py        # 差分反映エンジン（引数による上書き対応）
├── param/config/              # 接続設定定義（remote_router.conf等）
├── vault/                     # セキュリティ情報（.pass_router等のパスワード）
├── data/                      # データストア
│   ├── raw/                   # 同期した未加工のマスターデータ
│   ├── interim/               # 処理中の中間ファイル（差分CFG等）
│   └── processed/             # 反映済みの履歴・バックアップ
└── log/                       # 実行結果（process.log）

```

---

## 2. セットアップ

### 2.1 接続情報の設定 (Config)

`param/config/` 内に、接続先ホストやリモートパスを定義するファイルを作成します。ファイル名は `remote_[識別名].conf` としてください。

**作成例: `remote_router.conf**`

```bash
REMOTE_USER="admin"         # ログインユーザー名
REMOTE_HOST="192.168.1.1"   # ルータのIP
REMOTE_SRC_PATH="/var/cfg"  # ルータ側のファイル保存先（SCPで使用）

```

### 2.2 パスワード管理 (Vault)

セキュリティのため、パスワードは隠しファイルで管理します。改行を入れないよう `printf` で作成し、権限を制限してください。

```bash
printf "MySecurePass123" > ./vault/.pass_router
chmod 700 ./vault
chmod 600 ./vault/.pass_*

```

---

## 3. メインスクリプトの実行と自動運用

### 3.1 手動実行

```bash
./main_provisioning.sh subscriber  # 加入者反映のみ
./main_provisioning.sh shaper      # 帯域制御反映のみ
./main_provisioning.sh all         # 全プロセス実行

```

### 3.2 定期実行 (CRON) の設定

夜間自動実行などを行う場合、絶対パスで指定してください。

```bash
# 毎日AM 2:00に全反映を実行
0 2 * * * /path/to/PAS/main_provisioning.sh all >> /path/to/PAS/log/cron.log 2>&1

```

### 3.3 ログの確認

すべての進捗は `log/process.log` に記録されます。リアルタイム監視には `tail` を使用してください。

```bash
tail -f log/process.log
# [INFO] (緑): 正常終了
# [WARN] (黄): 注意（ファイル不在など）
# [ERROR] (赤): 異常（認証失敗、疎通不可など）

```

---

## 4. 各スクリプトの詳細仕様（メンテナンス用）

### 4.1 外部同期: `lib/remote_fetch.sh`

* **syncモード**: 送信元と「完全に一致」させます。ローカルの不要な古いファイルを自動削除します。
```bash
./lib/remote_fetch.sh sub_db ./data/raw/sub sync "*.csv"

```


* **copyモード**: 「追加・上書き」のみ行います。ローカルの過去分を消したくない（ログ等）場合に使用します。
```bash
./lib/remote_fetch.sh log_svr ./data/raw/logs copy "*.log"

```



### 4.2 非対話転送: `lib/scp_transfer.sh`

* **重要ルール**: ソースコードの引数指定の仕様から、**「ローカルとリモートでファイル名が同一であること」** が前提です。
* **uploadモード**: ローカルからリモートへファイルアップロードします。アップロード先は `REMOTE_SRC_PATH` に固定されます。
```bash
./lib/scp_transfer.sh router upload ./data/interim/config.cfg

```


* **downloadモード**: リモートからローカルへファイルダウンロードします。ダウンロード元は `REMOTE_SRC_PATH` に固定されます。また、ダウンロード時の**ファイル名はリモートと同じにしてください。**
```bash
./lib/scp_transfer.sh router download ./data/raw/running.cfg

```



### 4.3 コマンド実行・反映: `lib/exec_cmd.py` / `lib/apply_config.py`

これらは「接続情報の設定 (Config)」を参照しますが、**引数で接続情報を直接上書き**して実行可能です。

* **引数フラグ**:
| 引数 (短縮 / フル) | 必須 / 任意 | 説明・挙動 |
| --- | --- | --- |
| **`-t`, `--target`** | **必須** | **ターゲット識別名**。`remote_[識別名].conf` および `vault/.pass_[識別名]` を特定するためのキーです。 |
| **`-H`, `--host`** | 任意 | **接続先ホスト (IP)**。設定ファイルの `REMOTE_HOST` を一時的に上書きして接続します。 |
| **`-u`, `--user`** | 任意 | **ユーザー名**。設定ファイルの `REMOTE_USER` を一時的に上書きします。 |
| **`-p`, `--password`** | 任意 | **パスワード**。Vaultファイルを読み込まず、この引数で指定された文字列で認証を試みます。 |



* **実行例 (コマンドの実行**:
```bash
python3 ./lib/exec_cmd.py -t router -c "show running-config"
```

* **実行例 (設定ファイルの送信)**:
```bash
python3 ./lib/apply_config.py -t router -f ./data/interim/diff.cfg
```

* **実行例 (一時的に別のアドレスへコマンド実行)**:
```bash
python3 ./lib/exec_cmd.py -t router -H 10.0.0.1 -c "show version"

```



### 4.4 CSV統合: `lib/csv_merge.sh`

* **機能**: `.gz` 圧縮の自動解凍、2ファイル目以降のヘッダー自動除去。
* **自爆防止**: 入力元と出力先が同じディレクトリの場合、上書きによる無限ループを防ぐためエラー停止します。

---

## 5. 設計思想と安全性

* **べき等性 (Idempotency)**: 現用設定と新設定を比較し、差分（PATCH）のみを反映します。
* **Trapによる保護**: 認証時の一時ファイルは、中断（Ctrl+C）時も必ず自動削除されます。
* **動的ルート特定**: どこから実行しても `PROJ_ROOT` を自動特定し、パス崩れを防ぎます。

---
