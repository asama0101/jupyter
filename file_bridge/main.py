"""SCP ファイル転送ツール — CLI エントリーポイント。

プロジェクトルートから以下のコマンドで実行します::

    python3 main.py download --profile jupyter --remote "/data/*.csv"
    python3 main.py upload   --profile jupyter --local  "./reports/*.pdf"
    python3 main.py download --help
"""

import logging
import sys

from src.cli import create_parser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """CLI エントリーポイント。

    argparse でサブコマンド（download / upload）を解析して実行する。

    Returns:
        None

    Raises:
        SystemExit: 正常終了（0）またはエラー終了（1）時。

    Examples:
        >>> # コマンドラインから実行
        >>> # python3 main.py download --profile jupyter --remote "/data/*.csv"
    """
    parser = create_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except FileNotFoundError as e:
        logger.error("ファイルが見つかりません: %s", e)
        sys.exit(1)
    except (KeyError, ValueError) as e:
        logger.error("設定エラー: %s", e)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n中断されました。", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
