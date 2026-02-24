"""CLI エントリーポイント。

コマンドライン引数を解析し、指定した機器にコマンドを実行して
結果を表示・保存する。差分表示モードにも対応。

使用方法:
    python main.py --host vmx1
    python main.py --host vmx1 --diff 20260223_100000
    python main.py --host vmx1 --output-dir /var/log/netcollector
    python main.py --host vmx1 --no-confirm
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# プロジェクトルートを sys.path に追加（src パッケージを import するため）
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src import CollectionResult, NetCollector
from src.config import ConfigLoader
from src.connector import ConnectionManager
from src.executor import CommandExecutor
from src.output import DiffDisplay, OutputDisplay, OutputSaver


# ---------------------------------------------------------------------------
# ロギング設定
# ---------------------------------------------------------------------------

def _setup_logging(log_file: str = "execution.log", verbose: bool = False) -> None:
    """ロギングを設定する。

    標準エラー出力とファイルに同時出力する。

    Args:
        log_file: ログファイルのパス。
        verbose: True の場合は DEBUG レベルで出力する。

    Returns:
        None
    """
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handlers: list = [
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(log_file, encoding="utf-8"),
    ]
    logging.basicConfig(level=level, format=fmt, datefmt=datefmt, handlers=handlers)


# ---------------------------------------------------------------------------
# CLI 引数パーサー
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """コマンドライン引数パーサーを構築する。

    Args:
        なし。

    Returns:
        設定済みの ArgumentParser インスタンス。
    """
    parser = argparse.ArgumentParser(
        description="ネットワーク機器コマンド収集ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 機器にコマンドを実行して保存
  python main.py --host vmx1

  # 差分表示モード（指定タイムスタンプとの比較）
  python main.py --host vmx1 --diff 20260223_100000

  # 出力ディレクトリを指定
  python main.py --host vmx1 --output-dir /var/log/netcollector

  # 確認なしで実行（自動化向け）
  python main.py --host vmx1 --no-confirm

  # 保存済みタイムスタンプ一覧（全機器）
  python main.py --list-timestamps

  # 保存済みタイムスタンプ一覧（特定機器）
  python main.py --host vmx1 --list-timestamps
        """,
    )
    parser.add_argument(
        "--host",
        required=False,
        default=None,
        metavar="DEVICE_NAME",
        help="実行対象の機器識別名（hosts.yaml の name フィールド）",
    )
    parser.add_argument(
        "--list-timestamps",
        action="store_true",
        help="保存済みタイムスタンプの一覧を表示する（--host 省略時は全機器）",
    )
    parser.add_argument(
        "--diff",
        metavar="YYYYMMDD_HHMMSS",
        default=None,
        help="差分表示モード: 指定タイムスタンプの保存データと比較する",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        metavar="DIR",
        help="出力保存先ディレクトリ（デフォルト: outputs）",
    )
    parser.add_argument(
        "--hosts-file",
        default="configs/hosts.yaml",
        metavar="FILE",
        help="接続先設定ファイルのパス（デフォルト: configs/hosts.yaml）",
    )
    parser.add_argument(
        "--commands-file",
        default="configs/commands.yaml",
        metavar="FILE",
        help="コマンド定義ファイルのパス（デフォルト: configs/commands.yaml）",
    )
    parser.add_argument(
        "--review-file",
        default="configs/review_points.yaml",
        metavar="FILE",
        help="レビュー定義ファイルのパス（デフォルト: configs/review_points.yaml）",
    )
    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="実行前の Yes/No 確認をスキップする",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="詳細ログ（DEBUG レベル）を出力する",
    )
    return parser


# ---------------------------------------------------------------------------
# タイムスタンプ一覧表示モード
# ---------------------------------------------------------------------------

def _run_list_timestamps(host: Optional[str], output_dir: str) -> None:
    """保存済みタイムスタンプの一覧を表示する（コマンド実行なし）。

    host を指定した場合はその機器のタイムスタンプのみ、
    省略した場合は outputs/ 配下の全機器を対象にする。

    Args:
        host: 機器識別名。None の場合は全機器を表示。
        output_dir: 保存済みデータのルートディレクトリ。

    Returns:
        None
    """
    from pathlib import Path

    saver = OutputSaver(output_dir)
    output_path = Path(output_dir)

    if host:
        # 指定機器のみ表示
        timestamps = saver.list_timestamps(host)
        if not timestamps:
            print(f"[情報] {host} の保存データはありません: {output_dir}/{host}/")
            return
        print(f"機器: {host}  ({len(timestamps)} 件)\n")
        for ts in timestamps:
            dir_path = output_path / host / ts
            files = sorted(f.stem for f in dir_path.glob("*.txt"))
            print(f"  {ts}  [{', '.join(files)}]")
    else:
        # 全機器を表示
        if not output_path.exists():
            print(f"[情報] 保存データなし: {output_dir}/")
            return
        devices = sorted(
            d.name
            for d in output_path.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        )
        if not devices:
            print(f"[情報] 保存データなし: {output_dir}/")
            return
        for device in devices:
            timestamps = saver.list_timestamps(device)
            print(f"\n機器: {device}  ({len(timestamps)} 件)")
            for ts in timestamps:
                dir_path = output_path / device / ts
                files = sorted(f.stem for f in dir_path.glob("*.txt"))
                print(f"  {ts}  [{', '.join(files)}]")


# ---------------------------------------------------------------------------
# 差分表示専用モード
# ---------------------------------------------------------------------------

def _run_diff_only(
    host: str,
    old_timestamp: str,
    hosts_file: str,
    commands_file: str,
    output_dir: str,
) -> None:
    """保存済みデータとの差分を表示する（コマンド実行なし）。

    Args:
        host: 機器識別名。
        old_timestamp: 比較対象のタイムスタンプ（YYYYMMDD_HHMMSS）。
        hosts_file: 接続先設定ファイルのパス。
        commands_file: コマンド定義ファイルのパス。
        output_dir: 保存済みデータのルートディレクトリ。

    Returns:
        None

    Raises:
        SystemExit: タイムスタンプが存在しない場合。
    """
    loader = ConfigLoader()
    commands_config = loader.load_commands(commands_file)
    saver = OutputSaver(output_dir)

    timestamps = saver.list_timestamps(host)
    if not timestamps:
        print(f"[エラー] {host} の保存データが見つかりません: {output_dir}/{host}/",
              file=sys.stderr)
        sys.exit(1)

    latest = timestamps[-1]
    print(f"比較: {old_timestamp}  →  {latest}\n")

    disp = DiffDisplay()

    # 最新保存データを CommandResult として読み込む
    from src.executor import CommandResult
    from datetime import datetime

    results = []
    for cmd in commands_config.commands:
        output = saver.load(host, latest, cmd.name)
        if output is None:
            continue
        results.append(
            CommandResult(
                command_name=cmd.name,
                command=cmd.command,
                output=output,
                device_name=host,
                executed_at=datetime.now(),
            )
        )

    if not results:
        print(f"[情報] {latest} に保存データがありません")
        return

    disp.show_terminal(results, old_timestamp, saver)


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------

def main() -> None:
    """CLIエントリーポイントのメイン処理。

    Returns:
        None
    """
    parser = _build_parser()
    args = parser.parse_args()

    _setup_logging(verbose=args.verbose)
    logger = logging.getLogger(__name__)

    # カレントディレクトリをプロジェクトルートに設定
    import os
    os.chdir(_PROJECT_ROOT)

    try:
        # タイムスタンプ一覧表示モード（--host 不要）
        if args.list_timestamps:
            _run_list_timestamps(host=args.host, output_dir=args.output_dir)
            return

        # --host が必須の操作（diff / 実行）では明示チェック
        if args.host is None:
            parser.error("--host は必須です（--list-timestamps のみ省略可）")

        # 差分表示専用モード
        if args.diff is not None:
            _run_diff_only(
                host=args.host,
                old_timestamp=args.diff,
                hosts_file=args.hosts_file,
                commands_file=args.commands_file,
                output_dir=args.output_dir,
            )
            return

        # コマンド実行モード
        nc = NetCollector(
            hosts_file=args.hosts_file,
            commands_file=args.commands_file,
            review_file=args.review_file,
        )

        result = nc.run(
            device=args.host,
            output_dir=args.output_dir,
            confirm=not args.no_confirm,
        )

        if result is None:
            # ユーザーがキャンセル
            sys.exit(0)

        # ターミナルに出力表示
        disp = OutputDisplay()
        disp.show_terminal(result.results)

        print(f"\n[完了] 保存先: {args.output_dir}/{args.host}/{result.timestamp}/")

    except FileNotFoundError as exc:
        print(f"[エラー] 設定ファイルが見つかりません: {exc}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(f"[エラー] {exc}", file=sys.stderr)
        sys.exit(1)
    except ConnectionError as exc:
        print(f"[エラー] 接続失敗: {exc}", file=sys.stderr)
        logger.error(f"接続失敗: {exc}", exc_info=True)
        sys.exit(1)
    except TimeoutError as exc:
        print(f"[エラー] タイムアウト: {exc}", file=sys.stderr)
        logger.error(f"タイムアウト: {exc}", exc_info=True)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[中断] ユーザーが中断しました", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"[エラー] 予期しないエラー: {exc}", file=sys.stderr)
        logger.exception("予期しないエラー")
        sys.exit(1)


if __name__ == "__main__":
    main()
