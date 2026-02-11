#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import html
import re

def load_commands(cmd_file):
    """
    Purpose:
        コマンド定義ファイルを読み込み、実行用リストを生成する。
    Usage:
        raw_lines, cmd_list = load_commands("commands.txt")
    Arguments:
        cmd_file (str): コマンドが定義されたテキストファイルのパス
    Returns:
        raw_lines (list): ファイルの各行（コメントや観点を含む生データ）
        cmd_list (list): 実行対象のコマンドのみを抽出したリスト
    """
    # 定義ファイルの存在確認
    if not os.path.exists(cmd_file):
        raise FileNotFoundError(f"定義ファイルが見つかりません: {cmd_file}")

    with open(cmd_file, "r", encoding="utf-8") as f:
        # 1. 空行を除外し、'[' で始まるセクションヘッダ等を除外して読み込む
        raw_lines = [line.strip() for line in f if line.strip() and not line.startswith('[')]
        
        # 2. ';;' 区切りの先頭要素（コマンド本体）のみを抽出してリスト化
        cmd_list = [line.split(';;')[0].strip() for line in raw_lines]
        
    return raw_lines, cmd_list


def execute_commands(conn, commands, read_timeout=300):
    """
    Purpose:
        接続中のデバイスに対してコマンドを順次実行し、結果を収集する。
    Usage:
        results = execute_commands(conn, ["show version", "show interfaces"])
    Arguments:
        conn (ConnectHandler): Netmikoの接続オブジェクト
        commands (list): 実行するコマンドのリスト
        read_timeout (int): コマンド応答のタイムアウト秒数
    Returns:
        results (dict): {コマンド: 実行結果} の形式の辞書
    """
    results = {}
    
    # Juniperデバイスの場合、ページング（More表示）を無効化する
    if 'juniper' in conn.device_type:
        conn.send_command("set cli screen-length 0")
    
    for cmd in commands:
        try:
            # 前のコマンドの残骸がバッファに残らないようクリア
            conn.clear_buffer()
            
            # コマンド実行
            # strip_prompt/command=Falseにすることで、出力結果にプロンプト等を含めた生のログを維持
            output = conn.send_command(
                cmd, 
                read_timeout=read_timeout, 
                strip_prompt=False, 
                strip_command=False
            )
            
            # 結果が取得できれば格納、空ならエラーメッセージを格納
            results[cmd] = output if (output and output.strip()) else "Error: コマンドの出力が空、または取得に失敗しました。"
        except Exception as e:
            # タイムアウト等の例外発生時の処理
            results[cmd] = f"Execution Error: {e}"
            
    return results


def generate_html_report(raw_lines, results_map, show_checklist=True):
    """
    Purpose:
        実行結果を視覚的に確認するためのHTMLレポートを生成する。
    Usage:
        html_str = generate_html_report(raw_lines, results)
    Arguments:
        raw_lines (list): load_commandsで取得した定義行のリスト
        results_map (dict): execute_commandsで取得した実行結果の辞書
        show_checklist (bool): チェックリスト（サイドバー）を表示するかどうか
    Returns:
        report_html (str): 生成されたHTMLソースコードの文字列
    """
    total_count = len(raw_lines)
    
    # 表示設定の切り替え
    checklist_style = "block" if show_checklist else "none"
    main_margin = "40px" if show_checklist else "20px"
    footer_style = "flex" if show_checklist else "none"

    # --- HTMLヘッダ・スタイル定義 ---
    report_html = f"""
<style>
    body {{ font-family: 'Segoe UI', Tahoma, sans-serif; background-color: #f4f7f6; margin: 0; padding: 20px; }}
    /* 左側固定のインデックス（確認リスト） */
    .index-container {{
        display: {checklist_style};
        position: fixed; left: 10px; top: 20px; width: 220px;
        background: rgba(255, 255, 255, 0.9); border: 1px solid #ddd; border-radius: 8px;
        padding: 15px; max-height: 85vh; overflow-y: auto; z-index: 1000;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1); backdrop-filter: blur(4px);
    }}
    .index-title {{ font-weight: bold; font-size: 14px; margin-bottom: 10px; border-bottom: 2px solid #eee; }}
    .index-item {{ color: #ff4d4d; font-weight: bold; margin-bottom: 8px; font-size: 11px; }}
    .index-item.done {{ color: #e0e0e0; font-weight: normal; text-decoration: line-through; opacity: 0.5; }}
    
    /* メインコンテンツエリア */
    .main-content {{ margin-left: {main_margin}; transition: margin 0.3s; }}
    .res-box {{ background: white; margin-bottom: 30px; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden; }}
    .res-header {{ background: #2c3e50; color: white; padding: 12px 15px; font-weight: bold; font-size: 14px; }}
    
    /* 観点・強調キーワードの表示バー */
    .info-bar {{ background: #fafafa; padding: 15px; border-bottom: 1px solid #eee; display: flex; flex-direction: column; gap: 10px; }}
    .tag-row {{ display: flex; align-items: flex-start; }}
    .tag-label-v {{ background: #2980b9; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; margin-right: 12px; min-width: 60px; text-align: center; flex-shrink: 0; font-size: 11px; }}
    .tag-label-k {{ background: #d35400; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; margin-right: 12px; min-width: 60px; text-align: center; flex-shrink: 0; font-size: 11px; }}
    .tag-content {{ line-height: 1.5; color: #333; font-size: 13px; font-weight: bold; }}
    
    /* 黒背景のログ表示エリア */
    .log-body {{ background: #1e1e1e; color: #d4d4d4; padding: 15px; overflow: auto; max-height: 600px; white-space: pre-wrap; font-family: monospace; font-size: 13px; }}
    
    /* ハイライト（キーワード一致行）の装飾 */
    .hl-line {{ background: rgba(255, 255, 0, 0.15); border-left: 5px solid #ff0; padding-left: 10px; }}
    .hl-keyword {{ color: #ff0; text-decoration: underline; font-weight: bold; }}
    
    /* 確認済みチェック時の透過処理 */
    .checked-card {{ opacity: 0.35; filter: grayscale(1); }}
    .footer-action {{ display: {footer_style}; background: #f8f9fa; padding: 15px; border-top: 1px solid #eee; align-items: center; }}
    .all-done-msg {{ color: #27ae60; font-weight: bold; display: none; margin-top: 10px; font-size: 15px; }}
</style>

<script>
// 進捗状況を更新するJavaScript関数
function updateProgress() {{
    const total = {total_count};
    const checked = document.querySelectorAll('.check-item:checked').length;
    const statusText = document.getElementById('progress-status');
    if(!statusText) return;
    statusText.innerHTML = '(' + checked + ' / ' + total + ')';
    // 全てチェックされたらお祝いメッセージを表示
    document.getElementById('all-done-text').style.display = (checked === total) ? 'block' : 'none';
}}
</script>

<div class="index-container">
    <div class="index-title">確認リスト <span id="progress-status">(0 / {total_count})</span></div>
    <div id="all-done-text" class="all-done-msg">✨ すべて確認完了！</div>
"""
    # サイドバーのインデックス項目を作成
    for i, line in enumerate(raw_lines):
        cmd_short = line.split(';;')[0].strip()[:25]
        report_html += f'<div class="index-item" id="idx-{i}">#{i+1} {cmd_short}</div>'

    report_html += '</div><div class="main-content">'

    # 各コマンドの結果カードを作成
    for i, line in enumerate(raw_lines):
        parts = line.split(';;')
        cmd = parts[0].strip()
        view = parts[1].strip() if len(parts) > 1 else "未設定"
        key = parts[2].strip() if len(parts) > 2 else ""
        out = results_map.get(cmd, "No Output")

        log_content = ""
        # 1行ずつハイライト判定を行いながらログを組み立て
        for o_line in out.splitlines():
            s_line = html.escape(o_line)
            # ハイライト処理：キーワードに一致した行を装飾
            if key and key != "なし" and key.strip() != "" and key.lower() in o_line.lower():
                pattern = re.compile(re.escape(key), re.IGNORECASE)
                highlighted = pattern.sub(f'<span class="hl-keyword">{key}</span>', s_line)
                log_content += f'<div class="hl-line">{highlighted}</div>'
            else:
                log_content += f'<div>{s_line}</div>'

        # カード部分のHTML生成（チェックボックスと連動するJSを埋め込み）
        report_html += f"""
<div class="res-box" id="card-{i}">
    <div class="res-header">#{i+1} {cmd}</div>
    <div class="info-bar">
        <div class="tag-row"><span class="tag-label-v">観点</span><span class="tag-content">{view}</span></div>
        <div class="tag-row"><span class="tag-label-k">強調</span><span class="tag-content">{key if key else "なし"}</span></div>
    </div>
    <div class="log-body">{log_content}</div>
    <div class="footer-action">
        <label style="cursor:pointer; display: flex; align-items: center; font-weight: bold;">
            <input type="checkbox" class="check-item" style="width: 20px; height: 20px; margin-right: 12px;" onchange="
                document.getElementById('card-{i}').classList.toggle('checked-card');
                document.getElementById('idx-{i}').classList.toggle('done');
                updateProgress();
            "> 確認済み
        </label>
    </div>
</div>"""

    report_html += '</div>'
    return report_html