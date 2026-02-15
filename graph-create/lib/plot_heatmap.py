import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import argparse
import sys

# ==============================================================================
# NAME
#    plot_heatmap.py - Traffic Accuracy Temporal Heatmap Generator
#
# SYNOPSIS
#    python3 plot_heatmap.py --file <CSV_FILE> [OPTIONS]
#
# DESCRIPTION
#    指定された結果CSVを読み込み、特定または全てのパイプの精度(Accuracy%)の推移を
#    日付×時間のヒートマップ形式で生成する。
#    --pipe の指定がない場合は、CSVに含まれる全てのpipeに対して個別に生成し保存する。
#
# OPTIONS
#    -f, --file   読み込むCSVファイル名 (data/interim フォルダ内を想定)
#    -p, --pipe   特定のパイプ名のみ出力する場合に指定 (省略時は全実行)
#
# EXAMPLE
#    python3 plot_heatmap.py --file result.csv
#    python3 plot_heatmap.py -f result.csv -p ISP-A_Osaka-01
# ==============================================================================

# --- ディレクトリ設定 ---
current_file_path = Path(__file__).resolve()
ROOT_DIR = current_file_path.parent.parent
WORK_DIR = ROOT_DIR / "data" / "interim"
REPORT_DIR = ROOT_DIR / "result"

def create_heatmap(df, pipe_name):
    """
    指定されたパイプのヒートマップを生成・保存する
    (0%を緑、±100%を赤とするカスタムカラーマップ版)
    """
    plot_df = df[df['pipe'] == pipe_name].copy()
    if plot_df.empty:
        print(f"SKIP: No data found for {pipe_name}")
        return

    # --- データの加工 ---
    plot_df['date'] = plot_df['timestamp'].dt.date
    plot_df['time_slot'] = plot_df['timestamp'].dt.strftime('%H:%M')
    
    # 5分刻みの生データをピボット
    heatmap_data = plot_df.pivot_table(index='date', columns='time_slot', values='accuracy_%')

    # --- カスタムカラーマップの作成 ---
    # LinearSegmentedColormap を使い、-100(赤) -> 0(緑) -> 100(赤) を定義
    from matplotlib.colors import LinearSegmentedColormap
    colors = ["red", "yellow", "green", "yellow", "red"]
    # 0% が中心（緑）にくるように配置
    custom_cmap = LinearSegmentedColormap.from_list("AccuracyCmap", colors)

    # --- 描画処理 ---
    fig_height = max(6, len(heatmap_data.index) * 0.4)
    fig, ax = plt.subplots(figsize=(18, fig_height))

    # 作成したカスタムカラーマップを適用
    im = ax.imshow(heatmap_data, cmap=custom_cmap, aspect='auto', vmin=-100, vmax=100)

    # 軸・ラベル設定（1時間ごとに目盛りを振る）
    xticks = range(0, len(heatmap_data.columns), 12) 
    xticklabels = [heatmap_data.columns[i] for i in xticks]
    ax.set_xticks(xticks)
    ax.set_xticklabels(xticklabels, rotation=0)
    ax.set_yticks(range(len(heatmap_data.index)))
    ax.set_yticklabels(heatmap_data.index)
    
    ax.set_title(f"Shaping Accuracy Heatmap (0%=Green, ±100%=Red): {pipe_name}", fontsize=15, fontweight='bold', pad=20)
    ax.set_xlabel("Time of Day", fontsize=12)
    ax.set_ylabel("Date", fontsize=12)

    # カラーバー
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Accuracy Deviation (%)', fontsize=10)

    plt.tight_layout()

    # 保存
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    save_path = REPORT_DIR / f"heatmap_{pipe_name}.png"
    plt.savefig(save_path)
    plt.close()
    print(f"SAVED HEATMAP: {save_path}")

def main():
    parser = argparse.ArgumentParser(description='精度(Accuracy%)の5分間隔ヒートマップ生成')
    parser.add_argument('-f', '--file', type=str, required=True, help='CSVファイル名')
    parser.add_argument('-p', '--pipe', type=str, default=None, help='パイプ名（省略時は全実行）')
    args = parser.parse_args()

    csv_path = WORK_DIR / args.file
    if not csv_path.exists():
        print(f"ERROR: File not found: {csv_path}")
        sys.exit(1)

    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    target_pipes = [args.pipe] if args.pipe else sorted(df['pipe'].unique())

    for pipe in target_pipes:
        create_heatmap(df, pipe)

if __name__ == '__main__':
    main()