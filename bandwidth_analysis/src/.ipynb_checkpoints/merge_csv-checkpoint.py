"""
merge_csv.py - CSV統合モジュール
================================
3種類のCSV.gzファイルを読み込み、1つの統合CSVにマージする。

修正内容:
  - 各入力ファイルのヘッダー名を辞書で定義し、ハードコーディングで変更可能に
  - 文字コード（UTF-8, CP932など）が混在していても自動試行で読み込み
  - マージロジックを設定されたヘッダー名に追従するよう汎用化

使い方:
    from src.merge_csv import merge_traffic_csv

    df = merge_traffic_csv(
        new_path="data/new_traffic.csv.gz",
        current_path="data/current_traffic.csv.gz",
        limit_path="data/bandwidth_limit.csv.gz",
        output_path="data/merged_traffic.csv",
    )
"""

import os
import pandas as pd
from .calc_traffic import bytes_to_mbps

# ===========================================================================
# ヘッダー定義設定（入力CSVに合わせてここを書き換える）
# ===========================================================================

# 新規帯域制御装置 (new_traffic.csv.gz)
COL_NEW = {
    "timestamp": "time_stamp",
    "id": "subport",
    "volume_bytes_in": "volume_in",
    "volume_bytes_out": "volume_out",
    "dropped_packets_in": "dropped_packets_in",
    "dropped_bytes_in": "dropped_bytes_in"
}

# 現行帯域制御装置 (current_traffic.csv.gz)
COL_CUR = {
    "timestamp": "timestamp",
    "id": "policy_line_key",
    "volume_bytes_in": "volume_in",
    "volume_bytes_out": "volume_out"
}

# 帯域上限値 (bandwidth_limit.csv.gz)
COL_LIM = {
    "timestamp": "timestamp",
    "id": "subport_name",
    "limit_kbps_in": "pir_value"
}


# ---------------------------------------------------------------------------
# 内部関数
# ---------------------------------------------------------------------------

def _read_csv_with_encoding(path):
    """
    複数の文字コードを試行してCSVを読み込む（内部関数）。
    UTF-8 -> CP932 (Shift_JIS) -> EUC-JP の順に試行する。
    """
    for enc in ["utf-8", "cp932", "euc-jp"]:
        try:
            return pd.read_csv(path, encoding=enc)
        except (UnicodeDecodeError, ValueError):
            continue
    raise UnicodeDecodeError(f"ファイルの読み込みに失敗しました（対応外の文字コード）: {path}")


# ---------------------------------------------------------------------------
# 公開関数
# ---------------------------------------------------------------------------

def merge_traffic_csv(new_path, current_path, limit_path, output_path):
    # --- 1. 3種のCSV.gzを読み込み ---
    df_new = _read_csv_with_encoding(new_path).fillna(0)
    df_cur = _read_csv_with_encoding(current_path).fillna(0)
    df_lim = _read_csv_with_encoding(limit_path).fillna(0)

    # --- 2. 各データの整形と列名固定（マージ前に "timestamp" と "id" に統一） ---
    
    # 現行データ
    df_cur[COL_CUR["timestamp"]] = pd.to_datetime(df_cur[COL_CUR["timestamp"]], format="%Y%m%d%H%M%S")
    df_cur = df_cur.rename(columns={
        COL_CUR["timestamp"]: "timestamp",
        COL_CUR["id"]: "id",
        COL_CUR["volume_bytes_in"]: "cur_volume_bytes_in",
        COL_CUR["volume_bytes_out"]: "cur_volume_bytes_out"
    })

    # 新規データ
    df_new[COL_NEW["timestamp"]] = pd.to_datetime(df_new[COL_NEW["timestamp"]])    
    df_new = df_new.rename(columns={
        COL_NEW["timestamp"]: "timestamp",
        COL_NEW["id"]: "id",
        COL_NEW["volume_bytes_in"]: "new_volume_bytes_in",
        COL_NEW["volume_bytes_out"]: "new_volume_bytes_out",
        COL_NEW["dropped_packets_in"]: "new_dropped_packets_in",
        COL_NEW["dropped_bytes_in"]: "new_dropped_bytes_in"
    })

    # 帯域上限値
    df_lim[COL_LIM["timestamp"]] = pd.to_datetime(df_lim[COL_LIM["timestamp"]])
    df_lim = df_lim.rename(columns={
        COL_LIM["timestamp"]: "timestamp",
        COL_LIM["id"]: "id",
        COL_LIM["limit_kbps_in"]: "limit_kbps_in"
    })
    df_lim = df_lim.sort_values(["timestamp", "id"])
    
    # リサンプリング処理
    df_lim_5min = (
        df_lim.set_index("timestamp")
        .groupby("id")["limit_kbps_in"]
        .resample("5min")
        .ffill()
        .reset_index()
    )

    # --- 5. timestamp, id をキーに3つをマージ ---
    df_merged = pd.merge(
        df_new,
        df_cur,
        on=["timestamp", "id"],
        how="left"
    )

    df_merged = pd.merge(
        df_merged,
        df_lim_5min,
        on=["timestamp", "id"],
        how="left"
    )

    # --- 6. 数値補完（NaN対応） ---
    num_cols = ["new_volume_bytes_in", "new_volume_bytes_out", 
                "new_dropped_packets_in", "new_dropped_bytes_in",
                "cur_volume_bytes_in", "cur_volume_bytes_out", "limit_kbps_in"]
    # 存在しない行がマージで作られるため、一括で0埋め
    df_merged[num_cols] = df_merged[num_cols].fillna(0)

    # --- 7. ID分解と属性補完 ---
    df_merged[["limit_group", "poi_code"]] = df_merged["id"].str.rsplit("-", n=1, expand=True)
    # outer結合で欠落した属性情報を埋める
    df_merged["limit_group"] = df_merged.groupby("id")["limit_group"].ffill().bfill()
    df_merged["poi_code"] = df_merged.groupby("id")["poi_code"].ffill().bfill()

    # --- 8. Mbps変換・制限前推定 ---
    df_merged["new_volume_mbps_in"] = bytes_to_mbps(df_merged["new_volume_bytes_in"])
    df_merged["new_volume_mbps_out"] = bytes_to_mbps(df_merged["new_volume_bytes_out"])
    df_merged["new_dropped_mbps_in"] = bytes_to_mbps(df_merged["new_dropped_bytes_in"])
    df_merged["cur_volume_mbps_in"] = bytes_to_mbps(df_merged["cur_volume_bytes_in"])
    df_merged["cur_volume_mbps_out"] = bytes_to_mbps(df_merged["cur_volume_bytes_out"])
    
    df_merged["limit_mbps_in"] = df_merged["limit_kbps_in"] / 1000
    
    df_merged["new_pre_control_bytes_in"] = df_merged["new_volume_bytes_in"] + df_merged["new_dropped_bytes_in"]
    df_merged["new_pre_control_mbps_in"] = bytes_to_mbps(df_merged["new_pre_control_bytes_in"])

    # --- 9. 列の並び替え ---
    # 読みやすい順番にリストを定義
    final_cols = [
        "timestamp", "id", "limit_group", "poi_code",             # 基本情報
        "new_pre_control_mbps_in",                                # 制限前推定(Mbps)
        "limit_mbps_in",                                          # 上限値(Mbps)
        "new_volume_mbps_in", "new_volume_mbps_out",              # 新装置(Mbps)
        "new_dropped_mbps_in",                                    # 新装置(Mbps)        
        "cur_volume_mbps_in", "cur_volume_mbps_out",              # 現行装置(Mbps)
        "new_volume_bytes_in", "new_volume_bytes_out",            # (参考)新装置Bytes系
        "cur_volume_bytes_in", "cur_volume_bytes_out",            # (参考)旧装置Bytes系
        "limit_kbps_in",                                           # (参考)上限値(Kbps)
        "new_dropped_bytes_in", "new_dropped_packets_in"          # (参考)破棄詳細        
    ]

    # 定義した列だけを抽出し、存在しない列があってもエラーにならないよう調整
    existing_cols = [c for c in final_cols if c in df_merged.columns]
    df_merged = df_merged[existing_cols]

    # --- 10. 保存 ---
    df_merged.to_csv(output_path, index=False, encoding="utf-8")
    return df_merged