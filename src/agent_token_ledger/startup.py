from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "AgentTokenLedger"
STARTUP_ARGUMENT = "--startup"


class RunRegistry(Protocol):
    """Minimal registry contract used by the startup manager."""

    def read_value(self, name: str) -> str | None:
        ...

    def write_value(self, name: str, value: str) -> None:
        ...

    def delete_value(self, name: str) -> None:
        ...


@dataclass(frozen=True, slots=True)
class StartupStatus:
    supported: bool
    enabled: bool
    error: str = ""
    command: str = ""

    def to_dict(self) -> dict[str, bool | str]:
        return {
            "supported": self.supported,
            "enabled": self.enabled,
            "error": self.error,
            "command": self.command,
        }


class WindowsRunRegistry:
    """Current-user Run key backend; no administrator rights are required."""

    def __init__(self, key_path: str = RUN_KEY_PATH):
        self.key_path = key_path

    def read_value(self, name: str) -> str | None:
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.key_path,
                0,
                winreg.KEY_READ,
            ) as key:
                value, _ = winreg.QueryValueEx(key, name)
        except FileNotFoundError:
            return None
        return str(value) if value else ""

    def write_value(self, name: str, value: str) -> None:
        import winreg

        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            self.key_path,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)

    def delete_value(self, name: str) -> None:
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.key_path,
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                winreg.DeleteValue(key, name)
        except FileNotFoundError:
            return


class StartupManager:
    """Read and update the current user's Windows startup registration."""

    def __init__(
        self,
        *,
        executable: Path | str | None = None,
        platform: str | None = None,
        frozen: bool | None = None,
        registry: RunRegistry | None = None,
    ):
        self.platform = platform or sys.platform
        self.frozen = (
            bool(getattr(sys, "frozen", False))
            if frozen is None
            else bool(frozen)
        )
        self.executable = Path(executable or sys.executable).expanduser()
        self._registry = registry

    @property
    def supported(self) -> bool:
        return self.platform == "win32" and self.frozen

    def status(self) -> StartupStatus:
        if not self.supported:
            return StartupStatus(
                supported=False,
                enabled=False,
                error=self._unavailable_reason(),
            )
        try:
            command = self._backend().read_value(RUN_VALUE_NAME) or ""
        except Exception as exc:
            logging.exception("读取 Windows 开机启动项失败")
            return StartupStatus(
                supported=True,
                enabled=False,
                error=f"读取开机启动设置失败：{type(exc).__name__}: {exc}",
            )
        return StartupStatus(
            supported=True,
            enabled=bool(command),
            command=command,
        )

    def set_enabled(self, enabled: bool) -> StartupStatus:
        current = self.status()
        if not self.supported:
            return current
        try:
            if enabled:
                self._backend().write_value(
                    RUN_VALUE_NAME,
                    self._command(),
                )
            else:
                self._backend().delete_value(RUN_VALUE_NAME)
        except Exception as exc:
            logging.exception("更新 Windows 开机启动项失败")
            return StartupStatus(
                supported=True,
                enabled=current.enabled,
                error=f"更新开机启动设置失败：{type(exc).__name__}: {exc}",
                command=current.command,
            )
        return self.status()

    def _backend(self) -> RunRegistry:
        if self._registry is not None:
            return self._registry
        if self.platform != "win32":
            raise RuntimeError("开机自动启动仅支持 Windows")
        self._registry = WindowsRunRegistry()
        return self._registry

    def _command(self) -> str:
        return subprocess.list2cmdline([str(self.executable), STARTUP_ARGUMENT])

    def _unavailable_reason(self) -> str:
        if self.platform != "win32":
            return "开机自动启动仅在 Windows 发布版中可用。"
        return "开机自动启动仅在发布版 EXE 中可用，源码运行不会修改系统启动项。"
