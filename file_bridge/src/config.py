"""設定ファイルの読み込みとプロファイル管理モジュール。"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)

DEFAULT_PORT = 22
DEFAULT_LOG_FILE = "transfer.log"
DEFAULT_CONFIG_FILE = "config.yaml"
DEFAULT_REMOTE_BASE = "~/"
DEFAULT_LOCAL_BASE = "./"


@dataclass
class ServerProfile:
    """サーバー接続プロファイルを表すデータクラス。

    Attributes:
        name: プロファイル名。
        host: 接続先ホスト名または IP アドレス。
        port: SSH ポート番号。
        user: SSH ユーザー名。
        password: SSH パスワード（設定ファイルから読み込んだ場合のみ設定される）。
        remote_base: リモートのデフォルトディレクトリ。
        local_base: ローカルのデフォルトディレクトリ。
        log: ログファイルパス。
        checksum: チェックサム検証の有効フラグ。
    """

    name: str
    host: str
    port: int = DEFAULT_PORT
    user: str = ""
    password: Optional[str] = None
    remote_base: str = DEFAULT_REMOTE_BASE
    local_base: str = DEFAULT_LOCAL_BASE
    log: str = DEFAULT_LOG_FILE
    checksum: bool = True


@dataclass
class TransferConfig:
    """転送実行時の全設定をまとめたデータクラス。

    Attributes:
        host: 接続先ホスト名または IP アドレス。
        port: SSH ポート番号。
        user: SSH ユーザー名。
        password: SSH パスワード。
        remote_path: リモートパス（ワイルドカード可）。
        local_path: ローカルパス（ワイルドカード可）。
        log_file: ログファイルパス。
        checksum: チェックサム検証の有効フラグ。
    """

    host: str
    port: int
    user: str
    password: str
    remote_path: str
    local_path: str
    log_file: str
    checksum: bool


class ConfigLoader:
    """設定ファイルの読み込みとプロファイル管理クラス。

    YAML 形式の設定ファイルを読み込み、プロファイルを管理する。

    Attributes:
        config_path: 設定ファイルのパス。
        _profiles: プロファイル名と ServerProfile のマッピング。
        _default_profile: デフォルトプロファイル名。

    Examples:
        >>> loader = ConfigLoader("config.yaml")
        >>> profile = loader.get_profile("production")
        >>> profile.host
        'prod.example.com'
    """

    def __init__(self, config_path: str = DEFAULT_CONFIG_FILE) -> None:
        """ConfigLoader を初期化し、設定ファイルを読み込む。

        Args:
            config_path: 設定ファイルのパス（デフォルト: 'config.yaml'）。

        Raises:
            FileNotFoundError: 設定ファイルが存在しない場合。
            yaml.YAMLError: YAML の解析に失敗した場合。
        """
        self.config_path = Path(config_path)
        self._profiles: dict[str, ServerProfile] = {}
        self._default_profile: str = ""
        self._load()

    def _load(self) -> None:
        """設定ファイルを読み込み、プロファイルを解析する。

        Returns:
            None

        Raises:
            FileNotFoundError: 設定ファイルが存在しない場合。
            yaml.YAMLError: YAML の解析に失敗した場合。
        """
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"設定ファイルが見つかりません: {self.config_path}\n"
                f"config.yaml.example を参考に {self.config_path} を作成してください。"
            )

        with open(self.config_path, "r", encoding="utf-8") as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}

        self._default_profile = raw.get("default_profile", "")
        profiles_data: dict[str, Any] = raw.get("profiles", {})

        for name, data in profiles_data.items():
            self._profiles[name] = ServerProfile(
                name=name,
                host=data.get("host", ""),
                port=int(data.get("port", DEFAULT_PORT)),
                user=data.get("user", ""),
                password=data.get("password", None),
                remote_base=data.get("remote_base", DEFAULT_REMOTE_BASE),
                local_base=data.get("local_base", DEFAULT_LOCAL_BASE),
                log=data.get("log", DEFAULT_LOG_FILE),
                checksum=bool(data.get("checksum", True)),
            )

        logger.info(
            "設定ファイルを読み込みました: %s (%d プロファイル)",
            self.config_path,
            len(self._profiles),
        )

    def get_profile(self, profile_name: Optional[str] = None) -> ServerProfile:
        """指定されたプロファイルを取得する。

        Args:
            profile_name: プロファイル名。None の場合はデフォルトプロファイルを使用。

        Returns:
            対応する ServerProfile インスタンス。

        Raises:
            ValueError: プロファイル名が指定されておらず、デフォルトも未設定の場合。
            KeyError: 指定されたプロファイルが存在しない場合。
        """
        name = profile_name or self._default_profile
        if not name:
            raise ValueError(
                "プロファイルが指定されていません。"
                " --profile オプションか config.yaml の default_profile を設定してください。"
            )

        if name not in self._profiles:
            available = ", ".join(self._profiles.keys())
            raise KeyError(
                f"プロファイル '{name}' が見つかりません。利用可能なプロファイル: {available}"
            )

        return self._profiles[name]

    @property
    def available_profiles(self) -> list[str]:
        """利用可能なプロファイル名の一覧を返す。

        Returns:
            プロファイル名のリスト。
        """
        return list(self._profiles.keys())

    @property
    def default_profile(self) -> str:
        """デフォルトプロファイル名を返す。

        Returns:
            デフォルトプロファイル名。未設定の場合は空文字列。
        """
        return self._default_profile


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    config_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CONFIG_FILE
    try:
        loader = ConfigLoader(config_path)
        print(f"デフォルトプロファイル: {loader.default_profile}")
        print(f"利用可能なプロファイル: {loader.available_profiles}")
        profile = loader.get_profile()
        print(f"\n[{profile.name}]")
        print(f"  host: {profile.host}:{profile.port}")
        print(f"  user: {profile.user}")
        print(f"  remote_base: {profile.remote_base}")
        print(f"  local_base: {profile.local_base}")
        print(f"  checksum: {profile.checksum}")
    except (FileNotFoundError, KeyError, ValueError) as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)
