import argparse
import sys
import os
sys.path.append(os.path.dirname(__file__))
from fitelnet_api import FitelnetAPI, setup_logger, resolve_auth

# ==============================================================================
# NAME
#   apply_config.py - FITELnet Configuration Patch Tool
#
# SYNOPSIS
#   python3 apply_config.py -t <TARGET> -f <CONFIG_FILE> [OPTIONS]
#
# DESCRIPTION
#   指定されたコンフィグファイルを読み込み、API経由で装置へ差分反映(PATCH)を行う。
#   本スクリプトは反映のみを行い、確定(commit)は行わない。
#
# OPTIONS
#   -t, --target   装置識別名 (Vaultファイルの特定に必須)
#   -f, --file     投入するコンフィグファイルのパス (必須)
#   -H, --host     接続先IPアドレス (デフォルト: 環境変数 $REMOTE_HOST)
#   -u, --user     ログインユーザー名 (デフォルト: 環境変数 $REMOTE_USER)
#   -p, --password パスワードを直接指定 (省略時はVaultを参照)
#
# EXAMPLE
#   python3 apply_config.py -t edge-router-01 -f ./work/diff.cfg
#   python3 apply_config.py -H 192.168.1.1 -u admin -p pass123 -t router -f test.cfg
# ==============================================================================

logger = setup_logger(__name__)

def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-H', '--host',     default=os.environ.get("REMOTE_HOST"))
    parser.add_argument('-u', '--user',     default=os.environ.get("REMOTE_USER"))
    parser.add_argument('-p', '--password')
    parser.add_argument('-t', '--target',   required=True)
    parser.add_argument('-f', '--file',     required=True)
    args = parser.parse_args()

    host, user, password = resolve_auth(args, logger)
    api = FitelnetAPI(host, user, password)

    try:
        with open(args.file, "r") as f:
            data = f.read()
        
        if not data.strip():
            logger.warning(f"Target: {host} | Config file is empty. Skipping.")
            return

        logger.info(f"Target: {host} | Sending patch config from '{args.file}'")
        api.patch_config(data)
        logger.info(f"Target: {host} | Configuration patched successfully.")

    except Exception as e:
        logger.error(f"Target: {host} | Failed to apply config: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()