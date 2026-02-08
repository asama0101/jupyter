import pandas as pd
import os
import glob
import logging

# traffic_proc.py側でセットアップされる共通ロガーを取得
logger = logging.getLogger("TRAFFIC_PROC")

def load_csv(base_dir, pattern, opts=None):
    """
    指定ディレクトリから複数のCSVを検索・読み込み、1つに結合する。
    """
    search_path = os.path.join(base_dir, pattern)
    files = glob.glob(search_path)
    
    if not files:
        logger.warning(f"File not found: {search_path}")
        return None
    
    try:
        # ファイルを順次読み込みリストに格納
        dfs = [pd.read_csv(f, **(opts or {})) for f in files]
        # 縦方向に結合し、行番号を振り直す
        combined_df = pd.concat(dfs, ignore_index=True)
        logger.info(f"Successfully loaded {len(files)} files.")
        return combined_df
    except Exception as e:
        logger.error(f"Error during loading: {str(e)}")
        return None

def save_csv(df, path):
    """
    ディレクトリを自動生成した上でデータをCSV保存する。
    """
    if df is None or df.empty: return False
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        df.to_csv(path, index=False, encoding='utf-8-sig') # Excel文字化け防止
        return True
    except Exception as e:
        logger.error(f"Error during saving: {str(e)}")
        return False