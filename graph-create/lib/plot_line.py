import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
import argparse
import sys

# ==============================================================================
# NAME
#    plot_line.py - Traffic Trend Line Chart Generator
#
# SYNOPSIS
#    python3 plot_line.py --file <CSV_FILE> --date <YYYY-MM-DD> [OPTIONS]
#
# DESCRIPTION
#    指定された結果CSVを読み込み、特定の日付のトラフィック推移グラフ(折れ線)を生成する。
#    --pipe の指定がない場合は、CSVに含まれる全てのpipeに対して個別にグラフを生成し保存する。
#
# OPTIONS
#    --file   読み込むCSVファイル名 (data/interim フォルダ内を想定)
#    --date   対象年月日 (YYYY-MM-DD 形式)
#    --pipe   特定のパイプ名のみ出力する場合に指定 (省略時は全実行)
#
# EXAMPLE
#    python3 plot_line.py --file result.csv --date 2025-10-01
#    python3 plot_line.py --file result.csv --date 2025-10-01 --pipe ISP-B_Kanagawa-01
# ==============================================================================

# ディレクトリ設定
current_file_path = Path(__file__).resolve()
ROOT_DIR = current_file_path.parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
WORK_DIR = ROOT_DIR / "data" / "interim"
REPORT_DIR = ROOT_DIR / "result"

def main():
    # --- 引数の解析 ---
    parser = argparse.ArgumentParser(description='トラフィック推移グラフ(折れ線)生成ツール')
    parser.add_argument('-f', '--file', type=str, required=True, help='読み込むCSVファイル名 (必須)\n例: result.csv')
    parser.add_argument('-d', '--date', type=str, required=True, help='対象年月日 (必須)\n形式: YYYY-MM-DD')
    parser.add_argument('-p', '--pipe', type=str, default=None, help='特定のパイプ名のみ出力する場合に指定 (任意)\n省略時は全pipeを出力')
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

        # グラフサイズ
        fig, ax = plt.subplots(figsize=(15, 7))

        # Y1/Y2軸設定
        ax.plot(plot_df['timestamp'], plot_df['rx_MBps_x'], label='Data1 (Main)', color='tab:blue', alpha=0.8)
        ax.plot(plot_df['timestamp'], plot_df['rx_MBps_y'], label='Data2 (-1%)', color='tab:purple', linestyle='--', alpha=0.8)
        ax.plot(plot_df['timestamp'], plot_df['limit'], label='Limit', color='tab:red', linestyle='--', alpha=0.8)

        # X軸設定
        ax.xaxis.set_major_locator(mdates.MinuteLocator(byminute=[0, 30]))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax.set_xlim(start_dt, end_dt)
        fig.autofmt_xdate()

        # タイトル・ラベル
        plt.title(f"Traffic Trend: {pipe_name}", fontsize=14)
        plt.xlabel(f"Time ({args.date})", fontsize=12)
        plt.ylabel("Mbps", fontsize=12)

        # 凡例の位置
        plt.legend(loc='upper left')
        
        # その他（補助線・自動調整）
        plt.grid(True, which='both', linestyle='--', alpha=0.5)
        plt.tight_layout()

        # --- 保存処理 ---
        save_path = REPORT_DIR / f"line_{pipe_name}_{args.date}.png"
        plt.savefig(save_path)
        plt.close()
        print(f"SAVED: {save_path}")

if __name__ == '__main__':
    main()