"""SCP 転送ツール — CLI コマンド定義モジュール。

このモジュールは argparse パーサーとサブコマンド実装を提供する。
直接実行せず、プロジェクトルートの main.py 経由で使用すること::

    python3 main.py download --profile jupyter --remote "/data/*.csv"
    python3 main.py upload   --profile jupyter --local  "./reports/*.pdf"
"""

import argparse
import getpass
import sys
from typing import Optional

from .client import SCPClient
from .config import ConfigLoader, ServerProfile, TransferConfig, DEFAULT_CONFIG_FILE


def _resolve_password(
    cli_password: Optional[str],
    profile_password: Optional[str],
    user: str,
    host: str,
) -> str:
    """パスワードを解決する。

    優先順位: CLI 引数 > プロファイル設定 > 環境変数 > 対話入力。

    Args:
        cli_password: CLI から渡されたパスワード（存在しない場合は None）。
        profile_password: プロファイルに設定されたパスワード（存在しない場合は None）。
        user: 対話入力プロンプト用のユーザー名。
        host: 対話入力プロンプト用のホスト名。

    Returns:
        解決されたパスワード文字列。

    Raises:
        SystemExit: パスワードの対話入力がキャンセルされた場合。
    """
    import os

    password = cli_password or profile_password or os.environ.get("SCP_PASSWORD")
    if not password:
        try:
            password = getpass.getpass(f"{user}@{host} のパスワード: ")
        except (KeyboardInterrupt, EOFError):
            print("\nキャンセルされました。", file=sys.stderr)
            sys.exit(1)
    return password


def build_transfer_config(
    args: argparse.Namespace,
    profile: ServerProfile,
) -> TransferConfig:
    """CLI オプションとプロファイル設定をマージして転送設定を構築する。

    CLI オプションがプロファイルのデフォルト値より優先される。

    Args:
        args: argparse で解析済みの CLI 引数。
        profile: 使用するサーバープロファイル。

    Returns:
        マージ済みの TransferConfig インスタンス。

    Raises:
        SystemExit: パスワードの対話入力がキャンセルされた場合。
    """
    host = getattr(args, "host", None) or profile.host
    port = getattr(args, "port", None) or profile.port
    user = getattr(args, "user", None) or profile.user
    log_file = getattr(args, "log", None) or profile.log

    no_checksum = getattr(args, "no_checksum", False)
    checksum = profile.checksum if not no_checksum else False

    password = _resolve_password(
        cli_password=getattr(args, "password", None),
        profile_password=profile.password,
        user=user,
        host=host,
    )

    remote_path = getattr(args, "remote", None) or profile.remote_base
    local_path = getattr(args, "local", None) or profile.local_base

    return TransferConfig(
        host=host,
        port=port,
        user=user,
        password=password,
        remote_path=remote_path,
        local_path=local_path,
        log_file=log_file,
        checksum=checksum,
    )


def cmd_download(args: argparse.Namespace) -> None:
    """ダウンロードサブコマンドを実行する。

    Args:
        args: argparse で解析済みの CLI 引数。

    Returns:
        None
    """
    config_path = getattr(args, "config", DEFAULT_CONFIG_FILE)
    loader = ConfigLoader(config_path)
    profile = loader.get_profile(getattr(args, "profile", None))
    cfg = build_transfer_config(args, profile)

    client = SCPClient(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        log_file=cfg.log_file,
        use_checksum=cfg.checksum,
    )
    results = client.download(remote=cfg.remote_path, local=cfg.local_path)

    failed_count = sum(1 for r in results if not r["success"])
    sys.exit(1 if failed_count > 0 else 0)


def cmd_upload(args: argparse.Namespace) -> None:
    """アップロードサブコマンドを実行する。

    Args:
        args: argparse で解析済みの CLI 引数。

    Returns:
        None
    """
    config_path = getattr(args, "config", DEFAULT_CONFIG_FILE)
    loader = ConfigLoader(config_path)
    profile = loader.get_profile(getattr(args, "profile", None))
    cfg = build_transfer_config(args, profile)

    client = SCPClient(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        log_file=cfg.log_file,
        use_checksum=cfg.checksum,
    )
    results = client.upload(local=cfg.local_path, remote=cfg.remote_path)

    failed_count = sum(1 for r in results if not r["success"])
    sys.exit(1 if failed_count > 0 else 0)


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    """共通 CLI オプションをパーサーに追加する。

    Args:
        parser: オプションを追加する ArgumentParser インスタンス。

    Returns:
        None
    """
    parser.add_argument("--profile", metavar="NAME", help="使用するプロファイル名")
    parser.add_argument("--host", metavar="HOST", help="接続先ホスト名または IP アドレス")
    parser.add_argument("--port", type=int, metavar="PORT", help="SSH ポート番号")
    parser.add_argument("--user", metavar="USER", help="SSH ユーザー名")
    parser.add_argument(
        "--password",
        metavar="PASS",
        help="SSH パスワード（未指定時は環境変数 SCP_PASSWORD または対話入力）",
    )
    parser.add_argument("--log", metavar="FILE", help="ログファイルパス")
    parser.add_argument(
        "--no-checksum",
        dest="no_checksum",
        action="store_true",
        help="SHA-256 チェックサム検証をスキップする",
    )


def create_parser() -> argparse.ArgumentParser:
    """CLI パーサーを生成して返す。

    Returns:
        設定済みの ArgumentParser インスタンス。

    Examples:
        >>> parser = create_parser()
        >>> parser.prog
        'main.py'
    """
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="SCP プロトコルを用いたリモートファイル転送ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "例:\n"
            "  %(prog)s download --profile jupyter --remote '/data/*.csv'\n"
            "  %(prog)s upload   --profile jupyter --local  './data_*.csv'\n"
        ),
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_FILE,
        metavar="FILE",
        help=f"設定ファイルパス（デフォルト: {DEFAULT_CONFIG_FILE}）",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    # --- download ---
    dl = subparsers.add_parser("download", help="ファイルをリモートからローカルへダウンロード")
    _add_common_options(dl)
    dl.add_argument(
        "--remote",
        metavar="PATH",
        help="リモートファイルパス（ワイルドカード可）。デフォルトはプロファイルの remote_base",
    )
    dl.add_argument(
        "--local",
        metavar="DIR",
        help="ローカル保存先ディレクトリ。デフォルトはプロファイルの local_base",
    )
    dl.set_defaults(func=cmd_download)

    # --- upload ---
    ul = subparsers.add_parser("upload", help="ファイルをローカルからリモートへアップロード")
    _add_common_options(ul)
    ul.add_argument(
        "--local",
        metavar="PATH",
        help="アップロードするローカルファイルパス（ワイルドカード可）。デフォルトはプロファイルの local_base",
    )
    ul.add_argument(
        "--remote",
        metavar="DIR",
        help="リモート保存先ディレクトリ。デフォルトはプロファイルの remote_base",
    )
    ul.set_defaults(func=cmd_upload)

    return parser


if __name__ == "__main__":
    # このモジュールはパッケージの一部です。プロジェクトルートから実行してください:
    #   python3 main.py download --help
    #   python3 main.py upload   --help
    print("使い方: python3 main.py download --help")
