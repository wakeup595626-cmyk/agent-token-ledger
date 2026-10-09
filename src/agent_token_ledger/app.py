from __future__ import annotations

import argparse
import logging
from logging.handlers import RotatingFileHandler
import os
import shutil
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
        help="扫描工作目录；默认写入本用户数据目录",
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
    _migrate_legacy_data(data_dir)
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
    """确定本机数据目录：优先放在非系统盘的可写固定盘符上。

    读取顺序：
    1. 环境变量 AGENT_TOKEN_LEDGER_DATA_DIR（显式覆盖，供高级用户使用）。
    2. Windows 下第一个可写、非系统盘的固定盘符（DRIVE_FIXED），目录名为
       AgentTokenLedger；没有可用非系统盘时回退 LocalAppData。
    3. 非 Windows 平台沿用各系统惯例路径。
    所有路径都在运行时解析，不写死用户名或盘符。
    """
    override = os.environ.get("AGENT_TOKEN_LEDGER_DATA_DIR")
    if override and override.strip():
        return Path(override.strip()).expanduser()
    if sys.platform == "win32":
        for root in _non_system_fixed_roots():
            candidate = root / "AgentTokenLedger"
            if _ensure_writable_dir(candidate):
                return candidate
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / "AgentTokenLedger"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "AgentTokenLedger"
    if sys.platform != "win32":
        return Path.home() / ".local" / "share" / "AgentTokenLedger"
    return Path.home() / ".agent-token-ledger"


def _non_system_fixed_roots() -> list[Path]:
    """返回除系统盘外的固定盘符根目录（按盘符顺序）。

    只收 DRIVE_FIXED（本地固定磁盘），排除可移动盘、光驱、网络盘和内存盘，
    避免把数据写到随手插的 U 盘或网盘映射上。
    """
    if sys.platform != "win32":
        return []
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        bits = kernel32.GetLogicalDrives()
        if not bits:
            return []
        system_drive = (os.environ.get("SystemDrive") or "").rstrip("\\").upper()
        roots: list[Path] = []
        for index in range(26):
            if not (bits >> index) & 1:
                continue
            letter = chr(ord("A") + index)
            drive = f"{letter}:"
            try:
                drive_type = kernel32.GetDriveTypeW(f"{drive}\\")
            except Exception:
                continue
            if drive_type != 3:  # DRIVE_FIXED
                continue
            if system_drive and drive.upper() == system_drive:
                continue
            roots.append(Path(f"{drive}\\"))
        return roots
    except Exception:
        return []


def _ensure_writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-probe"
        probe.write_text("", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _local_appdata_data_dir() -> Path | None:
    local_appdata = os.environ.get("LOCALAPPDATA")
    if not local_appdata:
        return None
    return Path(local_appdata) / "AgentTokenLedger"


#: 从旧 LocalAppData 目录迁移到新数据目录时，需要保留的运行期文件。
_MIGRATABLE_FILES = (
    "settings.json",
    "cost_anchor_v1.json",
    "codex_native_cache_v1.json",
    "dsh_native_cache_v1.json",
)


def _migrate_legacy_data(data_dir: Path) -> None:
    """把旧数据目录中的设置与解析缓存复制到当前数据目录。

    只做复制、不删除旧目录：旧目录里的文件属于用户已有数据，迁移失败或用户
    想回退时仍可手动处理。目标文件已存在时跳过，避免覆盖本次运行的新写入。
    """
    legacy = _local_appdata_data_dir()
    if legacy is None:
        return
    try:
        if legacy.resolve() == data_dir.resolve():
            return
    except OSError:
        pass
    for name in _MIGRATABLE_FILES:
        source = legacy / name
        target = data_dir / name
        if not source.is_file() or target.exists():
            continue
        try:
            shutil.copy2(source, target)
            logging.info("已将旧数据目录中的 %s 复制到当前数据目录", name)
        except OSError:
            logging.warning("复制旧数据文件失败：%s", name, exc_info=True)


def _configure_logging(path: Path) -> None:
    root = logging.getLogger()
    if any(
        isinstance(handler, logging.FileHandler)
        and getattr(handler, "baseFilename", "") == str(path)
        for handler in root.handlers
    ):
        return
    handler = RotatingFileHandler(
        str(path),
        maxBytes=1_000_000,
        backupCount=2,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root.setLevel(logging.INFO)
    root.addHandler(handler)


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
