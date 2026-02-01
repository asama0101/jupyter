from netmiko import ConnectHandler
from datetime import datetime

def login_telnet(device_params, hostname_key, log_file=None) -> ConnectHandler:
    """
    目的: 踏み台サーバ等へTelnetでログインし、対話的な認証（ユーザー名/パスワード）を行う。
    
    引数:
        device_params (dict): Netmikoの接続パラメータ（device_type, host, username, password等）。
        hostname_key (str): ログイン成功を判定するための期待されるプロンプト（ホスト名の一部など）。
        log_file (str, optional): セッションログを保存するファイル名。指定すると全通信内容が記録される。
    
    戻り値:
        ConnectHandler: 接続済みのNetmikoコネクションオブジェクト。
        
    使い方例:
        conn = login_telnet(device_info['jump_server'], "clab-shuttle01", log_file="telnet.log")
    """
    # print(f"[{datetime.now().strftime('%H:%M:%S')}] [DEBUG]: {hostname_key}へログイン開始")

    # ログの保尊開始
    if log_file:
        device_params['session_log'] = log_file
    
    # Telnet接続
    conn = ConnectHandler(**device_params)
    username = device_params["username"]
    password = device_params["password"]

    # ログイン入力プロンプト表示を待機
    conn.send_command_timing("")
    prompt = conn.find_prompt()

    if "login:" not in prompt.lower():
        # Enterキーを送信して、ユーザー入力プロンプトの表示を促す
        conn.send_command_timing("")
    
    # Telnet接続の試行回数【定義】
    max_tries = 5

    # ユーザー認証
    for try_count in range(1, max_tries + 1):

        # ユーザー入力（パスワード入力プロンプトを返り値として期待）
        auth_prompt = conn.send_command_timing(username, strip_prompt=False)

        # パスワード入力
        if "password:" in auth_prompt.lower() or "パスワード:" in auth_prompt:
            out_prompt = conn.send_command_timing(password, strip_prompt=False)
      
        # 認証失敗チェック
        if "login incorrect" in out_prompt.lower() or "ログインが違います" in out_prompt:
            # print(f"[{datetime.now().strftime('%H:%M:%S')}] [DEBUG]: {username}の認証失敗（再試行中... {try_count}/{max_tries}）")
            continue
        
        # プロンプト出力させるためにEnterキー送信
        conn.send_command_timing("", strip_prompt=False)
        prompt = conn.find_prompt()
        
        # 成功失敗判定（基準：プロンプトにhost_keyが含まれているか）
        if hostname_key in prompt:
            # print(f"[{datetime.now().strftime('%H:%M:%S')}] [DEBUG]: {hostname_key}へログイン成功（試行回数: {try_count}/{max_tries}）")
            # print(f"[{datetime.now().strftime('%H:%M:%S')}] [DEBUG]: 現在のプロンプト {prompt}")
            return conn

    raise RuntimeError(f"[{datetime.now().strftime('%H:%M:%S')}] [Error]: {hostname_key}へログイン失敗")


def login_jump_ssh(conn, host, username, password, label=None) -> ConnectHandler:
    """
    目的: 既にログイン済みのセッション（踏み台）から、別のターゲット機器へSSHで二段階ログインを行う。
    
    引数:
        conn (ConnectHandler): 踏み台サーバに接続済みのNetmikoオブジェクト。
        host (str): ターゲット機器のIPアドレスまたはホスト名。
        username (str): ターゲット機器のSSHユーザー名。
        password (str): ターゲット機器のSSHパスワード。
        label (str, optional): ログ表示用の識別名（ホスト名など）。省略時はhostを使用。
    
    戻り値:
        ConnectHandler: ターゲット機器にSSHログインした状態のコネクションオブジェクト。
        
    使い方例:
        conn = login_jump_ssh(conn, "192.168.3.64", "admin", "admin@123", label="clab-dev-vmx01")
    """
    name = label or host
    # print(f"[{datetime.now().strftime('%H:%M:%S')}] [DEBUG]: {name}へログイン開始")

    # SSH接続
    ssh_option = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    ssh_cmd = f"ssh {ssh_option} {username}@{host}"
    auth_prompt = conn.send_command_timing(ssh_cmd, strip_prompt=False)
    
    # パスワード入力
    if "password:" in auth_prompt.lower():
        out_prompt = conn.send_command_timing(password)
    
    # 認証失敗チェック
    if "permission denied" in out_prompt.lower():
        raise RuntimeError(f"[{datetime.now().strftime('%H:%M:%S')}] [FAILED]: {username}の認証失敗（permission denied）")

    # プロンプト出力させるためにEnterキー送信
    conn.send_command_timing("", strip_prompt=False)
    out_prompt = conn.find_prompt()

    # print(f"[{datetime.now().strftime('%H:%M:%S')}] [DEBUG]: {name}へログイン成功")
    # print(f"[{datetime.now().strftime('%H:%M:%S')}] [DEBUG]: 現在のプロンプト {out_prompt}")

    return conn


def enable_mode(conn, enable_secret) -> ConnectHandler:
    """
    目的: 特権モード（enableモード）のない機器や、設定モードへの移行が必要な場合に認証を行う。
    
    引数:
        conn (ConnectHandler): ターゲット機器に接続済みのNetmikoオブジェクト。
        enable_secret (str): 特権モード用パスワード。
    
    戻り値:
        ConnectHandler: 特権モードへ移行した状態のコネクションオブジェクト。
        
    使い方例:
        conn = enable_mode(conn, "admin@123")
    """
    # enableコマンド実行
    conn.write_channel('enable\n')
    auth_prompt = conn.read_channel()

    # パスワード入力
    if "password:" in auth_prompt.lower():
        out_prompt = conn.send_command_timing(enable_secret)

    # 認証失敗チェック
    out_prompt = conn.find_prompt()
    if out_prompt.endswith("#"):
        # print(f"[{datetime.now().strftime('%H:%M:%S')}] [DEBUG]: enableモードへ移行成功")
        return conn
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [DEBUG]: enableモードへ移行失敗")