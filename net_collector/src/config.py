"""設定ファイル読み込みモジュール。

YAML形式の接続先・コマンド・レビュー定義を読み込み、
dataclassとして返す。
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional

import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# データクラス定義
# ---------------------------------------------------------------------------

@dataclass
class BastionConfig:
    """踏み台サーバの接続設定。

    Attributes:
        name: 踏み台の識別名。
        host: ホスト名またはIPアドレス。
        port: ポート番号。
        protocol: 接続プロトコル（"ssh" または "telnet"）。
        username: ログインユーザー名。
        password: ログインパスワード。
    """

    name: str
    host: str
    port: int
    protocol: str
    username: str
    password: str


@dataclass
class DeviceConfig:
    """ネットワーク機器の接続設定。

    Attributes:
        name: 機器の識別名。
        host: ホスト名またはIPアドレス。
        port: ポート番号。
        protocol: 接続プロトコル（"ssh" または "telnet"）。
        vendor: 機器ベンダー（"cisco" / "juniper" / "generic"）。
        username: ログインユーザー名。
        password: ログインパスワード。
        enable_password: Cisco enable用パスワード（省略可）。
    """

    name: str
    host: str
    port: int
    protocol: str
    vendor: str
    username: str
    password: str
    enable_password: Optional[str] = None


@dataclass
class KeywordConfig:
    """ハイライト対象キーワードの定義。

    Attributes:
        word: ハイライトする文字列。
        color: ハイライト色名（"red" / "green" / "blue" 等）。
    """

    word: str
    color: str


@dataclass
class CommandConfig:
    """実行コマンドの定義。

    Attributes:
        name: コマンドの識別名（ファイル名にも使用）。
        command: 実行するコマンド文字列。
        vendor: 対象ベンダー（省略時は全ベンダー共通）。
        keywords: ハイライト対象キーワードリスト。
    """

    name: str
    command: str
    vendor: Optional[str] = None
    keywords: List[KeywordConfig] = field(default_factory=list)


@dataclass
class ReviewPoint:
    """レビュー確認観点の定義。

    Attributes:
        name: 対応するコマンド識別名。
        points: 確認観点のリスト。
    """

    name: str
    points: List[str] = field(default_factory=list)


@dataclass
class HostsConfig:
    """接続先設定ファイル全体。

    Attributes:
        bastions: 踏み台サーバ設定のリスト。
        devices: ネットワーク機器設定のリスト。
    """

    bastions: List[BastionConfig]
    devices: List[DeviceConfig]


@dataclass
class CommandsConfig:
    """コマンド定義ファイル全体。

    Attributes:
        commands: コマンド定義のリスト。
    """

    commands: List[CommandConfig]


@dataclass
class ReviewConfig:
    """レビュー定義ファイル全体。

    Attributes:
        review_points: レビュー確認観点のリスト。
    """

    review_points: List[ReviewPoint]


# ---------------------------------------------------------------------------
# ローダークラス
# ---------------------------------------------------------------------------

class ConfigLoader:
    """YAMLファイルから各種設定を読み込むクラス。

    Examples:
        >>> loader = ConfigLoader()
        >>> hosts = loader.load_hosts("configs/hosts.yaml")
        >>> hosts.bastions[0].name
        'bastion-1'
    """

    def load_hosts(self, filepath: str) -> HostsConfig:
        """接続先設定ファイルを読み込む。

        Args:
            filepath: hosts.yaml のパス。

        Returns:
            HostsConfig オブジェクト。

        Raises:
            FileNotFoundError: ファイルが存在しない場合。
            yaml.YAMLError: YAMLパースエラーの場合。
        """
        logger.debug(f"接続先設定読み込み: {filepath}")
        data = self._load_yaml(filepath)

        bastions = [
            BastionConfig(
                name=b["name"],
                host=b["host"],
                port=int(b.get("port", 22)),
                protocol=b.get("protocol", "ssh").lower(),
                username=b["username"],
                password=str(b["password"]),
            )
            for b in data.get("bastions", [])
        ]

        devices = [
            DeviceConfig(
                name=d["name"],
                host=d["host"],
                port=int(d.get("port", 22)),
                protocol=d.get("protocol", "ssh").lower(),
                vendor=d.get("vendor", "generic").lower(),
                username=d["username"],
                password=str(d["password"]),
                enable_password=str(d["enable_password"]) if d.get("enable_password") else None,
            )
            for d in data.get("devices", [])
        ]

        return HostsConfig(bastions=bastions, devices=devices)

    def load_commands(self, filepath: str) -> CommandsConfig:
        """コマンド定義ファイルを読み込む。

        Args:
            filepath: commands.yaml のパス。

        Returns:
            CommandsConfig オブジェクト。

        Raises:
            FileNotFoundError: ファイルが存在しない場合。
            yaml.YAMLError: YAMLパースエラーの場合。
        """
        logger.debug(f"コマンド定義読み込み: {filepath}")
        data = self._load_yaml(filepath)

        commands = []
        for c in data.get("commands", []):
            keywords = [
                KeywordConfig(word=str(k["word"]), color=str(k["color"]))
                for k in c.get("keywords", [])
            ]
            commands.append(
                CommandConfig(
                    name=c["name"],
                    command=c["command"],
                    vendor=c.get("vendor", None),
                    keywords=keywords,
                )
            )

        return CommandsConfig(commands=commands)

    def load_review_points(self, filepath: str) -> ReviewConfig:
        """レビュー定義ファイルを読み込む。

        Args:
            filepath: review_points.yaml のパス。

        Returns:
            ReviewConfig オブジェクト。

        Raises:
            FileNotFoundError: ファイルが存在しない場合。
            yaml.YAMLError: YAMLパースエラーの場合。
        """
        logger.debug(f"レビュー定義読み込み: {filepath}")
        data = self._load_yaml(filepath)

        points = [
            ReviewPoint(
                name=rp["name"],
                points=list(rp.get("points", [])),
            )
            for rp in data.get("review_points", [])
        ]

        return ReviewConfig(review_points=points)

    @staticmethod
    def _load_yaml(filepath: str) -> dict:
        """YAMLファイルを読み込んで辞書を返す。

        Args:
            filepath: YAMLファイルのパス。

        Returns:
            パースされた辞書。

        Raises:
            FileNotFoundError: ファイルが存在しない場合。
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"設定ファイルが見つかりません: {filepath}")
        with open(filepath, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.DEBUG)
    loader = ConfigLoader()

    hosts = loader.load_hosts("configs/hosts.yaml")
    print("=== bastions ===")
    for b in hosts.bastions:
        print(f"  {b.name}: {b.protocol}://{b.host}:{b.port}")

    print("=== devices ===")
    for d in hosts.devices:
        print(f"  {d.name}: {d.vendor} {d.protocol}://{d.host}:{d.port}")

    cmds = loader.load_commands("configs/commands.yaml")
    print("=== commands ===")
    for c in cmds.commands:
        print(f"  [{c.vendor or 'all'}] {c.name}: {c.command}")
