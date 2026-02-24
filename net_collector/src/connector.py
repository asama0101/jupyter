"""接続管理モジュール。

踏み台サーバ経由でネットワーク機器に接続するための
Telnet（ソケットベース）・SSH（Paramiko）チェーン接続を実装する。

接続フロー:
    ローカル → 踏み台1（telnet or SSH）→ … → ネットワーク機器

Telnet踏み台の場合はソケットを使い、踏み台上でSSH/telnetコマンドを
対話的に実行して次のホップへ繋ぐ。
SSH踏み台のみの場合はParamikoのdirect-tcpipチャネルで転送する。
"""

from __future__ import annotations

import logging
import re
import socket
import time
from abc import ABC, abstractmethod
from typing import List, Optional

import paramiko

from .config import BastionConfig, DeviceConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

# Telnet IAC 関連
_IAC = 0xFF
_DONT = 0xFE
_DO = 0xFD
_WONT = 0xFC
_WILL = 0xFB
_SB = 0xFA   # subnegotiation begin
_SE = 0xF0   # subnegotiation end

_READ_CHUNK = 4096
_DEFAULT_TIMEOUT: float = 30.0
_STABLE_WAIT: float = 0.3   # 出力が安定したと見なすまでの無受信時間（秒）
_SHORT_WAIT: float = 0.1    # 追加データ待ちのソケットタイムアウト（秒）

# ベンダーごとのプロンプトパターン（MULTILINE モードで使用）
VENDOR_PROMPT = {
    "juniper": r"[a-zA-Z0-9._@-]+[>#%]\s*$",
    "cisco":   r"[a-zA-Z0-9._@-]+[>#]\s*$",
    "generic": r"[$#>%]\s*$",
}

# 踏み台Linuxシェル用プロンプトパターン
_SHELL_PROMPT = r"[$#>%]\s*$"

# ページャーパターン
_PAGER_PATTERN = r"--[-(]more[)-]-+|<more>|\(END\)"

# ANSI エスケープシーケンス除去パターン
_ANSI_ESC = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x07]*\x07")

# ページャー無効化コマンド（ベンダー別）
DISABLE_PAGER_CMD = {
    "juniper": "set cli screen-length 0",
    "cisco":   "terminal length 0",
    "generic": None,
}


# ---------------------------------------------------------------------------
# TelnetSocket: ソケットベースの最小限 Telnet 実装
# ---------------------------------------------------------------------------

class TelnetSocket:
    """ソケットを使ったシンプルなTelnetクライアント。

    telnetlibを使わず socket モジュールのみで IAC ネゴシエーションを
    処理し、テキストの送受信を行う。

    Attributes:
        host: 接続先ホスト。
        port: 接続先ポート番号。
        timeout: デフォルトタイムアウト（秒）。

    Examples:
        >>> ts = TelnetSocket("192.168.0.1", 23)
        >>> ts.open()
        >>> ts.read_until([r"login:"], timeout=10)
        >>> ts.write("admin")
        >>> ts.close()
    """

    def __init__(self, host: str, port: int = 23, timeout: float = _DEFAULT_TIMEOUT) -> None:
        """初期化。

        Args:
            host: 接続先ホスト名またはIPアドレス。
            port: 接続先ポート番号。
            timeout: デフォルトタイムアウト（秒）。
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock: Optional[socket.socket] = None
        self._buffer = b""

    def open(self) -> None:
        """Telnet接続を開始する。

        Returns:
            None

        Raises:
            ConnectionRefusedError: 接続が拒否された場合。
            socket.timeout: タイムアウトした場合。
        """
        self._sock = socket.create_connection(
            (self.host, self.port), timeout=self.timeout
        )
        logger.debug(f"Telnet接続確立: {self.host}:{self.port}")

    def close(self) -> None:
        """接続を閉じる。

        Returns:
            None
        """
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
            logger.debug(f"Telnet切断: {self.host}:{self.port}")

    def write(self, text: str) -> None:
        """文字列を送信する（末尾に CRLF を付加）。

        Args:
            text: 送信する文字列。

        Returns:
            None

        Raises:
            RuntimeError: ソケットが接続されていない場合。
        """
        if not self._sock:
            raise RuntimeError("ソケットが接続されていません")
        payload = text.encode("utf-8") + b"\r\n"
        self._sock.sendall(payload)
        logger.debug(f"送信: {repr(text)}")

    def read_until(
        self, patterns: List[str], timeout: float = _DEFAULT_TIMEOUT
    ) -> str:
        """指定パターンのいずれかにマッチするまでデータを読み込む。

        パターンにマッチした後、_STABLE_WAIT 秒間データが来なければ
        確定して返す（途中のプロンプトとの誤マッチを防ぐため）。

        Args:
            patterns: 検索する正規表現パターンのリスト。
            timeout: タイムアウト（秒）。

        Returns:
            受信したテキスト全体（ANSIエスケープ除去済み、\r 正規化済み）。

        Raises:
            TimeoutError: タイムアウトした場合。
            ConnectionError: 接続が切断された場合。
        """
        compiled = [
            re.compile(p, re.IGNORECASE | re.MULTILINE) for p in patterns
        ]
        deadline = time.monotonic() + timeout

        while True:
            text = self._decode_buffer()

            # パターンマッチ確認
            if any(pat.search(text) for pat in compiled):
                # 出力が安定するまで追加データを待つ
                stable_end = time.monotonic() + _STABLE_WAIT
                while time.monotonic() < stable_end:
                    assert self._sock is not None
                    self._sock.settimeout(_SHORT_WAIT)
                    try:
                        chunk = self._sock.recv(_READ_CHUNK)
                        if chunk:
                            self._buffer += self._process_iac(chunk)
                            stable_end = time.monotonic() + _STABLE_WAIT
                    except socket.timeout:
                        pass
                result = self._decode_buffer()
                self._buffer = b""
                logger.debug(f"パターン検出 ({self.host}), 末尾: {result[-100:]!r}")
                return result

            # タイムアウト確認
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"タイムアウト ({timeout}s) [{self.host}]. "
                    f"バッファ末尾: {text[-200:]!r}"
                )

            # 追加データ受信
            assert self._sock is not None
            self._sock.settimeout(min(remaining, 1.0))
            try:
                chunk = self._sock.recv(_READ_CHUNK)
                if not chunk:
                    raise ConnectionError(
                        f"接続が切断されました: {self.host}:{self.port}"
                    )
                self._buffer += self._process_iac(chunk)
            except socket.timeout:
                pass

    def _decode_buffer(self) -> str:
        """バッファをデコードして正規化した文字列を返す。

        Args:
            なし。

        Returns:
            UTF-8デコード済み・ANSI除去済み・改行正規化済みの文字列。
        """
        text = self._buffer.decode("utf-8", errors="replace")
        text = _ANSI_ESC.sub("", text)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        return text

    def _process_iac(self, data: bytes) -> bytes:
        """Telnet IACシーケンスを処理し、クリーンなデータを返す。

        WILL に対して DONT を、DO に対して WONT を送信することで
        全オプションを拒否する最小限のネゴシエーションを行う。

        Args:
            data: ソケットから受信した生バイト列。

        Returns:
            IACシーケンスを除去したバイト列。
        """
        result = bytearray()
        i = 0
        while i < len(data):
            b = data[i]
            if b == _IAC:
                if i + 1 >= len(data):
                    i += 1
                    continue
                cmd = data[i + 1]
                if cmd in (_WILL, _WONT, _DO, _DONT) and i + 2 < len(data):
                    opt = data[i + 2]
                    if cmd == _DO:
                        assert self._sock is not None
                        self._sock.sendall(bytes([_IAC, _WONT, opt]))
                    elif cmd == _WILL:
                        assert self._sock is not None
                        self._sock.sendall(bytes([_IAC, _DONT, opt]))
                    i += 3
                elif cmd == _SB:
                    # サブネゴシエーション: IAC SE まで読み飛ばす
                    end = data.find(bytes([_IAC, _SE]), i + 2)
                    i = (end + 2) if end != -1 else len(data)
                elif cmd == _IAC:
                    result.append(_IAC)
                    i += 2
                else:
                    i += 2
            else:
                result.append(b)
                i += 1
        return bytes(result)


# ---------------------------------------------------------------------------
# DeviceSession: 機器接続セッションの抽象基底クラス
# ---------------------------------------------------------------------------

class DeviceSession(ABC):
    """機器接続セッションの抽象基底クラス。

    NetmikoベースとSocketベースの両実装に共通するインターフェースを定義する。

    Attributes:
        device: 接続中の機器設定。
    """

    def __init__(self, device: DeviceConfig) -> None:
        """初期化。

        Args:
            device: 接続する機器の設定。
        """
        self.device = device

    @abstractmethod
    def send_command(self, command: str, timeout: float = 60.0) -> str:
        """コマンドを送信して結果を返す。

        Args:
            command: 実行するコマンド文字列。
            timeout: タイムアウト（秒）。

        Returns:
            コマンド出力（コマンドエコーとプロンプトを除去済み）。

        Raises:
            TimeoutError: タイムアウトした場合。
        """

    @abstractmethod
    def disconnect(self) -> None:
        """接続を切断する。

        Returns:
            None
        """


# ---------------------------------------------------------------------------
# InteractiveSession: ソケット経由の対話型セッション
# ---------------------------------------------------------------------------

class InteractiveSession(DeviceSession):
    """TelnetSocketを通じた対話型デバイスセッション。

    踏み台サーバのシェルから SSH/Telnet を発行して次ホップへ接続し、
    最終的にネットワーク機器のCLIを操作する。

    Attributes:
        device: 接続中の機器設定。

    Examples:
        >>> ts = TelnetSocket("192.168.0.1", 23)
        >>> ts.open()
        >>> session = InteractiveSession(ts, device_config)
        >>> session.login_shell("user", "pass")
        >>> session.ssh_to("10.0.0.1", 22, "admin", "pass")
        >>> output = session.send_command("show version")
    """

    def __init__(self, telnet: TelnetSocket, device: DeviceConfig) -> None:
        """初期化。

        Args:
            telnet: オープン済みの TelnetSocket インスタンス。
            device: 最終接続先の機器設定。
        """
        super().__init__(device)
        self._telnet = telnet
        self._prompt_pattern = VENDOR_PROMPT.get(
            device.vendor.lower(), VENDOR_PROMPT["generic"]
        )

    def login_shell(self, username: str, password: str) -> None:
        """Telnet接続先のシェルにログインする。

        login: / username: プロンプトにユーザー名を入力し、
        Password: プロンプトにパスワードを入力する。

        Args:
            username: ログインユーザー名。
            password: ログインパスワード。

        Returns:
            None

        Raises:
            TimeoutError: ログインプロンプトが現れない場合。
        """
        output = self._telnet.read_until(
            [r"[Ll]ogin\s*:", r"[Uu]sername\s*:", r"[Pp]assword\s*:", _SHELL_PROMPT],
            timeout=20,
        )
        # パスワードプロンプトパターン（英語・日本語両対応）
        _PASS_PATTERN = r"[Pp]assword\s*:|パスワード\s*:"

        if re.search(r"[Ll]ogin\s*:|[Uu]sername\s*:", output, re.IGNORECASE):
            logger.debug("ユーザー名プロンプト検出")
            self._telnet.write(username)
            output = self._telnet.read_until([_PASS_PATTERN], timeout=15)

        logger.debug("パスワードプロンプト検出")
        self._telnet.write(password)

        self._telnet.read_until([_SHELL_PROMPT], timeout=20)
        logger.debug(f"シェルログイン完了: {self._telnet.host}")

    def ssh_to(
        self, host: str, port: int, username: str, password: str
    ) -> None:
        """現在のシェルからSSHで次のホストに接続する。

        Args:
            host: 接続先ホスト名またはIPアドレス。
            port: SSHポート番号。
            username: SSHユーザー名。
            password: SSHパスワード。

        Returns:
            None

        Raises:
            ConnectionError: SSH接続に失敗した場合。
            TimeoutError: タイムアウトした場合。
        """
        cmd = (
            f"ssh -o StrictHostKeyChecking=no "
            f"-o UserKnownHostsFile=/dev/null "
            f"-o ConnectTimeout=10"
        )
        if port != 22:
            cmd += f" -p {port}"
        cmd += f" {username}@{host}"

        logger.debug(f"SSHホップ開始: {username}@{host}:{port}")
        self._telnet.write(cmd)

        output = self._telnet.read_until(
            [
                r"[Pp]assword\s*:",
                r"yes/no",
                r"continue connecting",
                r"[Cc]onnection refused",
                r"[Nn]o route to host",
                r"[Nn]ame or service not known",
            ],
            timeout=30,
        )

        if re.search(r"[Cc]onnection refused|[Nn]o route to host|not known",
                     output, re.IGNORECASE):
            raise ConnectionError(
                f"SSH接続失敗: {host}:{port} — {output[-200:]}"
            )

        if re.search(r"yes/no|continue connecting", output, re.IGNORECASE):
            self._telnet.write("yes")
            output = self._telnet.read_until([r"[Pp]assword\s*:"], timeout=15)

        self._telnet.write(password)

        # 機器プロンプトが現れるまで待機
        self._telnet.read_until([self._prompt_pattern], timeout=40)
        logger.debug(f"SSH接続完了: {host}")

    def telnet_to(
        self, host: str, port: int, username: str, password: str
    ) -> None:
        """現在のシェルからtelnetで次のホストに接続する。

        Args:
            host: 接続先ホスト名またはIPアドレス。
            port: Telnetポート番号。
            username: ログインユーザー名。
            password: ログインパスワード。

        Returns:
            None

        Raises:
            ConnectionError: Telnet接続に失敗した場合。
            TimeoutError: タイムアウトした場合。
        """
        cmd = f"telnet {host} {port}"
        logger.debug(f"Telnetホップ開始: {host}:{port}")
        self._telnet.write(cmd)

        output = self._telnet.read_until(
            [
                r"[Ll]ogin\s*:",
                r"[Uu]sername\s*:",
                r"[Pp]assword\s*:",
                r"[Cc]onnection refused",
            ],
            timeout=20,
        )

        if re.search(r"[Cc]onnection refused", output, re.IGNORECASE):
            raise ConnectionError(f"Telnet接続失敗: {host}:{port}")

        if re.search(r"[Ll]ogin\s*:|[Uu]sername\s*:", output, re.IGNORECASE):
            self._telnet.write(username)
            output = self._telnet.read_until([r"[Pp]assword\s*:"], timeout=10)

        self._telnet.write(password)
        self._telnet.read_until([self._prompt_pattern], timeout=20)
        logger.debug(f"Telnet接続完了: {host}")

    def setup_device(self) -> None:
        """機器接続後の初期設定を行う。

        ページャー無効化と（Ciscoの場合）enableモード昇格を実施する。

        Returns:
            None
        """
        disable_cmd = DISABLE_PAGER_CMD.get(self.device.vendor.lower())
        if disable_cmd:
            logger.debug(f"ページャー無効化: {disable_cmd}")
            self._telnet.write(disable_cmd)
            self._telnet.read_until([self._prompt_pattern], timeout=15)

        if self.device.vendor.lower() == "cisco" and self.device.enable_password:
            self._enable_cisco()

    def _enable_cisco(self) -> None:
        """Cisco機器でenableモードに昇格する。

        Returns:
            None

        Raises:
            TimeoutError: プロンプトが現れない場合。
        """
        self._telnet.write("enable")
        self._telnet.read_until([r"[Pp]assword\s*:"], timeout=10)
        assert self.device.enable_password is not None
        self._telnet.write(self.device.enable_password)
        self._telnet.read_until([r"#\s*$"], timeout=10)
        logger.debug("Cisco enableモード昇格完了")

    def send_command(self, command: str, timeout: float = 60.0) -> str:
        """コマンドを送信して出力を返す。

        ページャープロンプトが現れた場合はスペースを送信して継続する。

        Args:
            command: 実行するコマンド文字列。
            timeout: タイムアウト（秒）。

        Returns:
            コマンド出力（コマンドエコーとプロンプトを除去済み）。

        Raises:
            TimeoutError: タイムアウトした場合。
        """
        self._telnet.write(command)
        raw_parts: List[str] = []

        while True:
            chunk = self._telnet.read_until(
                [self._prompt_pattern, _PAGER_PATTERN],
                timeout=timeout,
            )
            if re.search(_PAGER_PATTERN, chunk, re.IGNORECASE):
                # ページャー: スペースで次ページ
                raw_parts.append(re.sub(_PAGER_PATTERN, "", chunk, flags=re.IGNORECASE))
                self._telnet.write(" ")
                continue
            raw_parts.append(chunk)
            break

        raw = "".join(raw_parts)
        return self._clean_output(command, raw)

    def disconnect(self) -> None:
        """接続を切断する。

        Returns:
            None
        """
        self._telnet.close()

    def _clean_output(self, command: str, raw: str) -> str:
        """コマンドエコーと末尾プロンプトを除去してクリーンな出力を返す。

        Args:
            command: 実行したコマンド（エコー検出に使用）。
            raw: read_until から得た生テキスト。

        Returns:
            コマンドエコーと末尾プロンプトを除いた出力文字列。
        """
        lines = raw.splitlines()

        # コマンドエコー（最初の非空行にコマンドが含まれる場合）を除去
        start = 0
        while start < len(lines) and not lines[start].strip():
            start += 1
        if start < len(lines) and command.strip() in lines[start]:
            start += 1

        # 末尾プロンプト行を除去
        end = len(lines)
        while end > start and re.search(
            self._prompt_pattern, lines[end - 1].strip(), re.IGNORECASE
        ):
            end -= 1

        return "\n".join(lines[start:end]).strip()


# ---------------------------------------------------------------------------
# NetmikoSession: Paramiko ProxyJump + Netmiko セッション（全SSH用）
# ---------------------------------------------------------------------------

class NetmikoSession(DeviceSession):
    """ParamikoのProxyJump + Netmikoを使ったデバイスセッション。

    全ホップがSSHの場合に使用する。Paramikoのdirect-tcpipチャネルで
    踏み台をチェーンし、最終的にNetmikoのConnectHandlerに渡す。

    Attributes:
        device: 接続中の機器設定。

    Examples:
        >>> session = NetmikoSession._build(bastions, device_config)
        >>> output = session.send_command("show version")
        >>> session.disconnect()
    """

    _VENDOR_TO_NETMIKO = {
        "cisco":   "cisco_ios",
        "juniper": "juniper_junos",
        "generic": "generic",
    }

    def __init__(
        self,
        netmiko_conn,
        paramiko_clients: List[paramiko.SSHClient],
        device: DeviceConfig,
    ) -> None:
        """初期化。

        Args:
            netmiko_conn: Netmiko の BaseConnection インスタンス。
            paramiko_clients: 作成した Paramiko SSHClient のリスト（切断時にクローズ）。
            device: 接続した機器の設定。
        """
        super().__init__(device)
        self._conn = netmiko_conn
        self._clients = paramiko_clients

    @classmethod
    def build(
        cls, bastions: List[BastionConfig], device: DeviceConfig
    ) -> "NetmikoSession":
        """SSH踏み台チェーンを構築してセッションを返す。

        Args:
            bastions: SSH踏み台設定のリスト（順番に経由する）。
            device: 最終接続先の機器設定。

        Returns:
            構築済みの NetmikoSession インスタンス。

        Raises:
            paramiko.AuthenticationException: 認証失敗の場合。
            socket.error: ネットワーク接続エラーの場合。
        """
        from netmiko import ConnectHandler  # type: ignore

        clients: List[paramiko.SSHClient] = []
        sock: Optional[paramiko.Channel] = None

        for i, bastion in enumerate(bastions):
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            kwargs: dict = {
                "hostname":     bastion.host,
                "port":         bastion.port,
                "username":     bastion.username,
                "password":     bastion.password,
                "look_for_keys": False,
                "allow_agent":  False,
            }
            if sock:
                kwargs["sock"] = sock
            client.connect(**kwargs)
            clients.append(client)
            logger.debug(f"SSH踏み台接続完了: {bastion.name} ({bastion.host})")

            # 次ホップへのチャネルを開く
            if i + 1 < len(bastions):
                next_host, next_port = bastions[i + 1].host, bastions[i + 1].port
            else:
                next_host, next_port = device.host, device.port

            transport = client.get_transport()
            assert transport is not None
            sock = transport.open_channel(
                "direct-tcpip", (next_host, next_port), ("", 0)
            )

        # Netmiko で機器に接続
        base_type = cls._VENDOR_TO_NETMIKO.get(device.vendor.lower(), "generic")
        device_type = (
            f"{base_type}_telnet"
            if device.protocol.lower() == "telnet"
            else base_type
        )

        connect_params: dict = {
            "device_type": device_type,
            "host":        device.host,
            "port":        device.port,
            "username":    device.username,
            "password":    device.password,
        }
        if sock:
            connect_params["sock"] = sock
        if device.enable_password:
            connect_params["secret"] = device.enable_password

        conn = ConnectHandler(**connect_params)
        if device.enable_password:
            conn.enable()
        logger.debug(f"機器接続完了: {device.name} ({device.host})")

        return cls(conn, clients, device)

    def send_command(self, command: str, timeout: float = 60.0) -> str:
        """Netmikoのsend_commandでコマンドを実行する。

        Args:
            command: 実行するコマンド文字列。
            timeout: タイムアウト（秒）。

        Returns:
            コマンド出力文字列。
        """
        return self._conn.send_command(command, read_timeout=timeout)

    def disconnect(self) -> None:
        """Netmiko接続とParamikoクライアントを切断する。

        Returns:
            None
        """
        try:
            self._conn.disconnect()
        except Exception as exc:
            logger.debug(f"Netmiko切断エラー（無視）: {exc}")

        for client in reversed(self._clients):
            try:
                client.close()
            except Exception as exc:
                logger.debug(f"Paramikoクライアント切断エラー（無視）: {exc}")

        logger.debug(f"機器切断完了: {self.device.name}")


# ---------------------------------------------------------------------------
# ConnectionManager: 接続方式を選択して DeviceSession を返す
# ---------------------------------------------------------------------------

class ConnectionManager:
    """接続チェーン全体を管理し、適切な DeviceSession を構築するクラス。

    踏み台の構成（SSH のみ / Telnet 含む）を判断し、
    適切な接続方式（Netmiko または InteractiveSession）を選択する。

    Attributes:
        bastions: 踏み台サーバ設定のリスト。
        device: 接続先機器の設定。

    Examples:
        >>> manager = ConnectionManager(bastions, device_config)
        >>> session = manager.connect()
        >>> output = session.send_command("show version")
        >>> manager.disconnect()
    """

    def __init__(
        self, bastions: List[BastionConfig], device: DeviceConfig
    ) -> None:
        """初期化。

        Args:
            bastions: 踏み台サーバ設定のリスト。
            device: 接続先機器の設定。
        """
        self.bastions = bastions
        self.device = device
        self._session: Optional[DeviceSession] = None

    def connect(self) -> DeviceSession:
        """接続を確立して DeviceSession を返す。

        踏み台にTelnetが含まれる場合は InteractiveSession を使用し、
        全SSHの場合は NetmikoSession を使用する。

        Returns:
            確立済みの DeviceSession インスタンス。

        Raises:
            ConnectionError: 接続に失敗した場合。
            TimeoutError: タイムアウトした場合。
        """
        telnet_idx = self._find_first_telnet_idx()

        if telnet_idx == -1:
            # 全SSH: Paramiko ProxyJump + Netmiko
            logger.debug("接続方式: 全SSH (NetmikoSession)")
            self._session = NetmikoSession.build(self.bastions, self.device)
        else:
            # Telnet踏み台あり: ソケットベース対話セッション
            logger.debug("接続方式: Telnet踏み台あり (InteractiveSession)")
            self._session = self._connect_with_telnet(telnet_idx)

        return self._session

    def disconnect(self) -> None:
        """接続を切断する。

        Returns:
            None
        """
        if self._session:
            self._session.disconnect()
            self._session = None

    def _find_first_telnet_idx(self) -> int:
        """最初のTelnetホップのインデックスを返す。見つからない場合は -1。

        Args:
            なし。

        Returns:
            最初のTelnet踏み台のインデックス。全SSHなら -1。
        """
        for i, b in enumerate(self.bastions):
            if b.protocol.lower() == "telnet":
                return i
        return -1

    def _connect_with_telnet(self, telnet_idx: int) -> InteractiveSession:
        """Telnetが含まれる接続チェーンを構築する。

        Args:
            telnet_idx: 最初のTelnet踏み台のインデックス。

        Returns:
            確立済みの InteractiveSession インスタンス。

        Raises:
            NotImplementedError: SSH→Telnet混在（SSH後にTelnet）の場合。
        """
        if telnet_idx > 0:
            raise NotImplementedError(
                "SSH踏み台の後にTelnet踏み台が続く構成は未対応です。"
            )

        # 最初の踏み台がTelnet
        first_bastion = self.bastions[0]
        telnet = TelnetSocket(first_bastion.host, first_bastion.port)
        telnet.open()

        session = InteractiveSession(telnet, self.device)
        session.login_shell(first_bastion.username, first_bastion.password)

        # 残りの踏み台を順番にホップ
        for hop in self.bastions[1:]:
            if hop.protocol.lower() == "ssh":
                session.ssh_to(hop.host, hop.port, hop.username, hop.password)
            else:
                session.telnet_to(hop.host, hop.port, hop.username, hop.password)

        # 最終機器へ接続
        if self.device.protocol.lower() == "ssh":
            session.ssh_to(
                self.device.host,
                self.device.port,
                self.device.username,
                self.device.password,
            )
        else:
            session.telnet_to(
                self.device.host,
                self.device.port,
                self.device.username,
                self.device.password,
            )

        session.setup_device()
        return session


if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 簡易動作確認用（実際の接続情報に変更して使用）
    from .config import BastionConfig, DeviceConfig
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
    manager = ConnectionManager(bastions, device)
    session = manager.connect()
    print(session.send_command("show version"))
    manager.disconnect()
