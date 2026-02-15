import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mtick
from pathlib import Path
import argparse
import sys

# ==============================================================================
# NAME
#    plot_bar.py - Traffic Stacked Bar Chart Generator
#
# SYNOPSIS
#    python3 plot_bar.py --file <CSV_FILE> --date <YYYY-MM-DD> [OPTIONS]
#
# DESCRIPTION
#    指定された結果CSVを読み込み、特定の日付のトラフィック推移(積み上げ棒グラフ)を生成する。
#    左軸(ax1)にトラフィック量(Mbps)、右軸(ax2)に精度(Accuracy%)を表示する。
#    --pipe の指定がない場合は、全pipeに対して個別にグラフを生成し保存する。
#
# OPTIONS
#    -f, --file   読み込むCSVファイル名 (data/interim フォルダ内を想定)
#    -d, --date   対象年月日 (YYYY-MM-DD 形式)
#    -p, --pipe   特定のパイプ名のみ出力する場合に指定 (省略時は全実行)
#
# EXAMPLE
#    python3 plot_bar.py -f result.csv -d 2025-10-01
#    python3 plot_bar.py -f result.csv -d 2025-10-01 -p ISP-A_Kanagawa-01
# ==============================================================================

# ディレクトリ設定
current_file_path = Path(__file__).resolve()
ROOT_DIR = current_file_path.parent.parent
WORK_DIR = ROOT_DIR / "data" / "interim"
REPORT_DIR = ROOT_DIR / "result"

def main():
    # --- 引数の解析 ---
    parser = argparse.ArgumentParser(
        description='トラフィック推移グラフ(積み上げ棒)生成ツール',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('-f', '--file', type=str, required=True, help='読み込むCSVファイル名 (必須)')
    parser.add_argument('-d', '--date', type=str, required=True, help='対象年月日 (必須)\n形式: YYYY-MM-DD')
    parser.add_argument('-p', '--pipe', type=str, default=None, help='特定のパイプ名のみ出力 (任意)')
    args = parser.parse_args()

    # --- データ読み込み ---
    csv_path = WORK_DIR / args.file
    if not csv_path.exists():
        print(f"ERROR: File not found: {csv_path}")
        sys.exit(1)

    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # --- 抽出期間の設定 ---
    start_dt = pd.to_datetime(f"{args.date} 00:00:00")
    end_dt   = pd.to_datetime(f"{args.date} 23:55:00")

    # 対象となるPipeのリストを作成
    target_pipes = [args.pipe] if args.pipe else df['pipe'].unique()

    # 保存先フォルダの作成
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    for pipe_name in target_pipes:
        # データの絞り込み
        mask = (df['pipe'] == pipe_name) & \
               (df['timestamp'] >= start_dt) & \
               (df['timestamp'] <= end_dt)
        plot_df = df[mask].sort_values('timestamp')

        if plot_df.empty:
            print(f"SKIP: No data for {pipe_name} on {args.date}")
            continue

        # --- 描画処理 ---
        fig, ax1 = plt.subplots(figsize=(15, 7))

        # 左軸 (ax1): トラヒック量と廃棄量の積み上げ棒グラフ & Limit線
        ax1.bar(plot_df['timestamp'], plot_df['rx_MBps_x'], 
                label='Data1 (Main)', color='tab:blue', alpha=0.7, width=0.003)
        ax1.bar(plot_df['timestamp'], plot_df['rx_drop_MBps'], 
                bottom=plot_df['rx_MBps_x'], 
                label='Data1 (drop)', color='tab:orange', alpha=0.7, width=0.003)
        ax1.plot(plot_df['timestamp'], plot_df['limit'], 
                 label='Limit', color='tab:red', linestyle='--', alpha=0.8)

        # 右軸 (ax2): Accuracy
        ax2 = ax1.twinx()
        ax2.plot(plot_df['timestamp'], plot_df['accuracy_%'], 
                 label='Accuracy', color='green', marker=None, linewidth=1.5)

        # X軸設定
        ax1.xaxis.set_major_locator(mdates.MinuteLocator(byminute=[0, 30]))
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax1.set_xlim(start_dt, end_dt)
        fig.autofmt_xdate()

        # 凡例の統合 (ax1とax2のラベルをまとめて表示)
        h1, l1 = ax1.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        ax1.legend(h1 + h2, l1 + l2, loc='upper left')

        # ラベル・書式設定
        plt.title(f"Traffic Trend (Stacked Bar): {pipe_name}", fontsize=14)
        ax1.set_xlabel(f"Time: {args.date}", fontsize=12)
        ax1.set_ylabel("Mbps", fontsize=12)
        ax1.grid(True, which='both', linestyle='--', alpha=0.5)

        ax2.set_ylabel("Shaping Accuracy (%)", fontsize=12)
        ax2.yaxis.set_major_formatter(mtick.PercentFormatter(100.0))
        ax2.set_ylim(-200, 200)

        plt.tight_layout()

        # --- 保存処理 ---
        save_path = REPORT_DIR / f"bar_{pipe_name}_{args.date}.png"
        plt.savefig(save_path)
        plt.close()
        print(f"SAVED: {save_path}")

if __name__ == '__main__':
    main()