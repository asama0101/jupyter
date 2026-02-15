#!/bin/bash

# ==============================================================================
#  csv_merge.sh
#
#  Description:
#    複数ソースファイルの透過的統合。
#    .gz(圧縮)と.csv(非圧縮)を自動判別し、ヘッダー重複を排除して結合する。
#    入力ディレクトリへの直接出力を禁止する安全ガードを実装。
#
#  Arguments:
#    1..N-1 : 入力ファイルパス群 (ワイルドカード展開可)
#    Last   : 出力ファイルパス (入力ディレクトリとは別であること)
#
#  Usage:
#    ./csv_merge.sh <input_patterns...> <output_file>
#
#  Example:
#    ./csv_merge.sh ./data/raw/sub/add_*.csv ./data/interim/sub_add_combined.csv
# ==============================================================================

# --- Environment ---
CM_LIB_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
if [ -f "${CM_LIB_DIR}/utils.sh" ]; then
    source "${CM_LIB_DIR}/utils.sh"
else
    echo "Error: Required library 'utils.sh' not found." >&2
    exit 1
fi

# --- Usage Definition ---
show_usage() {
    echo "Usage: $0 <input_patterns...> <output_file>"
    echo "Note: Output directory must be different from input directory."
}

# --- Parameters ---
if [[ $# -lt 2 ]]; then
    show_usage
    exit 1
fi

# [LOGIC] 最後の引数を出力先、それ以外を入力ファイル群として取得
RS_OUTPUT="${@: -1}"      
files=( "${@:1:$#-1}" )  

# --- Safety Validation ---
# 出力先の親ディレクトリを絶対パスで取得
OUT_DIR=$(cd "$(dirname "$RS_OUTPUT")" 2>/dev/null && pwd)

for f in "${files[@]}"; do
    # 入力ファイルの親ディレクトリを絶対パスで取得
    IN_DIR=$(cd "$(dirname "$f")" 2>/dev/null && pwd)
    
    # 1. 同一ディレクトリへの出力を禁止 (ワイルドカードによる自己上書き事故防止)
    if [[ "$IN_DIR" == "$OUT_DIR" ]]; then
        log_error "Safety Break: Direct output to the same input directory is prohibited."
        log_error "Input Dir  : $IN_DIR"
        log_error "Output File: $RS_OUTPUT"
        exit 1
    fi

    # 2. 入力ファイルと出力ファイルの完全一致（同一実体）をチェック
    ABS_F=$(readlink -f "$f" 2>/dev/null)
    ABS_O=$(readlink -f "$RS_OUTPUT" 2>/dev/null)
    if [[ -n "$ABS_F" && "$ABS_F" == "$ABS_O" ]]; then
        log_error "Safety Break: Output file overlaps with an existing input file."
        exit 1
    fi
done

# 入力ファイルが存在しない場合のハンドリング
if [[ ${#files[@]} -eq 0 ]]; then
    log_info "No input files found. Creating an empty file: $RS_OUTPUT"
    touch "$RS_OUTPUT"
    exit 0
fi

# --- Main Logic ---
log_info "Initiating transparent merge for ${#files[@]} files..."
log_info "Target Output: $RS_OUTPUT"

# 出力先を初期化（空にする）
: > "$RS_OUTPUT"

# [TECH] ループによる個別処理
# 1ファイルずつ zcat | awk を通すことで、確実に各ファイルの1行目を判定する。
is_first_file=true

for f in "${files[@]}"; do
    if [[ ! -f "$f" ]]; then continue; fi

    if [[ "$is_first_file" == true ]]; then
        # 最初の1ファイル目：ヘッダーを含めて全て出力
        zcat -f "$f" >> "$RS_OUTPUT"
        is_first_file=false
    else
        # 2ファイル目以降：1行目(FNR==1)をスキップして追記
        zcat -f "$f" | awk 'FNR > 1' >> "$RS_OUTPUT"
    fi
done

# --- Finalization ---
if [[ -s "$RS_OUTPUT" ]]; then
    log_info "Merge completed successfully. (Lines: $(wc -l < "$RS_OUTPUT"))"
else
    log_warn "Process finished, but output file is empty."
fi

exit 0