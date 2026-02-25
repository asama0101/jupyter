"""SHA-256 チェックサム計算・検証モジュール。"""

import hashlib
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CHUNK_SIZE = 8192
SHA256_COMMAND = 'sha256sum "{path}"'


def calculate_local_sha256(file_path: Path) -> str:
    """ローカルファイルの SHA-256 ハッシュを計算する。

    Args:
        file_path: ハッシュを計算するファイルのパス。

    Returns:
        SHA-256 ハッシュの 16 進数文字列（64 文字）。

    Raises:
        FileNotFoundError: 指定されたファイルが存在しない場合。
        IOError: ファイルの読み込みに失敗した場合。

    Examples:
        >>> hash_value = calculate_local_sha256(Path("data.csv"))
        >>> len(hash_value)
        64
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def calculate_remote_sha256(connection: Any, remote_path: str) -> str:
    """リモートサーバー上のファイルの SHA-256 ハッシュを計算する。

    ssh_conn の send_command を使用してリモートで sha256sum を実行する。

    Args:
        connection: netmiko の ConnectHandler インスタンス。
        remote_path: ハッシュを計算するリモートファイルの絶対パス。

    Returns:
        SHA-256 ハッシュの 16 進数文字列（64 文字）。

    Raises:
        ValueError: sha256sum コマンドの出力が予期しない形式の場合。
        RuntimeError: リモートコマンドの実行に失敗した場合。

    Examples:
        >>> hash_value = calculate_remote_sha256(conn, "/data/file.csv")
        >>> len(hash_value)
        64
    """
    command = SHA256_COMMAND.format(path=remote_path)
    output = connection.send_command(command, read_timeout=120)
    parts = output.strip().split()
    if not parts or len(parts) < 2:
        raise ValueError(f"sha256sum の出力が予期しない形式です: {output!r}")
    return parts[0]


def verify_checksum(local_hash: str, remote_hash: str) -> bool:
    """ローカルとリモートのチェックサムを比較する。

    Args:
        local_hash: ローカルファイルの SHA-256 ハッシュ。
        remote_hash: リモートファイルの SHA-256 ハッシュ。

    Returns:
        チェックサムが一致する場合は True、不一致の場合は False。

    Examples:
        >>> verify_checksum("abc123", "abc123")
        True
        >>> verify_checksum("abc123", "def456")
        False
    """
    return local_hash.lower() == remote_hash.lower()


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    # ローカルファイルのチェックサム計算サンプル
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
        if target.exists():
            h = calculate_local_sha256(target)
            print(f"SHA-256: {h}")
        else:
            print(f"ファイルが存在しません: {target}")
    else:
        # 一時ファイルを使ったサンプル
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
            tmp.write(b"hello world\n")
            tmp_path = Path(tmp.name)

        h = calculate_local_sha256(tmp_path)
        print(f"SHA-256 (hello world): {h}")
        tmp_path.unlink()
