import argparse
import sys
import os
sys.path.append(os.path.dirname(__file__))
from fitelnet_api import FitelnetAPI, setup_logger, resolve_auth

# ==============================================================================
# NAME
#   exec_cmd.py - FITELnet CLI Command Executor
#
# SYNOPSIS
#   python3 exec_cmd.py [OUTPUT_FILE] -t <TARGET> [OPTIONS]
#
# DESCRIPTION
#   API経由で任意のCLI運用コマンドを実行します。
#   OUTPUT_FILE を指定した場合はファイルへ保存し、省略した場合は画面に表示します。
#
# ARGUMENTS
#   OUTPUT_FILE    (任意) 実行結果を保存するファイルパス。省略時は標準出力。
#
# OPTIONS
#   -t, --target   装置識別名 (Vaultファイルの特定に必須)
#   -c, --cmd      実行コマンド (デフォルト: "show version")
#   -H, --host     接続先IPアドレス
#   -u, --user     ログインユーザー名
#   -p, --password パスワード直接指定
# ==============================================================================

logger = setup_logger(__name__)

def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('output', nargs='?', default=None)
    parser.add_argument('-H', '--host',     default=os.environ.get("REMOTE_HOST"))
    parser.add_argument('-u', '--user',     default=os.environ.get("REMOTE_USER"))
    parser.add_argument('-p', '--password')
    parser.add_argument('-t', '--target',   required=True)
    parser.add_argument('-c', '--cmd',      default='show version')
    args = parser.parse_args()

    host, user, password = resolve_auth(args, logger)
    api = FitelnetAPI(host, user, password)

    try:
        logger.info(f"Target: {host} | Executing CLI: '{args.cmd}'")
        res = api.exec_cli(args.cmd)
        
        if args.output:
            with open(args.output, "w") as f:
                f.write(res)
            logger.info(f"Result successfully saved to: {args.output}")
        else:
            print("\n" + "="*50)
            print(f"--- COMMAND RESULT ---")
            print(res)
            print("="*50 + "\n")

    except Exception as e:
        logger.error(f"Target: {host} | CLI execution failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()