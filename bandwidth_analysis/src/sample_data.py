"""
sample_data.py - サンプルデータ生成モジュール
=============================================
動作検証用の3種類のCSV.gzファイルを生成する。
  1. 新規帯域制御装置のトラヒック統計  (new_traffic.csv.gz)
  2. 現行帯域制御装置のトラヒック統計  (current_traffic.csv.gz)
  3. 新規帯域制御装置の帯域上限値      (bandwidth_limit.csv.gz)

特徴:
  - 全IDで帯域制御（packet_drop）が確実に発生する
  - 廃棄パケット/バイトは必ず0以上
  - 1日のトラヒックパターンは昼～夜にピーク、週周期のゆらぎ付き

使い方:
    from src.sample_data import generate_sample_data

    generate_sample_data(
        data_dir="data",
        start_date="2025-01-15",
        num_days=14,
        isp_list=["AA00-00", "BB01-01", "CC02-02"],
        poi_code="2015",
        seed=42,
    )
"""

import os
import gzip
import csv

import numpy as np
import pandas as pd

from .calc_traffic import mbps_to_bytes


# ---------------------------------------------------------------------------
# 内部関数
# ---------------------------------------------------------------------------

def _generate_traffic_pattern(n_points, base_mbps, peak_mbps):
    """
    1日周期のトラヒックパターンを生成する（内部関数）。

    昼13時と夜21時にピークを持つガウシアンの重ね合わせで、
    さらに日毎の週周期ゆらぎとノイズを加える。

    Args:
        n_points (int): 生成するデータ点数
        base_mbps (float): ベースライン（最低帯域, Mbps）
        peak_mbps (float): ピーク帯域 (Mbps)

    Returns:
        np.ndarray: 各時刻のトラヒック量 (Mbps), shape=(n_points,)
    """
    hours = np.array([
        ts.hour + ts.minute / 60
        for ts in pd.date_range("2000-01-01", periods=n_points, freq="5min")
    ])
    # 昼13時(弱)と夜21時(強)のダブルピーク
    pattern = base_mbps + (peak_mbps - base_mbps) * (
        0.3 * np.exp(-((hours % 24 - 13) ** 2) / 8)
        + 0.7 * np.exp(-((hours % 24 - 21) ** 2) / 6)
    )
    # 日毎の週周期ゆらぎ（±5%）
    day_indices = np.arange(n_points) // 288  # 288 = 24h * 60min / 5min
    day_factor = 1.0 + 0.05 * np.sin(day_indices * 2 * np.pi / 7)
    pattern = pattern * day_factor
    # ランダムノイズ
    noise = np.random.normal(0, base_mbps * 0.05, n_points)
    pattern = np.clip(pattern + noise, 200, 1e6)
    return pattern


def _save_csv_gz(df, filepath):
    """
    DataFrameをgzip圧縮したCSVファイルとして保存する（内部関数）。

    Args:
        df (pd.DataFrame): 保存するDataFrame
        filepath (str): 出力ファイルパス（例: "data/new_traffic.csv.gz"）
    """
    csv_data = df.to_csv(index=False)
    with gzip.open(filepath, "wt", encoding="utf-8") as f:
        f.write(csv_data)


# ---------------------------------------------------------------------------
# 公開関数
# ---------------------------------------------------------------------------

def generate_sample_data(
    data_dir,
    start_date="2025-01-15",
    num_days=14,
    isp_list=None,
    poi_code="2015",
    seed=42,
):
    """
    3種類のサンプルCSV.gzファイルを生成して data_dir に保存する。

    Args:
        data_dir (str): 出力先ディレクトリパス
        start_date (str): 開始日 (YYYY-MM-DD形式, デフォルト: "2025-01-15")
        num_days (int): 生成する日数 (デフォルト: 14)
        isp_list (list[str]): ISP管理IDのリスト
            (デフォルト: ["AA00-00", "BB01-01", "CC02-02"])
        poi_code (str): POI管理ID (デフォルト: "2015")
        seed (int): 乱数シード (デフォルト: 42)

    Returns:
        dict: 生成結果の情報
            {
                "ids": list[str],           # 生成されたID一覧
                "new_traffic_path": str,     # 新規トラヒック統計のファイルパス
                "current_traffic_path": str, # 現行トラヒック統計のファイルパス
                "bandwidth_limit_path": str, # 帯域上限値のファイルパス
                "num_rows_new": int,         # 新規トラヒック統計のレコード数
                "num_rows_current": int,     # 現行トラヒック統計のレコード数
                "num_rows_limit": int,       # 帯域上限値のレコード数
            }
    """
    if isp_list is None:
        isp_list = ["AA00-00", "BB01-01", "CC02-02"]

    os.makedirs(data_dir, exist_ok=True)
    np.random.seed(seed)

    end_date = (
        pd.Timestamp(start_date) + pd.Timedelta(days=num_days - 1)
    ).strftime("%Y-%m-%d")
    ids = [f"{isp}-{poi_code}" for isp in isp_list]

    # タイムスタンプ生成
    ts_5min = pd.date_range(f"{start_date} 00:00:00", f"{end_date} 23:55:00", freq="5min")
    ts_20min = pd.date_range(f"{start_date} 00:00:00", f"{end_date} 23:40:00", freq="20min")

    # ----- 1. 新規帯域制御装置のトラヒック統計 -----
    rows_new = []
    limit_map = {}  # 各IDのlimit基準値（帯域上限値と共有）
    for cid in ids:
        base = np.random.uniform(300, 500)
        peak = np.random.uniform(750, 950)
        # limitをピークの70〜85%に設定 → 確実に帯域制御を発生させる
        limit_mbps = peak * np.random.uniform(0.70, 0.85)
        limit_map[cid] = limit_mbps

        traffic = _generate_traffic_pattern(len(ts_5min), base, peak)

        for i, ts in enumerate(ts_5min):
            vol_in_mbps = traffic[i]
            vol_out_mbps = vol_in_mbps * np.random.uniform(0.05, 0.15)
            vol_in_bytes = mbps_to_bytes(vol_in_mbps)
            vol_out_bytes = mbps_to_bytes(vol_out_mbps)

            if vol_in_mbps > limit_mbps:
                # 帯域制御: 制御後はlimitの95〜100%に収める（負値防止）
                controlled = limit_mbps * np.random.uniform(0.95, 1.00)
                drop_bytes = max(0, mbps_to_bytes(vol_in_mbps - controlled))
                drop_pkt = max(0, int(drop_bytes / 1500))
                vol_in_bytes = mbps_to_bytes(controlled)
            else:
                drop_bytes = 0
                drop_pkt = 0

            # 低確率でトラヒック無し（空白レコード）
            if np.random.random() < 0.01:
                rows_new.append([ts.strftime("%Y-%m-%d %H:%M:%S"), cid, "", "", "", ""])
            else:
                rows_new.append([
                    ts.strftime("%Y-%m-%d %H:%M:%S"), cid,
                    int(vol_in_bytes), int(vol_out_bytes), drop_pkt, int(drop_bytes),
                ])

    df_new = pd.DataFrame(rows_new, columns=[
        "time_stamp", "subport", "volume_in", "volume_out", "dropped_packets_in", "dropped_bytes_in",
    ])

    # ----- 2. 現行帯域制御装置のトラヒック統計 -----
    rows_cur = []
    for cid in ids:
        isp = cid.rsplit("-", 1)[0]
        base = np.random.uniform(300, 500)
        peak = np.random.uniform(700, 950)
        traffic = _generate_traffic_pattern(len(ts_5min), base, peak)

        for i, ts in enumerate(ts_5min):
            vol_in_mbps = traffic[i]
            vol_out_mbps = vol_in_mbps * np.random.uniform(0.05, 0.15)
            vol_in_bytes = mbps_to_bytes(vol_in_mbps)
            vol_out_bytes = mbps_to_bytes(vol_out_mbps)

            if np.random.random() < 0.01:
                rows_cur.append([ts.strftime("%Y%m%d%H%M%S"), cid, "", ""])
            else:
                rows_cur.append([
                    ts.strftime("%Y%m%d%H%M%S"), cid,
                    int(vol_in_bytes), int(vol_out_bytes),
                ])

    df_cur = pd.DataFrame(rows_cur, columns=[
        "timestamp", "policy_line_key", "volume_in", "volume_out",
    ])

    # ----- 3. 帯域上限値 -----
    rows_lim = []
    for cid in ids:
        base_limit = limit_map[cid]
        for ts in ts_20min:
            hour = ts.hour
            if 9 <= hour <= 23:
                limit = base_limit * np.random.uniform(0.98, 1.02)
            else:
                limit = base_limit * np.random.uniform(1.0, 1.1)
            
            limit_kbps = limit * 1000
            
            rows_lim.append([
                ts.strftime("%Y-%m-%d %H:%M:%S"), 
                cid, 
                int(limit_kbps)
            ])

    df_lim = pd.DataFrame(rows_lim, columns=["timestamp", "subport_name", "pir_value"])

    # ----- ファイル保存 -----
    path_new = os.path.join(data_dir, "new_traffic.csv.gz")
    path_cur = os.path.join(data_dir, "current_traffic.csv.gz")
    path_lim = os.path.join(data_dir, "bandwidth_limit.csv.gz")

    _save_csv_gz(df_new, path_new)

    # current_traffic.csv.gz のみダブルクォーテーション付きで保存
    csv_text_cur = df_cur.to_csv(index=False, quoting=csv.QUOTE_ALL)
    with gzip.open(path_cur, "wt", encoding="utf-8") as f:
        f.write(csv_text_cur)

    _save_csv_gz(df_lim, path_lim)

    return {
        "ids": ids,
        "new_traffic_path": path_new,
        "current_traffic_path": path_cur,
        "bandwidth_limit_path": path_lim,
        "num_rows_new": len(df_new),
        "num_rows_current": len(df_cur),
        "num_rows_limit": len(df_lim),
    }