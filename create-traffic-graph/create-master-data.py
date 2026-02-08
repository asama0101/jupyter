# ==========================================
# ライブラリのインポート
# ==========================================
# 標準ライブラリのインポート
import sys
import os
import logging
from datetime import datetime
import pandas

# プロジェクトルートを検索パスに追加（lib/ をパッケージとして認識させるため）
sys.path.append(os.path.abspath('.'))

# 自作ライブラリのインポート
from lib import data_loader
from lib import logger_config


# ==========================================
# ユーザー設定 (CONFIG)
# ==========================================
# DIRS:          データの読み書きを行うフォルダの場所を指定します。
#   - BASE:      実行の基準となるフォルダ（通常は現在の場所）。
#   - RAW:       元データ（CSV）が届く場所。
#   - INTERIM:   日付やIDを整えた「クレンジング済み」の一時ファイルを置く場所。
#   - PROCESSED: 単位変換（Mbps計算）などを終えたファイルを置く場所。
#   - OUT:       全データを合体させた「最終アウトプット」を出す場所。
#
# KEYS:          異なるデータを合体させる際に「共通の目印」とする列の名前です。
#
# DEVICES:       機器ごとのCSVのクセを調整するための設定リストです。
#   - id:        機器を識別するための内部用の名前。
#   - pattern:   対象となるCSVファイルを探すための名前のルール。
#   - read_opts: CSV読み込み時の特殊ルール（コメント行の無視など）。
#   - clean:     「クレンジング」指示。日付形式の統一やIDの合体方法を決めます。
#   - renames:   列の名前を日本語からプログラム用の英語に変換するマップ。
#   - mbps:      計算（ByteからMbps）を行う対象の列を指定します。
# ==========================================
PROJECT_CONFIG = {
    "DIRS": {
        "BASE": os.getcwd(),
        "RAW": "./data/raw",
        "INTERIM": "./data/interim",
        "PROCESSED": "./data/processed",
        "OUT": "./result"
    },
    "KEYS": ["timestamp", "line_id"],
    "LOG_FILE_NAME": "execution.log",
    "DEVICES": [
        {
            "id": "dev01",
            "pattern": "*traffic-01*.csv",
            "renames": {
                "タイムスタンプ": "timestamp", 
                "回線番号": "line_id",
                "下りのトラヒック量(Byte)": "dev01_down_Byte",
                "上りのトラヒック量(Byte)": "dev01_up_Byte",
                "下りの廃棄量(Byte)": "dev01_drop_Byte"
            },
            "mbps": {
                "dev01_down_Byte": "dev01_down_Mbps",
                "dev01_up_Byte": "dev01_up_Mbps",
                "dev01_drop_Byte": "dev01_drop_Mbps"
            }
        },
        {
            "id": "dev02",
            "pattern": "sample-traffic-02.csv",
            "read_opts": {"comment": "#", "quotechar": '"'},
            "clean": {
                "date": {"col": "timestamp", "fmt": "%Y%m%d%H%M%S"},
                "id": ["code", "identifer"]
            },
            "renames": {
                "volume_in": "dev02_down_Byte",
                "volume_out": "dev02_up_Byte"
            },
            "mbps": {
                "dev02_down_Byte": "dev02_down_Mbps",
                "dev02_up_Byte": "dev02_up_Mbps"
            }
        }
    ]
}

APP_NAME = "CREATE_MASTER-DATA"

# ==========================================
# 関数定義
# CSVをクレンジング（掃除）・加工・結合し、マスターデータ作成
# ==========================================

def execute_pipeline(conf):
    """
    データ処理のメイン工程（パイプライン）を実行する関数。
    
    Args:
        conf (dict): フォルダの場所やデバイスごとの設定が入った辞書。
    Returns:
        str: 成功したら "Success"、失敗したらエラー内容を返す。
    """
    # 設定ファイルから「フォルダの場所(dirs)」と「結合の目印(keys)」を取り出す
    dirs = conf["DIRS"]
    keys = conf["KEYS"]
    
    # 処理の記録を付けるための「ロガー」を準備（どこに保存するかなどを指定）
    logger = logger_config.setup_logger(
        APP_NAME, 
        dirs.get("BASE"), 
        file_name=conf.get("LOG_FILE_NAME")
    )
    
    logger.info("=== Pipeline Execution Started (Full Logic) ===")

    try:
        # --------------------------------------------------
        # Step 1: Cleaning (生データの読み込みとお掃除)
        # --------------------------------------------------
        # 設定にあるデバイスの数だけ、順番に処理を繰り返す
        for dev in conf["DEVICES"]:
            # 生データ(RAW)フォルダから、指定されたパターンのCSVファイルを読み込む
            df = data_loader.load_csv(dirs["RAW"], dev["pattern"], dev.get("read_opts"))
            if df is None:
                continue # ファイルが見つからない場合は次のデバイスへ
            
            # 「clean」の設定がある場合、日付やIDを使いやすい形に整える
            if dev.get("clean"):
                # 日付変換の設定を取得
                d_cfg = dev["clean"].get("date")
                if d_cfg:
                    # 日付列を文字列から日時の形式（datetime）に変換した後、指定の形式（YYYY-MM-DD HH:MM:SS）の文字列に整える
                    df[d_cfg['col']] = pandas.to_datetime(df[d_cfg['col']], format=d_cfg['fmt']).dt.strftime('%Y-%m-%d %H:%M:%S')
                
                # ID（回線を識別する名前）を作る設定を取得
                id_p = dev["clean"].get("id")
                if id_p:
                    # 指定された2つの列を文字列として取得し、ハイフンで繋いで新しいID列「line_id」を作成する
                    df['line_id'] = df[id_p[0]].astype(str) + "-" + df[id_p[1]].astype(str)
            
            # クレンジングが終わったデータを、一時保存用の「INTERIM」フォルダに保存する
            data_loader.save_csv(df, os.path.join(dirs["INTERIM"], f"{dev['id']}_cleaned.csv"))

        # --------------------------------------------------
        # Step 2: Processing (リネームとMbps計算)
        # --------------------------------------------------
        # お掃除が終わったファイルを読み込み、計算や列名の変更を行う
        for dev in conf["DEVICES"]:
            in_path = os.path.join(dirs["INTERIM"], f"{dev['id']}_cleaned.csv")
            if not os.path.exists(in_path):
                continue
            
            # 保存した一時ファイルを読み直す
            df = pandas.read_csv(in_path)
            
            # 設定（CONFIG）で指定した対応表に従って、列名を日本語から英語などへ変更する
            df = df.rename(columns=dev["renames"])
            
            # 通信量の単位を「Byte」から「Mbps（速度）」に変換する計算
            m_map = dev.get("mbps", {})
            for b_col, m_col in m_map.items():
                if b_col in df.columns:
                    # 通信速度の計算式: (バイト数 * 8ビット) / (5分間の秒数 * 100万)
                    df[m_col] = ((df[b_col] * 8) / (300 * 1000000)).round(1)
            
            # 結合キー、変更後の列名、計算したMbps列を合算して「必要な列リスト」を作成する
            req = keys + list(dev["renames"].values()) + list(m_map.values())
            # 実際にデータフレーム内に存在している列だけを抽出し、不足エラーを防ぐ
            actual = [c for c in req if c in df.columns]
            # 必要な列だけに絞り込んだデータを、加工済みフォルダに保存する
            data_loader.save_csv(df[actual], os.path.join(dirs["PROCESSED"], f"{dev['id']}_processed.csv"))

        # --------------------------------------------------
        # Step 3: Merging (全デバイスのデータを合体)
        # --------------------------------------------------
        # バラバラだった各デバイスの表を、時間とIDを基準に「横」に繋げる
        merged_df = None
        for dev in conf["DEVICES"]:
            p_path = os.path.join(dirs["PROCESSED"], f"{dev['id']}_processed.csv")
            if not os.path.exists(p_path):
                continue
            
            df = pandas.read_csv(p_path)
            # 最初の1台目のデータなら、それを合体データの土台にする
            if merged_df is None:
                merged_df = df
            else:
                # 2台目以降は、時間(timestamp)とID(line_id)が一致する場所で横に合体させる
                merged_df = pandas.merge(merged_df, df, on=keys, how='outer').fillna(0)

        # 全ての合体が無事に終わっていたら、最後の仕上げをする
        if merged_df is not None:
            # 「_Byte」で終わる名前の列（通信量）を、小数点のない「整数型(int)」に変換して見やすくする
            for c in [c for c in merged_df.columns if c.endswith('_Byte')]:
                merged_df[c] = merged_df[c].astype(int)
            
            # 最終的なマスターデータを「OUT」フォルダに書き出す
            final_path = os.path.join(dirs["OUT"], "master_data.csv")
            data_loader.save_csv(merged_df, final_path)
            logger.info(f"Final Report created: {final_path}")
            return "Success"
        
        return "Error: No data to merge"

    # もし途中で予期せぬエラー（ファイルが壊れている等）が起きたら、ログに記録して中断する
    except Exception as e:
        logger.error(f"Critical Pipeline Error: {str(e)}")
        return f"Error: {str(e)}"

# ==========================================
# 実行エントリーポイント
# ==========================================
if __name__ == "__main__":
    result = execute_pipeline(PROJECT_CONFIG)
    print(f"Status: {result}")