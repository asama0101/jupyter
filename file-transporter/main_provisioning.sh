#!/bin/bash

# ==============================================================================
#  Script Name : main_provisioning.sh
#  Purpose     : 加入者情報および帯域制御の定期プロビジョニング実行
#  Arguments   : $1 - 実行対象 (subscriber | shaper | all)
#  Usage       : ./main_provisioning.sh {subscriber|shaper|all}
#  Example     : ./main_provisioning.sh subscriber  # 加入者プロビのみ実行
#                ./main_provisioning.sh all         # 全タスクを一括実行
# ==============================================================================

# --- Shell Options for Safety ---
set -u # 未定義変数参照時にエラー停止
set -o pipefail # パイプライン途中のエラーをキャッチ

# --- Environment Path Definitions ---
readonly CM_SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
readonly LIB_DIR="${CM_SCRIPT_DIR}/lib"
readonly DATA_DIR="${CM_SCRIPT_DIR}/data"
readonly SHAPER_DIR="${DATA_DIR}/raw/shaper"
readonly SUB_DIR="${DATA_DIR}/raw/sub"
readonly DL_DIR="${DATA_DIR}/raw/config"
readonly WORKING_DIR="${DATA_DIR}/interim"
readonly HISTORY_DIR="${DATA_DIR}/processed"
readonly LOG_DIR="${CM_SCRIPT_DIR}/log"
readonly LOCK_FILE="/tmp/main_provisioning.lock"

# --- Configuration ---
readonly TARGET_ROUTER="router"
readonly TARGET_DB="shaper_db"

# 共通ユーティリティ関数のロード
[[ -f "${LIB_DIR}/utils.sh" ]] && source "${LIB_DIR}/utils.sh" || { echo "Core library missing"; exit 1; }

# --- External Tool Definitions (All scripts consolidated in lib/) ---
readonly PY_EXEC_CMD="${LIB_DIR}/exec_cmd.py"
readonly PY_APPLY_CONFIG="${LIB_DIR}/apply_config.py"
readonly SH_SCP_TRANSFER="${LIB_DIR}/scp_transfer.sh"

# ==============================================================================
#  TASK 1: 加入者情報プロビジョニング (Subscriber Provisioning)
#  - カスコン指示と実機現設定を比較し、差分(Add/Del)を同期する
# ==============================================================================
job_subscriber_provisioning() {
    log_info "[SUB] Starting Subscriber Provisioning Task..."

    # 1. カスコンから最新マスターデータを同期取得
    "${LIB_DIR}/remote_fetch.sh" "${TARGET_DB}" "${SUB_DIR}" sync "*.csv" || return 1

    # 2. カテゴリ別に指示CSVファイルをマージ
    "${LIB_DIR}/csv_merge.sh" ${SUB_DIR}/add_*.csv "${WORKING_DIR}/sub_add_combined.csv" || return 1
    "${LIB_DIR}/csv_merge.sh" ${SUB_DIR}/del_*.csv "${WORKING_DIR}/sub_del_combined.csv" || return 1

    # 3. ルータ投入用フォーマットへ整形 (@区切り展開)
    awk -F'@' '{printf "%s", $0; for(i=2; i<=NF; i++) printf " %s", $i; print ""}' \
        "${WORKING_DIR}/sub_add_combined.csv" > "${WORKING_DIR}/sub_add_split.csv" || return 1
    awk -F'@' '{printf "%s", $0; for(i=2; i<=NF; i++) printf " %s", $i; print ""}' \
        "${WORKING_DIR}/sub_del_combined.csv" > "${WORKING_DIR}/sub_del_split.csv" || return 1

    # 4. 現用ルータから最新設定をバックアップ取得 (差分比較のソース)
    log_info "[SUB] Requesting router to save current config to dyn_q_flow_save.cfg"
    python3 "${PY_EXEC_CMD}" /dev/null -t "${TARGET_ROUTER}" -c "dynamic-queueing flow save moff" || return 1
    "${SH_SCP_TRANSFER}" "${TARGET_ROUTER}" download "${DL_DIR}/dyn_q_flow_save.cfg" || return 1

    # 5. 実機設定 vs カスコン指示による差分抽出
    [[ -f "${DL_DIR}/dyn_q_flow_save.cfg" ]] || { log_error "Backup file not found"; return 1; }
    # Set分: カスコン指示にあり、実機に未設定の行を抽出
    grep -Fvxf "${DL_DIR}/dyn_q_flow_save.cfg" "${WORKING_DIR}/sub_add_split.csv" > "${WORKING_DIR}/dyn_q_flow_set.cfg" || true
    # Unset分: カスコン削除指示にあり、実機に設定済みの行を抽出
    grep -Fxf "${DL_DIR}/dyn_q_flow_save.cfg" "${WORKING_DIR}/sub_del_split.csv" > "${WORKING_DIR}/dyn_q_flow_unset.cfg" || true

    # 6. 差分検知および条件付き実行 (削除優先)

    # --- CASE A: 設定削除 (Unset) ---
    if [[ -s "${WORKING_DIR}/dyn_q_flow_unset.cfg" ]]; then
        log_info "[SUB] Target deletion detected. Applying Unset configuration..."
        "${SH_SCP_TRANSFER}" "${TARGET_ROUTER}" upload "${WORKING_DIR}/dyn_q_flow_unset.cfg" || return 1
        python3 "${PY_EXEC_CMD}" /dev/null -t "${TARGET_ROUTER}" -c "dynamic-queueing flow set moff" || return 1
        
        # 実行ログとして証跡保管
        mv "${WORKING_DIR}/dyn_q_flow_unset.cfg" "${HISTORY_DIR}/sub_prov_del_$(date +%Y%m%d_%H%M%S).csv"
    else
        log_info "[SUB] No deletion required."
    fi

    # --- CASE B: 設定追加 (Set) ---
    if [[ -s "${WORKING_DIR}/dyn_q_flow_set.cfg" ]]; then
        log_info "[SUB] New entries detected. Applying Set configuration..."
        "${SH_SCP_TRANSFER}" "${TARGET_ROUTER}" upload "${WORKING_DIR}/dyn_q_flow_set.cfg" || return 1
        python3 "${PY_EXEC_CMD}" /dev/null -t "${TARGET_ROUTER}" -c "dynamic-queueing flow set moff" || return 1
        
        # 実行ログとして証跡保管
        mv "${WORKING_DIR}/dyn_q_flow_set.cfg" "${HISTORY_DIR}/sub_prov_add_$(date +%Y%m%d_%H%M%S).csv"
    else
        log_info "[SUB] No addition required."
    fi
    log_info "[SUB] Task completed (No commit required for Subscriber)."
}

# ==============================================================================
#  TASK 2: 帯域制御プロビジョニング (Shaper Provisioning)
#  - 前回の反映内容と比較し、変更がある場合のみ全件更新を実行する
# ==============================================================================
job_shaper_provisioning() {
    log_info "[SHAPER] Starting Shaper Provisioning Task..."

    # 1. カスコンからシェーパ設定ファイルを同期取得
    "${LIB_DIR}/remote_fetch.sh" "${TARGET_DB}" "${SHAPER_DIR}" sync "*.txt" || return 1

    # 2. 投入用コンフィグの生成および特定IDの除外
    "${LIB_DIR}/generate_tm_config.sh" "${SHAPER_DIR}/latest_shaper.txt" "${WORKING_DIR}/new_shaper.conf" || return 1

    # 特定IDの除外
    sed -i '/AA00-00-1000/d' "${WORKING_DIR}/new_shaper.conf"

    # 3. 前回反映データとの内容比較による更新要否判定
    if diff -q "${WORKING_DIR}/new_shaper.conf" "${HISTORY_DIR}/last_shaper.conf" > /dev/null 2>&1; then
        log_info "[SHAPER] Current configuration is up-to-date. Skipping."
    else
        log_info "[SHAPER] Configuration changes detected. Provisioning..."

        # 設定反映
        python3 "${PY_APPLY_CONFIG}" -t "${TARGET_ROUTER}" -f "${WORKING_DIR}/new_shaper.conf" || return 1
        python3 "${PY_EXEC_CMD}" "${WORKING_DIR}/commit_shaper.log" -t "${TARGET_ROUTER}" -c "commit moff" || return 1

        # 実行ログとして証跡保管
        cp "${WORKING_DIR}/new_shaper.conf" "${HISTORY_DIR}/last_shaper.conf"
        mv "${WORKING_DIR}/new_shaper.conf" "${HISTORY_DIR}/shaper_prov_$(date +%Y%m%d_%H%M%S).conf"
    fi
}

# --- CLI Entry Point ---
# 2重起動の禁止
(
    flock -n 9 || { echo "Error: Another instance is running." >&2; exit 1; }

    case "${1:-}" in
        subscriber) job_subscriber_provisioning ;;
        shaper)     job_shaper_provisioning ;;
        all)        job_subscriber_provisioning && job_shaper_provisioning ;;
        *)          echo "Usage: $0 {subscriber|shaper|all}"; exit 1 ;;
    esac

) 9>"${LOCK_FILE}"

# 結果判定
if [[ $? -ne 0 ]]; then
    log_error "Provisioning script failed."
    exit 1
fi