"""出力保存・差分表示モジュール。

コマンド実行結果をファイルに保存し、過去結果との差分を
ターミナル（unified diff）および Jupyter（HTML ハイライト）で表示する。
"""

from __future__ import annotations

import difflib
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .executor import CommandResult

logger = logging.getLogger(__name__)

# ターミナル出力用ANSIカラーコード
_ANSI_GREEN = "\033[32m"
_ANSI_RED = "\033[31m"
_ANSI_CYAN = "\033[36m"
_ANSI_RESET = "\033[0m"

# ファイルヘッダーのコメント行プレフィックス
_HEADER_PREFIX = "# "


class OutputSaver:
    """コマンド実行結果をファイルに保存・読み込みするクラス。

    保存先: outputs/{device_name}/{YYYYMMDD_HHMMSS}/{command_name}.txt

    Attributes:
        output_dir: 保存先ルートディレクトリの Path。

    Examples:
        >>> saver = OutputSaver("outputs")
        >>> timestamp = saver.save(results)
        >>> old_output = saver.load("vmx1", "20260224_100000", "show_version")
    """

    def __init__(self, output_dir: str = "outputs") -> None:
        """初期化。

        Args:
            output_dir: 保存先ルートディレクトリのパス。
        """
        self.output_dir = Path(output_dir)

    def save(
        self,
        results: List[CommandResult],
        timestamp: Optional[str] = None,
    ) -> str:
        """コマンド実行結果をファイルに保存する。

        Args:
            results: CommandResult のリスト。
            timestamp: タイムスタンプ文字列（省略時は現在時刻で生成）。

        Returns:
            使用したタイムスタンプ文字列（YYYYMMDD_HHMMSS 形式）。
        """
        if not timestamp:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for result in results:
            dir_path = self.output_dir / result.device_name / timestamp
            dir_path.mkdir(parents=True, exist_ok=True)

            file_path = dir_path / f"{result.command_name}.txt"
            content = self._build_file_content(result)
            file_path.write_text(content, encoding="utf-8")
            logger.debug(f"保存: {file_path}")

        return timestamp

    def load(
        self, device_name: str, timestamp: str, command_name: str
    ) -> Optional[str]:
        """保存済みコマンド出力を読み込む。

        Args:
            device_name: 機器の識別名。
            timestamp: タイムスタンプ文字列（YYYYMMDD_HHMMSS 形式）。
            command_name: コマンドの識別名。

        Returns:
            保存されたコマンド出力文字列。ファイルが存在しない場合は None。
        """
        file_path = (
            self.output_dir / device_name / timestamp / f"{command_name}.txt"
        )
        if not file_path.exists():
            return None

        content = file_path.read_text(encoding="utf-8")
        return self._strip_header(content)

    def list_timestamps(self, device_name: str) -> List[str]:
        """指定機器の保存済みタイムスタンプ一覧を返す（昇順）。

        Args:
            device_name: 機器の識別名。

        Returns:
            タイムスタンプ文字列のリスト（古い順）。
        """
        device_dir = self.output_dir / device_name
        if not device_dir.exists():
            return []
        return sorted(
            d.name for d in device_dir.iterdir() if d.is_dir()
        )

    @staticmethod
    def _build_file_content(result: CommandResult) -> str:
        """ファイル保存用テキストを生成する。

        Args:
            result: 保存する CommandResult。

        Returns:
            ヘッダーと出力を含む保存用テキスト。
        """
        header = (
            f"# Device  : {result.device_name}\n"
            f"# Command : {result.command}\n"
            f"# Executed: {result.executed_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"# {'=' * 60}\n\n"
        )
        return header + result.output + "\n"

    @staticmethod
    def _strip_header(content: str) -> str:
        """ファイルヘッダー行を除去してコマンド出力のみ返す。

        Args:
            content: ファイルの全内容。

        Returns:
            ヘッダーを除いたコマンド出力文字列。
        """
        lines = content.splitlines()
        body = [ln for ln in lines if not ln.startswith(_HEADER_PREFIX)]
        return "\n".join(body).strip()


class DiffDisplay:
    """コマンド出力の差分を表示するクラス。

    ターミナル（unified diff + ANSIカラー）と
    Jupyter（HTML ハイライト）の両方に対応する。

    Examples:
        >>> display = DiffDisplay()
        >>> display.show_terminal(results, "20260223_100000", saver)
        >>> display.show_jupyter(results, "20260223_100000", saver, review_map)
    """

    def show_terminal(
        self,
        results: List[CommandResult],
        old_timestamp: str,
        saver: OutputSaver,
    ) -> None:
        """ターミナル向けにunified diff形式で差分を表示する。

        Args:
            results: 今回の CommandResult のリスト。
            old_timestamp: 比較対象のタイムスタンプ。
            saver: OutputSaver インスタンス。

        Returns:
            None
        """
        for result in results:
            print(f"\n{'=' * 60}")
            print(f"コマンド: {result.command_name}  ({result.command})")
            print(f"{'=' * 60}")

            old_output = saver.load(
                result.device_name, old_timestamp, result.command_name
            )
            if old_output is None:
                print(f"  [情報] {old_timestamp} に保存データが見つかりません")
                continue

            diff = list(
                difflib.unified_diff(
                    old_output.splitlines(keepends=True),
                    result.output.splitlines(keepends=True),
                    fromfile=f"{old_timestamp}/{result.command_name}",
                    tofile=f"current/{result.command_name}",
                    lineterm="",
                )
            )

            if not diff:
                print("  変更なし")
            else:
                for line in diff:
                    if line.startswith("+") and not line.startswith("+++"):
                        print(f"{_ANSI_GREEN}{line}{_ANSI_RESET}")
                    elif line.startswith("-") and not line.startswith("---"):
                        print(f"{_ANSI_RED}{line}{_ANSI_RESET}")
                    elif line.startswith("@@"):
                        print(f"{_ANSI_CYAN}{line}{_ANSI_RESET}")
                    else:
                        print(line)

    def show_jupyter(
        self,
        results: List[CommandResult],
        old_timestamp: str,
        saver: OutputSaver,
        review_map: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        """Jupyter向けにHTMLハイライト付きで差分を表示する。

        追加行（緑）・削除行（赤）でハイライト表示し、
        レビュー確認観点も合わせて出力する。

        Args:
            results: 今回の CommandResult のリスト。
            old_timestamp: 比較対象のタイムスタンプ。
            saver: OutputSaver インスタンス。
            review_map: {command_name: [確認観点...]} の辞書（省略可）。

        Returns:
            None
        """
        from IPython.display import HTML, display  # type: ignore

        if review_map is None:
            review_map = {}

        for result in results:
            html_parts = [
                f"<h3 style='margin-top:1em;border-bottom:2px solid #ccc;'>"
                f"{result.command_name}"
                f" <code style='font-size:0.8em;color:#555;'>{result.command}</code>"
                f"</h3>"
            ]

            # 確認観点（コマンド出力より先に表示）
            points = review_map.get(result.command_name, [])
            if points:
                html_parts.append(
                    "<details open><summary><b>確認観点</b></summary><ul>"
                )
                for point in points:
                    html_parts.append(f"<li>{point}</li>")
                html_parts.append("</ul></details>")

            old_output = saver.load(
                result.device_name, old_timestamp, result.command_name
            )

            # コマンド結果（折りたたみ可能）
            html_parts.append("<details open><summary><b>コマンド結果</b></summary>")

            if old_output is None:
                html_parts.append(
                    f"<p style='color:gray;'>比較対象なし: {old_timestamp}</p>"
                )
            else:
                diff = list(
                    difflib.ndiff(
                        old_output.splitlines(),
                        result.output.splitlines(),
                    )
                )
                changed = any(
                    ln.startswith("+ ") or ln.startswith("- ") for ln in diff
                )

                if not changed:
                    html_parts.append(
                        "<p style='color:gray;font-style:italic;'>変更なし</p>"
                    )
                else:
                    lines_html: List[str] = []
                    for line in diff:
                        escaped = (
                            line[2:]
                            .replace("&", "&amp;")
                            .replace("<", "&lt;")
                            .replace(">", "&gt;")
                        )
                        if line.startswith("+ "):
                            lines_html.append(
                                f'<div style="background:#d4edda;color:#155724;'
                                f'padding:1px 4px;">{escaped}</div>'
                            )
                        elif line.startswith("- "):
                            lines_html.append(
                                f'<div style="background:#f8d7da;color:#721c24;'
                                f'padding:1px 4px;">{escaped}</div>'
                            )
                        elif line.startswith("  "):
                            lines_html.append(
                                f'<div style="padding:1px 4px;">{escaped}</div>'
                            )
                    html_parts.append(
                        f'<pre style="background:#f8f9fa;padding:8px;'
                        f'overflow-x:auto;font-size:0.85em;">'
                        + "\n".join(lines_html)
                        + "</pre>"
                    )

            html_parts.append("</details>")
            display(HTML("\n".join(html_parts)))


class OutputDisplay:
    """コマンド実行結果を表示するクラス。

    Jupyter（HTMLキーワードハイライト）とターミナル（テキスト）の
    両方に対応する。

    Examples:
        >>> disp = OutputDisplay()
        >>> disp.show_terminal(results)
        >>> disp.show_jupyter(results, commands_config, review_map)
    """

    # Jupyter表示で使用するキーワードカラーマッピング
    _COLOR_MAP = {
        "red":    "#dc3545",
        "green":  "#28a745",
        "blue":   "#007bff",
        "yellow": "#ffc107",
        "orange": "#fd7e14",
        "cyan":   "#17a2b8",
    }

    def show_terminal(self, results: List[CommandResult]) -> None:
        """ターミナル向けにコマンド出力を表示する。

        Args:
            results: 表示する CommandResult のリスト。

        Returns:
            None
        """
        for result in results:
            print(f"\n{'=' * 60}")
            print(f"[{result.device_name}] {result.command_name}: {result.command}")
            print(f"{'=' * 60}")
            print(result.output)

    def show_jupyter(
        self,
        results: List[CommandResult],
        keyword_map: Optional[Dict[str, list]] = None,
        review_map: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        """Jupyter向けにキーワードハイライト付きで結果を表示する。

        Args:
            results: 表示する CommandResult のリスト。
            keyword_map: {command_name: [KeywordConfig, ...]} の辞書（省略可）。
            review_map: {command_name: [確認観点...]} の辞書（省略可）。

        Returns:
            None
        """
        from IPython.display import HTML, display  # type: ignore

        if keyword_map is None:
            keyword_map = {}
        if review_map is None:
            review_map = {}

        for result in results:
            html_parts = [
                f"<h3 style='margin-top:1em;border-bottom:2px solid #ccc;'>"
                f"[{result.device_name}] {result.command_name}"
                f" <code style='font-size:0.8em;color:#555;'>"
                f"{result.command}</code></h3>"
            ]

            output_html = (
                result.output
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )

            # キーワードハイライト
            keywords = keyword_map.get(result.command_name, [])
            for kw in keywords:
                color = self._COLOR_MAP.get(kw.color.lower(), kw.color)
                pattern = re.compile(re.escape(kw.word), re.IGNORECASE)
                output_html = pattern.sub(
                    lambda m: (
                        f'<span style="color:{color};font-weight:bold;">'
                        f"{m.group()}</span>"
                    ),
                    output_html,
                )

            # 確認観点（コマンド出力より先に表示）
            points = review_map.get(result.command_name, [])
            if points:
                html_parts.append(
                    "<details open><summary><b>確認観点</b></summary><ul>"
                )
                for point in points:
                    html_parts.append(f"<li>{point}</li>")
                html_parts.append("</ul></details>")

            # コマンド結果（折りたたみ可能）
            html_parts.append(
                f'<details open><summary><b>コマンド結果</b></summary>'
                f'<pre style="background:#f8f9fa;padding:8px;'
                f'overflow-x:auto;font-size:0.85em;">{output_html}</pre>'
                f'</details>'
            )

            display(HTML("\n".join(html_parts)))


if __name__ == "__main__":
    import sys
    from datetime import datetime

    # 動作確認サンプル
    sample = CommandResult(
        command_name="show_version",
        command="show version",
        output="Junos: 21.4R1.12\nHostname: vmx1\nUptime: 1 hour",
        device_name="vmx1",
        executed_at=datetime.now(),
    )

    disp = OutputDisplay()
    disp.show_terminal([sample])

    saver = OutputSaver("outputs")
    ts = saver.save([sample])
    print(f"\n保存タイムスタンプ: {ts}")
    loaded = saver.load("vmx1", ts, "show_version")
    print(f"読み込み結果:\n{loaded}")
