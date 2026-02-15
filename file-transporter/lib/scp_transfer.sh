#!/bin/bash

# ==============================================================================
#  scp_transfer.sh
#
#  Description:
#    ルータとのファイル転送を実行。
#    SSH_ASKPASSを利用し、パスワード認証環境下での非対話転送を実現する。
#
#  Arguments:
#    1. config_name : 接続先識別名 (remote_[NAME].conf)
#    2. mode        : download | upload
#    3. local_path  : 処理対象のローカルファイルパス
#
#  Usage:
#    ./scp_transfer.sh <config_name> <download|upload> <local_file_path>
#
#  Example:
#    # 'router' 設定を使用して現用設定をダウンロード
#    ./scp_transfer.sh router download ./data/interim/dyn_q_flow_save.cfg
#
#    # 'router02' 設定を使用して差分ファイルをアップロード
#    ./scp_transfer.sh router02 upload ./data/interim/dyn_q_flow_set.cfg
# ==============================================================================

# --- Environment ---
CM_LIB_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

# 共通ユーティリティのロード
if [ -f "${CM_LIB_DIR}/utils.sh" ]; then
    source "${CM_LIB_DIR}/utils.sh"
else
    echo "Error: Required library 'utils.sh' not found." >&2
    exit 1
fi

# --- Parameters ---
if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <config_name> <download|upload> <local_file_path>"
    exit 1
fi

readonly TARGET_CONF="$1"
readonly TRANSFER_MODE="$2"
readonly LOCAL_PATH="$3"

# --- Configuration Load ---
readonly CONF_FILE="${PROJ_ROOT}/param/config/remote_${TARGET_CONF}.conf"
readonly PASS_FILE="${PROJ_ROOT}/vault/.pass_${TARGET_CONF}"

if [ -f "$CONF_FILE" ]; then
    source "$CONF_FILE"
else
    log_error "Config not found: $CONF_FILE"
    exit 1
fi

if [ ! -f "$PASS_FILE" ]; then
    log_error "Password file missing: $PASS_FILE"
    exit 1
fi

# --- Auth Setup (SSH_ASKPASS) ---
readonly REMOTE_PASS=$(cat "$PASS_FILE")
readonly PASS_HELPER="${CM_LIB_DIR}/.temp_pass_${TARGET_CONF}.sh"

# 非対話認証用のヘルパースクリプト生成
echo -e "#!/bin/bash\necho '${REMOTE_PASS}'" > "$PASS_HELPER"
chmod 700 "$PASS_HELPER"

# 終了時に一時ファイルを確実に削除
trap 'rm -f "$PASS_HELPER"' EXIT

# --- Execution ---
readonly SSH_OPTS="-o StrictHostKeyChecking=no \
                   -o NumberOfPasswordPrompts=1 \
                   -o ControlMaster=no \
                   -o UserKnownHostsFile=/dev/null \
                   -o LogLevel=ERROR"

if [ "${TRANSFER_MODE}" = "download" ]; then
    log_info "[${TARGET_CONF}] Downloading: ${REMOTE_HOST}:${REMOTE_SRC_PATH} -> ${LOCAL_PATH}"
    
    # リモート側のファイル名はローカルパスの末尾を利用
    REMOTE_FILE_NAME=$(basename "${LOCAL_PATH}")
    
    # ダウンロード実行 (REMOTE_SRC_PATH とファイル名の間に / を明示)
    if env DISPLAY=:0 SSH_ASKPASS="${PASS_HELPER}" SSH_ASKPASS_REQUIRE=force \
       setsid scp ${SSH_OPTS} "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_SRC_PATH}/${REMOTE_FILE_NAME}" "${LOCAL_PATH}"; then
        log_info "Download successful."
    else
        log_error "Download failed."
        exit 1
    fi
else
    # Mode: upload
    log_info "[${TARGET_CONF}] Uploading: ${LOCAL_PATH} -> ${REMOTE_HOST}:${REMOTE_SRC_PATH}"
    
    if [ ! -f "${LOCAL_PATH}" ]; then
        log_error "Local file not found: ${LOCAL_PATH}"
        exit 1
    fi

    # アップロード実行 (REMOTE_SRC_PATH をそのまま宛先ディレクトリとして利用)
    if env DISPLAY=:0 SSH_ASKPASS="${PASS_HELPER}" SSH_ASKPASS_REQUIRE=force \
       setsid scp ${SSH_OPTS} "${LOCAL_PATH}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_SRC_PATH}"; then
        log_info "Upload successful."
    else
        log_error "Upload failed."
        exit 1
    fi
fi