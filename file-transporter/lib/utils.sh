#!/bin/bash

# ==============================================================================
#  COMMON UTILITIES
# ==============================================================================
#  Description : プロジェクト共通の定数定義および汎用関数 (Utility Functions)
#
#  Functions   : log_info, log_warn, log_error
#  Constants   : PROJ_ROOT, LOG_DIR
# ==============================================================================

# --- Global Constants ---
# スクリプトの格納場所を基準にプロジェクトルートを自動特定
readonly UTIL_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
readonly PROJ_ROOT=$(cd "${UTIL_DIR}/.." && pwd)
readonly LOG_DIR="${PROJ_ROOT}/log"

# --- Logging Functions ---

# [INFO] 処理の進捗や成功を記録
log_info() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $1"
    echo -e "\e[32m${msg}\e[m" # 画面表示：緑
    echo "${msg}" >> "${LOG_DIR}/process.log"
}

# [WARN] 続行可能だが注意が必要な事象を記録
log_warn() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [WARN] $1"
    echo -e "\e[33m${msg}\e[m" # 画面表示：黄
    echo "${msg}" >> "${LOG_DIR}/process.log"
}

# [ERROR] 処理の中断を伴う重大なエラーを記録
log_error() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $1"
    echo -e "\e[31m${msg}\e[m" >&2 # 画面表示：赤 (標準エラー出力)
    echo "${msg}" >> "${LOG_DIR}/error.log"
}

# --- Initialization ---
# 必要なディレクトリの存在保証
if [ ! -d "${LOG_DIR}" ]; then
    mkdir -p "${LOG_DIR}"
fi