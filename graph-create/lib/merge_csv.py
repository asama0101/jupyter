import argparse
import sys
from pathlib import Path
import pandas as pd

# ディレクトリ設定
current_file_path = Path(__file__).resolve()
ROOT_DIR = current_file_path.parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
WORK_DIR = ROOT_DIR / "data" / "interim"

def main():
    # 引数の設定
    parser = argparse.ArgumentParser(description='トラヒック統計データをマージするスクリプト')
    parser.add_argument('-f1', '--file1', default='data1.csv', help='1つ目のデータ (default: data1.csv)')
    parser.add_argument('-f2', '--file2', default='data2.csv', help='2つ目のデータ (default: data2.csv)')
    parser.add_argument('-o', '--output', default=None, help='出力ファイル名 (指定なしなら標準出力)')

    args = parser.parse_args()

    # ファイルの読み込み
    try:
        df1 = pd.read_csv(RAW_DIR / args.file1)
        df2 = pd.read_csv(RAW_DIR / args.file2)
    except FileNotFoundError as e:
        print(f"Error: ファイルが見つかりません。{e}")
        return

    # ヘッダー統一
    df1 = df1.rename(columns={
        'タイムスタンプ': 'timestamp',
        'パイプ名': 'pipe',
        '下りのトラヒック量(Byte)': 'rx_bytes',
        '上りのトラヒック量(Byte)': 'tx_bytes',
        '下りの廃棄量(Packets)': 'rx_drop_pkts',
        '下りの廃棄量(Bytes)': 'rx_drop_bytes'
    })

    df2 = df2.rename(columns={
        'volume_in': 'rx_bytes',
        'volume_out': 'tx_bytes'
    })
    
    df2['pipe'] = df2['ISP'].astype(str) + "_" + df2['POI_identifer'].astype(str)

    # Mbps変換
    # 計算前に欠損値をすべて 0 で埋める
    df1 = df1.fillna(0)
    df2 = df2.fillna(0)

    # Mbps変換（定数は変数にまとめると管理が楽です）
    # 300秒間隔の Byte -> Mbps 変換係数: 8bit / (300s * 10^6)
    factor = 8 / (300 * 1000000)

    df1['rx_MBps'] = (df1['rx_bytes'] * factor).round(1)
    df1['tx_MBps'] = (df1['tx_bytes'] * factor).round(1)
    df1['rx_drop_MBps'] = (df1['rx_drop_bytes'] * factor).round(1)
    df1['rx_total_MBps'] = (df1['rx_MBps'] + df1['rx_drop_MBps']).round(1)

    df2['rx_MBps'] = (df2['rx_bytes'] * factor).round(1)
    df2['tx_MBps'] = (df2['tx_bytes'] * factor).round(1)
    
    # ---★ Limitを書くためのもので本来不要 ★---

    # 1. 08:00台のデータを抽出するための準備（一時的に日付型を利用）
    tmp_ts = pd.to_datetime(df1['timestamp'])
    
    # 08:00台の行だけをピックアップ
    mask_08 = (tmp_ts.dt.hour == 8)
    df_08 = df1[mask_08].copy()

    # 2. 拠点(pipe)ごとに08:00台の平均値を計算
    # ※最大値にしたい場合は .mean() を .max() に変更してください
    limit_values = df_08.groupby('pipe')['rx_MBps'].mean().reset_index()
    limit_values = limit_values.rename(columns={'rx_MBps': 'limit'})

    # 3. 元の df1 に limit カラムとしてマージ
    df1 = pd.merge(df1, limit_values, on='pipe', how='left')
    
    # 08:00台のデータがない拠点などは NaN になるので 0 で埋める
    df1['limit'] = df1['limit'].fillna(0).round(1)

    # --- ★ ここまでは本来不要 ★ ---

    # Shaping Accuracy算出（廃棄パケットが無い場合は、0%に上書き）
    df1['accuracy_%'] = ((((df1['limit'] - df1['rx_MBps']) / df1['limit'])) * 100).round(1)
    df1.loc[df1['rx_drop_pkts'] == 0, 'accuracy_%'] = 0
    
    # 日付型に変換
    df1['timestamp'] = pd.to_datetime(df1['timestamp'], format='%Y-%m-%d %H:%M:%S')
    df2['timestamp'] = pd.to_datetime(df2['timestamp'], format='%Y%m%d%H%M%S')

    # マージ・空白埋め・ソート
    df_merged = pd.merge(df1, df2, on=['timestamp', 'pipe'], how='outer')
    df_merged = df_merged.fillna(0)
    df_merged = df_merged.sort_values(['timestamp', 'pipe']).reset_index(drop=True)

    # 出力の分岐
    if args.output:
        # 出力先が指定されていれば保存
        output_path = WORK_DIR / args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df_merged.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"Success: ファイルを保存しました {output_path}")
    else:
        # 指定がなければ標準出力（全件だと長いので head で表示）
        print("=== マージ結果 (標準出力) ===")
        print(df_merged.head(20))
        print(f"\n... 合計 {len(df_merged)} 行")

if __name__ == '__main__':
    main()