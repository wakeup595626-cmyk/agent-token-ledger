from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


APP_TITLE = "本机智能体用量账本"


@dataclass(slots=True)
class WindowSession:
    mode: str
    run: Callable[[], None]
    close: Callable[[], None]


@dataclass(frozen=True, slots=True)
class WindowGeometry:
    width: int
    height: int
    x: int | None = None
    y: int | None = None


def open_window(url: str, data_dir: Path) -> WindowSession:
    """Open a native-looking application window with graceful fallbacks."""

    try:
        return _webview_session(url, data_dir)
    except Exception:
        logging.exception("原生 WebView 初始化失败，尝试 Edge 应用窗口")
    try:
        return _edge_session(url, data_dir)
    except Exception:
        logging.exception("Edge 应用窗口启动失败，回退到默认浏览器")
    return _browser_session(url)


def _webview_session(url: str, data_dir: Path) -> WindowSession:
    import webview  # type: ignore[import-not-found]

    geometry = _window_geometry()
    storage_path = Path(data_dir) / "webview"
    storage_path.mkdir(parents=True, exist_ok=True)
    window = webview.create_window(
        APP_TITLE,
        url,
        width=geometry.width,
        height=geometry.height,
        x=geometry.x,
        y=geometry.y,
        min_size=(min(980, geometry.width), min(640, geometry.height)),
        resizable=True,
        confirm_close=False,
        background_color="#eef3f4",
    )

    def close() -> None:
        try:
            window.destroy()
        except Exception:
            logging.debug("WebView 窗口已经关闭", exc_info=True)

    def run() -> None:
        webview.start(
            gui="edgechromium",
            debug=False,
            private_mode=True,
            storage_path=str(storage_path.resolve()),
        )

    return WindowSession("webview", run, close)


def _edge_session(url: str, data_dir: Path) -> WindowSession:
    if sys.platform != "win32":
        raise RuntimeError("Edge 应用窗口仅适用于 Windows")
    executable = _find_edge()
    if not executable:
        raise FileNotFoundError("未找到 Microsoft Edge")
    profile_dir = Path(data_dir) / "edge-app-profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    geometry = _window_geometry()
    flags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        flags = subprocess.CREATE_NO_WINDOW
    process = subprocess.Popen(
        [
            str(executable),
            f"--app={url}",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            f"--window-size={geometry.width},{geometry.height}",
            f"--window-position={geometry.x},{geometry.y}",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )

    def run() -> None:
        process.wait()

    def close() -> None:
        if process.poll() is None:
            process.terminate()

    return WindowSession("edge", run, close)


def _browser_session(url: str) -> WindowSession:
    opened = webbrowser.open(url, new=1, autoraise=True)
    stop_event = threading.Event()
    if not opened:
        raise RuntimeError("无法打开默认浏览器")

    def run() -> None:
        stop_event.wait()

    def close() -> None:
        stop_event.set()

    return WindowSession("browser", run, close)


def _window_geometry() -> WindowGeometry:
    """Fit and center the app inside the current Windows work area."""

    width, height = 1440, 900
    if sys.platform != "win32":
        return WindowGeometry(width, height)

    try:
        import ctypes
        from ctypes import wintypes

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        work_area = RECT()
        if not ctypes.windll.user32.SystemParametersInfoW(
            0x0030,  # SPI_GETWORKAREA
            0,
            ctypes.byref(work_area),
            0,
        ):
            return WindowGeometry(width, height)

        available_width = max(1, work_area.right - work_area.left)
        available_height = max(1, work_area.bottom - work_area.top)
        margin = 24
        width = min(width, max(640, available_width - margin * 2))
        height = min(height, max(520, available_height - margin * 2))
        x = work_area.left + max(0, (available_width - width) // 2)
        y = work_area.top + max(0, (available_height - height) // 2)
        return WindowGeometry(width, height, x, y)
    except Exception:
        logging.debug("无法读取 Windows 工作区，使用默认窗口尺寸", exc_info=True)
        return WindowGeometry(width, height)


def _find_edge() -> Path | None:
    candidates = [
        shutil.which("msedge"),
        os.environ.get("PROGRAMFILES", "")
        + r"\Microsoft\Edge\Application\msedge.exe",
        os.environ.get("PROGRAMFILES(X86)", "")
        + r"\Microsoft\Edge\Application\msedge.exe",
        os.environ.get("LOCALAPPDATA", "")
        + r"\Microsoft\Edge\Application\msedge.exe",
    ]
    for candidate in candidates:
        if candidate:
            path = Path(candidate)
            if path.is_file():
                return path
    return None
