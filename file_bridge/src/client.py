"""SCP ファイル転送クライアントモジュール。"""

import glob as glob_module
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from netmiko import ConnectHandler
from netmiko.scp_handler import SCPConn

from .checksum import calculate_local_sha256, calculate_remote_sha256, verify_checksum
from .logger import TransferLogger, TransferRecord

logger = logging.getLogger(__name__)

SSH_TIMEOUT = 60
SCP_SOCKET_TIMEOUT = 60.0
SEND_CMD_TIMEOUT = 120


def _is_jupyter() -> bool:
    """Jupyter 環境で実行されているかどうかを判定する。

    Returns:
        Jupyter Notebook / JupyterLab 環境の場合は True、そうでない場合は False。

    Examples:
        >>> _is_jupyter()
        False
    """
    try:
        from IPython import get_ipython  # type: ignore[import]

        ip = get_ipython()
        return ip is not None and "IPKernelApp" in ip.config
    except ImportError:
        return False


class SCPClient:
    """SCP プロトコルを用いたファイル転送クライアント。

    netmiko を使用してリモートサーバーとのファイル転送を行う。
    CLI と Jupyter Notebook の両環境で動作する。

    Attributes:
        host: 接続先ホスト名または IP アドレス。
        port: SSH ポート番号。
        user: SSH ユーザー名。
        use_checksum: チェックサム検証の有効フラグ。
        transfer_logger: 転送ログマネージャ。

    Examples:
        >>> client = SCPClient(host="192.168.3.61", user="sysope", password="secret")
        >>> results = client.download(remote="/data/*.csv", local="./output/")
        >>> results = client.upload(local="./data/*.csv", remote="/uploads/")
    """

    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        port: int = 22,
        log_file: str = "transfer.log",
        use_checksum: bool = True,
    ) -> None:
        """SCPClient を初期化する。

        Args:
            host: 接続先ホスト名または IP アドレス。
            user: SSH ユーザー名。
            password: SSH パスワード。
            port: SSH ポート番号（デフォルト: 22）。
            log_file: ログファイルのパス。
            use_checksum: チェックサム検証を有効にするか（デフォルト: True）。
        """
        self.host = host
        self.port = port
        self.user = user
        self._password = password
        self.use_checksum = use_checksum
        self.transfer_logger = TransferLogger(log_file)
        self._jupyter = _is_jupyter()

    def _create_connection(self) -> ConnectHandler:
        """SSH 接続を確立して返す。

        Returns:
            接続済みの ConnectHandler インスタンス。

        Raises:
            netmiko.exceptions.NetmikoAuthenticationException: 認証に失敗した場合。
            netmiko.exceptions.NetmikoTimeoutException: 接続タイムアウトの場合。
        """
        device_params = {
            "device_type": "linux",
            "host": self.host,
            "username": self.user,
            "password": self._password,
            "port": self.port,
            "timeout": SSH_TIMEOUT,
        }
        logger.info("SSH 接続を確立します: %s@%s:%d", self.user, self.host, self.port)
        return ConnectHandler(**device_params)

    def _list_remote_files(
        self, connection: ConnectHandler, remote_pattern: str
    ) -> list[str]:
        """リモートサーバー上でパターンに一致するファイルを列挙する。

        ワイルドカードを含むパターンはリモートシェルで展開する。
        ディレクトリが指定された場合は再帰的にファイルを列挙する。

        Args:
            connection: 接続済みの ConnectHandler インスタンス。
            remote_pattern: ファイルパスまたはワイルドカードを含むパターン。

        Returns:
            一致したリモートファイルパスのリスト（ディレクトリは含まない）。

        Raises:
            FileNotFoundError: パターンに一致するファイルが存在しない場合。
        """
        output = connection.send_command(
            f"ls -1d {remote_pattern} 2>/dev/null",
            read_timeout=SEND_CMD_TIMEOUT,
        )
        entries = [line.strip() for line in output.strip().splitlines() if line.strip()]

        if not entries:
            raise FileNotFoundError(
                f"リモートにファイルが見つかりません: {remote_pattern}"
            )

        result: list[str] = []
        for entry in entries:
            type_out = connection.send_command(
                f'test -d "{entry}" && echo __DIR__ || echo __FILE__',
                read_timeout=SEND_CMD_TIMEOUT,
            )
            if "__DIR__" in type_out:
                sub_out = connection.send_command(
                    f'find "{entry}" -type f 2>/dev/null',
                    read_timeout=SEND_CMD_TIMEOUT,
                )
                sub_files = [
                    ln.strip() for ln in sub_out.strip().splitlines() if ln.strip()
                ]
                result.extend(sub_files)
            else:
                result.append(entry)

        return result

    def _get_remote_file_size(
        self, connection: ConnectHandler, remote_path: str
    ) -> int:
        """リモートファイルのサイズをバイト単位で取得する。

        Args:
            connection: 接続済みの ConnectHandler インスタンス。
            remote_path: サイズを取得するリモートファイルパス。

        Returns:
            ファイルサイズ（バイト）。取得できない場合は 0。
        """
        output = connection.send_command(
            f'stat -c%s "{remote_path}" 2>/dev/null',
            read_timeout=SEND_CMD_TIMEOUT,
        )
        try:
            return int(output.strip())
        except ValueError:
            return 0

    def _show_progress(
        self, current: int, total: int, filename: str, direction: str
    ) -> None:
        """ファイル転送の進捗をコンソールまたは Jupyter に表示する。

        Args:
            current: 現在の転送ファイル番号（1 始まり）。
            total: 転送ファイルの総数。
            filename: 現在転送中のファイル名。
            direction: 転送方向の説明文（例: 'uploading', 'downloading'）。

        Returns:
            None
        """
        msg = f"[{current}/{total}] {direction} {filename}..."
        if self._jupyter:
            try:
                from IPython.display import clear_output, display  # type: ignore[import]

                clear_output(wait=True)
                display(msg)
            except ImportError:
                print(f"\r{msg}", end="", flush=True)
        else:
            print(f"\r{msg:<80}", end="", flush=True)

    def _newline(self) -> None:
        """進捗表示後に改行を出力する（CLI 環境のみ）。

        Returns:
            None
        """
        if not self._jupyter:
            print()

    def download(
        self,
        remote: str,
        local: Optional[str] = None,
    ) -> list[dict]:
        """リモートサーバーからファイルをダウンロードする。

        ワイルドカードやディレクトリの再帰的ダウンロードに対応する。
        転送完了後にサマリーを表示し、各ファイルの結果をログに記録する。

        Args:
            remote: ダウンロードするリモートファイルパス（ワイルドカード可）。
            local: ローカルの保存先ディレクトリ。None の場合はカレントディレクトリ。

        Returns:
            各ファイルの転送結果を表す辞書のリスト。
            各辞書には 'remote', 'local', 'success', 'error' キーが含まれる。

        Raises:
            FileNotFoundError: リモートファイルが 1 件も見つからない場合。
            netmiko.exceptions.NetmikoAuthenticationException: 認証に失敗した場合。
        """
        local_dir = Path(local) if local else Path(".")
        local_dir.mkdir(parents=True, exist_ok=True)

        results: list[dict] = []

        with self._create_connection() as conn:
            remote_files = self._list_remote_files(conn, remote)
            total = len(remote_files)
            logger.info("ダウンロード対象: %d ファイル", total)

            for i, remote_file in enumerate(remote_files, 1):
                filename = Path(remote_file).name
                local_file = local_dir / filename
                self._show_progress(i, total, filename, "downloading")

                success = False
                error_msg = ""
                checksum_result = ""
                file_size = self._get_remote_file_size(conn, remote_file)

                try:
                    scp_conn = SCPConn(conn)
                    try:
                        scp_conn.scp_get_file(
                            source_file=remote_file,
                            dest_file=str(local_file),
                        )
                    finally:
                        scp_conn.close()

                    if self.use_checksum:
                        local_hash = calculate_local_sha256(local_file)
                        remote_hash = calculate_remote_sha256(conn, remote_file)
                        if verify_checksum(local_hash, remote_hash):
                            checksum_result = f"SHA256: {local_hash}"
                            success = True
                        else:
                            error_msg = (
                                f"チェックサム不一致: "
                                f"local={local_hash[:16]}... "
                                f"remote={remote_hash[:16]}..."
                            )
                            logger.error(error_msg)
                    else:
                        success = True
                        checksum_result = "チェックサムスキップ"

                    if success and local_file.exists():
                        file_size = local_file.stat().st_size

                except Exception as exc:
                    error_msg = str(exc)
                    logger.error("ダウンロード失敗 [%s]: %s", remote_file, error_msg)

                self._newline()
                record = TransferRecord(
                    timestamp=datetime.now(),
                    direction="DOWNLOAD",
                    source_path=remote_file,
                    dest_path=str(local_file),
                    file_size=file_size,
                    success=success,
                    checksum_result=checksum_result if success else error_msg,
                )
                self.transfer_logger.log_transfer(record)
                results.append(
                    {
                        "remote": remote_file,
                        "local": str(local_file),
                        "success": success,
                        "error": error_msg,
                    }
                )

        self._print_summary(results, "DOWNLOAD")
        return results

    def upload(
        self,
        local: str,
        remote: Optional[str] = None,
    ) -> list[dict]:
        """ローカルファイルをリモートサーバーへアップロードする。

        ワイルドカードによる複数ファイル指定に対応する。
        転送完了後にサマリーを表示し、各ファイルの結果をログに記録する。

        Args:
            local: アップロードするローカルファイルパス（ワイルドカード可）。
            remote: リモートの保存先ディレクトリ。None の場合はリモートホームディレクトリ。

        Returns:
            各ファイルの転送結果を表す辞書のリスト。
            各辞書には 'local', 'remote', 'success', 'error' キーが含まれる。

        Raises:
            FileNotFoundError: ローカルファイルが 1 件も見つからない場合。
            netmiko.exceptions.NetmikoAuthenticationException: 認証に失敗した場合。
        """
        local_files = sorted(glob_module.glob(local, recursive=True))
        local_files = [f for f in local_files if Path(f).is_file()]

        if not local_files:
            raise FileNotFoundError(
                f"ローカルにファイルが見つかりません: {local}"
            )

        remote_dir = remote.rstrip("/") if remote else "~"
        results: list[dict] = []
        total = len(local_files)
        logger.info("アップロード対象: %d ファイル", total)

        with self._create_connection() as conn:
            conn.send_command(
                f'mkdir -p "{remote_dir}" 2>/dev/null',
                read_timeout=SEND_CMD_TIMEOUT,
            )

            for i, local_file_str in enumerate(local_files, 1):
                local_path = Path(local_file_str)
                filename = local_path.name
                remote_file = f"{remote_dir}/{filename}"
                self._show_progress(i, total, filename, "uploading")

                success = False
                error_msg = ""
                checksum_result = ""
                file_size = local_path.stat().st_size

                try:
                    scp_conn = SCPConn(conn)
                    try:
                        scp_conn.scp_transfer_file(
                            source_file=str(local_path),
                            dest_file=remote_file,
                        )
                    finally:
                        scp_conn.close()

                    if self.use_checksum:
                        local_hash = calculate_local_sha256(local_path)
                        remote_hash = calculate_remote_sha256(conn, remote_file)
                        if verify_checksum(local_hash, remote_hash):
                            checksum_result = f"SHA256: {local_hash}"
                            success = True
                        else:
                            error_msg = (
                                f"チェックサム不一致: "
                                f"local={local_hash[:16]}... "
                                f"remote={remote_hash[:16]}..."
                            )
                            logger.error(error_msg)
                    else:
                        success = True
                        checksum_result = "チェックサムスキップ"

                except Exception as exc:
                    error_msg = str(exc)
                    logger.error("アップロード失敗 [%s]: %s", local_file_str, error_msg)

                self._newline()
                record = TransferRecord(
                    timestamp=datetime.now(),
                    direction="UPLOAD",
                    source_path=str(local_path),
                    dest_path=remote_file,
                    file_size=file_size,
                    success=success,
                    checksum_result=checksum_result if success else error_msg,
                )
                self.transfer_logger.log_transfer(record)
                results.append(
                    {
                        "local": str(local_path),
                        "remote": remote_file,
                        "success": success,
                        "error": error_msg,
                    }
                )

        self._print_summary(results, "UPLOAD")
        return results

    def _print_summary(self, results: list[dict], direction: str) -> None:
        """転送完了後のサマリーを環境に応じた形式で表示する。

        Args:
            results: 各ファイルの転送結果リスト。
            direction: 転送方向の表示文字列（'UPLOAD' または 'DOWNLOAD'）。

        Returns:
            None
        """
        total = len(results)
        succeeded = sum(1 for r in results if r["success"])
        failed = total - succeeded

        if self._jupyter:
            self._display_jupyter_summary(results, direction, total, succeeded, failed)
        else:
            self._display_cli_summary(results, direction, total, succeeded, failed)

    def _display_cli_summary(
        self,
        results: list[dict],
        direction: str,
        total: int,
        succeeded: int,
        failed: int,
    ) -> None:
        """CLI コンソールにサマリーを出力する。

        Args:
            results: 各ファイルの転送結果リスト。
            direction: 転送方向の表示文字列。
            total: 総ファイル数。
            succeeded: 成功ファイル数。
            failed: 失敗ファイル数。

        Returns:
            None
        """
        print(f"\n{'=' * 60}")
        print(f"{direction} 完了サマリー")
        print(f"{'=' * 60}")
        print(f"総ファイル数: {total}  成功: {succeeded}  失敗: {failed}")

        if failed > 0:
            print("\n[失敗したファイル]")
            for r in results:
                if not r["success"]:
                    file_key = "remote" if direction == "DOWNLOAD" else "local"
                    print(f"  - {r.get(file_key, '?')}: {r['error']}")

        print(f"{'=' * 60}")

    def _display_jupyter_summary(
        self,
        results: list[dict],
        direction: str,
        total: int,
        succeeded: int,
        failed: int,
    ) -> None:
        """Jupyter Notebook にサマリーを HTML テーブル形式で表示する。

        Args:
            results: 各ファイルの転送結果リスト。
            direction: 転送方向の表示文字列。
            total: 総ファイル数。
            succeeded: 成功ファイル数。
            failed: 失敗ファイル数。

        Returns:
            None
        """
        try:
            from IPython.display import HTML, display  # type: ignore[import]
        except ImportError:
            self._display_cli_summary(results, direction, total, succeeded, failed)
            return

        rows_html = ""
        for r in results:
            status_label = "✓ 成功" if r["success"] else "✗ 失敗"
            bg_color = "#d4edda" if r["success"] else "#f8d7da"
            file_label = r.get("remote", r.get("local", ""))
            error_label = r.get("error", "")
            rows_html += (
                f'<tr style="background-color:{bg_color};">'
                f"<td>{file_label}</td>"
                f"<td>{status_label}</td>"
                f"<td>{error_label}</td>"
                f"</tr>"
            )

        html = (
            f"<h3>{direction} 完了サマリー</h3>"
            f"<p>総ファイル数: <b>{total}</b> | "
            f"成功: <b>{succeeded}</b> | 失敗: <b>{failed}</b></p>"
            f'<table border="1" style="border-collapse:collapse;width:100%;">'
            f'<thead><tr style="background-color:#343a40;color:white;">'
            f"<th>ファイル</th><th>状態</th><th>エラー</th>"
            f"</tr></thead>"
            f"<tbody>{rows_html}</tbody>"
            f"</table>"
        )
        display(HTML(html))


if __name__ == "__main__":
    # このモジュールはパッケージの一部です。プロジェクトルートから実行してください:
    #   python3 main.py download --help
    #   python3 main.py upload   --help
    # Jupyter Notebook での使い方:
    #   from src.client import SCPClient
    #   client = SCPClient(host="192.168.3.61", user="sysope", password="...")
    print("使い方: python3 main.py download --help")
