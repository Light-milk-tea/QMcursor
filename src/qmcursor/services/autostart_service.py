"""Manage per-user Windows startup registration."""

from __future__ import annotations

import os
import subprocess
import sys
import winreg
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_VALUE_NAME = "QMcursor"


class AutostartService:
    def is_enabled(self) -> bool:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                RUN_KEY,
                0,
                winreg.KEY_QUERY_VALUE,
            ) as key:
                winreg.QueryValueEx(key, APP_VALUE_NAME)
                return True
        except FileNotFoundError:
            return False

    def set_enabled(self, enabled: bool) -> None:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            if enabled:
                winreg.SetValueEx(
                    key,
                    APP_VALUE_NAME,
                    0,
                    winreg.REG_SZ,
                    self.startup_command(),
                )
            else:
                try:
                    winreg.DeleteValue(key, APP_VALUE_NAME)
                except FileNotFoundError:
                    pass

    @staticmethod
    def startup_command() -> str:
        if getattr(sys, "frozen", False):
            executable = Path(sys.executable).resolve()
            return subprocess.list2cmdline([str(executable), "--startup"])

        python = Path(sys.executable).resolve()
        pythonw = python.with_name("pythonw.exe")
        if pythonw.exists():
            python = pythonw

        project_root = Path(__file__).resolve().parents[3]
        launcher = project_root / "run.py"
        return subprocess.list2cmdline(
            [str(python), str(launcher), "--startup"]
        )

    @staticmethod
    def is_windows() -> bool:
        return os.name == "nt"
