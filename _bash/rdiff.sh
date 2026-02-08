#!/bin/bash

###############################################################################
# README: Remote Command & Diff Checker
# ---------------------------------------------------------------------------
# 【概要】
# 指定したリモートサーバーにSSH接続し、コマンドを実行します。
# 実行結果を保存し、前回実行時からの「新しい差分」のみを抽出して出力します。
# 
# 【主な機能】
# 1. SSH_ASKPASSによるパスワード自動入力
# 2. 実行結果のバックアップ管理
# 3. grepによる行単位の差分（新規追加分）抽出
###############################################################################

# --- 設定項目 ---
HOST="root@192.168.3.21"           # 接続先ホスト
PASS="P!ssw0rd1234"                # ログインパスワード
COMMAND="date && cat /etc/os-release" # 実行コマンド
OUTPUT_FILE="result.txt"           # 今回の結果
PREV_FILE="result_prev.txt"        # 前回の結果（比較用）
DIFF_FILE="result_diff.txt"        # 抽出された差分

# 1. 前回のデータを比較用にローテーション
if [ -f "$OUTPUT_FILE" ]; then
    mv "$OUTPUT_FILE" "$PREV_FILE"
fi

# 2. パスワード自動入力用の仕掛け
# SSHにパスワードを安全に渡すため、一時的なエコープログラムを作成します
echo "echo $PASS" > .temp_pass.sh
chmod +x .temp_pass.sh

# 3. コマンド実行
# setsidとSSH_ASKPASSを組み合わせることで、対話プロンプトなしでログインします
export SSH_ASKPASS="./.temp_pass.sh"
export DISPLAY=":0" 
setsid ssh -o StrictHostKeyChecking=no "$HOST" "$COMMAND" > "$OUTPUT_FILE" 2>&1

# 4. 差分の抽出
# 前回のファイル(PREV)と比較して、今回のファイル(OUTPUT)にしかない行を特定します
if [ -f "$PREV_FILE" ]; then
    # -v: 一致しないもの / -F: 固定文字列 / -f: ファイル参照
    grep -v -F -f "$PREV_FILE" "$OUTPUT_FILE" > "$DIFF_FILE"
else
    # 初回実行時は比較対象がないため、全結果を差分とする
    cp "$OUTPUT_FILE" "$DIFF_FILE"
fi

# 5. 後片付け
# セキュリティのため、パスワードが書かれた一時ファイルは即座に削除
[ -f .temp_pass.sh ] && rm .temp_pass.sh

echo "処理完了。差分は $DIFF_FILE に保存されました。"