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

### グラフ5: 誤差ヒートマップ (最大14日間)

**概要:** 14日間の誤差 (%) を時間×日付のヒートマップで可視化し、精度劣化のパターンを確認するグラフ。

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
python main.py --all

```

## 必要ライブラリ

* Python 3
* pandas
* matplotlib
* numpy (graphs.py)

