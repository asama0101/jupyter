import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import argparse
import sys

# ==============================================================================
# NAME
#    plot_scatter.py - Traffic Correlation Scatter Plot
#
# SYNOPSIS
#    python3 plot_scatter.py --file <CSV_FILE> --date <YYYY-MM-DD> [OPTIONS]
#
# DESCRIPTION
#    指定された結果CSVを読み込み、特定の日付におけるトラフィック量と精度の相関図を生成する。
#    横軸にトラフィック総量（MBps）、縦軸に精度（Accuracy%）をプロットし、
#    Limit値を垂直線として表示することで、制限付近での挙動を可視化する。
#
# OPTIONS
#    -f, --file   読み込むCSVファイル名 (data/interim フォルダ内を想定)
#    -d, --date   対象年月日 (YYYY-MM-DD 形式)
#    -p, --pipe   特定のパイプ名のみ出力する場合に指定 (省略時は全実行)
#
# EXAMPLE
#    python3 plot_scatter.py -f result.csv -d 2025-10-01
#    python3 plot_scatter.py -f result.csv -d 2025-10-01 -p ISP-A_Kanagawa-01
# ==============================================================================

# --- ディレクトリ設定 ---
current_file_path = Path(__file__).resolve()
ROOT_DIR = current_file_path.parent.parent
WORK_DIR = ROOT_DIR / "data" / "interim"
REPORT_DIR = ROOT_DIR / "result"

def main():
    # --- 引数の解析 ---
    parser = argparse.ArgumentParser(
        description='トラフィック量と精度の相関散布図生成ツール',
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
    target_date = pd.to_datetime(args.date).date()
    
    # 対象となるPipeのリストを作成
    target_pipes = [args.pipe] if args.pipe else sorted(df['pipe'].unique())

    # 保存先フォルダの作成
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    for pipe_name in target_pipes:
        # データの絞り込み（指定日の1日分）
        mask = (df['pipe'] == pipe_name) & (df['timestamp'].dt.date == target_date)
        plot_df = df[mask].copy()

        if plot_df.empty:
            print(f"SKIP: No data for {pipe_name} on {args.date}")
            continue

        # --- 描画処理 ---
        fig, ax = plt.subplots(figsize=(10, 7))

        # 散布図のプロット
        # x軸: rx_total_MBps (トラフィック + 廃棄量)
        # y軸: accuracy_%
        ax.scatter(plot_df['rx_total_MBps'], plot_df['accuracy_%'], 
                    alpha=0.5, s=40, c='tab:blue', edgecolors='none', label='Actual Data')

        # Limit線の描画
        # その日の最初の有効なLimit値を取得（日中に変更がない前提）
        current_limit = plot_df['limit'].iloc[0]
        if pd.notna(current_limit):
            ax.axvline(x=current_limit, color='tab:red', linestyle='--', linewidth=2, 
                       label=f'Limit: {current_limit:.1f} Mbps')
            
            # Limit線のラベルテキスト
            ax.text(current_limit * 1.01, 150, f'Limit: {current_limit:.1f} Mbps', 
                    color='tab:red', fontweight='bold', rotation=90, verticalalignment='center')

        # 軸・ラベル設定
        ax.set_title(f"Traffic Correlation with Limit\n{pipe_name} ({args.date})", fontsize=14, fontweight='bold')
        ax.set_xlabel("Total Traffic Volume (Actual + Drop) [Mbps]", fontsize=12)
        ax.set_ylabel("Accuracy (%)", fontsize=12)
        
        # 精度は ±200% の範囲で固定（他グラフと統一）
        ax.set_ylim(-200, 200)
        
        # 補助線（0%の基準線を少し強調）
        ax.axhline(0, color='black', linewidth=1, alpha=0.5)
        ax.grid(True, linestyle='--', alpha=0.5)
        
        ax.legend(loc='lower left', frameon=True, shadow=True)

        plt.tight_layout()

        # --- 保存処理 ---
        save_path = REPORT_DIR / f"scatter_{pipe_name}_{args.date}.png"
        plt.savefig(save_path)
        plt.close()
        print(f"SAVED: {save_path}")

if __name__ == '__main__':
    main()