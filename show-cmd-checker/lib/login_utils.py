#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
from datetime import datetime
from netmiko import ConnectHandler, redispatch

def login_telnet(device_params, hostname_key, log_file=None) -> ConnectHandler:
    """
    Purpose:
        踏み台サーバ等へTelnet接続し、対話的な認証（ユーザ名・パスワード入力）を行う。
    Retry:
        接続失敗時、最大3回まで試行する。
    Usage:
        conn = login_telnet(params, "jump-host", "session-exe.log")
    Arguments:
        device_params (dict): 接続情報（ホスト名、ユーザ名、パスワード等）
        hostname_key (str): 接続成功を判定するための文字列（プロンプト等）
        log_file (str, optional): Netmikoのセッションログ保存先パス
    Returns:
        ConnectHandler: Telnetログイン完了後の接続オブジェクト
    """
    # ログ出力が指定されている場合、Netmikoのパラメータに追加
    if log_file:
        device_params['session_log'] = log_file

    max_retries = 3
    # 指定回数分リトライループを実行
    for attempt in range(1, max_retries + 1):
        try:
            # --- 1. 初期接続 ---
            # ConnectHandlerを使い、指定されたパラメータでTelnet接続を開始
            conn = ConnectHandler(**device_params)
            
            # --- 2. 対話認証フロー ---
            # 改行を送って反応を確認
            conn.send_command_timing("")
            prompt = conn.find_prompt()
            
            # "login:" プロンプトが出ていない場合は、もう一度改行を送る（接続直後のタイミング調整）
            if "login:" not in prompt.lower():
                conn.send_command_timing("")
            
            # ユーザ名とパスワードを順次送信
            # strip_prompt=Falseにすることで、エコーバックを含めて正確に制御
            conn.send_command_timing(device_params["username"], strip_prompt=False)
            conn.send_command_timing(device_params["password"], strip_prompt=False)
            
            # ログイン処理の完了を待つための微小な待機
            time.sleep(1)
            
            return conn # 認証に成功したら接続オブジェクトを返す
            
        except Exception as e:
            # 接続エラー時の処理
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [Warning]: Telnet接続失敗 (試行 {attempt}/{max_retries}): {e}")
            if attempt == max_retries:
                print(f"【Error】リトライ上限に達しました。接続を断念します。")
                raise
            time.sleep(2) # 次の試行まで2秒間隔をあける


def login_jump_ssh(conn, host, username, password, target_type='juniper_junos') -> ConnectHandler:
    """
    Purpose:
        既存の踏み台接続（conn）からSSHコマンドを実行し、ターゲット機器へ移動する。
        移動後、Netmikoの制御モードをターゲットOSの仕様に再定義（redispatch）する。
    Usage:
        conn = login_jump_ssh(conn, "1.1.1.1", "user", "pass", "juniper_junos")
    Arguments:
        conn (ConnectHandler): 踏み台（Jump-Host）との既存接続オブジェクト
        host (str): ターゲット機器のIPアドレスまたはホスト名
        username (str): ターゲット機器のログインユーザ名
        password (str): ターゲット機器のログインパスワード
        target_type (str): ターゲット機器のOS種別（Netmikoのdevice_type）
    Returns:
        ConnectHandler: ターゲット機器へのログインおよびredispatch完了後のオブジェクト
    """
    # --- 1. 踏み台からSSHコマンドを実行 ---
    # StrictHostKeyChecking=no を付けて、初回接続時のフィンガープリント確認を強制スキップ
    ssh_cmd = f"ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {username}@{host}"
    
    # 踏み台のプロンプト上でSSHコマンドを叩き、応答（パスワード入力要求など）を待つ
    auth_prompt = conn.send_command_timing(ssh_cmd, strip_prompt=False)
    
    # パスワードを要求されたら入力
    if "password:" in auth_prompt.lower():
        conn.send_command_timing(password)
    
    # --- 2. Netmikoのモード切り替え（重要） ---
    # これまでは「踏み台OS」として制御していたが、ここからは「ターゲットOS（例: Juniper）」
    # としてコマンド送受信を行うよう、Netmiko内部のハンドラを再割り当てする
    redispatch(conn, device_type=target_type)
    
    # --- 3. 接続の安定化 ---
    # OS切り替え後の同期処理
    time.sleep(1)
    conn.clear_buffer() # 認証時の残りカスなどの不要な出力をバッファから消去
    conn.find_prompt()  # ターゲット機器の新しいプロンプトを認識させる
    conn.send_command_timing("\n", strip_prompt=False) # ダミーの改行で応答を確認
    
    return conn