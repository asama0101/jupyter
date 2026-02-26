"""
calc_traffic.py - トラヒック計算ユーティリティ
==============================================
Byte⇔Mbps変換など、複数モジュールから使用される共通計算関数を提供する。

使い方:
    from src.calc_traffic import bytes_to_mbps, mbps_to_bytes
"""


def bytes_to_mbps(byte_value):
    """
    5分間のByte累積量をMbps（ビットレート）に変換する。

    変換式: Mbps = Byte × 8 / (5分 × 60秒) / 1,000,000

    Args:
        byte_value (float or pd.Series): 5分間のByte累積量

    Returns:
        float or pd.Series: Mbps値

    Example:
        >>> bytes_to_mbps(37_500_000_000)  # 100Mbps相当
        100.0
    """
    return byte_value * 8 / (5 * 60) / 1e6


def mbps_to_bytes(mbps_value):
    """
    Mbps（ビットレート）を5分間のByte累積量に変換する。
    bytes_to_mbps の逆変換。

    変換式: Byte = Mbps × 5分 × 60秒 / 8 × 1,000,000

    Args:
        mbps_value (float or pd.Series): Mbps値

    Returns:
        float or pd.Series: 5分間のByte累積量

    Example:
        >>> mbps_to_bytes(100.0)
        37500000000.0
    """
    return mbps_value * 5 * 60 / 8 * 1e6


def calc_error_pct(volume_in_mbps, limit_mbps):
    """
    limitに対するvolume_inの誤差(%)を計算する。

    計算式: (volume_in_mbps - limit_mbps) / limit_mbps × 100

    Args:
        volume_in_mbps (float): volume_in (Mbps)
        limit_mbps (float): limit (Mbps)

    Returns:
        float: 誤差(%)。limit_mbpsが0以下の場合はNaN。

    Example:
        >>> calc_error_pct(660, 600)  # limitより10%高い
        10.0
    """
    if limit_mbps <= 0:
        return float("nan")
    return (volume_in_mbps - limit_mbps) / limit_mbps * 100
