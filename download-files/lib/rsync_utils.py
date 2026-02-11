#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
目的：rsync同期の実行、および「今回ダウンロードされたファイルのみ」を共通ログ形式で出力する。
使い方：外部（Jupyter等）から rsync_pull(conf) を呼び出すか、本ファイルを直接実行する。
引数：
    conf (dict): 接続情報、パス、フィルタ等を含む設定辞書。
返り値：
    str: 実行結果の成否ステータスメッセージ。
"""

import pexpect
import os
import sys
from logger_config import setup_logger

def rsync_pull(conf):
    """
    目的：設定に基づきrsyncを実行し、実際に転送が発生したファイルのみログに記録する。
    使い方：JupyterまたはCLIから呼び出し。SSH初回確認は自動スキップされる。
    引数：
        conf (dict): 以下のキーを含む辞書
            - REMOTE_USER, REMOTE_HOST, PASSWORD, SRC_DIR, DEST_DIR, 
            - BW_LIMIT, EXT_FILTER, LOG_FILE_NAME, LOG_TO_FILE, ENABLE_LOG
    返り値：
        str: "Success: ..." または "Error: ..."
    """
    # ログ出力先ディレクトリの自動作成（FileNotFoundError対策）
    log_file_path = conf.get("LOG_FILE_NAME", "log/execute.log")
    log_dir = os.path.dirname(os.path.abspath(log_file_path))
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.basename(log_file_path)
    logger = setup_logger("RSYNC_PULL", log_dir, conf.get("LOG_TO_FILE", True), log_file)

    # SSHオプション（ホスト鍵確認スキップ）
    ssh_opts = "-e 'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'"
    command = (
        f"rsync -avz {ssh_opts} --itemize-changes --bwlimit={conf['BW_LIMIT']} "
        f"--include='{conf['EXT_FILTER']}' --exclude='*' "
        f"{conf['REMOTE_USER']}@{conf['REMOTE_HOST']}:{conf['SRC_DIR']} {conf['DEST_DIR']}"
    )

    try:
        logger.info(f"Sync started: {conf['REMOTE_HOST']} -> {conf['DEST_DIR']}")
        
        child = pexpect.spawn(command, timeout=None, encoding='utf-8')
        if conf.get("ENABLE_LOG", False):
            child.logfile_read = sys.stdout 

        index = child.expect(['assword:', pexpect.EOF, pexpect.TIMEOUT], timeout=30)
        if index == 0:
            child.sendline(conf["PASSWORD"])
        
        child.expect(pexpect.EOF)
        output = child.before
        
        # 転送されたファイルの抽出 (">f" で始まる行)
        downloaded_files = [line.split(' ', 1)[1] for line in output.splitlines() if line.startswith('>f')]

        res = "Success: Sync completed"
        logger.info(res)
        
        if downloaded_files:
            logger.info("--- Newly Downloaded Files List Start ---")
            for f in downloaded_files:
                logger.info(f"DOWNLOADED: {f}")
            logger.info("--- Newly Downloaded Files List End ---")
        else:
            logger.info("No new files were downloaded (Already up-to-date).")
        
        return res

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return f"Error: {str(e)}"

if __name__ == "__main__":
    """
    目的：CLIから直接実行された際、プロジェクトルートを起点に設定ファイルを読み込み同期を行う。
    使い方：python3 lib/rsync_utils.py （プロジェクトルートディレクトリで実行）
    引数：なし
    返り値：なし
    """
    import json
    
    # 実行ファイルの場所に関わらずプロジェクトルートを特定
    # lib/rsync_utils.py の1つ上の階層をルートとする
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CONFIG_PATH = os.path.join(BASE_DIR, "vault", "config.json")
    
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            conf = json.load(f)
        
        # パスをルート基準の絶対パスに補正して実行場所依存を排除
        if not os.path.isabs(conf["DEST_DIR"]):
            conf["DEST_DIR"] = os.path.join(BASE_DIR, conf["DEST_DIR"])
        if not os.path.isabs(conf["LOG_FILE_NAME"]):
            conf["LOG_FILE_NAME"] = os.path.join(BASE_DIR, conf["LOG_FILE_NAME"])
            
        print(f"Starting rsync process from CLI...")
        result = rsync_pull(conf)
        print(f"Result: {result}")
    else:
        print(f"Error: Config file not found at {CONFIG_PATH}")
        sys.exit(1)