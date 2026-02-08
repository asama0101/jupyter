import logging
import os

def setup_logger(name, base_dir, log_to_file=True, file_name="execute.log"):
    """
    プロジェクト共通のロガー（記録係）をセットアップする関数。

    Args:
        name (str): ロガーの識別名。この名前で記録者が区別されます。
        base_dir (str): ログファイルを保存するフォルダのパス。
        log_to_file (bool): Trueならファイルにも保存、Falseなら画面表示のみ。
        file_name (str): 保存するファイルの名前。指定がなければ "execute.log"。

    Returns:
        logging.Logger: 設定が完了したロガーオブジェクト。
    """
    
    # 1. 指定した名前でロガー（記録本体）を作成・取得
    logger = logging.getLogger(name)
    
    # 2. ログの重要度（レベル）を設定。INFO以上に設定すると「単なる情報」から記録する
    # (DEBUG < INFO < WARNING < ERROR < CRITICAL)
    logger.setLevel(logging.INFO)

    # 3. ハンドラの重複登録チェック
    # これをしないと、関数を何度も呼んだときにログが2重3重に出力されてしまいます
    if not logger.handlers:
        
        # 4. ログの見た目（フォーマット）を定義
        # 例: 2026-02-08 12:00:00 [INFO] [ロガーの識別名] メッセージ内容
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(name)s] %(message)s', 
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 5. コンソール（画面）に出力するための設定
        sh = logging.StreamHandler()
        sh.setFormatter(formatter) # 上で決めた見た目を適用
        logger.addHandler(sh)      # ロガーに「画面出力担当」を追加

        # 6. ファイルに出力するための設定
        if log_to_file:
            # フォルダパスとファイル名を合体させてフルパスを作成
            log_path = os.path.join(base_dir, file_name)
            
            # ファイル書き込み用の設定
            fh = logging.FileHandler(log_path)
            fh.setFormatter(formatter) # 画面と同じ見た目を適用
            logger.addHandler(fh)      # ロガーに「ファイル書き出し担当」を追加

    # 7. 準備が整ったロガーを返す
    return logger