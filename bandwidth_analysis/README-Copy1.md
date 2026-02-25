# 帯域制御装置 トラヒック統計分析

## 目的

新規帯域制御装置の導入可否を判断するため、トラヒック統計情報をグラフ画像に加工して可視化する。

## ディレクトリ構成

```
notebook/bandwidth_analysis/
├── README.md                      # 本ファイル
├── main.ipynb                     # メインノートブック（Jupyter実行用）
├── main.py                        # CLI実行用エントリーポイント
├── src/                           # ロジック・モジュール
│   ├── config.py                  # パス・デフォルト設定管理
│   ├── calc_traffic.py            # 統計計算ロジック
│   ├── sample_data.py             # サンプルデータ生成
│   ├── merge_csv.py               # CSV統合処理
│   └── graphs.py                  # グラフ描画エンジン
├── data/                          # 入力データ
│   ├── new_traffic.csv.gz         # 新規帯域制御装置トラヒック統計
│   ├── current_traffic.csv.gz     # 現行帯域制御装置トラヒック統計
│   ├── bandwidth_limit.csv.gz     # 帯域上限値
│   └── merged_traffic.csv         # 統合CSV（3種を結合、空白→0変換済）
└── output/                        # 出力グラフ画像
    ├── graph1_*_YYYY-MM-DD.png    # 新規vs現行比較
    ├── graph2_*_YYYY-MM-DD.png    # 帯域制御時のトラヒックとlimit
    ├── graph3_boxplot_*.png       # 全ID帯域制御精度(箱ひげ図)
    ├── graph4_*_YYYY-MM-DD.png    # トラヒック量と精度劣化の相関
    └── graph5_heatmap_*.png       # 誤差ヒートマップ(最大14日分)

```

## 処理フロー

```
1. new_traffic.csv.gz  ──┐
2. current_traffic.csv.gz ──┼── [merge_csv.py] ──→ merged_traffic.csv ──→ [graphs.py]
3. bandwidth_limit.csv.gz ──┘    (空白→0変換, Mbps変換列追加)          (グラフ1〜5出力)

```

**グラフ1〜5はすべて `src/merge_csv.py` によって生成された統合CSV (`merged_traffic.csv`) を参照します。**

## 統合CSV仕様 (`merged_traffic.csv`)

| カラム | 元ファイル | 説明 | 単位 |
| --- | --- | --- | --- |
| timestamp | 共通 | 5分間隔のタイムスタンプ | - |
| id | 共通 | 回線番号管理ID (isp-poi_code) | - |
| isp | 共通 | ISP管理ID | - |
| poi_code | 共通 | POI管理ID | - |
| new_volume_in | 新規 | 新規装置: インターネット→ユーザー | Byte |
| new_volume_in_mbps | 新規 | 同上 (Mbps変換済) | Mbps |
| new_volume_out | 新規 | 新規装置: ユーザー→インターネット | Byte |
| new_volume_out_mbps | 新規 | 同上 (Mbps変換済) | Mbps |
| packet_drop_pkt | 新規 | 帯域制御による廃棄パケット数 | Packet |
| packet_drop_byte | 新規 | 帯域制御による廃棄バイト数 | Byte |
| packet_drop_byte_mbps | 新規 | 同上 (Mbps変換済) | Mbps |
| new_pre_control | 新規 | 帯域制限前トラヒック量 (volume_in + drop_byte) | Byte |
| new_pre_control_mbps | 新規 | 同上 (Mbps変換済) | Mbps |
| cur_volume_in | 現行 | 現行装置: インターネット→ユーザー | Byte |
| cur_volume_in_mbps | 現行 | 同上 (Mbps変換済) | Mbps |
| cur_volume_out | 現行 | 現行装置: ユーザー→インターネット | Byte |
| cur_volume_out_mbps | 現行 | 同上 (Mbps変換済) | Mbps |
| limit | 上限値 | 帯域制御の指定帯域 (20分→5分にリサンプリング済) | Mbps |

* 空白(NaN)はすべて **0** に変換済み
* Byte→Mbps変換式: 
* `new_pre_control` = `new_volume_in` + `packet_drop_byte` (帯域制御されなかった場合の推定トラヒック量)

## 出力グラフと見方

### グラフ1: 新規 vs 現行 トラヒック比較

**概要:** 新規帯域制御装置と現行帯域制御装置のvolume_in (受信トラヒック) を1日単位で重ね合わせ、装置間の差分を確認するグラフ。

### グラフ2: 帯域制御時のトラヒック量

**概要:** 帯域制御前の推定トラヒック量 (volume_in + packet_drop_byte) とlimitの関係を確認するグラフ。

### グラフ3: 帯域制御精度 (箱ひげ図)

**概要:** 全IDを横並びで比較し、帯域制御の精度/誤差(%) を統計的に確認するグラフ。

### グラフ4: トラヒック量と精度劣化の相関 (散布図)

**概要:** 帯域制御実行時の受信トラヒック量と制御精度の関係を確認するグラフ。

## 使い方

### Jupyter Notebookで実行する場合

1. `data/` に3つのCSV.gzファイルを配置（サンプルを使う場合は不要）
2. `bandwidth_analysis.ipynb` を開く
3. セルを順に実行する：
* **セットアップ**: `src/` モジュールの読み込みとパス確認
* **サンプルデータ生成**: 必要に応じて実行
* **CSV統合**: 3つのソースを `merged_traffic.csv` に集約
* **グラフ描画**: 各セルの `TARGET_DATE` 等を変更して実行



### CLIから一括実行する場合

ターミナルから以下のコマンドを実行することで、全グラフを一括生成できます。

```bash
source /opt/jupyter/venv/bin/activate
python main.py --all

```

## 必要ライブラリ

* Python 3
* pandas
* matplotlib
* numpy (graphs.py)

---

## 他のCSVデータで使用する際の注意事項

### 1. ファイル形式・ファイル名

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

### 2. 各CSVの必須カラムと仕様

#### new_traffic.csv.gz

| カラム名 | 型 | 単位 | 説明 |
| --- | --- | --- | --- |
| `timestamp` | 文字列 `YYYY-MM-DD HH:MM:SS` | - | **5分間隔**であること |
| `id` | 文字列 | - | `{isp}-{poi_code}` 形式（後述） |
| `volume_in` | 整数（空白可） | **Byte** | 5分間の受信累積バイト数 |
| `volume_out` | 整数（空白可） | **Byte** | 5分間の送信累積バイト数 |
| `packet_drop_pkt` | 整数（空白可） | Packet | 帯域制御による廃棄パケット数 |
| `packet_drop_byte` | 整数（空白可） | **Byte** | 帯域制御による廃棄バイト数 |

#### current_traffic.csv.gz

| カラム名 | 型 | 単位 | 説明 |
| --- | --- | --- | --- |
| `timestamp` | 文字列 `YYYY-MM-DD HH:MM:SS` | - | **5分間隔**であること |
| `isp` | 文字列 | - | ISP管理ID |
| `poi_code` | 文字列/整数 | - | POI管理ID |
| `volume_in` | 整数（空白可） | **Byte** | 5分間の受信累積バイト数 |
| `volume_out` | 整数（空白可） | **Byte** | 5分間の送信累積バイト数 |

#### bandwidth_limit.csv.gz

| カラム名 | 型 | 単位 | 説明 |
| --- | --- | --- | --- |
| `timestamp` | 文字列 `YYYY-MM-DD HH:MM:SS` | - | **20分間隔**であること（ツールが5分にリサンプリング） |
| `id` | 文字列 | - | `{isp}-{poi_code}` 形式（new_traffic の `id` と完全一致） |
| `limit` | 数値 | **Mbps** | 帯域上限値。**Byteではなく Mbps で格納すること** |

> **重要**: `volume_in` / `volume_out` / `packet_drop_byte` は **Byte 単位**、`limit` は **Mbps 単位** と単位が異なる。`limit` を誤って Byte で入れるとグラフの縦軸スケールが著しく狂う。

---

### 3. ID形式の制約

このツールは `id` 列を `{isp}-{poi_code}` 形式として扱い、**最後のハイフン** で isp と poi_code に分割する（`rsplit("-", n=1)`）。

```
例) "AA00-00-2015"  →  isp="AA00-00",  poi_code="2015"   ← 正常
    "ISP-A-POI-01"  →  isp="ISP-A-POI", poi_code="01"    ← poi_codeにハイフン不可
```

**注意点:**

* `new_traffic` の `id` と `bandwidth_limit` の `id` は**完全一致**が必要
* `current_traffic` は `isp` 列と `poi_code` 列が別々に存在し、ツール内で `isp + "-" + poi_code` として結合して id を生成する
* 3ファイル間の id が一致しない場合でもツールは動作するが、**outer join** により不一致レコードは値が 0 に置き換えられ、グラフに無意味なデータが混入する。事前に id の整合性を確認すること

---

### 4. タイムスタンプ間隔の変更

Byte → Mbps の変換式は **5分間隔**を前提としている。

```python
# src/calc_traffic.py
Mbps = Byte × 8 / (5分 × 60秒) / 1,000,000
```

計測間隔が 5 分以外（例: 1 分、10 分）の場合は `src/calc_traffic.py` の `bytes_to_mbps()` および `mbps_to_bytes()` を修正する必要がある。また `bandwidth_limit.csv.gz` の間隔が 20 分以外の場合は `src/merge_csv.py` のリサンプリング処理（`resample("5min")`）も修正が必要。

---

### 5. 対象日付の変更

日付は以下の方法で指定できるため、`config.py` の修正は**任意**（デフォルト値の変更のみ）。

#### CLI の場合（引数で都度指定）

```bash
# グラフ1〜4の対象日を指定
python main.py --graphs --date 2025-03-10

# グラフ5のヒートマップ期間を指定
python main.py --graphs --heatmap-start 2025-03-01 --heatmap-end 2025-03-14

# 日付・ID・ヒートマップ範囲をまとめて指定
python main.py --graphs --date 2025-03-10 --ids AA00-00-2015 --heatmap-start 2025-03-01 --heatmap-end 2025-03-14
```

#### Jupyter Notebook の場合（各グラフセルの変数を変更）

各グラフセル冒頭の変数を変更するだけでよい。`config.py` の修正は不要。

```python
TARGET_DATE = "2025-03-10"   # グラフ1〜4
START_DATE  = "2025-03-01"   # グラフ5
END_DATE    = "2025-03-14"   # グラフ5
```

#### config.py のデフォルト値変更（任意）

引数・変数を毎回変更する手間を省きたい場合のみ、`config.py` を修正する。

```python
# src/config.py
DEFAULT_TARGET_DATE = "2025-01-15"      # グラフ1〜4の対象日（デフォルト）
DEFAULT_HEATMAP_START = "2025-01-15"    # グラフ5の開始日（デフォルト）
DEFAULT_HEATMAP_END = "2025-01-28"      # グラフ5の終了日（デフォルト）
```

---

### 6. タイムゾーンの注意

timestamp はタイムゾーン情報なし（naive datetime）を前提としている。タイムゾーン付き（例: `2025-01-15 00:00:00+09:00`）の timestamp が含まれていると `pandas.to_datetime()` の比較でエラーや意図しない挙動が発生する。使用前にタイムゾーン情報を除去すること。

---

### 7. 空白セルの扱い

`volume_in` 等に空白セルが含まれる場合、ツールは **0 として扱う**。「データなし（欠測）」と「トラヒックが実際に 0」を区別しないため、グラフ上では欠測期間が 0 Mbps として表示される。

---

### 8. カラム名が異なる場合の対応

カラム名のマッピングは `src/merge_csv.py` にハードコードされている。カラム名が異なるCSVを使う場合は、`merge_csv.py` の以下の箇所を修正すること。

#### new_traffic.csv.gz のカラム名を変更する場合

```python
# src/merge_csv.py 63〜64行目付近
# 数値化対象のカラム名リストを変更する
for col in ["volume_in", "volume_out", "packet_drop_pkt", "packet_drop_byte"]:
    df_new[col] = pd.to_numeric(df_new[col], errors="coerce")

# 72〜73行目付近
# id からisp/poi_codeを分解する際のカラム名
df_new["isp"] = df_new["id"].str.rsplit("-", n=1).str[0]
df_new["poi_code"] = df_new["id"].str.rsplit("-", n=1).str[1]

# 85〜91行目付近
# rename でツール内部カラム名にマッピングする
df_new_r = df_new[[
    "timestamp", "id", "isp", "poi_code",
    "volume_in", "volume_out", "packet_drop_pkt", "packet_drop_byte",
]].rename(columns={
    "volume_in": "new_volume_in",
    "volume_out": "new_volume_out",
})
```

#### current_traffic.csv.gz のカラム名を変更する場合

```python
# src/merge_csv.py 65〜66行目付近
for col in ["volume_in", "volume_out"]:
    df_current[col] = pd.to_numeric(df_current[col], errors="coerce")

# 70行目付近
# isp列とpoi_code列を結合してidを生成する
df_current["id"] = df_current["isp"] + "-" + df_current["poi_code"].astype(str)

# 93〜96行目付近
df_cur_r = df_current[["timestamp", "id", "volume_in", "volume_out"]].rename(columns={
    "volume_in": "cur_volume_in",
    "volume_out": "cur_volume_out",
})
```

#### bandwidth_limit.csv.gz のカラム名を変更する場合

```python
# src/merge_csv.py 77〜82行目付近
for cid in df_limit["id"].unique():
    tmp = df_limit[df_limit["id"] == cid].set_index("timestamp")
    ...

# 100〜103行目付近
df_merged = pd.merge(
    df_merged,
    df_limit_5min[["timestamp", "id", "limit"]],   # ← "limit" を変更
    on=["timestamp", "id"],
    how="outer",
)
```

> **注意**: カラム名を変更した後、統合CSV（`merged_traffic.csv`）を再生成（`--merge` または統合セルを再実行）してからグラフを描画すること。

---

### 9. チェックリスト（新しいCSVを使う前に確認）

- [ ] ファイル名が `new_traffic.csv.gz` / `current_traffic.csv.gz` / `bandwidth_limit.csv.gz` であること（または `config.py` を修正済み）
- [ ] 各ファイルが `.csv.gz`（gzip圧縮）形式であること
- [ ] `new_traffic` / `current_traffic` のタイムスタンプが **5分間隔** であること
- [ ] `bandwidth_limit` のタイムスタンプが **20分間隔** であること
- [ ] `volume_in` / `volume_out` / `packet_drop_byte` が **Byte** 単位であること
- [ ] `limit` が **Mbps** 単位であること
- [ ] `id` 形式が `{isp}-{poi_code}` で poi_code にハイフンが含まれないこと
- [ ] 3ファイル間の `id` が一致していること
- [ ] カラム名が異なる場合は `src/merge_csv.py` を修正済みであること
- [ ] 対象日付は CLI 引数または Notebook セル変数で指定すること
- [ ] タイムゾーン情報が timestamp に含まれていないこと
