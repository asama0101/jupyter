import requests
import urllib3
import logging
import os
import sys

# ==============================================================================
# FITELnet REST API Client Library (v1.0)
#
# DESCRIPTION:
#   FITELnet機器とREST API通信を行うための共通モジュール。
#   API認証、ロギング、および以下のエンドポイントへのリクエストを処理する。
#   - PATCH /api/v1/config (multipart/form-dataによる差分設定反映)
#   - POST  /api/v1/cli    (運用コマンドの実行)
#
# NOTES:
#   - SSL自己署名証明書の検証はスキップする設定(verify=False)となっている。
#   - 認証はBasic認証を使用する。
# ==============================================================================

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def setup_logger(name):
    """Bash互換のログフォーマットを設定"""
    logging.basicConfig(
        level=logging.INFO, 
        format='[%(asctime)s] [%(levelname)s] %(message)s', 
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(name)

def resolve_auth(args, logger):
    """
    接続パラメータ(Host/User/Pass)の解決。
    優先順位: 1. コマンドライン引数 / 2. 環境変数およびVaultファイル
    """
    host, user = args.host, args.user
    if args.password: 
        return host, user, args.password
    
    proj_root = os.environ.get("PROJ_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pass_file = f"{proj_root}/vault/.pass_{args.target}"
    
    try:
        with open(pass_file, "r") as f:
            return host, user, f.read().strip()
    except FileNotFoundError:
        logger.error(f"Authentication Failure: Password file not found at {pass_file}")
        sys.exit(1)

class FitelnetAPI:
    def __init__(self, host, user, password):
        self.base_url = f"https://{host}:50443/api/v1"
        self.auth = (user, password)

    def patch_config(self, config_data):
        """[PATCH] 差分コンフィグ反映。パラメータ 'config' にtext/plainを格納。"""
        url = f"{self.base_url}/config"
        files = {'config': ('config.txt', config_data, 'text/plain')}
        r = requests.patch(url, auth=self.auth, files=files, verify=False, timeout=60)
        r.raise_for_status()

    def exec_cli(self, command):
        """[POST] CLI運用コマンド実行。JSONボディでコマンドを送信。"""
        url = f"{self.base_url}/cli"
        r = requests.post(url, auth=self.auth, json={"cmd": command}, verify=False, timeout=60)
        r.raise_for_status()
        return r.json()