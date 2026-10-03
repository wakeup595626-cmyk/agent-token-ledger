from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

if __package__:
    from .webapp import DEFAULT_PORT, DEFAULT_REFRESH_SECONDS, run_webapp
else:
    # PyInstaller executes this file as a top-level entry point.
    from agent_token_ledger.webapp import (
        DEFAULT_PORT,
        DEFAULT_REFRESH_SECONDS,
        run_webapp,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="AgentTokenLedger",
        description="本机智能体令牌用量浏览器看板",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="扫描工作目录；默认写入本用户 LocalAppData",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="监听地址，默认只允许本机回环",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"首选端口，默认 {DEFAULT_PORT}",
    )
    parser.add_argument(
        "--refresh-seconds",
        type=int,
        default=DEFAULT_REFRESH_SECONDS,
        help=f"自动重扫间隔，默认 {DEFAULT_REFRESH_SECONDS} 秒",
    )
    parser.add_argument(
        "--skip-gateway",
        action="store_true",
        help="不扫描实时增长的 Cockpit 网关请求日志",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="只启动本机服务，不打开应用窗口或浏览器",
    )
    parser.add_argument(
        "--browser",
        action="store_true",
        help="使用默认浏览器打开页面，而不是应用窗口",
    )
    parser.add_argument(
        "--startup",
        action="store_true",
        help="由 Windows 开机启动项调用",
    )
    args = parser.parse_args(argv)

    data_dir = (args.work_dir or _default_data_dir()).expanduser()
    data_dir.mkdir(parents=True, exist_ok=True)
    _configure_logging(data_dir / "agent-token-ledger.log")
    if args.startup:
        logging.info("Agent Token Ledger launched from the Windows startup entry")
    try:
        return run_webapp(
            work_dir=data_dir,
            host=args.host,
            port=args.port,
            refresh_seconds=args.refresh_seconds,
            skip_gateway=args.skip_gateway,
            open_browser=args.browser,
            open_window=not args.no_browser and not args.browser,
        )
    except Exception as exc:
        logging.exception("本机智能体用量账本启动失败")
        _show_error(f"本机智能体用量账本启动失败：\n{type(exc).__name__}: {exc}")
        return 2


def _default_data_dir() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / "AgentTokenLedger"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "AgentTokenLedger"
    if sys.platform != "win32":
        return Path.home() / ".local" / "share" / "AgentTokenLedger"
    return Path.home() / ".agent-token-ledger"


def _configure_logging(path: Path) -> None:
    logging.basicConfig(
        filename=str(path),
        level=logging.INFO,
        encoding="utf-8",
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _show_error(message: str) -> None:
    if sys.platform != "win32":
        print(message, file=sys.stderr)
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "本机智能体用量账本", 0x10)
    except Exception:
        print(message, file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
