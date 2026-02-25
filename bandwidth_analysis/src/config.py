"""
config.py - 設定ファイル
========================
プロジェクト全体で使用するパス定数・デフォルトパラメータを一元管理する。

利用者は本ファイルの値を変更することで、ディレクトリ構成や
デフォルトの日付範囲などをカスタマイズできる。

使い方:
    from src.config import DATA_DIR, OUTPUT_DIR, DEFAULT_TARGET_DATE
"""

import os

# ===========================================================================
# ディレクトリ設定
# ===========================================================================
# プロジェクトのルートディレクトリ（このファイルの親の親）
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(_THIS_DIR)

# 入力データディレクトリ（3種のCSV.gzおよび統合CSVを格納）
DATA_DIR = os.path.join(BASE_DIR, "data")

# グラフ画像の出力先ディレクトリ
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# ===========================================================================
# ファイル名設定
# ===========================================================================
# 入力ファイル名（拡張子 .csv.gz）
NEW_TRAFFIC_FILENAME = "new_traffic.csv.gz"
CURRENT_TRAFFIC_FILENAME = "current_traffic.csv.gz"
BANDWIDTH_LIMIT_FILENAME = "bandwidth_limit.csv.gz"

# 統合CSVファイル名
MERGED_CSV_FILENAME = "merged_traffic.csv"

# ===========================================================================
# デフォルトパラメータ
# ===========================================================================
# グラフ1〜4のデフォルト対象日
DEFAULT_TARGET_DATE = "2025-01-15"

# グラフ5（ヒートマップ）のデフォルト日付範囲
DEFAULT_HEATMAP_START = "2025-01-15"
DEFAULT_HEATMAP_END = "2025-01-28"

# サンプルデータ生成のデフォルト設定
DEFAULT_SAMPLE_START_DATE = "2025-01-15"
DEFAULT_SAMPLE_NUM_DAYS = 14
DEFAULT_SAMPLE_ISP_LIST = ["AA00-00", "BB01-01", "CC02-02"]
DEFAULT_SAMPLE_POI_CODE = "2015"
DEFAULT_SAMPLE_SEED = 42

# ===========================================================================
# ヘルパー関数
# ===========================================================================

def get_filepath(filename):
    """
    DATA_DIR内のファイルパスを返す。

    Args:
        filename (str): ファイル名（例: "new_traffic.csv.gz"）

    Returns:
        str: DATA_DIR/filename のフルパス
    """
    return os.path.join(DATA_DIR, filename)


def ensure_dirs():
    """
    DATA_DIR と OUTPUT_DIR が存在しなければ作成する。

    Returns:
        None
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
