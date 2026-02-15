#!/bin/bash

# ==============================================================================
#  generate_tm_config.sh
#
#  Description:
#    shaper定義行をTraffic Manager用のsubport Config形式に変換する。
#    ソースファイルから特定のID形式を抽出し、テンプレート（Header/Footer）を付与する。
#
#  Arguments:
#    1. src_config : 変換元のマスターテキストファイル
#    2. out_config : 生成後のルータ投入用コンフィグファイル
#
#  Usage:
#    ./generate_tm_config.sh <src_config> <out_config>
#
#  Example:
#    ./generate_tm_config.sh "${DATA_DIR}/raw/shaper/latest_shaper.txt" "${WORKING_DIR}/new_shaper.conf"
# ==============================================================================

# --- Environment ---
CM_LIB_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
if [ -f "${CM_LIB_DIR}/utils.sh" ]; then
    source "${CM_LIB_DIR}/utils.sh"
else
    echo "Error: Required library 'utils.sh' not found." >&2
    exit 1
fi

# --- Parameters ---
if [[ $# -ne 2 ]]; then
    echo "Usage: $0 <src_config> <out_config>"
    exit 1
fi

readonly SRC_F="$1"
readonly OUT_F="$2"

# --- Validation ---
if [[ ! -f "$SRC_F" ]]; then
    log_error "Source file not found: $SRC_F"
    exit 1
fi

# --- Main Logic ---
log_info "Generating Traffic Manager configuration..."

# [TECH] 変換ロジックを一括実行して出力ファイルにリダイレクト
{
    # 1. Header: TMアクセラレータ設定の開始宣言
    echo "traffic-manager accelerator"
    echo "!"

    # 2. Body: awkによる変換処理
    # 入力例: shaper Down_AA_BB_CC rate 100M
    # 出力例:  subport AA-BB-CC shaper pir 100
    awk '
    /shaper Down_/ {
        # [LOGIC] ID整形: Down_AA_BB_CC -> AA-BB-CC
        # $2（Down_AA_BB_CC）をアンダースコアで分割
        n = split($2, p, "_");
        if (n < 4) { next; } # 形式不正な行はスキップ
        id = p[2] "-" p[3] "-" p[4];

        # [LOGIC] PIR抽出
        pir = 0;
        if ($3 == "rate") {
            pir = $4;
            # 単位（M, G等）を削除し数値のみ抽出
            gsub(/[^0-9]/, "", pir);
        } else if ($3 == "infinity") {
            # 無制限設定時は0（またはルータ仕様に合わせた値）
            pir = 0;
        }

        # 先頭にスペース1つ、各コマンドを出力
        printf " subport %s shaper pir %s\n", id, pir;
    }' "$SRC_F"

    # 3. Footer: 設定の終了と確定コマンド
    echo " exit"
    echo "!"
    echo "end"

} > "$OUT_F"

# --- Finalization ---
# [LOGIC] 出力ファイルが生成され、且つ中身（Header/Footer以外のBody）があるか
if [[ -s "$OUT_F" ]]; then
    # 生成された行数をカウント（Header/Footerの4行分を差し引き）
    body_count=$(grep -c "subport" "$OUT_F")
    if [[ $body_count -gt 0 ]]; then
        log_info "Configuration generated successfully. (Entries: $body_count)"
    else
        log_warn "Header created, but no valid shaper entries found in source."
    fi
else
    log_error "Failed to generate configuration file."
    exit 1
fi