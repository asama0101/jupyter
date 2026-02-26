# 帯域制御装置 トラヒック統計分析

## 目的

新規帯域制御装置の導入可否を判断するため、トラヒック統計情報をグラフ画像に加工して可視化する。

---

## 1. ディレクトリ構成

```text
notebook/bandwidth_analysis/
├── README.md                      # 本ファイル
├── main.ipynb                     # メインノートブック（Jupyter実行用）
├── main.py                        # CLI実行用エントリーポイント
├── src/
│   ├── merge_csv.py               # 3種のCSV統合とヘッダーマッピング
│   ├── config.py                  # パス・デフォルトパラメータ管理
│   ├── graphs.py                  # グラフ描画エンジン
│   ├── calc_traffic.py            # 物理量変換（Bytes to Mbps）
│   └── sample_data.py             # 動作確認用モックデータ生成
├── data/
│   ├── new_traffic.csv.gz         # 新規帯域制御装置トラヒック統計
│   ├── current_traffic.csv.gz     # 現行帯域制御装置トラヒック統計
│   ├── bandwidth_limit.csv.gz     # 帯域上限値
│   └── merged_traffic.csv         # 統合CSV（3種を結合、空白→0変換済）
└── output/
    ├── graph1_{id}_{YYYY-MM-DD}.png         # 新規vs現行比較（日別）
    ├── graph2_{id}_{YYYY-MM-DD}.png         # 帯域制御時のトラヒックとlimit（日別）
    ├── graph3_boxplot_{id}_{start}_{end}.png # IDごと帯域制御精度（新旧誤差比較）
    └── graph4_scatter_{id}.png              # トラヒック量と精度劣化の相関

```

---

## 2. 処理フロー

```
1. new_traffic.csv.gz  ──┐
2. current_traffic.csv.gz ──┼── [merge_csv.py] ──→ merged_traffic.csv ──→ [graphs.py]
3. bandwidth_limit.csv.gz ──┘    (空白→0変換, Mbps変換列追加)          (グラフ1〜4出力)
```

**グラフ1〜4はすべて `src/merge_csv.py` によって生成された統合CSV (`merged_traffic.csv`) を参照します。**

---

## 3. CSVヘッダーガイド (Schema Mapping)

ベンダー変更等によりCSVのヘッダー名が変更された場合、`src/merge_csv.py` 内の以下の辞書定数を書き換えることで、システム全体を新しいデータ形式に適合させる。

### 3-1. 新規装置統計 (`COL_NEW`)

`new_traffic.csv.gz` に対応。
| 定数内のキー | デフォルトヘッダー名 | 説明 |
| :--- | :--- | :--- |
| `timestamp` | `time_stamp` | 5分粒度の時刻 (YYYY-MM-DD HH:MM:SS) |
| `id` | `subport` | 制御対象の一意識別子 |
| `volume_bytes_in` | `volume_in` | Internet → User 方向の累積バイト数 |
| `volume_bytes_out` | `volume_out` | User → Internet 方向の累積バイト数 |
| `dropped_packets_in` | `dropped_packets_in` | 入力方向の廃棄パケット数 |
| `dropped_bytes_in` | `dropped_bytes_in` | 入力方向の廃棄バイト数 |

### 3-2. 現行装置統計 (`COL_CUR`)

`current_traffic.csv.gz` に対応。
| 定数内のキー | デフォルトヘッダー名 | 説明 |
| :--- | :--- | :--- |
| `timestamp` | `timestamp` | 比較用の既存装置統計の時刻 |
| `id` | `policy_line_key` | 制御対象の一意識別子 |
| `volume_bytes_in` | `volume_in` | 比較用の下り累積バイト数 |
| `volume_bytes_out` | `volume_out` | 比較用の上り累積バイト数 |

### 3-3. 帯域上限値設定 (`COL_LIM`)

`bandwidth_limit.csv.gz` に対応。
| 定数内のキー | デフォルトヘッダー名 | 説明 |
| :--- | :--- | :--- |
| `timestamp` | `timestamp` | 設定変更時刻 |
| `id` | `subport_name` | 制御対象ID |
| `limit_kbps_in` | `pir_value` | 下り方向上限値（kbps） |

### 3-4. 統合CSV

本ファイル (`merged_traffic.csv`) は、**グラフ生成フェーズにおける「唯一の正解（Single Source of Truth）」となる中間データです。**

`merge_csv.py` により生成。

| カラム名 | 単位 | 説明 |
| --- | --- | --- |
| **timestamp** | DateTime | 5分スロットの開始時刻 (YYYY-MM-DD HH:MM:SS) |
| **id** | String | 制御対象の識別子 (例: `AA00-00-2015`) |
| **limit_group** | String | IDから抽出したISP/グループ名 |
| **poi_code** | String | IDから抽出した拠点コード |
| **limit_mbps_in** | Mbps | 下り方向の帯域上限設定値 |
| **new_volume_mbps_in** | Mbps | 新規装置：下り方向の物理実効スループット |
| **new_volume_mbps_out** | Mbps | 新規装置：上り方向の物理実効スループット |
| **new_dropped_mbps_in** | Mbps | 新規装置：下り方向のパケット廃棄量（帯域換算） |
| **new_pre_control_mbps_in** | Mbps | **【推定値】** 下り方向の受信トラヒック推定量（Volume + Drop） |
| **cur_volume_mbps_in** | Mbps | 現行装置：下り方向の物理実効スループット |
| **cur_volume_mbps_out** | Mbps | 現行装置：上り方向の物理実効スループット |
| **new_volume_bytes_in** | Bytes | (参考値) 新規装置の5分間累積入力バイト数 |
| **new_dropped_packets_in** | Packets | (参考値) 新規装置の5分間累積廃棄パケット数 |

基本仕様
* **ファイル形式**: CSV (UTF-8)
* **生成タイミング**: `python main.py --merge` 実行時
* **データ粒度**: 5分間隔（タイムスライス）
* **欠損処理**: 結合時に発生した `NaN` は、トラヒック量に関しては `0`、上限値に関しては `Forward Fill`（前方補完）で処理済み。

---

## 4. 計算ロジック

### 4-1. 帯域速度（Bit per second）

$$Mbps = \frac{\text{Byte数} \times 8 \text{ (bit変換)}}{\text{300秒 (5分)} \times 1,000,000}$$

### 4-2. 制御誤差 (Accuracy Error)

$$Accuracy Error (\%) = \frac{\text{Actual Throughput} - \text{Target Limit}}{\text{Target Limit}} \times 100$$

`limit_mbps_in = 0` の場合は `NaN` として除外する（ゼロ除算回避）。

---

## 5. 使い方

### 5-1. Jupyter Notebookで実行する場合

1. `data/` に3つのCSV.gzファイルを配置（サンプルを使う場合は不要）
2. `main.ipynb` を開く
3. セルを順に実行する：
   * **セットアップ**: `src/` モジュールの読み込みとパス確認
   * **サンプルデータ生成**: 必要に応じて実行
   * **CSV統合**: 3つのソースを `merged_traffic.csv` に集約
   * **グラフ描画**: 各セルの `TARGET_DATE` 等を変更して実行

### 5-2. CLI 運用パターン全網羅

> [!Tip] 仮想環境に必須ライブラリをインストールしている場合、仮想環境を有効化する必要あり。
>
> `source /opt/jupyter/venv/bin/activate`

#### 日付指定の判定ロジック

引数の指定状況によって、グラフごとの対象日が以下のように決まる。

| `--date` | `--start-date` | `--end-date` | G1/G2 の対象 | G3/G4 の対象 |
| :---: | :---: | :---: | --- | --- |
| 省略(デフォルト) | 省略 | 省略 | `DEFAULT_TARGET_DATE` (config.py) の単日 | データ最新日の単日 |
| 指定 | 省略 | 省略 | 指定日の単日 | データ最新日の単日 |
| 任意 | 指定 | 省略 | `--start-date` の単日 | `--start-date` の単日 |
| 任意 | 指定 | 指定 | `--start-date` 〜 `--end-date` の日別出力 | `--start-date` 〜 `--end-date` の集計 |

> **ポイント**:
> - `--start-date` を指定した時点で、G1/G2 も `--date` より優先して複数日モードになる
> - `--end-date` のみ省略した場合は `--start-date` と同日として扱う（単日）
> - `--date` は `--start-date` が未指定のときのみ G1/G2 に適用される

| 分析シナリオ | 実行コマンド | 備考 |
| --- | --- | --- |
| **実データ一括処理** | `python main.py --all` | 統合から全グラフ(G1-G4)作成まで実行。日付はデータ最新日 |
| **日付範囲を指定して一括処理** | `python main.py --all --start-date 2025-01-15 --end-date 2025-01-21` | G1/G2は日別出力、G3/G4は期間全体で出力 |
| **初期テスト・デモ** | `python main.py --sample` → `python main.py --all` | 動作確認用のダミーデータで全工程をテスト |
| **データ統合のみ更新** | `python main.py --merge` | CSVの項目変更や追記を統合データに反映 |
| **グラフ全種を再生成** | `python main.py --graphs` | 統合済みCSVから全IDのG1-G4を一括作成 |
| **特定グラフのみ出力** | `python main.py --select 4` | **G4（散布図）だけ**を素早く出力したい場合 |
| **特定日の詳細調査** | `python main.py --select 1 2 --date 2025-01-20` | 特定の日の時系列比較とスタック図のみ生成 |
| **G1/G2 複数日出力** | `python main.py --select 1 2 --start-date 2025-01-15 --end-date 2025-01-17` | 3日分の比較グラフを日別に出力 |
| **長期精度相関分析** | `python main.py --select 3 4 --start-date 2025-01-10 --end-date 2025-01-16` | G3/G4の複数日集計 |
| **特定拠点の深掘り** | `python main.py --graphs --ids AA00-00-2015` | 特定のIDに絞って全レポートを生成 |

---

## 6. 分析成果物 (Visualization)

| ID | 名称 | 分析の主眼 |
| --- | --- | --- |
| **G1** | 新旧比較 | 装置間のカウンタ同期、パケットドロップ発生の相関。 |
| **G2** | 制御スタック | 物理帯域に対する制限値(Limit)と廃棄量のバランス。 |
| **G3** | 精度分布 | IDごとの制御安定性。新旧2装置の誤差を並列比較。中央値の±10%収束を確認。 |
| **G4** | 負荷相関 | 受信負荷量(Mbps)増大に伴う精度の検知。 |

### グラフ1: 新旧比較 (折れ線グラフ)

新規帯域制御装置と現行帯域制御装置の帯域制御**後**トラヒックを1日単位で重ね合わせ、装置間の差分を確認するグラフ。`--start-date`/`--end-date` 指定時は日別に複数ファイル出力。

### グラフ2: 帯域制御時のトラヒック量 (積み上げ棒グラフ)

帯域制御**前**の推定受信トラヒック量 (volume_mbps_in + dropped_mbps_in) と 上限帯域 (limit_mbps_in) の関係を確認するグラフ。`--start-date`/`--end-date` 指定時は日別に複数ファイル出力。

### グラフ3: 帯域制御精度 (箱ひげ図)

IDごとに個別出力し、`new_dropped_packets_in > 0` のレコードを対象に **新規装置** と **現行装置** それぞれの誤差(%)を1チャート内で並列比較。`--start-date`/`--end-date` で複数日集計に対応。

出力ファイル名: `graph3_boxplot_{id}_{start_date}_{end_date}.png`

### グラフ4: トラヒック量と精度劣化の相関 (散布図)

帯域制御**前**の推定受信トラヒック量と帯域制御の精度/誤差(%) の関係を確認するグラフ。複数日間対応。

---

## 7. 運用チェックリスト

1. **KeyError発生時**: `src/merge_csv.py` の定数とCSVのヘッダー名が1文字ずつ一致しているか確認。
2. **データ更新後**: ヘッダー修正やデータ差し替え後は、必ず `--merge` を実行して `data/merged_traffic.csv` を更新すること。
3. **単位変換**: `src/calc_traffic.py` の変換式が入力単位（Byte/Octet）と整合しているか確認。

---

## 8. 他のCSVデータで使用する際の注意事項

### 8-1. ファイル形式・ファイル名

| 項目 | 仕様 |
| --- | --- |
| **ファイル形式** | `.csv.gz`（gzip圧縮）のみ対応。非圧縮の `.csv` は読み込めない |
| **ファイル名** | `config.py` にハードコードされており変更不可。ファイル名が異なる場合は `config.py` の以下の定数を修正する |

```python
# src/config.py
NEW_TRAFFIC_FILENAME = "new_traffic.csv.gz"
CURRENT_TRAFFIC_FILENAME = "current_traffic.csv.gz"
BANDWIDTH_LIMIT_FILENAME = "bandwidth_limit.csv.gz"
```

---

### 8-2. 各CSVの必須カラムと仕様

#### new_traffic.csv.gz

| カラム名 | 型 | 単位 | 説明 |
| --- | --- | --- | --- |
| `time_stamp` | 文字列 `YYYY-MM-DD HH:MM:SS` | - | **5分間隔**であること |
| `subport` | 文字列 | - | `{isp}-{poi_code}` 形式（後述） |
| `volume_in` | 整数（空白可） | **Byte** | 5分間の受信累積バイト数 |
| `volume_out` | 整数（空白可） | **Byte** | 5分間の送信累積バイト数 |
| `dropped_packets_in` | 整数（空白可） | Packet | 帯域制御による廃棄パケット数 |
| `dropped_bytes_in` | 整数（空白可） | **Byte** | 帯域制御による廃棄バイト数 |

#### current_traffic.csv.gz

| カラム名 | 型 | 単位 | 説明 |
| --- | --- | --- | --- |
| `timestamp` | 文字列 `YYYYMMDDHHmmSS` | - | **5分間隔**であること |
| `policy_line_key` | 文字列 | - | 制御対象ID（new_traffic の `subport` と一致すること） |
| `volume_in` | 整数（空白可） | **Byte** | 5分間の受信累積バイト数 |
| `volume_out` | 整数（空白可） | **Byte** | 5分間の送信累積バイト数 |

#### bandwidth_limit.csv.gz

| カラム名 | 型 | 単位 | 説明 |
| --- | --- | --- | --- |
| `timestamp` | 文字列 `YYYY-MM-DD HH:MM:SS` | - | **20分間隔**であること（ツールが5分にリサンプリング） |
| `subport_name` | 文字列 | - | 制御対象ID（new_traffic の `subport` と完全一致） |
| `pir_value` | 整数 | **kbps** | 帯域上限値 |

> **重要**: `volume_in` / `volume_out` / `dropped_bytes_in` は **Byte 単位**、`pir_value` は **kbps 単位** と単位が異なる。ツール内でMbpsへ自動変換する。

---

### 8-3. ID形式の制約

このツールは `id` 列を `{isp}-{poi_code}` 形式として扱い、**最後のハイフン** で isp と poi_code に分割する（`rsplit("-", n=1)`）。

```
例) "AA00-00-2015"  →  isp="AA00-00",  poi_code="2015"   ← 正常
    "ISP-A-POI-01"  →  isp="ISP-A-POI", poi_code="01"    ← poi_codeにハイフン不可
```

**注意点:**

* `new_traffic` の `subport` と `bandwidth_limit` の `subport_name` は**完全一致**が必要
* `current_traffic` の `policy_line_key` も同じIDと一致していること
* 3ファイル間の id が一致しない場合でも動作するが、不一致レコードは値が 0 になりグラフに無意味なデータが混入する。事前に id の整合性を確認すること

---

### 8-4. タイムスタンプ間隔の変更

Byte → Mbps の変換式は **5分間隔**を前提としている。

```python
# src/calc_traffic.py
Mbps = Byte × 8 / (5分 × 60秒) / 1,000,000
```

計測間隔が 5 分以外（例: 1 分、10 分）の場合は `src/calc_traffic.py` の `bytes_to_mbps()` および `mbps_to_bytes()` を修正する必要がある。また `bandwidth_limit.csv.gz` の間隔が 20 分以外の場合は `src/merge_csv.py` のリサンプリング処理（`resample("5min")`）も修正が必要。

---

### 8-5. 対象日付の変更

日付は以下の方法で指定できるため、`config.py` の修正は**任意**（デフォルト値の変更のみ）。

#### CLI の場合（引数で都度指定）

```bash
# G1/G2 の対象日を指定（単日）
python main.py --graphs --date 2025-03-10

# G1-G4 の日付範囲を指定（複数日）
python main.py --graphs --start-date 2025-03-01 --end-date 2025-03-14

# 日付・IDをまとめて指定
python main.py --graphs --date 2025-03-10 --ids AA00-00-2015
```

#### Jupyter Notebook の場合（各グラフセルの変数を変更）

各グラフセル冒頭の変数を変更するだけでよい。`config.py` の修正は不要。

```python
TARGET_DATE = "2025-03-10"   # G1/G2 の単日指定
START_DATE  = "2025-03-01"   # G3/G4 の開始日
END_DATE    = "2025-03-14"   # G3/G4 の終了日
```

#### config.py のデフォルト値変更（任意）

引数・変数を毎回変更する手間を省きたい場合のみ、`config.py` を修正する。

```python
# src/config.py
DEFAULT_TARGET_DATE = "2025-01-15"   # G1・G2の対象日デフォルト
```

---

### 8-6. タイムゾーンの注意

timestamp はタイムゾーン情報なし（naive datetime）を前提としている。タイムゾーン付き（例: `2025-01-15 00:00:00+09:00`）の timestamp が含まれていると `pandas.to_datetime()` の比較でエラーや意図しない挙動が発生する。使用前にタイムゾーン情報を除去すること。

---

### 8-7. 空白セルの扱い

`volume_in` 等に空白セルが含まれる場合、ツールは **0 として扱う**。「データなし（欠測）」と「トラヒックが実際に 0」を区別しないため、グラフ上では欠測期間が 0 Mbps として表示される。

また **`new_volume_mbps_in` が常に 0 の ID** はグラフ生成対象から自動除外される。

---

### 8-8. カラム名が異なる場合の対応

カラム名のマッピングは `src/merge_csv.py` の辞書定数（`COL_NEW`, `COL_CUR`, `COL_LIM`）にハードコードされている。カラム名が異なるCSVを使う場合は、各辞書の値（デフォルトヘッダー名）を実際のカラム名に書き換えること。

```python
# src/merge_csv.py の定数定義箇所
COL_NEW = {
    "timestamp": "time_stamp",        # ← 実際のカラム名に変更
    "id": "subport",
    "volume_bytes_in": "volume_in",
    "volume_bytes_out": "volume_out",
    "dropped_packets_in": "dropped_packets_in",
    "dropped_bytes_in": "dropped_bytes_in",
}

COL_CUR = {
    "timestamp": "timestamp",
    "id": "policy_line_key",
    "volume_bytes_in": "volume_in",
    "volume_bytes_out": "volume_out",
}

COL_LIM = {
    "timestamp": "timestamp",
    "id": "subport_name",
    "limit_kbps_in": "pir_value",
}
```

> **注意**: カラム名を変更した後、統合CSV（`merged_traffic.csv`）を再生成（`--merge` または統合セルを再実行）してからグラフを描画すること。

---

### 8-9. グラフのタイトル・凡例ラベルを変更する場合

`src/graphs.py` の先頭付近に定義された定数を編集するだけで、全グラフのタイトルと凡例ラベルを一括変更できる。

```python
# src/graphs.py
G1_TITLE         = "Graph 1: New vs Current Traffic - ID: {tid} ({date})"
G1_LABEL_NEW_IN  = "Internet -> User (New)"
# ...（G1〜G4 の全定数）
```

---

### 8-10. チェックリスト（新しいCSVを使う前に確認）

- [ ] ファイル名が `new_traffic.csv.gz` / `current_traffic.csv.gz` / `bandwidth_limit.csv.gz` であること（または `config.py` を修正済み）
- [ ] 各ファイルが `.csv.gz`（gzip圧縮）形式であること
- [ ] `new_traffic` / `current_traffic` のタイムスタンプが **5分間隔** であること
- [ ] `bandwidth_limit` のタイムスタンプが **20分間隔** であること
- [ ] `volume_in` / `volume_out` / `dropped_bytes_in` が **Byte** 単位であること
- [ ] `pir_value` が **kbps** 単位であること
- [ ] `id` 形式が `{isp}-{poi_code}` で poi_code にハイフンが含まれないこと
- [ ] 3ファイル間の `id` が一致していること
- [ ] カラム名が異なる場合は `src/merge_csv.py` を修正済みであること
- [ ] タイムゾーン情報が timestamp に含まれていないこと
