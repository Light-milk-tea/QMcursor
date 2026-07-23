"""Read, apply, back up, and restore Windows cursor schemes."""

from __future__ import annotations

import ctypes
import json
import os
import winreg
from pathlib import Path
from typing import Any, Iterable

from arkcursor.models.theme import CURSOR_ROLES, CursorTheme

ACTIVE_CURSORS_KEY = r"Control Panel\Cursors"
USER_SCHEMES_KEY = rf"{ACTIVE_CURSORS_KEY}\Schemes"
SYSTEM_SCHEMES_KEY = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Control Panel\Cursors\Schemes"
)
SPI_SETCURSORS = 0x0057
MANAGED_VALUE_NAMES = ("", *CURSOR_ROLES, "Scheme Source")


class CursorServiceError(RuntimeError):
    """A user-facing cursor operation error."""


class CursorService:
    def __init__(self, data_dir: Path | None = None) -> None:
        local_app_data = os.environ.get("LOCALAPPDATA")
        default_dir = (
            Path(local_app_data) / "ArkCursor"
            if local_app_data
            else Path.home() / "AppData" / "Local" / "ArkCursor"
        )
        self.data_dir = Path(data_dir) if data_dir else default_dir
        self.backup_path = self.data_dir / "backup.json"
        self.state_path = self.data_dir / "state.json"

    @staticmethod
    def expand_cursor_path(path: str) -> str:
        value = path.strip().strip('"')
        return os.path.normpath(os.path.expandvars(value)) if value else ""

    def list_themes(self) -> list[CursorTheme]:
        """Enumerate user and system cursor schemes available on this PC."""
        themes: dict[str, CursorTheme] = {}
        locations = (
            (winreg.HKEY_LOCAL_MACHINE, SYSTEM_SCHEMES_KEY, 2),
            (winreg.HKEY_CURRENT_USER, USER_SCHEMES_KEY, 1),
        )

        for hive, key_path, source in locations:
            for name, value in self._enum_string_values(hive, key_path):
                try:
                    theme = CursorTheme.from_scheme_value(
                        name,
                        value,
                        source,
                        expand_path=self.expand_cursor_path,
                    )
                except (TypeError, ValueError):
                    continue
                if not theme.missing_files():
                    themes[name.casefold()] = theme

        if not themes:
            current = self.current_theme()
            themes[current.name.casefold()] = current

        return sorted(themes.values(), key=lambda item: item.name.casefold())

    def current_theme(self) -> CursorTheme:
        snapshot = self._read_managed_values()
        name = str(snapshot.get("", {}).get("value") or "当前方案")
        source = int(snapshot.get("Scheme Source", {}).get("value") or 1)
        cursors = {
            role: self.expand_cursor_path(
                str(snapshot.get(role, {}).get("value") or "")
            )
            for role in CURSOR_ROLES
        }
        return CursorTheme(name=name, cursors=cursors, source=source)

    def apply_theme(self, theme: CursorTheme, *, remember: bool = True) -> None:
        missing = theme.missing_files()
        if missing:
            names = "\n".join(str(path) for path in missing[:5])
            raise CursorServiceError(f"以下指针文件不存在：\n{names}")

        self.ensure_initial_backup()
        before = self._read_managed_values()

        try:
            with winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER,
                ACTIVE_CURSORS_KEY,
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, theme.name)
                winreg.SetValueEx(
                    key, "Scheme Source", 0, winreg.REG_DWORD, theme.source
                )
                for role in CURSOR_ROLES:
                    path = theme.cursors[role]
                    value_type = (
                        winreg.REG_EXPAND_SZ if "%" in path else winreg.REG_SZ
                    )
                    winreg.SetValueEx(key, role, 0, value_type, path)

            self._reload_system_cursors()
        except Exception as exc:
            try:
                self._restore_managed_values(before)
                self._reload_system_cursors()
            except Exception:
                pass
            raise CursorServiceError(f"应用鼠标指针失败：{exc}") from exc

        if remember:
            self.save_selected_theme(theme)

    def ensure_initial_backup(self) -> None:
        if self.backup_path.exists():
            return
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(
            self.backup_path,
            {"version": 1, "values": self._read_managed_values()},
        )

    def restore_initial_backup(self) -> None:
        if not self.backup_path.exists():
            raise CursorServiceError("尚未创建原始指针备份。")

        try:
            payload = self._read_json(self.backup_path)
            values = payload["values"]
            if not isinstance(values, dict):
                raise ValueError("备份 values 格式无效")
            self._restore_managed_values(values)
            self._reload_system_cursors()
            self.clear_selected_theme()
        except CursorServiceError:
            raise
        except Exception as exc:
            raise CursorServiceError(f"恢复鼠标指针失败：{exc}") from exc

    def save_selected_theme(self, theme: CursorTheme) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(
            self.state_path,
            {"version": 1, "selected_theme": theme.to_dict()},
        )

    def load_selected_theme(self) -> CursorTheme | None:
        if not self.state_path.exists():
            return None
        try:
            payload = self._read_json(self.state_path)
            return CursorTheme.from_dict(payload["selected_theme"])
        except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError):
            return None

    def clear_selected_theme(self) -> None:
        try:
            self.state_path.unlink()
        except FileNotFoundError:
            pass

    @staticmethod
    def _enum_string_values(
        hive: int, key_path: str
    ) -> Iterable[tuple[str, str]]:
        try:
            with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ) as key:
                index = 0
                while True:
                    try:
                        name, value, value_type = winreg.EnumValue(key, index)
                    except OSError:
                        break
                    index += 1
                    if value_type in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
                        yield name, str(value)
        except FileNotFoundError:
            return

    @staticmethod
    def _read_managed_values() -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            ACTIVE_CURSORS_KEY,
            0,
            winreg.KEY_QUERY_VALUE,
        ) as key:
            for name in MANAGED_VALUE_NAMES:
                try:
                    value, value_type = winreg.QueryValueEx(key, name)
                except FileNotFoundError:
                    continue
                result[name] = {"value": value, "type": value_type}
        return result

    @staticmethod
    def _restore_managed_values(values: dict[str, dict[str, Any]]) -> None:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            ACTIVE_CURSORS_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            for name in MANAGED_VALUE_NAMES:
                item = values.get(name)
                if item is None:
                    try:
                        winreg.DeleteValue(key, name)
                    except FileNotFoundError:
                        pass
                    continue
                winreg.SetValueEx(
                    key,
                    name,
                    0,
                    int(item["type"]),
                    item["value"],
                )

    @staticmethod
    def _reload_system_cursors() -> None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        function = user32.SystemParametersInfoW
        function.argtypes = [
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_void_p,
            ctypes.c_uint,
        ]
        function.restype = ctypes.c_bool

        if not function(SPI_SETCURSORS, 0, None, 0):
            error = ctypes.get_last_error()
            raise ctypes.WinError(error)

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        temporary = path.with_suffix(f"{path.suffix}.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON 根节点必须是对象。")
        return payload
