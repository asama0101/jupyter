"""
main.py - 帯域制御精度分析ツール 実行エントリポイント
===================================================
コマンドラインからCSV統合、グラフ描画（G1-G4）を一括または個別に実行可能。
実データ運用を想定し、サンプル生成は明示的な指定時のみ実行する仕様に変更。

使い方:
    # 1. 実データでの全工程実行 (CSV統合 -> 全グラフG1-G4描画)
    # ※ --ids 指定がない場合は merged_traffic.csv 内の全IDを自動抽出して処理
    python main.py --all

    # 2. データの準備・サンプル生成
    python main.py --sample  # 動作確認用モックデータの生成 (実データがある場合は注意)
    python main.py --merge   # 個別CSVの正規化・結合 (merged_traffic.csv作成)

    # 3. 特定のグラフを選択して実行 (--select で 1, 2, 3, 4 を指定)
    # - 例: 散布図 (G4) のみを長期間指定で作成
    python main.py --select 4 --start-date 2025-01-01 --end-date 2025-01-31
    # - 例: 特定日の時系列比較 (G1) と 精度分布 (G3) を作成
    python main.py --select 1 3 --date 2025-01-20

    # 4. グラフ描画のみを実行 (全種類 G1-G4)
    python main.py --graphs --date 2025-01-20 --ids AA00-00-2015

引数詳細:
    --all         : CSV統合、グラフ描画の全工程を順次実行 (サンプル生成は含まない)
    --sample      : data/ ディレクトリにテスト用のCSVファイルを生成
    --merge       : 異種ソースCSVを統合し、分析用中間ファイルを作成
    --graphs      : 全種類の可視化レポートを生成
    --select      : 描画するグラフ番号を選択 (1, 2, 3, 4 から複数指定可)
    --date        : G1, G2, G3 の対象日 (YYYY-MM-DD)
    --start-date  : G4 の相関分析を開始する日 (YYYY-MM-DD)
    --end-date    : G4 の相関分析を終了する日 (YYYY-MM-DD)
    --ids         : 分析対象とするIDリスト (スペース区切り)。未指定時は全IDを自動抽出。
"""


import argparse
import os
import sys
import pandas as pd

# srcディレクトリをモジュール検索パスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import (
    DATA_DIR, OUTPUT_DIR,
    DEFAULT_TARGET_DATE,
    DEFAULT_SAMPLE_START_DATE, DEFAULT_SAMPLE_NUM_DAYS,
    DEFAULT_SAMPLE_ISP_LIST, DEFAULT_SAMPLE_POI_CODE, DEFAULT_SAMPLE_SEED,
    MERGED_CSV_FILENAME, NEW_TRAFFIC_FILENAME, CURRENT_TRAFFIC_FILENAME, BANDWIDTH_LIMIT_FILENAME
)
from src.sample_data import generate_sample_data
from src.merge_csv import merge_traffic_csv
from src.graphs import (
    plot_graph1, plot_graph2, plot_graph3, plot_graph4
)

def main():
    parser = argparse.ArgumentParser(
        description="Bandwidth Control Precision Analyzer (BCPA) CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # 実行モード
    mode = parser.add_argument_group("Execution Mode")
    # --all からサンプル生成を分離
    mode.add_argument("--all", action="store_true", help="CSV統合と全グラフ描画を実行 (サンプル生成は含みません)")
    mode.add_argument("--sample", action="store_true", help="サンプルデータ生成のみ実行")
    mode.add_argument("--merge", action="store_true", help="CSV統合のみ実行")
    mode.add_argument("--graphs", action="store_true", help="グラフ描画を実行")
    # 特定グラフの選択機能
    mode.add_argument("--select", nargs="+", type=int, choices=[1, 2, 3, 4],
                        help="描画するグラフ番号を選択 (例: --select 1 4)")

    # パラメータ
    params = parser.add_argument_group("Analysis Parameters")
    params.add_argument("--date", default=DEFAULT_TARGET_DATE,
                        help=f"G1-G3用対象日 (YYYY-MM-DD, デフォルト: {DEFAULT_TARGET_DATE})")
    params.add_argument("--start-date", default=None,
                        help="G4用開始日 (YYYY-MM-DD)")
    params.add_argument("--end-date", default=None,
                        help="G4用終了日 (YYYY-MM-DD)")
    params.add_argument("--ids", nargs="+", default=None,
                        help="対象IDリスト (未指定時は全ID)")

    args = parser.parse_args()

    if not (args.all or args.sample or args.merge or args.graphs or args.select):
        parser.print_help()
        sys.exit(0)

    # 1. サンプルデータ生成 (明示的に --sample が指定された時のみ)
    if args.sample:
        print(f"Generating sample data...")
        generate_sample_data(DATA_DIR, DEFAULT_SAMPLE_START_DATE, DEFAULT_SAMPLE_NUM_DAYS,
                             DEFAULT_SAMPLE_ISP_LIST, DEFAULT_SAMPLE_POI_CODE, DEFAULT_SAMPLE_SEED)

    # 2. CSV統合
    if args.all or args.merge:
        print("Merging CSV files...")
        merge_traffic_csv(os.path.join(DATA_DIR, NEW_TRAFFIC_FILENAME),
                          os.path.join(DATA_DIR, CURRENT_TRAFFIC_FILENAME),
                          os.path.join(DATA_DIR, BANDWIDTH_LIMIT_FILENAME),
                          os.path.join(DATA_DIR, MERGED_CSV_FILENAME))

    # 3. グラフ描画
    if args.all or args.graphs or args.select:
        merged_path = os.path.join(DATA_DIR, MERGED_CSV_FILENAME)
        if not os.path.exists(merged_path):
            print(f"Error: {merged_path} がありません。先に --merge を実行してください。")
            sys.exit(1)

        df = pd.read_csv(merged_path, parse_dates=["timestamp"])
        target_ids = args.ids if args.ids else df["id"].unique()
        s_date = args.start_date if args.start_date else df["timestamp"].min().strftime("%Y-%m-%d")
        e_date = args.end_date if args.end_date else df["timestamp"].max().strftime("%Y-%m-%d")

        # 描画対象グラフの決定
        # --select があればそれを優先、なければ 1-4 すべて
        selected_graphs = args.select if args.select else [1, 2, 3, 4]

        print(f"--- Analysis Execution ---")
        print(f"Selected Graphs: {selected_graphs}")

        # G3 (Boxplot) はループ外
        if 3 in selected_graphs:
            print("Plotting Graph 3 (Boxplot)...")
            plot_graph3(df, target_date=args.date, output_dir=OUTPUT_DIR)

        # 各IDごとのループ
        for tid in target_ids:
            print(f"Processing ID: {tid}")
            if 1 in selected_graphs:
                plot_graph1(df, target_date=args.date, output_dir=OUTPUT_DIR, target_ids=[tid])
            if 2 in selected_graphs:
                plot_graph2(df, target_date=args.date, output_dir=OUTPUT_DIR, target_ids=[tid])
            if 4 in selected_graphs:
                plot_graph4(df, start_date=s_date, end_date=e_date, output_dir=OUTPUT_DIR, target_ids=[tid])

        print(f"\nCompleted. Outputs: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()