"""
graphs.py - グラフ描画モジュール
================================
統合CSVのDataFrameから5種類のグラフを描画・保存する関数群。

すべての関数は統合CSV (pd.DataFrame) と対象パラメータを受け取り、
指定ディレクトリにPNG画像を保存する。

使い方:
    import pandas as pd
    from src.graphs import plot_graph1, plot_graph2, plot_graph3, plot_graph4, plot_graph5

    df = pd.read_csv("data/merged_traffic.csv", parse_dates=["timestamp"])
    plot_graph1(df, target_date="2025-01-15", output_dir="output")
"""

import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
import matplotlib.patches as mpatches


# ===========================================================================
# 共通設定
# ===========================================================================
plt.rcParams["font.size"] = 10
plt.rcParams["figure.dpi"] = 100


def _filter_day(df, target_id, target_date):
    """
    DataFrameから指定IDと指定日の 00:00:00 以上、翌日の 00:00:00 未満を抽出する（内部ヘルパー）。

    Args:
        df (pd.DataFrame): 統合CSV DataFrame
        target_id (str): 対象ID (例: "AA00-00-2015")
        target_date (str): 対象日 (YYYY-MM-DD)

    Returns:
        pd.DataFrame: フィルタ済みコピー。データ無しの場合は空DataFrame。
    """
    start_ts = pd.Timestamp(target_date)
    next_day_ts = start_ts + pd.Timedelta(days=1)
    
    mask = (
        (df["id"] == target_id)
        & (df["timestamp"] >= start_ts)
        & (df["timestamp"] < next_day_ts)
    )
    return df[mask].copy()

# ===========================================================================
# グラフ1: 新規 vs 現行 トラヒック比較
# ===========================================================================

def plot_graph1(df, target_date, output_dir, target_ids=None):
    """
    新規 vs 現行のvolume_in比較グラフを描画する。

    表示要素:
      - 新規 volume_in (青線), 現行 volume_in (緑破線)
      - limit (オレンジ線) + limit±10%範囲 (薄オレンジ塗り)
      - packet_drop_pkt (赤棒, 右Y軸)
      - Y軸0スタート, X軸00:00スタート1時間おき, 補助線あり

    Args:
        df (pd.DataFrame): 統合CSV DataFrame
        target_date (str): 対象日 (YYYY-MM-DD)
        output_dir (str): 画像出力先ディレクトリ
        target_ids (list[str], optional):
            描画対象のIDリスト。Noneの場合はdf内の全IDを対象とする。

    Returns:
        list[str]: 保存したファイルパスのリスト
    """
    if target_ids is None:
        target_ids = df["id"].unique()

    os.makedirs(output_dir, exist_ok=True)
    saved = []

    for tid in target_ids:
        d = _filter_day(df, tid, target_date)
        if len(d) == 0:
            continue

        start_ts = pd.Timestamp(f"{target_date} 00:00:00")
        end_ts = pd.Timestamp(f"{target_date} 23:55:00")

        fig, ax1 = plt.subplots(figsize=(16, 7))

        # limit ±10% 塗りつぶし
        ax1.fill_between(
            d["timestamp"], d["limit_mbps_in"] * 0.9, d["limit_mbps_in"] * 1.1,
            color="orange", alpha=0.15, label="limit +/-10% range",
        )

        # packet_drop_pkt (右Y軸)
        ax2 = ax1.twinx()
        ax2.bar(d["timestamp"], d["new_dropped_packets_in"],
                width=0.003, alpha=0.3, color="red", label="drop_packets (New)", zorder=1)
        ax2.set_ylabel("drop_packets (pkt)", color="red")
        ax2.tick_params(axis="y", labelcolor="red")
        # 指数表記(1e6など)をオフにし、カンマ区切り表記
        ax2.get_yaxis().get_major_formatter().set_scientific(False) 
        ax2.get_yaxis().set_major_formatter(matplotlib.ticker.StrMethodFormatter('{x:,.0f}'))

        # volume_in 折れ線
        ax1.plot(d["timestamp"], d["new_volume_mbps_in"],
                 color="blue", linewidth=1.2, label="Internet -> User (New)", zorder=3)
        ax1.plot(d["timestamp"], d["cur_volume_mbps_in"],
                 color="green", linewidth=1.2, linestyle="--", label="Internet -> User (Current)", zorder=3)

        # limit 折れ線
        ax1.plot(d["timestamp"], d["limit_mbps_in"],
                 color="orange", linewidth=2, label="traffic_limit (New)", zorder=4)

        ax1.set_xlabel("Time")
        ax1.set_ylabel("Throughput (Mbps)")
        ax1.set_title(f"Graph 1: New vs Current Traffic - ID: {tid} ({target_date})")
        ax1.set_ylim(bottom=0)
        ax1.set_xlim(start_ts, end_ts)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax1.xaxis.set_major_locator(mdates.HourLocator(interval=1))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, fontsize=8)
        ax1.grid(True, alpha=0.3, linestyle="--")

        h1, l1 = ax1.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        ax1.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=8)

        plt.tight_layout()
        fname = f"graph1_{tid}_{target_date}.png"
        fpath = os.path.join(output_dir, fname)
        fig.savefig(fpath, bbox_inches="tight")
        plt.close(fig)
        saved.append(fpath)

    return saved


# ===========================================================================
# グラフ2: 帯域制御時の積み上げ棒グラフ + limit
# ===========================================================================

def plot_graph2(df, target_date, output_dir, target_ids=None):
    """
    帯域制御時のトラヒック量とlimitの関係を積み上げ棒グラフで描画する。

    表示要素:
      - volume_in (青棒) + packet_drop_byte (赤棒) の積み上げ
      - limit (オレンジ線) + limit±10%範囲 (薄オレンジ塗り)
      - X軸00:00スタート1時間おき, 補助線あり

    Args:
        df (pd.DataFrame): 統合CSV DataFrame
        target_date (str): 対象日 (YYYY-MM-DD)
        output_dir (str): 画像出力先ディレクトリ
        target_ids (list[str], optional): 描画対象IDリスト

    Returns:
        list[str]: 保存したファイルパスのリスト
    """
    if target_ids is None:
        target_ids = df["id"].unique()

    os.makedirs(output_dir, exist_ok=True)
    saved = []

    for tid in target_ids:
        d = _filter_day(df, tid, target_date)
        if len(d) == 0:
            continue

        start_ts = pd.Timestamp(f"{target_date} 00:00:00")
        end_ts = pd.Timestamp(f"{target_date} 23:55:00")

        fig, ax = plt.subplots(figsize=(16, 7))

        # limit ±10% 塗りつぶし
        ax.fill_between(
            d["timestamp"], d["limit_mbps_in"] * 0.9, d["limit_mbps_in"] * 1.1,
            color="orange", alpha=0.15, label="limit +/-10% range",
        )

        # 積み上げ棒グラフ
        ax.bar(d["timestamp"], d["new_volume_mbps_in"],
               width=0.003, color="steelblue", alpha=0.7, label="Internet -> User (New)")
        ax.bar(d["timestamp"], d["new_dropped_mbps_in"],
               width=0.003, bottom=d["new_volume_mbps_in"],
               color="salmon", alpha=0.7, label="drop_traffic (New)")

        # limit 折れ線
        ax.plot(d["timestamp"], d["limit_mbps_in"],
                color="orange", linewidth=2, label="traffic_limit (New)", zorder=5)

        ax.set_xlabel("Time")
        ax.set_ylabel("Throughput (Mbps)")
        ax.set_title(
            f"Graph 2: Bandwidth Control - volume_in + drop vs limit"
            f" - ID: {tid} ({target_date})"
        )
        ax.set_xlim(start_ts, end_ts)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, fontsize=8)
        ax.legend(loc="upper left", fontsize=9)
        ax.grid(True, alpha=0.3, linestyle="--")

        plt.tight_layout()
        fname = f"graph2_{tid}_{target_date}.png"
        fpath = os.path.join(output_dir, fname)
        fig.savefig(fpath, bbox_inches="tight")
        plt.close(fig)
        saved.append(fpath)

    return saved


# ===========================================================================
# グラフ3: 帯域制御精度 箱ひげ図 (全ID横並び)
# ===========================================================================

def plot_graph3(df, target_date, output_dir):
    """
    全IDの帯域制御精度を箱ひげ図で横並び比較する。
    """
    os.makedirs(output_dir, exist_ok=True)
    all_ids = df["id"].unique()

    error_data = {}
    for tid in all_ids:
        # 日付フィルタリング
        d = df[
            (df["id"] == tid)
            & (df["timestamp"].dt.date == pd.Timestamp(target_date).date())
        ]
        # 制限が発動（ドロップ発生）しているデータのみ抽出
        d_drop = d[d["new_dropped_packets_in"] > 0]
        if len(d_drop) > 0:
            # 誤差計算 (%)
            err = (d_drop["new_volume_mbps_in"] - d_drop["limit_mbps_in"]) / d_drop["limit_mbps_in"] * 100
            error_data[tid] = err.dropna().values

    fig, ax = plt.subplots(figsize=(14, 8)) # 凡例スペース確保のため少し横幅を広げました

    if error_data:
        labels = list(error_data.keys())
        data = [error_data[k] for k in labels]

        # 箱ひげ図の描画
        ax.boxplot(
            data, tick_labels=labels, patch_artist=True,
            boxprops=dict(facecolor="lightblue", alpha=0.7),
            medianprops=dict(color="red", linewidth=2),
            whiskerprops=dict(linewidth=1.2),
            flierprops=dict(marker="o", markersize=4, alpha=0.5, markerfacecolor="gray"),
        )

        # 基準線の描画
        ax.axhline(y=0, color="orange", linestyle="--", linewidth=1)
        ax.axhline(y=10, color="red", linestyle=":", linewidth=2.0, alpha=0.5)
        ax.axhline(y=-10, color="red", linestyle=":", linewidth=2.0, alpha=0.5)

        # --- 数値ラベルとn数の表示 ---
        for i, (label, vals) in enumerate(zip(labels, data)):
            if len(vals) == 0: continue
            
            q1, med, q3 = np.percentile(vals, [25, 50, 75])
            iqr = q3 - q1
            wl = np.min(vals[vals >= q1 - 1.5 * iqr]) if any(vals >= q1 - 1.5 * iqr) else np.min(vals)
            wh = np.max(vals[vals <= q3 + 1.5 * iqr]) if any(vals <= q3 + 1.5 * iqr) else np.max(vals)
            
            x = i + 1
            off = 0.35
            fs = 8
            
            # 統計数値ラベル (小数第1位に丸め)
            ax.text(x + off, med, f"Med: {med:.1f}%", va="center", ha="left", fontsize=fs, color="red", fontweight="bold")
            ax.text(x + off, q3,  f"Q3:  {q3:.1f}%",  va="bottom", ha="left", fontsize=fs, color="gray")
            ax.text(x + off, q1,  f"Q1:  {q1:.1f}%",  va="top",    ha="left", fontsize=fs, color="gray")
            ax.text(x + off, wh,  f"Max: {wh:.1f}%",  va="bottom", ha="left", fontsize=fs, color="gray")
            ax.text(x + off, wl,  f"Min: {wl:.1f}%",  va="top",    ha="left", fontsize=fs, color="gray")
            
            # n数（サンプル数）の表示 - グラフ下部に青字太字で配置
            ax.text(x, ax.get_ylim()[0], f"n={len(vals)}", 
                    va="bottom", ha="center", fontsize=9, color="blue", fontweight="bold")

        # --- カスタム凡例の作成 ---
        custom_elements = [
            Line2D([0], [0], color="red", lw=2, label="Median (Actual)"),
            mpatches.Patch(facecolor="lightblue", alpha=0.7, label="Interquartile Range (Q1-Q3)"),
            Line2D([0], [0], color="orange", lw=1, ls="--", label="Target Limit (0%)"),
            Line2D([0], [0], color="red", lw=1, ls=":", alpha=0.5, label="±10% Threshold"),
            Line2D([0], [0], marker="o", color="w", markerfacecolor="gray", markersize=6, label="Outliers"),
            Line2D([0], [0], color="blue", marker="None", ls="None", label=f"n = Sample Count (Drop detected)")
        ]
        ax.legend(handles=custom_elements, loc="upper right", fontsize=9, frameon=True, shadow=True)

        ax.set_xlabel("ID")
        ax.set_ylabel("Error: (volume_in - limit) / limit * 100 (%)")
        ax.set_title(f"Graph 3: Bandwidth Control Accuracy by ID ({target_date})")
        ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    fname = f"graph3_boxplot_{target_date}.png"
    fpath = os.path.join(output_dir, fname)
    fig.savefig(fpath, bbox_inches="tight")
    plt.close(fig)
    return fpath


# ===========================================================================
# グラフ4: トラヒック量 vs 精度劣化 散布図 (複数日間対応)
# ===========================================================================

def plot_graph4(df, start_date, end_date, output_dir, target_ids=None):
    """
    指定期間におけるトラヒック量と帯域制御精度劣化の相関を散布図で描画する。

    表示要素:
      - X軸: volume_in (Mbps)
      - Y軸: 誤差(%), packet_drop_pkt > 0 のみ
      - 色: 時刻 (00:00〜23:55 固定カラーマップ)
      - 期間内の全データをプロット

    Args:
        df (pd.DataFrame): 統合CSV DataFrame
        start_date (str): 開始日 (YYYY-MM-DD)
        end_date (str): 終了日 (YYYY-MM-DD)
        output_dir (str): 画像出力先ディレクトリ
        target_ids (list[str], optional): 
            描画対象のIDリスト。Noneの場合はdf内の全IDを対象とする。

    Returns:
        list[str]: 保存したファイルパスのリスト。
                   データが存在しないIDについてはリストに含まれない。
    """
    if target_ids is None:
        target_ids = df["id"].unique()

    os.makedirs(output_dir, exist_ok=True)
    saved = []

    start_d = pd.Timestamp(start_date).date()
    end_d = pd.Timestamp(end_date).date()

    for tid in target_ids:
        # 期間でフィルタリング
        d = df[
            (df["id"] == tid)
            & (df["timestamp"].dt.date >= start_d)
            & (df["timestamp"].dt.date <= end_d)
        ].copy()

        # 制限が発動（ドロップ発生）しているデータのみ抽出
        d_drop = d[d["new_dropped_packets_in"] > 0].copy()
        if len(d_drop) == 0:
            continue

        # 誤差計算 (%)
        d_drop["error_pct"] = (
            (d_drop["new_volume_mbps_in"] - d_drop["limit_mbps_in"]) / d_drop["limit_mbps_in"] * 100
        )
        
        # 時刻を0〜1に正規化（色の指定用: 00:00=0, 23:55=1）
        d_drop["time_norm"] = (
            d_drop["timestamp"].dt.hour * 60 + d_drop["timestamp"].dt.minute
        ) / (24 * 60)

        fig, ax = plt.subplots(figsize=(12, 7))

        # 散布図の描画 (複数日分が重なるため alpha=0.5 で透過)
        scatter = ax.scatter(
            d_drop["new_volume_mbps_in"], d_drop["error_pct"],
            c=d_drop["time_norm"], 
            cmap="turbo",        # ← 見やすさ重視の虹色マップ
            vmin=0, vmax=1,
            alpha=0.6,           # 透過度
            s=50,                # 点のサイズを少し大きく
            edgecolors="black",  # 点の縁取りを黒に
            linewidths=0.2       # 縁取りの太さ
        )

        # 基準線 (0%, +/-10%)
        ax.axhline(y=0, color="gray", linewidth=1.0, alpha=0.8)
        ax.axhline(y=10, color="red", linewidth=1.5, linestyle=":", alpha=0.6, label="+/-10% Threshold")
        ax.axhline(y=-10, color="red", linewidth=1.5, linestyle=":", alpha=0.6)

        ax.set_xlabel("Internet -> User Throughput (Mbps)")
        ax.set_ylabel("Accuracy Error (%)")
        ax.set_title(f"Graph 4: Traffic Volume vs Control Accuracy\nID: {tid} ({start_date} ~ {end_date})")
        
        # 凡例の設定
        from matplotlib.lines import Line2D
        custom_legend = [
            Line2D([0], [0], color="red", lw=1.5, ls=":", label="±10% Threshold"),
            Line2D([0], [0], color="blue", marker='o', ls='None', label=f"n={len(d_drop)} (Total Drops)")
        ]
        ax.legend(handles=custom_legend, loc="upper right", fontsize=9)
        
        ax.grid(True, alpha=0.2)

        # カラーバー（右側の時刻ガイド）
        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label("Time of Day")
        cbar.set_ticks([i / 24 for i in range(0, 25, 3)])
        cbar.set_ticklabels([f"{i:02d}:00" for i in range(0, 25, 3)])

        plt.tight_layout()
        fname = f"graph4_scatter_{tid}.png"
        fpath = os.path.join(output_dir, fname)
        fig.savefig(fpath, bbox_inches="tight")
        plt.close(fig)
        saved.append(fpath)

    return saved


