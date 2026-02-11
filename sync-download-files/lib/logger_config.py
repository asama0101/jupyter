#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os

def setup_logger(name, base_dir, log_to_file=True, file_name="execute.log"):
    """
    Purpose:
        プロジェクト共通のロガー（記録係）をセットアップする。
    Usage:
        logger = setup_logger("MY_APP", "logs/", log_to_file=True)
    Arguments:
        name (str): ロガーの識別名。この名前で記録者が区別される。
        base_dir (str): ログファイルを保存するディレクトリのパス。
        log_to_file (bool): Trueならファイルにも保存、Falseなら画面表示のみ。
        file_name (str): 保存するファイルの名前。デフォルトは "execute.log"。
    Returns:
        logging.Logger: 設定が完了したロガーオブジェクト。
    """
    
    # 指定した名前でロガー（記録本体）を作成・取得
    logger = logging.getLogger(name)
    
    # ログの重要度（レベル）を設定 (DEBUG < INFO < WARNING < ERROR < CRITICAL)
    logger.setLevel(logging.INFO)

    # ハンドラの重複登録チェック（二重出力を防止）
    if not logger.handlers:
        
        # ログの見た目（フォーマット）を定義
        # 例: 2026-02-11 15:00:00 [INFO] [識別名] メッセージ
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(name)s] %(message)s', 
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # コンソール（画面）出力用のハンドラ設定
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        logger.addHandler(sh)

        # ファイル出力用のハンドラ設定
        if log_to_file:
            # ディレクトリパスとファイル名を結合
            log_path = os.path.join(base_dir, file_name)
            
            fh = logging.FileHandler(log_path)
            fh.setFormatter(formatter)
            logger.addHandler(fh)

    # 設定済みのロガーを返す
    return logger