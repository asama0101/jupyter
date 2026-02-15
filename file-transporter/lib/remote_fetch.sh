#!/bin/bash

# ==============================================================================
#  remote_fetch.sh
#
#  Description:
#    リモート同期の実行。
#    SSH環境を汚さず、パスワード非対話セッションでファイルを収集する。
#
#  Arguments:
#    1. config_name : 設定識別名 (remote_[NAME].conf)
#    2. local_dest  : ローカル保存先パス
#    3. mode        : 動作モード (sync | copy)
#    4. pattern     : ファイル抽出パターン (例: "*.csv")
#
#  Usage:
#    ./remote_fetch.sh <config_name> <local_dest> [mode] [pattern]
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
    echo "Usage: $0 <config_name> <local_dest> [sync|copy] [pattern]"
}


# --- Parameters ---
if [ "$#" -lt 2 ]; then
    show_usage
    exit 1
fi

readonly RS_CONF_NAME="$1"
readonly RS_DEST="$2"
readonly RS_MODE="${3:-copy}"
readonly RS_PATTERN="$4"


# --- Configuration ---
readonly CONF_FILE="${PROJ_ROOT}/param/config/remote_${RS_CONF_NAME}.conf"

if [ -f "$CONF_FILE" ]; then
    source "$CONF_FILE"
    log_info "Loaded config: $RS_CONF_NAME"
else
    log_error "Config not found: $CONF_FILE"
    exit 1
fi

[[ "${REMOTE_SRC_PATH}" != */ ]] && REMOTE_SRC_PATH="${REMOTE_SRC_PATH}/"

readonly PASS_FILE="${PROJ_ROOT}/vault/.pass_${RS_CONF_NAME}"
readonly RS_SRC="${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_SRC_PATH}"


# --- Validation ---
if [ ! -d "$RS_DEST" ]; then
    log_error "Dest directory missing: $RS_DEST"
    exit 1
fi

if [ ! -f "$PASS_FILE" ]; then
    log_error "Password missing in vault: $PASS_FILE"
    exit 1
fi


# --- Auth Setup (SSH_ASKPASS) ---
readonly RS_PASS=$(cat "$PASS_FILE")
readonly PASS_HELPER="${CM_SCRIPT_DIR}/.temp_pass.sh"

echo -e "#!/bin/bash\necho '${RS_PASS}'" > "$PASS_HELPER"
chmod 700 "$PASS_HELPER"

trap 'rm -f "$PASS_HELPER"' EXIT


# --- Build Options ---
RS_OPTS="-avzh"

if [ "$RS_MODE" = "sync" ]; then
    RS_OPTS="${RS_OPTS} --delete"
    log_info "Mode: Full Synchronization"
else
    log_info "Mode: Copy/Update only"
fi

if [ -n "$RS_PATTERN" ]; then
    RS_OPTS="${RS_OPTS} --include=${RS_PATTERN} --exclude=*"
    log_info "Pattern: ${RS_PATTERN}"
fi


# --- Execution ---
log_info "Starting fetch: $RS_CONF_NAME -> $RS_DEST"

# [TECH] SSH_ASKPASS_REQUIRE=force により非対話認証を強制
if env DISPLAY=:0 \
       SSH_ASKPASS="${PASS_HELPER}" \
       SSH_ASKPASS_REQUIRE=force \
   rsync ${RS_OPTS} \
   -e "setsid ssh -o StrictHostKeyChecking=no \
                  -o NumberOfPasswordPrompts=1 \
                  -o ControlMaster=no \
                  -o UserKnownHostsFile=/dev/null \
                  -o LogLevel=ERROR" \
   "${RS_SRC}" "${RS_DEST}"; then
    log_info "Completed."
else
    log_error "Failed. Verify credentials in vault/."
    exit 1
fi