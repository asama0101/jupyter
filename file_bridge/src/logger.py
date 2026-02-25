"""転送ログの管理モジュール。"""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_module_logger = logging.getLogger(__name__)

LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_LOG_FILE = "transfer.log"
FIELD_SEP = " | "

SIZE_KB = 1024
SIZE_MB = 1024 ** 2
SIZE_GB = 1024 ** 3


@dataclass
class TransferRecord:
    """転送ログの 1 レコードを表すデータクラス。

    Attributes:
        timestamp: 転送日時。
        direction: 転送方向（'UPLOAD' または 'DOWNLOAD'）。
        source_path: 転送元パス。
        dest_path: 転送先パス。
        file_size: ファイルサイズ（バイト）。
        success: 転送成功フラグ。
        checksum_result: チェックサム結果またはエラーメッセージ。
    """

    timestamp: datetime
    direction: str
    source_path: str
    dest_path: str
    file_size: int
    success: bool
    checksum_result: str = ""

    def to_log_line(self) -> str:
        """ログファイル用のパイプ区切り文字列に変換する。

        Returns:
            パイプ区切りのログ行文字列。

        Examples:
            >>> record = TransferRecord(
            ...     timestamp=datetime(2024, 1, 15, 12, 34, 56),
            ...     direction="DOWNLOAD",
            ...     source_path="/remote/data.csv",
            ...     dest_path="./local/data.csv",
            ...     file_size=2411724,
            ...     success=True,
            ...     checksum_result="SHA256: abc123...",
            ... )
            >>> "DOWNLOAD" in record.to_log_line()
            True
        """
        timestamp_str = self.timestamp.strftime(LOG_DATE_FORMAT)
        size_str = _format_file_size(self.file_size)
        result_str = "SUCCESS" if self.success else "FAILED "
        parts = [
            timestamp_str,
            self.direction.ljust(8),
            f"{self.source_path} -> {self.dest_path}",
            size_str,
            result_str,
            self.checksum_result,
        ]
        return FIELD_SEP.join(parts)


def _format_file_size(size_bytes: int) -> str:
    """ファイルサイズを人間が読みやすい形式に変換する。

    Args:
        size_bytes: バイト単位のファイルサイズ。

    Returns:
        フォーマットされたサイズ文字列（例: '2.3MB'、'512KB'）。

    Examples:
        >>> _format_file_size(512)
        '512B'
        >>> _format_file_size(1536)
        '1.5KB'
    """
    if size_bytes < SIZE_KB:
        return f"{size_bytes}B"
    elif size_bytes < SIZE_MB:
        return f"{size_bytes / SIZE_KB:.1f}KB"
    elif size_bytes < SIZE_GB:
        return f"{size_bytes / SIZE_MB:.1f}MB"
    else:
        return f"{size_bytes / SIZE_GB:.1f}GB"


class TransferLogger:
    """転送ログの管理クラス。

    ファイル転送の記録をログファイルと標準ロガーの両方に出力する。

    Attributes:
        log_file: ログファイルのパス。
        _file_logger: ファイル出力専用のロガー。

    Examples:
        >>> tl = TransferLogger("./transfer.log")
        >>> record = TransferRecord(
        ...     timestamp=datetime.now(),
        ...     direction="UPLOAD",
        ...     source_path="./file.csv",
        ...     dest_path="/remote/file.csv",
        ...     file_size=1024,
        ...     success=True,
        ... )
        >>> tl.log_transfer(record)
    """

    def __init__(self, log_file: str = DEFAULT_LOG_FILE) -> None:
        """TransferLogger を初期化する。

        Args:
            log_file: ログファイルのパス。ディレクトリが存在しない場合は自動作成する。
        """
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # ロガー名にパスを含めて複数インスタンスの競合を防ぐ
        logger_name = f"transfer_file.{id(self)}"
        self._file_logger = logging.getLogger(logger_name)
        self._file_logger.setLevel(logging.INFO)
        self._file_logger.propagate = False

        if not self._file_logger.handlers:
            handler = logging.FileHandler(self.log_file, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._file_logger.addHandler(handler)

    def log_transfer(self, record: TransferRecord) -> None:
        """転送レコードをログファイルに記録する。

        Args:
            record: 記録する TransferRecord インスタンス。

        Returns:
            None
        """
        log_line = record.to_log_line()
        self._file_logger.info(log_line)
        _module_logger.debug("転送ログ記録: %s", log_line)

    def close(self) -> None:
        """ログファイルハンドラを閉じる。

        Returns:
            None
        """
        for handler in self._file_logger.handlers[:]:
            handler.close()
            self._file_logger.removeHandler(handler)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    tl = TransferLogger("./transfer.log")
    record = TransferRecord(
        timestamp=datetime.now(),
        direction="DOWNLOAD",
        source_path="/remote/data.csv",
        dest_path="./downloads/data.csv",
        file_size=2411724,
        success=True,
        checksum_result="SHA256: abc123def456...",
    )
    tl.log_transfer(record)
    print(f"ログを書き込みました: {tl.log_file}")
    print(f"ログ内容: {record.to_log_line()}")
