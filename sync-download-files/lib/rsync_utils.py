#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pexpect
import os
import sys
from logger_config import setup_logger

def rsync_pull(conf):
    """
    Purpose:
        設定に基づきrsyncを実行し、実際に転送が発生したファイルのみログに記録する。
    Usage:
        result = rsync_pull(conf)
    Arguments:
        conf (dict): 以下のキーを含む設定辞書
            - REMOTE_USER: リモートユーザ名
            - REMOTE_HOST: リモートホスト名/IP
            - PASSWORD: SSHパスワード
            - SRC_DIR: 送信元ディレクトリパス
            - DEST_DIR: 送信先ディレクトリパス
            - BW_LIMIT: 帯域制限(kbps)
            - EXT_FILTER: フィルタする拡張子
            - LOG_FILE_NAME: ログファイル出力パス
            - LOG_TO_FILE: ファイル出力の有無(bool)
            - ENABLE_LOG: 標準出力への表示有無(bool)
    Returns:
        str: 実行結果の成否ステータスメッセージ
    """
    # --- 1. 準備：ログ設定とディレクトリ作成 ---
    # ログファイルのフルパスから親ディレクトリを取得
    log_file_path = conf.get("LOG_FILE_NAME", "log/execute.log")
    log_dir = os.path.dirname(os.path.abspath(log_file_path))
    
    # ログ保存先フォルダが存在しない場合は自動で作成（エラー防止）
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # 共通ロガーを初期化
    log_file = os.path.basename(log_file_path)
    logger = setup_logger("RSYNC_PULL", log_dir, conf.get("LOG_TO_FILE", True), log_file)

    # --- 2. rsyncコマンドの構築 ---
    # SSH接続時のオプション定義
    # StrictHostKeyChecking=no: 初回接続時の「Are you sure you want to continue connecting?」をスキップ
    ssh_opts = "-e 'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'"
    
    # rsyncコマンドの組み立て
    # -a: アーカイブモード, -v: 詳細表示, -z: 圧縮転送
    # --itemize-changes: 転送された理由（新規、更新等）を示す符号を各行の先頭に付与する
    # --bwlimit: ネットワーク帯域を制限
    # --include/--exclude: 特定の拡張子のみを抽出し、それ以外を除外
    command = (
        f"rsync -avz {ssh_opts} --itemize-changes --bwlimit={conf['BW_LIMIT']} "
        f"--include='{conf['EXT_FILTER']}' --exclude='*' "
        f"{conf['REMOTE_USER']}@{conf['REMOTE_HOST']}:{conf['SRC_DIR']} {conf['DEST_DIR']}"
    )

    try:
        logger.info(f"Sync started: {conf['REMOTE_HOST']} -> {conf['DEST_DIR']}")
        
        # --- 3. pexpectによる対話制御の開始 ---
        # コマンドを非同期で実行し、出力を監視する
        child = pexpect.spawn(command, timeout=None, encoding='utf-8')
        
        # ENABLE_LOGが有効なら、rsyncの標準出力を現在のターミナル（sys.stdout）にリアルタイム表示
        if conf.get("ENABLE_LOG", False):
            child.logfile_read = sys.stdout 

        # 「assword:」（Password: の後ろ部分）という文字列が出るのを待つ
        # EOF（終了）や TIMEOUT（失敗）も同時に待ち受ける
        index = child.expect(['assword:', pexpect.EOF, pexpect.TIMEOUT], timeout=30)
        
        # パスワードプロンプトが出た場合
        if index == 0:
            child.sendline(conf["PASSWORD"]) # パスワードを送ってEnterを叩く
        
        # 転送作業が完了（EOF）するまで待機
        child.expect(pexpect.EOF)
        output = child.before # ここまでの標準出力をすべて変数に格納
        
        # --- 4. 実行結果の解析（今回の目玉機能） ---
        # --itemize-changes により、新規転送されたファイルは行頭が ">f" で始まる
        # 例: ">f+++++++ filename.txt"
        # この行を抽出し、スペースで区切った後の「ファイル名部分」だけを取り出す
        downloaded_files = [line.split(' ', 1)[1] for line in output.splitlines() if line.startswith('>f')]

        res = "Success: Sync completed"
        logger.info(res)
        
        # 今回実際にダウンロードされたファイルがあれば一覧をログに記録
        if downloaded_files:
            logger.info("--- Newly Downloaded Files List Start ---")
            for f in downloaded_files:
                logger.info(f"DOWNLOADED: {f}")
            logger.info("--- Newly Downloaded Files List End ---")
        else:
            # 転送対象がなかった場合
            logger.info("No new files were downloaded (Already up-to-date).")
        
        return res

    except Exception as e:
        # 予期せぬエラー（接続失敗、パス間違い等）のログ記録
        logger.error(f"Error: {str(e)}")
        return f"Error: {str(e)}"


if __name__ == "__main__":
    """
    直接実行（ python3 rsync_utils.py ）時の挙動
    """
    import json
    
    # スクリプトの場所からプロジェクトルート（BASE_DIR）を計算
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CONFIG_PATH = os.path.join(BASE_DIR, "vault", "config.json")
    
    # 1. 設定ファイルの読み込み
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            conf = json.load(f)
        
        # 2. パス補正（相対パスをBASE_DIR起点に書き換え、どこから実行してもパスが通るようにする）
        if not os.path.isabs(conf["DEST_DIR"]):
            conf["DEST_DIR"] = os.path.join(BASE_DIR, conf["DEST_DIR"])
        if not os.path.isabs(conf["LOG_FILE_NAME"]):
            conf["LOG_FILE_NAME"] = os.path.join(BASE_DIR, conf["LOG_FILE_NAME"])
            
        print(f"Starting rsync process from CLI...")
        # 3. 同期処理の実行
        result = rsync_pull(conf)
        print(f"Result: {result}")
    else:
        print(f"Error: Config file not found at {CONFIG_PATH}")
        sys.exit(1)