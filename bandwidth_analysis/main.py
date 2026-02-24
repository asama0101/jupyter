"""
main.py - CLIエントリーポイント
===============================
コマンドラインから全処理（サンプルデータ生成・CSV統合・グラフ描画）を
一括実行、または個別に実行できる。

使い方:
    # 全処理を一括実行（サンプルデータ生成→CSV統合→全グラフ描画）
    python main.py --all

    # サンプルデータ生成のみ
    python main.py --sample

    # CSV統合のみ（3種のCSV.gzが既にdata/にある前提）
    python main.py --merge

    # グラフ描画のみ（統合CSVが既にdata/にある前提）
    python main.py --graphs

    # 日付やIDを指定して実行
    python main.py --all --date 2025-01-20 --ids AA00-00-2015 BB01-01-2015

    # ヒートマップの日付範囲を指定
    python main.py --graphs --heatmap-start 2025-01-15 --heatmap-end 2025-01-28
"""

import argparse
import os
import sys

import pandas as pd

# このファイルからの相対インポートを可能にする
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import (
    DATA_DIR, OUTPUT_DIR,
    DEFAULT_TARGET_DATE, DEFAULT_HEATMAP_START, DEFAULT_HEATMAP_END,
    DEFAULT_SAMPLE_START_DATE, DEFAULT_SAMPLE_NUM_DAYS,
    DEFAULT_SAMPLE_ISP_LIST, DEFAULT_SAMPLE_POI_CODE, DEFAULT_SAMPLE_SEED,
    NEW_TRAFFIC_FILENAME, CURRENT_TRAFFIC_FILENAME,
    BANDWIDTH_LIMIT_FILENAME, MERGED_CSV_FILENAME,
    ensure_dirs,
)
from src.sample_data import generate_sample_data
from src.merge_csv import merge_traffic_csv
from src.graphs import plot_graph1, plot_graph2, plot_graph3, plot_graph4, plot_graph5


def run_sample(args):
    """サンプルデータを生成する。"""
    ensure_dirs()
    print("=" * 60)
    print("サンプルデータ生成")
    print("=" * 60)
    result = generate_sample_data(
        data_dir=DATA_DIR,
        start_date=DEFAULT_SAMPLE_START_DATE,
        num_days=DEFAULT_SAMPLE_NUM_DAYS,
        isp_list=DEFAULT_SAMPLE_ISP_LIST,
        poi_code=DEFAULT_SAMPLE_POI_CODE,
        seed=DEFAULT_SAMPLE_SEED,
    )
    print(f"  IDs: {result['ids']}")
    print(f"  新規トラヒック: {result['num_rows_new']} rows -> {result['new_traffic_path']}")
    print(f"  現行トラヒック: {result['num_rows_current']} rows -> {result['current_traffic_path']}")
    print(f"  帯域上限値: {result['num_rows_limit']} rows -> {result['bandwidth_limit_path']}")
    print()


def run_merge(args):
    """3種CSVを統合CSVにマージする。"""
    ensure_dirs()
    print("=" * 60)
    print("CSV統合")
    print("=" * 60)
    new_path = os.path.join(DATA_DIR, NEW_TRAFFIC_FILENAME)
    cur_path = os.path.join(DATA_DIR, CURRENT_TRAFFIC_FILENAME)
    lim_path = os.path.join(DATA_DIR, BANDWIDTH_LIMIT_FILENAME)
    out_path = os.path.join(DATA_DIR, MERGED_CSV_FILENAME)

    for p in [new_path, cur_path, lim_path]:
        if not os.path.exists(p):
            print(f"  ERROR: {p} が見つかりません。先に --sample を実行してください。")
            return None

    df = merge_traffic_csv(new_path, cur_path, lim_path, out_path)
    print(f"  レコード数: {len(df)}")
    print(f"  カラム: {list(df.columns)}")
    print(f"  ID一覧: {df['id'].unique().tolist()}")
    print(f"  期間: {df['timestamp'].min()} ~ {df['timestamp'].max()}")
    print(f"  出力先: {out_path} ({os.path.getsize(out_path):,} bytes)")
    print()
    return df


def run_graphs(args, df=None):
    """全グラフを描画する。"""
    ensure_dirs()
    print("=" * 60)
    print("グラフ描画")
    print("=" * 60)

    # 統合CSVの読み込み（dfが渡されていない場合）
    if df is None:
        csv_path = os.path.join(DATA_DIR, MERGED_CSV_FILENAME)
        if not os.path.exists(csv_path):
            print(f"  ERROR: {csv_path} が見つかりません。先に --merge を実行してください。")
            return
        df = pd.read_csv(csv_path, parse_dates=["timestamp"])

    target_date = args.date
    target_ids = args.ids if args.ids else None
    hm_start = args.heatmap_start
    hm_end = args.heatmap_end

    # --- グラフ1 ---
    print(f"  Graph 1: New vs Current ({target_date})")
    files = plot_graph1(df, target_date, OUTPUT_DIR, target_ids)
    for f in files:
        print(f"    -> {os.path.basename(f)}")

    # --- グラフ2 ---
    print(f"  Graph 2: Stacked bar + limit ({target_date})")
    files = plot_graph2(df, target_date, OUTPUT_DIR, target_ids)
    for f in files:
        print(f"    -> {os.path.basename(f)}")

    # --- グラフ3 ---
    print(f"  Graph 3: Boxplot ({target_date})")
    fpath = plot_graph3(df, target_date, OUTPUT_DIR)
    print(f"    -> {os.path.basename(fpath)}")

    # --- グラフ4 ---
    print(f"  Graph 4: Scatter ({target_date})")
    files = plot_graph4(df, target_date, OUTPUT_DIR, target_ids)
    for f in files:
        print(f"    -> {os.path.basename(f)}")

    # --- グラフ5 ---
    print(f"  Graph 5: Heatmap ({hm_start} ~ {hm_end})")
    files = plot_graph5(df, hm_start, hm_end, OUTPUT_DIR, target_ids)
    for f in files:
        print(f"    -> {os.path.basename(f)}")

    print()
    print("完了!")


def main():
    parser = argparse.ArgumentParser(
        description="帯域制御装置トラヒック統計分析ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python main.py --all                          # 全処理を一括実行
  python main.py --sample                       # サンプルデータ生成のみ
  python main.py --merge                        # CSV統合のみ
  python main.py --graphs                       # グラフ描画のみ
  python main.py --graphs --date 2025-01-20     # 日付指定でグラフ描画
  python main.py --graphs --ids AA00-00-2015    # ID指定でグラフ描画
        """,
    )

    # 実行モード
    mode = parser.add_argument_group("実行モード（1つ以上を指定）")
    mode.add_argument("--all", action="store_true", help="全処理を一括実行")
    mode.add_argument("--sample", action="store_true", help="サンプルデータ生成")
    mode.add_argument("--merge", action="store_true", help="CSV統合")
    mode.add_argument("--graphs", action="store_true", help="グラフ描画")

    # パラメータ
    params = parser.add_argument_group("パラメータ")
    params.add_argument("--date", default=DEFAULT_TARGET_DATE,
                        help=f"グラフ1-4の対象日 (YYYY-MM-DD, デフォルト: {DEFAULT_TARGET_DATE})")
    params.add_argument("--ids", nargs="+", default=None,
                        help="対象IDリスト (スペース区切り, デフォルト: 全ID)")
    params.add_argument("--heatmap-start", default=DEFAULT_HEATMAP_START,
                        help=f"グラフ5の開始日 (デフォルト: {DEFAULT_HEATMAP_START})")
    params.add_argument("--heatmap-end", default=DEFAULT_HEATMAP_END,
                        help=f"グラフ5の終了日 (デフォルト: {DEFAULT_HEATMAP_END})")

    args = parser.parse_args()

    # 何も指定されていない場合はヘルプ表示
    if not (args.all or args.sample or args.merge or args.graphs):
        parser.print_help()
        return

    df = None

    if args.all or args.sample:
        run_sample(args)

    if args.all or args.merge:
        df = run_merge(args)

    if args.all or args.graphs:
        run_graphs(args, df)


if __name__ == "__main__":
    main()
