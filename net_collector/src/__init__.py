"""net_collector パッケージ。

Jupyter ノートブックから簡単に使えるよう、
NetCollector クラスと CollectionResult クラスを公開する。

Examples:
    >>> from src import NetCollector
    >>> nc = NetCollector()
    >>> result = nc.run(device="vmx1")
    >>> result.show()
    >>> result.diff()
"""

from __future__ import annotations

import logging
import os
import re
from typing import Dict, List, Optional

from .config import ConfigLoader, ReviewConfig
from .connector import ConnectionManager
from .executor import CommandExecutor, CommandResult
from .output import DiffDisplay, OutputDisplay, OutputSaver

logger = logging.getLogger(__name__)


def _is_jupyter() -> bool:
    """Jupyter環境で実行されているか確認する。

    Args:
        なし。

    Returns:
        Jupyter環境であれば True、そうでなければ False。
    """
    try:
        from IPython import get_ipython  # type: ignore

        shell = get_ipython()
        return shell is not None
    except ImportError:
        return False


class CollectionResult:
    """コマンド収集結果を保持し、表示・差分比較機能を提供するクラス。

    NetCollector.run() の戻り値として返される。

    Attributes:
        results: CommandResult のリスト。
        timestamp: 保存タイムスタンプ（YYYYMMDD_HHMMSS）。

    Examples:
        >>> result = nc.run(device="vmx1")
        >>> result.show()          # 結果を表示
        >>> result.diff()          # 直前の保存データと差分表示
        >>> result.diff("20260223_100000")  # 指定タイムスタンプと比較
    """

    def __init__(
        self,
        results: List[CommandResult],
        saver: OutputSaver,
        review_config: Optional[ReviewConfig],
        keyword_map: Optional[dict],
        timestamp: str,
    ) -> None:
        """初期化。

        Args:
            results: CommandResult のリスト。
            saver: OutputSaver インスタンス。
            review_config: レビュー定義設定（省略可）。
            keyword_map: {command_name: [KeywordConfig, ...]} の辞書（省略可）。
            timestamp: 保存タイムスタンプ文字列。
        """
        self.results = results
        self.timestamp = timestamp
        self._saver = saver
        self._review_config = review_config
        self._keyword_map = keyword_map or {}

    def show(self) -> None:
        """コマンド実行結果を表示する。

        Jupyter 環境ではキーワードハイライト + 確認観点付きHTML表示、
        ターミナルではテキスト表示する。

        Returns:
            None
        """
        display = OutputDisplay()
        review_map = self._build_review_map()

        if _is_jupyter():
            display.show_jupyter(self.results, self._keyword_map, review_map)
        else:
            display.show_terminal(self.results)

    def diff(self, old_timestamp: Optional[str] = None) -> None:
        """過去の保存データとの差分を表示する。

        old_timestamp を省略した場合、最新の一つ前の保存データと比較する。

        Args:
            old_timestamp: 比較対象のタイムスタンプ（省略時は自動選択）。

        Returns:
            None
        """
        if not self.results:
            print("表示する結果がありません")
            return

        device_name = self.results[0].device_name

        if old_timestamp is None:
            timestamps = self._saver.list_timestamps(device_name)
            # 現在のタイムスタンプを除外して最新を選択
            candidates = [t for t in timestamps if t != self.timestamp]
            if not candidates:
                print("比較対象の過去データがありません")
                return
            old_timestamp = candidates[-1]

        print(f"比較: {old_timestamp}  →  {self.timestamp}")

        disp = DiffDisplay()
        review_map = self._build_review_map()

        if _is_jupyter():
            disp.show_jupyter(self.results, old_timestamp, self._saver, review_map)
        else:
            disp.show_terminal(self.results, old_timestamp, self._saver)

    def _build_review_map(self) -> Dict[str, List[str]]:
        """確認観点を {command_name: [points]} 形式の辞書に変換する。

        Args:
            なし。

        Returns:
            確認観点辞書。ReviewConfig が未設定の場合は空辞書。
        """
        if not self._review_config:
            return {}
        return {
            rp.name: rp.points
            for rp in self._review_config.review_points
        }


class NetCollector:
    """ネットワーク機器コマンド収集ツールのメインクラス。

    設定ファイルを読み込み、指定した機器に接続してコマンドを実行する。
    Jupyter ノートブックと CLI の両方から使用できる。

    Attributes:
        hosts_file: 接続先設定ファイルのパス。
        commands_file: コマンド定義ファイルのパス。
        review_file: レビュー定義ファイルのパス。

    Examples:
        >>> nc = NetCollector()
        >>> result = nc.run(device="vmx1")
        >>> result.show()
    """

    def __init__(
        self,
        hosts_file: str = "configs/hosts.yaml",
        commands_file: str = "configs/commands.yaml",
        review_file: str = "configs/review_points.yaml",
    ) -> None:
        """初期化。設定ファイルを読み込む。

        Args:
            hosts_file: 接続先設定ファイル（hosts.yaml）のパス。
            commands_file: コマンド定義ファイル（commands.yaml）のパス。
            review_file: レビュー定義ファイル（review_points.yaml）のパス（省略可）。
        """
        loader = ConfigLoader()
        self.hosts_config = loader.load_hosts(hosts_file)
        self.commands_config = loader.load_commands(commands_file)
        self.review_config: Optional[ReviewConfig] = None
        if os.path.exists(review_file):
            self.review_config = loader.load_review_points(review_file)

    def run(
        self,
        device: str,
        output_dir: str = "outputs",
        confirm: bool = True,
    ) -> Optional[CollectionResult]:
        """指定した機器に接続してコマンドを実行し、結果を返す。

        Args:
            device: 実行対象の機器識別名（hosts.yaml の name フィールド）。
            output_dir: 出力保存先ディレクトリのパス。
            confirm: True の場合、実行前に Yes/No 確認を行う。

        Returns:
            CollectionResult インスタンス。キャンセルした場合は None。

        Raises:
            ValueError: 指定した機器が設定ファイルに存在しない場合。
            ConnectionError: 接続に失敗した場合。
        """
        # 機器設定を検索
        device_config = next(
            (d for d in self.hosts_config.devices if d.name == device), None
        )
        if device_config is None:
            raise ValueError(
                f"機器が見つかりません: '{device}' — "
                f"利用可能: {[d.name for d in self.hosts_config.devices]}"
            )

        # 実行確認
        if confirm:
            prompt_msg = (
                f"\n機器 [{device}] ({device_config.host}) に "
                f"{len(self._get_target_commands(device_config))} 件の"
                f"コマンドを実行しますか? [y/N]: "
            )
            answer = input(prompt_msg)
            if answer.strip().lower() not in ("y", "yes"):
                print("キャンセルしました")
                return None

        logger.info(
            f"接続開始: {device} ({device_config.host}) via "
            f"{len(self.hosts_config.bastions)} 踏み台"
        )

        manager = ConnectionManager(self.hosts_config.bastions, device_config)
        session = manager.connect()

        try:
            executor = CommandExecutor(session, device_config)
            results = executor.execute_commands(self.commands_config.commands)

            saver = OutputSaver(output_dir)
            timestamp = saver.save(results)
            logger.info(f"保存完了: {output_dir}/{device}/{timestamp}/")

            keyword_map = {
                cmd.name: cmd.keywords
                for cmd in self.commands_config.commands
                if cmd.keywords
            }

            return CollectionResult(
                results=results,
                saver=saver,
                review_config=self.review_config,
                keyword_map=keyword_map,
                timestamp=timestamp,
            )
        finally:
            manager.disconnect()

    def _get_target_commands(self, device_config) -> list:
        """指定機器で実行対象となるコマンドリストを返す。

        Args:
            device_config: 機器設定。

        Returns:
            実行対象の CommandConfig リスト。
        """
        return [
            c for c in self.commands_config.commands
            if c.vendor is None or c.vendor.lower() == device_config.vendor.lower()
        ]
