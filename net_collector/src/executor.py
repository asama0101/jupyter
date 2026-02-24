"""コマンド実行モジュール。

DeviceSession を通じてネットワーク機器にコマンドを送信し、
結果を CommandResult として返す。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from .config import CommandConfig, DeviceConfig
from .connector import DeviceSession

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    """コマンド実行結果を保持するデータクラス。

    Attributes:
        command_name: コマンドの識別名（ファイル名にも使用）。
        command: 実行したコマンド文字列。
        output: コマンド出力（クリーン済み）。
        device_name: 実行した機器の識別名。
        executed_at: 実行日時。
        error: エラーメッセージ（正常終了時は None）。
    """

    command_name: str
    command: str
    output: str
    device_name: str
    executed_at: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None


class CommandExecutor:
    """接続済みセッションでコマンドを順次実行するクラス。

    ベンダーフィルタを適用し、対象外コマンドをスキップする。
    エラー発生時は即座に例外を発生させ、後続コマンドの実行を中止する。

    Attributes:
        _session: 接続済みの DeviceSession インスタンス。
        device: 接続先機器の設定。

    Examples:
        >>> executor = CommandExecutor(session, device_config)
        >>> results = executor.execute_commands(commands)
        >>> for r in results:
        ...     print(r.command_name, len(r.output))
    """

    def __init__(self, session: DeviceSession, device: DeviceConfig) -> None:
        """初期化。

        Args:
            session: 接続済みの DeviceSession インスタンス。
            device: 接続先機器の設定。
        """
        self._session = session
        self.device = device

    def execute_commands(
        self, commands: List[CommandConfig], timeout: float = 60.0
    ) -> List[CommandResult]:
        """コマンドリストを順次実行して結果リストを返す。

        vendor フィールドが設定されているコマンドは、機器の vendor と
        一致する場合のみ実行する。実行前に対象コマンドを確定し、
        ログに [N/M] 形式の進捗を付加することで逐次実行であることを明示する。

        Args:
            commands: 実行するコマンド定義のリスト。
            timeout: コマンドごとのタイムアウト（秒）。

        Returns:
            CommandResult のリスト（スキップされたコマンドは含まない）。

        Raises:
            TimeoutError: コマンド実行がタイムアウトした場合。
            ConnectionError: 接続が切断された場合。
        """
        # ベンダーフィルタを事前適用して実行対象を確定する
        targets = [c for c in commands if self._should_execute(c)]
        skipped = [c for c in commands if not self._should_execute(c)]

        for cmd in skipped:
            logger.debug(
                f"スキップ: {cmd.name} "
                f"(vendor={cmd.vendor}, 機器vendor={self.device.vendor})"
            )

        total = len(targets)
        results: List[CommandResult] = []

        for idx, cmd_config in enumerate(targets, start=1):
            result = self._execute_one(cmd_config, timeout, idx, total)
            results.append(result)

        return results

    def _should_execute(self, cmd: CommandConfig) -> bool:
        """コマンドをこの機器で実行すべきか判定する。

        Args:
            cmd: 対象のコマンド定義。

        Returns:
            実行すべき場合は True、スキップする場合は False。
        """
        if cmd.vendor is None:
            return True
        return cmd.vendor.lower() == self.device.vendor.lower()

    def _execute_one(
        self,
        cmd: CommandConfig,
        timeout: float,
        idx: int,
        total: int,
    ) -> CommandResult:
        """コマンドを1件実行して CommandResult を返す。

        Args:
            cmd: 実行するコマンド定義。
            timeout: タイムアウト（秒）。
            idx: 実行中のコマンドの順番（1始まり）。
            total: 実行対象コマンドの総件数。

        Returns:
            実行結果の CommandResult。

        Raises:
            TimeoutError: タイムアウトした場合。
            ConnectionError: 接続エラーが発生した場合。
        """
        logger.info(
            f"[{self.device.name}] コマンド実行 [{idx}/{total}]: {cmd.command}"
        )
        output = self._session.send_command(cmd.command, timeout=timeout)
        logger.debug(
            f"[{self.device.name}] 完了: {cmd.name} ({len(output)} 文字)"
        )
        return CommandResult(
            command_name=cmd.name,
            command=cmd.command,
            output=output,
            device_name=self.device.name,
        )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 動作確認サンプル（実際の接続情報に変更して使用）
    from .config import BastionConfig, CommandConfig, DeviceConfig
    from .connector import ConnectionManager

    bastions = [
        BastionConfig(
            name="bastion-1",
            host="192.168.3.23",
            port=23,
            protocol="telnet",
            username="sysope",
            password="P!ssw0rd1234",
        )
    ]
    device = DeviceConfig(
        name="vmx1",
        host="172.20.20.2",
        port=22,
        protocol="ssh",
        vendor="juniper",
        username="admin",
        password="admin@123",
    )
    commands = [
        CommandConfig(name="show_version", command="show version", vendor="juniper"),
    ]

    manager = ConnectionManager(bastions, device)
    session = manager.connect()
    try:
        executor = CommandExecutor(session, device)
        results = executor.execute_commands(commands)
        for r in results:
            print(f"=== {r.command_name} ===")
            print(r.output)
    finally:
        manager.disconnect()
