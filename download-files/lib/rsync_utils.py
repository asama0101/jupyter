#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
【rsync_pull: 汎用リモート同期モジュール】

■ 目的:
    SSH鍵が設定できない環境において、パスワード認証を自動化し、
    リモートから指定したパターンのファイルを同期する。

■ 設定項目の凡例 (DEFAULT_CONFIG):
    - BASE_DIR      : 基準ディレクトリ。ログ出力や同期先の起点。
    - REMOTE_USER   : 接続先サーバのユーザー名。
    - REMOTE_HOST   : 接続先サーバのIPアドレス。
    - PASSWORD      : SSHパスワード。
    - SRC_DIR       : 同期元（リモート）パス。末尾 / でディレクトリ内を同期。
    - DEST_DIR      : 同期先（ローカル）パス。NoneならBASE_DIR配下に作成。
    - BW_LIMIT      : 帯域制限 (KB/s)。1024 = 1MB/s。
    - EXT_FILTER    : 同期対象ファイルパターン (例: *.csv, *.log)。
    - ENABLE_LOG    : Trueで詳細な転送ログを画面にリアルタイム表示。
    - LOG_FILE_NAME : ログファイル名 (デフォルト: execute.log)。

■ 使い方1：直接実行（cronなど）
    $ python3 rsync_utils.py
    ※ 下記の DEFAULT_CONFIG の内容で動作します。

■ 使い方2：cron（定期実行）への登録
    $ crontab -e
    以下の1行を末尾に追加してください（例：毎日深夜1時に実行）
    00 01 * * * /usr/bin/python3 /home/jupyter_projects/download-files/lib/rsync_utils.py

■ 使い方3：他のPythonファイルから呼び出し（モジュール利用）
    from lib.rsync_utils import rsync_pull
    rsync_pull({"EXT_FILTER": "*.log"})

■ 依存関係:
    - pexpect（外部ライブラリ）
    - logger_config（自作モジュール）
"""

import pexpect
import sys
import os

# 自分のディレクトリを検索パスに加える
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)
    
from logger_config import setup_logger

# ==========================================
# デフォルト設定項目
# ==========================================
DEFAULT_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_NAME = "RSYNC_PULL"

DEFAULT_CONFIG = {
    "BASE_DIR": DEFAULT_BASE_DIR,
    "REMOTE_USER": "asama",
    "REMOTE_HOST": "192.168.3.61",
    "PASSWORD": "Qu!ckly4589",
    "SRC_DIR": "/home/jupyter_projects/input/",
    "DEST_DIR": None,
    "BW_LIMIT": "1024",
    "EXT_FILTER": "*.csv",
    "ENABLE_LOG": False,
    "LOG_TO_FILE": True,
    "LOG_FILE_NAME": "execute.log"
}

def rsync_pull(config_override=None):
    """
    rsync同期を実行する。
    :param config_override: デフォルト値を上書きしたい項目を辞書で指定
    :return: 実行結果のメッセージ
    """
    # 設定の準備
    conf = DEFAULT_CONFIG.copy()
    if config_override:
        conf.update(config_override)

    # 基準ディレクトリの確定と移動
    target_base = conf["BASE_DIR"]
    os.chdir(target_base)

    # 同期先ディレクトリの確定
    if conf["DEST_DIR"] is None:
        conf["DEST_DIR"] = os.path.join(target_base, "rsync_pull_files")

    # ロガーのセットアップ（logger_config.pyから読み込み）
    logger = setup_logger(
        name=APP_NAME, 
        base_dir=target_base, 
        log_to_file=conf["LOG_TO_FILE"],
        file_name=conf["LOG_FILE_NAME"]
    )

    # 同期先ディレクトリの作成
    if not os.path.exists(conf["DEST_DIR"]):
        os.makedirs(conf["DEST_DIR"])

    # rsyncコマンドの構築
    command = (
        f'rsync -az --bwlimit={conf["BW_LIMIT"]} '
        f'-e "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" '
        f'--include="{conf["EXT_FILTER"]}" '
        f'--exclude="*" '
        f'{conf["REMOTE_USER"]}@{conf["REMOTE_HOST"]}:{conf["SRC_DIR"]} {conf["DEST_DIR"]}'
    )

    logger.info(f"Sync started: {conf['REMOTE_HOST']}:{conf['SRC_DIR']} -> {conf['DEST_DIR']}")

    try:
        # pexpectを使用してrsyncコマンドを起動
        # timeout=None は大きなファイル転送中にpexpect自体がタイムアウトで終了するのを防ぐ設定
        child = pexpect.spawn(command, timeout=None)

        # 設定(ENABLE_LOG)がTrueなら、rsyncの標準出力を直接画面に表示する
        if conf["ENABLE_LOG"]:
            child.logfile = sys.stdout.buffer

        # プロンプト（入力待ち）に特定の文字列が出るのを待つ
        # 0: 'assword:' が出た / 1: 終了した(EOF) / 2: 30秒経っても反応なし(TIMEOUT)
        i = child.expect(['assword:', pexpect.EOF, pexpect.TIMEOUT], timeout=30)

        if i == 0:
            # --- ケース0: パスワードを求められた場合 ---
            # 設定したパスワードを送信する
            child.sendline(conf["PASSWORD"])
            # 同期が完了して接続が切れる(EOF)まで待機する
            child.expect(pexpect.EOF)
            logger.info("Success: Sync completed via password authentication.")
            return "Success: Sync completed"

        elif i == 1:
            # --- ケース1: パスワードを求められずに終了した場合 ---
            logger.info("Success: Sync finished (No password prompted).")
            return "Success: No password prompted"

        elif i == 2:
            # --- ケース2: タイムアウトした場合 ---
            logger.error("Error: Connection Timeout during password prompt.")
            return "Error: Connection Timeout"

    except Exception as e:
        # 予期せぬ不具合（rsync未インストール等）をキャッチして記録する
        logger.error(f"Unexpected error: {str(e)}")
        return f"Error: {str(e)}"

    finally:
        # 起動したプロセスがまだ生きていれば確実に終了させる
        if 'child' in locals() and child.isalive():
            child.close()

if __name__ == "__main__":
    rsync_pull()