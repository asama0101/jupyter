import pandas as pd
from pathlib import Path
import sys

# --- ディレクトリ設定（提供されたコードの方式を継承） ---
current_file_path = Path(__file__).resolve()
# libフォルダにあることを前提に、親の親をROOTとする
ROOT_DIR = current_file_path.parent.parent

# 入出力パスを固定
INPUT_DIR = ROOT_DIR / "data" / "interim"
OUTPUT_DIR = ROOT_DIR / "data" / "processed"
OUTPUT_FILE = OUTPUT_DIR / "combined_data.csv"

# ソート対象を固定
SORT_COL = "timestamp"

def main():
    # 入力ディレクトリの存在確認
    if not INPUT_DIR.exists():
        print(f"Error: 入力ディレクトリが見つかりません: {INPUT_DIR}")
        print(f"現在のスクリプト位置: {current_file_path}")
        return

    # 入力ファイル一覧の取得 (*.csv)
    all_files = sorted(list(INPUT_DIR.glob("*.csv")))
    
    # 出力ファイル名と同じものが入力にあれば除外する
    all_files = [f for f in all_files if f.name != OUTPUT_FILE.name]
    
    if not all_files:
        print(f"Error: {INPUT_DIR} 内にCSVファイルが見つかりません。")
        return

    print(f"Processing: {len(all_files)} files found in {INPUT_DIR}")

    # データの読み込み
    df_list = []
    for f in all_files:
        try:
            df = pd.read_csv(f)
            # 指定されたソート用カラムが存在するか確認
            if SORT_COL not in df.columns:
                # 既存コードで「タイムスタンプ」を「timestamp」にリネームしている場合を考慮
                if "タイムスタンプ" in df.columns:
                    df = df.rename(columns={"タイムスタンプ": SORT_COL})
                else:
                    print(f"Warning: '{SORT_COL}' カラムが {f.name} にありません。スキップします。")
                    continue
            df_list.append(df)
        except Exception as e:
            print(f"Error reading {f.name}: {e}")

    if not df_list:
        print("有効なデータセットがありませんでした。")
        return

    # 縦方向に結合
    df_combined = pd.concat(df_list, ignore_index=True)

    # 時系列でソート
    # 日付として正しく並べるため一度datetime型に変換
    df_combined[SORT_COL] = pd.to_datetime(df_combined[SORT_COL])
    df_combined = df_combined.sort_values(SORT_COL).reset_index(drop=True)

    # 重複排除
    before_count = len(df_combined)
    df_combined = df_combined.drop_duplicates(subset=[SORT_COL, 'pipe'])
    after_count = len(df_combined)
    
    # 保存
    df_combined.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')

    print(f"--- 完了 ---")
    print(f"結合ファイル数: {len(df_list)}")
    print(f"総行数: {after_count} (重複削除: {before_count - after_count}件)")
    print(f"保存先: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()