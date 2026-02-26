"""
main.py - 帯域制御精度分析ツール 実行エントリポイント
===================================================
コマンドラインからCSV統合、グラフ描画（G1-G4）を一括または個別に実行可能。
実データ運用を想定し、サンプル生成は明示的な指定時のみ実行する仕様。

使い方:
    # 1. 実データでの全工程実行 (CSV統合 -> 全グラフG1-G4描画)
    # ※ --ids 指定がない場合は merged_traffic.csv 内の全IDを自動抽出して処理
    python main.py --all

    # 1-b. 開始日と終了日を指定して全工程実行（G3/G4 が複数日対応、G1/G2 も複数日出力）
    python main.py --all --start-date 2025-01-15 --end-date 2025-01-21

    # 2. データの準備・サンプル生成
    python main.py --sample  # 動作確認用モックデータの生成 (実データがある場合は注意)
    python main.py --merge   # 個別CSVの正規化・結合 (merged_traffic.csv作成)

    # 3. 特定のグラフを選択して実行 (--select で 1, 2, 3, 4 を指定)
    # - 例: 散布図 (G4) のみを長期間指定で作成
    python main.py --select 4 --start-date 2025-01-01 --end-date 2025-01-31
    # - 例: 特定日の時系列比較 (G1) と 精度分布 (G3) を作成
    python main.py --select 1 3 --date 2025-01-20
    # - 例: G1/G2 を複数日まとめて作成
    python main.py --select 1 2 --start-date 2025-01-15 --end-date 2025-01-17

    # 4. グラフ描画のみを実行 (全種類 G1-G4)
    python main.py --graphs --date 2025-01-20 --ids AA00-00-2015

引数詳細:
    --all         : CSV統合、グラフ描画の全工程を順次実行 (サンプル生成は含みません)
    --sample      : data/ ディレクトリにテスト用のCSVファイルを生成
    --merge       : 異種ソースCSVを統合し、分析用中間ファイルを作成
    --graphs      : 全種類の可視化レポートを生成
    --select      : 描画するグラフ番号を選択 (1, 2, 3, 4 から複数指定可)
    --date        : G1, G2 の対象日 (YYYY-MM-DD)。--start-date/--end-date 指定時は上書きされる
    --start-date  : 分析開始日 (YYYY-MM-DD)。省略時はデータ最新日
    --end-date    : 分析終了日 (YYYY-MM-DD)。省略時は --start-date と同日
    --ids         : 分析対象とするIDリスト (スペース区切り)。未指定時は有効ID全自動抽出。
"""


import argparse
import logging
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
    MERGED_CSV_FILENAME, NEW_TRAFFIC_FILENAME, CURRENT_TRAFFIC_FILENAME, BANDWIDTH_LIMIT_FILENAME,
)
from src.sample_data import generate_sample_data
from src.merge_csv import merge_traffic_csv
from src.graphs import (
    plot_graph1, plot_graph2, plot_graph3, plot_graph4,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    """
    帯域制御精度分析ツールのCLIエントリポイント。

    Returns:
        None
    """
    parser = argparse.ArgumentParser(
        description="Bandwidth Control Precision Analyzer (BCPA) CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # 実行モード
    mode = parser.add_argument_group("Execution Mode")
    mode.add_argument("--all", action="store_true",
                      help="CSV統合と全グラフ描画を実行 (サンプル生成は含みません)")
    mode.add_argument("--sample", action="store_true",
                      help="サンプルデータ生成のみ実行")
    mode.add_argument("--merge", action="store_true",
                      help="CSV統合のみ実行")
    mode.add_argument("--graphs", action="store_true",
                      help="グラフ描画を実行")
    mode.add_argument("--select", nargs="+", type=int, choices=[1, 2, 3, 4],
                      help="描画するグラフ番号を選択 (例: --select 1 4)")

    # パラメータ
    params = parser.add_argument_group("Analysis Parameters")
    params.add_argument("--date", default=DEFAULT_TARGET_DATE,
                        help=(
                            f"G1・G2の対象日 (YYYY-MM-DD, デフォルト: {DEFAULT_TARGET_DATE})。"
                            "--start-date / --end-date を指定するとそちらが優先される"
                        ))
    params.add_argument("--start-date", default=None,
                        help="分析開始日 (YYYY-MM-DD)。省略時はデータ最新日")
    params.add_argument("--end-date", default=None,
                        help="分析終了日 (YYYY-MM-DD)。省略時は --start-date と同日")
    params.add_argument("--ids", nargs="+", default=None,
                        help="対象IDリスト (未指定時は new_volume_mbps_in が有効な全IDを自動抽出)")

    args = parser.parse_args()

    if not (args.all or args.sample or args.merge or args.graphs or args.select):
        parser.print_help()
        sys.exit(0)

    # 1. サンプルデータ生成 (明示的に --sample が指定された時のみ)
    if args.sample:
        logger.info("Generating sample data...")
        generate_sample_data(DATA_DIR, DEFAULT_SAMPLE_START_DATE, DEFAULT_SAMPLE_NUM_DAYS,
                             DEFAULT_SAMPLE_ISP_LIST, DEFAULT_SAMPLE_POI_CODE, DEFAULT_SAMPLE_SEED)

    # 2. CSV統合
    if args.all or args.merge:
        logger.info("Merging CSV files...")
        merge_traffic_csv(
            os.path.join(DATA_DIR, NEW_TRAFFIC_FILENAME),
            os.path.join(DATA_DIR, CURRENT_TRAFFIC_FILENAME),
            os.path.join(DATA_DIR, BANDWIDTH_LIMIT_FILENAME),
            os.path.join(DATA_DIR, MERGED_CSV_FILENAME),
        )

    # 3. グラフ描画
    if args.all or args.graphs or args.select:
        merged_path = os.path.join(DATA_DIR, MERGED_CSV_FILENAME)
        if not os.path.exists(merged_path):
            logger.error(f"Error: {merged_path} がありません。先に --merge を実行してください。")
            sys.exit(1)

        df = pd.read_csv(merged_path, parse_dates=["timestamp"])

        # new_volume_mbps_in が常に 0 の ID はグラフ生成対象外
        all_ids = df["id"].unique()
        valid_ids = [
            tid for tid in all_ids
            if df[df["id"] == tid]["new_volume_mbps_in"].max() > 0
        ]
        if args.ids:
            # ユーザー指定IDのうち有効なものだけ使用
            target_ids = [tid for tid in args.ids if tid in valid_ids]
            excluded = [tid for tid in args.ids if tid not in valid_ids]
            if excluded:
                logger.warning(f"以下のIDは new_volume_mbps_in=0 のためスキップ: {excluded}")
        else:
            target_ids = valid_ids

        if not target_ids:
            logger.warning("有効な対象IDがありません。処理を終了します。")
            sys.exit(0)

        # 日付範囲の決定
        # --start-date 省略時はデータ最新日をデフォルトとする
        max_date = df["timestamp"].max().strftime("%Y-%m-%d")
        s_date = args.start_date or max_date
        # --end-date 省略時は start_date と同日（単日扱い）
        e_date = args.end_date or s_date

        # G1/G2: --date が基本（単日）。--start-date が指定されたら複数日モード（end は e_date）
        g12_start = s_date if args.start_date else args.date
        g12_end   = e_date if args.start_date else args.date

        # G3/G4: --start-date/--end-date の範囲をそのまま使用
        g34_start = s_date
        g34_end   = e_date

        # 描画対象グラフの決定
        # --select があればそれを優先、なければ 1-4 すべて
        selected_graphs = args.select if args.select else [1, 2, 3, 4]

        logger.info("--- Analysis Execution ---")
        logger.info(f"Selected Graphs : {selected_graphs}")
        logger.info(f"Target IDs      : {target_ids}")
        logger.info(f"G1/G2 date range: {g12_start} ~ {g12_end}")
        logger.info(f"G3/G4 date range: {g34_start} ~ {g34_end}")

        # IDごとのループ（全グラフ共通）
        for tid in target_ids:
            logger.info(f"Processing ID: {tid}")
            if 1 in selected_graphs:
                plot_graph1(df, start_date=g12_start, end_date=g12_end,
                            output_dir=OUTPUT_DIR, target_ids=[tid])
            if 2 in selected_graphs:
                plot_graph2(df, start_date=g12_start, end_date=g12_end,
                            output_dir=OUTPUT_DIR, target_ids=[tid])
            if 3 in selected_graphs:
                plot_graph3(df, start_date=g34_start, end_date=g34_end,
                            output_dir=OUTPUT_DIR, target_ids=[tid])
            if 4 in selected_graphs:
                plot_graph4(df, start_date=g34_start, end_date=g34_end,
                            output_dir=OUTPUT_DIR, target_ids=[tid])

        logger.info(f"\nCompleted. Outputs: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
