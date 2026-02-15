import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from pathlib import Path
import argparse
import sys

# ==============================================================================
# NAME
#    plot_box.py - Traffic Accuracy Distribution Box Plot
#
# SYNOPSIS
#    python3 plot_box.py --file <CSV_FILE> --date <YYYY-MM-DD>
#
# DESCRIPTION
#    指定された結果CSVを読み込み、特定の日付における全拠点の精度(Accuracy%)の分布を
#    横並びの箱ひげ図で生成する。
#    その日の limit の累計が 0 であるパイプは、未設定または無効とみなし自動的に除外する。
#
# OPTIONS
#    -f, --file   読み込むCSVファイル名 (data/interim フォルダ内を想定)
#    -d, --date   対象年月日 (YYYY-MM-DD 形式)
#
# EXAMPLE
#    python3 plot_box.py --file result.csv --date 2025-10-01
# ==============================================================================

# --- ディレクトリ設定 ---
current_file_path = Path(__file__).resolve()
ROOT_DIR = current_file_path.parent.parent
WORK_DIR = ROOT_DIR / "data" / "interim"
REPORT_DIR = ROOT_DIR / "result"

def main():
    # --- 引数の解析 ---
    parser = argparse.ArgumentParser(
        description='精度(Accuracy%)分布を比較する箱ひげ図生成ツール',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('-f', '--file', type=str, required=True, help='読み込むCSVファイル名')
    parser.add_argument('-d', '--date', type=str, required=True, help='対象年月日 (YYYY-MM-DD)')
    args = parser.parse_args()

    # --- データ読み込み ---
    csv_path = WORK_DIR / args.file
    if not csv_path.exists():
        print(f"ERROR: File not found: {csv_path}")
        sys.exit(1)

    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # --- 日付の絞り込み ---
    target_date = pd.to_datetime(args.date).date()
    day_df = df[df['timestamp'].dt.date == target_date].copy()

    if day_df.empty:
        print(f"ERROR: No data found for {args.date}")
        sys.exit(1)

    # 全てのユニークなパイプ名を取得し、名前順でソート
    all_pipes = sorted(day_df['pipe'].unique())

    # 描画用データの準備
    data_to_plot = []
    labels = []

    for pipe in all_pipes:
        pipe_data = day_df[day_df['pipe'] == pipe]
        
        # --- limit の累計が 0 または 全てNaN のパイプを除外 ---
        if pipe_data['limit'].sum() == 0 or pipe_data['limit'].isna().all():
            print(f"SKIP: Limit sum is 0 for {pipe}")
            continue

        accuracy_data = pipe_data['accuracy_%'].dropna()
        if not accuracy_data.empty:
            data_to_plot.append(accuracy_data)
            labels.append(pipe)

    if not data_to_plot:
        print(f"ERROR: No valid pipes (limit sum > 0) found on {args.date}")
        sys.exit(1)

    # --- 描画処理 ---
    # 拠点数に応じて横幅を動的に変更
    fig_width = max(10, len(labels) * 1.5)
    fig, ax = plt.subplots(figsize=(fig_width, 8))

    # 箱ひげ図の描画
    ax.boxplot(data_to_plot, 
                patch_artist=True,
                showmeans=True,
                # 平均値の設定（白い菱形）
                meanprops=dict(marker='D', markerfacecolor='white', markeredgecolor='black', markersize=7),
                # 箱の設定（薄い青）
                boxprops=dict(facecolor='lightblue', color='blue', alpha=0.7),
                # 中央値の設定（太い赤線）
                medianprops=dict(color='red', linewidth=2),
                # 外れ値の設定（小さいグレーの点）
                flierprops=dict(marker='o', markerfacecolor='gray', markersize=4, alpha=0.5))

    # --- 凡例の手動作成 (フォントエラー回避のためラベルは英語) ---
    legend_elements = [
        Line2D([0], [0], color='red', lw=2, label='Median'),
        Line2D([0], [0], marker='D', color='w', label='Mean',
               markerfacecolor='white', markeredgecolor='black', markersize=8),
        Line2D([0], [0], marker='o', color='w', label='Outlier',
               markerfacecolor='gray', markersize=6, alpha=0.5)
    ]
    ax.legend(handles=legend_elements, loc='upper right', frameon=True, shadow=True)

    # 軸・タイトルの設定
    ax.set_title(f"Accuracy Distribution Comparison ({args.date})", fontsize=15, fontweight='bold')
    ax.set_ylabel("Accuracy (%)", fontsize=12)
    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=10)
    ax.set_ylim(-200, 200)

    # 補助線と基準線
    ax.grid(True, axis='y', linestyle='--', alpha=0.6)
    ax.axhline(0, color='black', linewidth=1.2, linestyle='-')

    plt.tight_layout()

    # --- 保存処理 ---
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    save_path = REPORT_DIR / f"box_accuracy_summary_{args.date}.png"
    
    plt.savefig(save_path)
    plt.close()
    print(f"SAVED SUMMARY: {save_path}")

if __name__ == '__main__':
    main()