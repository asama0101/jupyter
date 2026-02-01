from datetime import datetime

def load_commands(cmd_file):
    """
    目的: 
        コマンドファイルからデータを読み込み、生データと実行用コマンドの2種類を作成する。
    
    引数:
        cmd_file (str): 読み込むテキストファイルのパス。
        
    戻り値:
        tuple: (raw_lines, cmd_list_for_device)
               - raw_lines: パイプやメモを含んだままの全行リスト。
               - cmd_list_for_device: 機器実行用にパイプ以前を抽出したリスト。
    """
    try:
        with open(cmd_file, "r", encoding="utf-8") as f:
            # 生の行データをリストとして保持
            raw_lines = [line.strip() for line in f if line.strip()]

            # 機器に送るための純粋なコマンドリストを作成
            cmd_list_for_device = [line.split(';;')[0].strip() if ';;' in line else line for line in raw_lines]
            
        return raw_lines, cmd_list_for_device

    except FileNotFoundError:
        # print(f"[{datetime.now().strftime('%H:%M:%S')}] [DEBUG]: {cmd_file} が見つかりません")
        # ノートブックの処理を中断させるために例外を投げる
        raise


def execute_commands(conn, commands):
    """
    目的: 
        接続済みのデバイスに対してリスト形式のコマンドを順次実行し、
        実行ログにタイムスタンプを記録しながら結果を収集する。
    
    引数:
        conn (ConnectHandler): Netmikoの接続オブジェクト。
        commands (list): 実行したい純粋なコマンド文字列のリスト。
        
    戻り値:
        dict: {実行コマンド: 実行結果(出力)} の形式の辞書。
        
    使い方例:
        results = execute_commands(conn, ["show version", "show interfaces"])
    """
    results = {}
    for cmd in commands:
        
        # セッションログ（ファイル）へのタイムスタンプ手動挿入
        # conn.session_log は開いているファイルオブジェクトそのもの
        if conn.session_log:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # ログファイル内でコマンドの区切りを分かりやすくするための装飾
            conn.session_log.write(f"\n\n{'='*40}\n[Execute at: {timestamp}]\n[Command: {cmd}]\n{'='*40}\n")
            conn.session_log.flush()  # バッファを強制的にファイルへ書き出す

        # コマンド実行
        output = conn.send_command(cmd)
        results[cmd] = output
      
    return results


def prepare_and_map_results(raw_lines, results_map):
    """
    目的: 
        テキストファイルから読み込んだ生の行データ（コマンド;;観点;;期待値）と、
        機器からの実行結果を紐付けて、HTML表示用の辞書(outputs)を作成する。
    
    引数:
        raw_lines (list): commands.txtから読み込んだ加工前の全行リスト。
        results_map (dict): execute_commands関数から返された {純粋コマンド: 実行結果} の辞書。
        
    戻り値:
        dict: {生コマンド行: 実行結果} の形式の辞書。
    """
    outputs = {}
    
    for line in raw_lines:
        # パイプがあれば左側を抽出、なければ行全体をコマンドとして扱う
        command_key = line.split(';;')[0].strip() if ';;' in line else line
        
        # 実行結果マップから結果を取得（見つからない場合は "No Output"）
        result_content = results_map.get(command_key, "No Output")
        
        # 生の1行をキーにして紐付け
        outputs[line] = result_content
        
    return outputs
