# Traffic Analysis Toolset

Python 3.8+ | Pandas | Matplotlib

本プロジェクトは、ネットワーク統計データの統合、帯域制御（Shaping/Policing）の精度計算、および多角的な可視化を行うためのエンジニアリング・ツールキットです。

---

## 1. 動作環境と前提条件 (Prerequisites)

本ツールを実行する前に、以下の環境が整っていることを確認してください。

### 実行環境

* **Python**: 3.8 以上 (3.10以降推奨)
* **OS**: Linux (Ubuntu/CentOS), macOS, Windows (WSL2推奨)
* **メモリ**: 8GB以上（100万行を超えるCSVを処理する場合は16GB以上を推奨）

### 依存ライブラリ

```bash
pip install pandas matplotlib

```

### データフォーマットの想定

* **文字コード**: UTF-8 または Shift-JIS (スクリプト内で utf-8-sig を推奨)
* **タイムスタンプ**: ISO8601形式（例: 2026-02-15 15:00:00）または、スクリプト内の rename 処理で変換可能な形式。
* **項目**: 少なくとも「時間」「拠点名(pipe)」「トラフィック量(Byte)」が含まれていること。

---

## 2. スクリプト詳細解説 (Component Deep Dive)

各スクリプトは単一責任の原則に基づき設計されています。

### データパイプライン

#### lib/concat_fixed.py (Data Aggregation)

* **目的**: 期間や拠点ごとに分断されたCSVを、解析可能な単一マスタに統合。
* **参照 (Input)**: data/interim/*.csv （全ファイル）
* **出力 (Output)**: data/processed/combined_data.csv
* **重要機能**:
* **スマート重複排除**: timestamp と pipe を主キーとして重複を排除。同じ時間のデータが複数あってもクリーンな1行にまとめます。
* **パス自動解決**: スクリプトの実行場所に関わらず、プロジェクトルートからの相対パスで data/interim を走査します。



#### lib/merge_csv.py (Metrics Engine)

* **目的**: 異なるソース（例：実流量と理論値）をマージし、精度指標を算出。
* **参照 (Input)**: data/raw/ 内の指定された2ファイル
* **出力 (Output)**: 引数 -o で指定したパス（例: data/interim/result.csv）
* **算出ロジック**:
* **Mbps換算**: 
* **Limit推定**: 特定時間帯（例: 08:00）の平均流量をその日の論理制限値として抽出。
* **Accuracy（精度）**: 以下の式で定義：



※廃棄パケット（Drop）が0の場合は精度0%として正規化します。



### ビジュアライゼーション

すべてのプロットスクリプトは、基本的に data/interim/ の計算済みCSVを参照し、result/ に画像を保存します。

| スクリプト | 特徴 | 分析の狙い |
| --- | --- | --- |
| **plot_line.py** | 折れ線グラフ | 2ソース間のトラフィック乖離（ズレ）の時系列確認。 |
| **plot_bar.py** | 積み上げ棒 | 実流量＋廃棄量をスタックし、帯域上限を突き抜けているかを確認。 |
| **plot_box.py** | 箱ひげ図 | 全拠点の精度偏差を横並びで比較し、不安定な拠点を特定。 |
| **plot_scatter.py** | 散布図 | 流量負荷が増えた際の精度劣化（相関）をプロット。 |
| **plot_heatmap.py** | ヒートマップ | 日付×時間のマトリクスで、特定の時間帯に発生する周期的な異常を検知。 |

---

## 3. ディレクトリ構造 (Layout)

```text
graph-create/
├── data/
│   ├── raw/          # 元データ（マージ前の一次ソース）
│   ├── interim/      # 【入力】解析対象のCSVを配置
│   └── processed/    # 【中間】統合後のマスタ（combined_data.csv）
├── lib/              # 【コア】Pythonロジック
├── result/           # 【出力】生成されたPNGレポート
└── README.md         # 本ドキュメント

```

---

## 4. カスタマイズ・ガイド (For Developers)

### A. 参照・出力先の変更

すべてのスクリプトに共通して、冒頭にディレクトリ定義があります。ここを書き換えることで、任意のフォルダを読み書き対象にできます。

```python
# 各スクリプトの冒頭部分を修正
ROOT_DIR = current_file_path.parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"        # 入力元フォルダ
WORK_DIR = ROOT_DIR / "data" / "interim"    # 読み込み先フォルダ
REPORT_DIR = ROOT_DIR / "result"            # 保存先フォルダ

```

### B. 列名のマッピング変更

lib/merge_csv.py の rename セクションを修正することで、独自のCSV形式に対応可能です。

```python
df1 = df1.rename(columns={
    'タイムスタンプ': 'timestamp',
    # 既存のCSVヘッダーをここに追加
})

```

### C. Mbps計算のインターバル調整

デフォルトは5分（300s）です。1分間隔の場合は 300 を 60 に変更してください。

```python
factor = 8 / (60 * 1000000)

```

---

## 5. 運用上のヒント (Troubleshooting)

* **FileNotFoundError**: スクリプトが ROOT_DIR から見て正しい階層（lib/ フォルダ内）にあるか確認してください。
* **グラフの日付が空になる**: 指定した日付（-d）が、CSV内の timestamp 形式と一致しているか確認してください。
* **結合に時間がかかる**: interim フォルダに数GB単位のデータがある場合、月単位などでフォルダを分けて処理することを推奨します。

