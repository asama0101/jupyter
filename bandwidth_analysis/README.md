# 帯域制御装置 トラヒック統計分析

帯域制御装置の導入可否を判断するため、トラヒック統計情報をグラフ画像に加工して可視化する。

## 1. ディレクトリ構成

```text
notebook/bandwidth_analysis/
├── README.md                      # 本ファイル
├── main.ipynb                     # メインノートブック（Jupyter実行用）
├── main.py                        # CLI実行用エントリーポイント
├── src/
│   ├── merge_csv.py               # 3種のCSV統合とヘッダーマッピング
│   ├── config.py                  # Config: パス・デフォルトパラメータ管理
│   ├── graphs.py                  # Visualization: グラフ描画エンジン
│   ├── calc_traffic.py            # Caluculation: 物理量変換（Bytes to Mbps）
│   └── sample_data.py             # Sample Data: 動作確認用モックデータ生成
├── data/
│   ├── new_traffic.csv.gz         # 新規帯域制御装置トラヒック統計
│   ├── current_traffic.csv.gz     # 現行帯域制御装置トラヒック統計
│   ├── bandwidth_limit.csv.gz     # 帯域上限値
│   └── merged_traffic.csv         # 統合CSV（3種を結合、空白→0変換済）
└── output/
    ├── graph1_*_YYYY-MM-DD.png    # 新規vs現行比較
    ├── graph2_*_YYYY-MM-DD.png    # 帯域制御時のトラヒックとlimit
    ├── graph3_boxplot_*.png       # 全ID帯域制御精度(箱ひげ図)
    └── graph4_*_YYYY-MM-DD.png    # トラヒック量と精度劣化の相関(最大14日分)

```

---

## 2. CSVヘッダーガイド (Schema Mapping)

ベンダー変更等によりCSVのヘッダー名が変更された場合、`src/merge_csv.py` 内の以下の辞書定数を書き換えることで、システム全体を新しいデータ形式に適合させる。

### 2-1. 新規装置統計 (`COL_NEW`)

`new_traffic.csv.gz` に対応。
| 定数内のキー | デフォルトヘッダー名 | 説明 |
| :--- | :--- | :--- |
| `timestamp` | `time_stamp` | 5分粒度の時刻 (YYYY-MM-DD HH:MM:SS) |
| `id` | `subport` | 制御対象の一意識別子 |
| `volume_bytes_in` | `volume_in` | Internet → User 方向の累積バイト数 |
| `volume_bytes_out` | `volume_out` | User → Internet 方向の累積バイト数 |
| `dropped_packets_in` | `dropped_packets_in` | 入力方向の廃棄パケット数 |
| `dropped_bytes_in` | `dropped_bytes_in` | 入力方向の廃棄バイト数 |

### 2-2. 現行装置統計 (`COL_CUR`)

`current_traffic.csv.gz` に対応。
| 定数内のキー | デフォルトヘッダー名 | 説明 |
| :--- | :--- | :--- |
| `timestamp` | `timestamp` | 比較用の既存装置統計の時刻 |
| `isp` | `isp_name` | ID生成用接頭辞 |
| `poi_code` | `poi_code` | ID生成用接尾辞 |
| `volume_in` | `volume_in` | 比較用の下り累積バイト数 |

### 2-3. 帯域上限値設定 (`COL_LIM`)

`bandwidth_limit.csv.gz` に対応。
| 定数内のキー | デフォルトヘッダー名 | 説明 |
| :--- | :--- | :--- |
| `timestamp` | `timestamp` | 設定変更時刻 |
| `id` | `subport_name` | 制御対象ID |
| `limit_kbps` | `pir_value` | 下り方向上限値（kbps） |

### 2-4. 統合CSV 

本ファイル (`merged_traffic.csv`) は、**グラフ生成フェーズにおける「唯一の正解（Single Source of Truth）」となる中間データです。**

`merge_csv.py`により生成。


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

## 3. 計算ロジック

### 3-1. 帯域速度（Bit per second）

$$Mbps = \frac{\text{Byte数} \times 8 \text{ (bit変換)}}{\text{300秒 (5分)} \times 1,000,000}$$

### 3-2. 制御誤差 (Accuracy Error)

$$Accuracy Error (\%) = \frac{\text{Actual Throughput} - \text{Target Limit}}{\text{Target Limit}} \times 100$$

---

## 4. 使い方

### 4-1. Jupyter Notebookで実行する場合

1. `data/` に3つのCSV.gzファイルを配置（サンプルを使う場合は不要）
2. `bandwidth_analysis.ipynb` を開く
3. セルを順に実行する：
* **セットアップ**: `src/` モジュールの読み込みとパス確認
* **サンプルデータ生成**: 必要に応じて実行
* **CSV統合**: 3つのソースを `merged_traffic.csv` に集約
* **グラフ描画**: 各セルの `TARGET_DATE` 等を変更して実行

### 4-2. CLI 運用パターン全網羅

`main.py` で実行可能な全コマンドパターン。

> [!Tip] 仮想環境に必須ライブラリをインストールしている場合、仮想環境を有効化する必要あり。
> 
> `source /opt/jupyter/venv/bin/activate`

| 分析シナリオ | 実行コマンド | 備考 |
| --- | --- | --- |
| **実データ一括処理** | `python main.py --all` | **実データ**の統合から全グラフ(G1-G4)作成まで実行 |
| **初期テスト・デモ** | `python main.py --sample` → `python main.py --all` | 動作確認用のダミーデータで全工程をテスト |
| **データ統合のみ更新** | `python main.py --merge` | CSVの項目変更や追記を統合データに反映 |
| **グラフ全種を再生成** | `python main.py --graphs` | 統合済みCSVから全IDのG1-G4を一括作成 |
| **特定グラフのみ出力** | `python main.py --select 4` | **G4（散布図）だけ**を素早く出力したい場合 |
| **特定日の詳細調査** | `python main.py --select 1 2 --date 2025-01-20` | 特定の日の時系列比較とスタック図のみ生成 |
| **長期精度相関分析** | `python main.py --select 4 --start-date 2025-01-10 --end-date 2025-01-16` | 蓄積データで精度の傾向を確認 |
| **特定拠点の深掘り** | `python main.py --graphs --ids AA00-2015` | 特定のIDに絞って全レポートを生成 |

---

## 5. 分析成果物 (Visualization)

| ID | 名称 | 分析の主眼 |
| --- | --- | --- |
| **G1** | 新旧比較 | 装置間のカウンタ同期、パケットドロップ発生の相関。 |
| **G2** | 制御スタック | 物理帯域に対する制限値(Limit)と廃棄量のバランス。 |
| **G3** | 精度分布 | IDごとの制御安定性。中央値の±10%収束を確認。 |
| **G4** | 負荷相関 | 受信負荷量(Mbps)増大に伴う精度の検知。 |

### グラフ1: 新旧比較 (折れ線グラフ)

新規帯域制御装置と現行帯域制御装置の帯域制御**後**トラヒックを1日単位で重ね合わせ、装置間の差分を確認するグラフ。

### グラフ2: 帯域制御時のトラヒック量 (積み上げ棒グラフ)

帯域制御**前**の推定受信トラヒック量 (volume_mbps_in + dropped_mbps_in) と 上限帯域 (limit_mbps_in) の関係を確認するグラフ。

### グラフ3: 帯域制御精度 (箱ひげ図)

全IDを横並びで比較し、帯域制御の精度/誤差(%) を統計的に確認するグラフ。

### グラフ4: トラヒック量と精度劣化の相関 (散布図)

帯域制御**前**の推定受信トラヒック量と帯域制御の精度/誤差(%) の関係を確認するグラフ。

---

## 6. 運用チェックリスト

1. **KeyError発生時**: `src/merge_csv.py` の定数とCSVのヘッダー名が1文字ずつ一致しているか確認。
2. **データ更新後**: ヘッダー修正やデータ差し替え後は、必ず `--merge` を実行して `data/merged_traffic.csv` を更新すること。
3. **単位変換**: `src/calc_traffic.py` の変換式が入力単位（Byte/Octet）と整合しているか確認。

---
