"""Read, apply, back up, and restore Windows cursor schemes."""

from __future__ import annotations

import ctypes
import json
import os
import re
import shutil
import struct
import tempfile
import winreg
import zipfile
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any, Iterable

from arkcursor.models.theme import CURSOR_ROLES, CursorTheme

ACTIVE_CURSORS_KEY = r"Control Panel\Cursors"
USER_SCHEMES_KEY = rf"{ACTIVE_CURSORS_KEY}\Schemes"
SYSTEM_SCHEMES_KEY = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Control Panel\Cursors\Schemes"
)
BUNDLED_THEMES_DIR = Path(__file__).resolve().parents[1] / "themes"
SPI_SETCURSORS = 0x0057
SPI_SETCURSORBASESIZE = 0x2029
SPIF_UPDATEINIFILE = 0x01
CURSOR_SIZE_VALUE = "CursorBaseSize"
CURSOR_SIZE_MIN = 32
CURSOR_SIZE_MAX = 256
CURSOR_SIZE_STEP = 8
MANAGED_VALUE_NAMES = ("", *CURSOR_ROLES, "Scheme Source", CURSOR_SIZE_VALUE)
MAX_ANI_IMPORT_BYTES = 64 * 1024 * 1024
ANI_ROLE_STEMS = {
    "normal": "Arrow",
    "arrow": "Arrow",
    "help": "Help",
    "working": "AppStarting",
    "appstarting": "AppStarting",
    "app_starting": "AppStarting",
    "busy": "Wait",
    "wait": "Wait",
    "precision": "Crosshair",
    "crosshair": "Crosshair",
    "text": "IBeam",
    "ibeam": "IBeam",
    "handwriting": "NWPen",
    "nwpen": "NWPen",
    "pen": "NWPen",
    "unavailable": "No",
    "no": "No",
    "vertical": "SizeNS",
    "sizens": "SizeNS",
    "size_ns": "SizeNS",
    "horizontal": "SizeWE",
    "sizewe": "SizeWE",
    "size_we": "SizeWE",
    "diagonal1": "SizeNWSE",
    "sizenwse": "SizeNWSE",
    "size_nwse": "SizeNWSE",
    "diagonal2": "SizeNESW",
    "sizenesw": "SizeNESW",
    "size_nesw": "SizeNESW",
    "move": "SizeAll",
    "sizeall": "SizeAll",
    "size_all": "SizeAll",
    "alternate": "UpArrow",
    "uparrow": "UpArrow",
    "up_arrow": "UpArrow",
    "link": "Hand",
    "hand": "Hand",
}
ROLE_OUTPUT_NAMES = {
    "Arrow": "arrow.ani",
    "Help": "help.ani",
    "AppStarting": "app_starting.ani",
    "Wait": "wait.ani",
    "Crosshair": "crosshair.ani",
    "IBeam": "ibeam.ani",
    "NWPen": "pen.ani",
    "No": "no.ani",
    "SizeNS": "size_ns.ani",
    "SizeWE": "size_we.ani",
    "SizeNWSE": "size_nwse.ani",
    "SizeNESW": "size_nesw.ani",
    "SizeAll": "size_all.ani",
    "UpArrow": "up_arrow.ani",
    "Hand": "hand.ani",
}


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
        self.imported_themes_dir = self.data_dir / "imported"

    @staticmethod
    def expand_cursor_path(path: str) -> str:
        value = path.strip().strip('"')
        return os.path.normpath(os.path.expandvars(value)) if value else ""

    def list_themes(self) -> list[CursorTheme]:
        """Enumerate Windows schemes and themes bundled with ArkCursor."""
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

        for theme in self.list_bundled_themes():
            themes[theme.name.casefold()] = theme
        for theme in self.list_imported_themes():
            themes[theme.name.casefold()] = theme

        if not themes:
            current = self.current_theme()
            themes[current.name.casefold()] = current

        return sorted(themes.values(), key=lambda item: item.name.casefold())

    @staticmethod
    def list_bundled_themes(
        themes_dir: Path = BUNDLED_THEMES_DIR,
    ) -> list[CursorTheme]:
        """Load valid theme manifests shipped inside the application."""
        return CursorService._list_manifest_themes(themes_dir)

    def list_imported_themes(self) -> list[CursorTheme]:
        """Load valid themes previously imported into the user data directory."""
        return self._list_manifest_themes(self.imported_themes_dir)

    @staticmethod
    def _list_manifest_themes(themes_dir: Path) -> list[CursorTheme]:
        themes: list[CursorTheme] = []
        if not themes_dir.is_dir():
            return themes

        for manifest in sorted(themes_dir.glob("*/theme.json")):
            try:
                payload = json.loads(manifest.read_text(encoding="utf-8"))
                cursor_values = payload["cursors"]
                if not isinstance(cursor_values, dict):
                    continue
                cursors = {
                    str(role): CursorService._resolve_manifest_path(
                        manifest.parent, str(path)
                    )
                    for role, path in cursor_values.items()
                    if path
                }
                raw_sizes = payload.get("sizes")
                sizes = None
                if isinstance(raw_sizes, dict):
                    sizes = {
                        int(size): {
                            str(role): CursorService._resolve_manifest_path(
                                manifest.parent, str(path)
                            )
                            for role, path in values.items()
                            if path
                        }
                        for size, values in raw_sizes.items()
                        if isinstance(values, dict)
                    }
                theme = CursorTheme(
                    name=str(payload["name"]),
                    cursors=cursors,
                    source=int(payload.get("source", 1)),
                    is_custom=True,
                    kind=str(payload.get("kind", "cur")),
                    sizes=sizes,
                    frame_interval_ms=payload.get("frame_interval_ms"),
                )
            except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError):
                continue
            checked_sizes: Iterable[int | None] = (
                theme.sizes if theme.sizes else (None,)
            )
            if all(not theme.missing_files(size) for size in checked_sizes):
                themes.append(theme)
        return themes

    @staticmethod
    def _resolve_manifest_path(theme_dir: Path, value: str) -> str:
        path = Path(value)
        return str(path.resolve() if path.is_absolute() else (theme_dir / path).resolve())

    def import_ani_pack(self, source: Path | str) -> CursorTheme:
        """Import a directory or ZIP containing conventionally named ANI files."""
        source_path = Path(source)
        if not source_path.exists():
            raise CursorServiceError(f"导入来源不存在：{source_path}")

        try:
            files = self._read_ani_pack_files(source_path)
            inf_bytes = next(
                (data for name, data in files.items() if name.casefold().endswith(".inf")),
                None,
            )
            display_name = self._theme_name_from_inf(inf_bytes) or source_path.stem
            display_name = display_name.strip() or "导入的动画指针"
            display_name = self._available_import_name(display_name)

            role_data: dict[str, bytes] = {}
            for name, data in files.items():
                if not name.casefold().endswith(".ani"):
                    continue
                role = ANI_ROLE_STEMS.get(Path(name).stem.casefold())
                if role is None:
                    continue
                if role in role_data:
                    raise CursorServiceError(f"导入包中角色文件重复：{role}")
                if not self._is_valid_ani(data):
                    raise CursorServiceError(f"不是有效的 ANI 文件：{name}")
                role_data[role] = data

            if not role_data:
                raise CursorServiceError(
                    "未找到可识别的 ANI 文件。请使用 Normal/Busy 等标准文件名。"
                )

            self.imported_themes_dir.mkdir(parents=True, exist_ok=True)
            folder_name = self._available_import_folder(display_name)
            target = self.imported_themes_dir / folder_name
            temporary = Path(
                tempfile.mkdtemp(prefix=f".{folder_name}-", dir=self.imported_themes_dir)
            )
            try:
                cursor_values: dict[str, str] = {}
                for role, data in role_data.items():
                    output_name = ROLE_OUTPUT_NAMES[role]
                    (temporary / output_name).write_bytes(data)
                    cursor_values[role] = output_name
                manifest = {
                    "name": display_name,
                    "source": 1,
                    "is_custom": True,
                    "kind": "ani",
                    "cursors": cursor_values,
                }
                (temporary / "theme.json").write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                temporary.replace(target)
            except Exception:
                shutil.rmtree(temporary, ignore_errors=True)
                raise
        except CursorServiceError:
            raise
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            raise CursorServiceError(f"导入 ANI 包失败：{exc}") from exc

        return CursorTheme(
            name=display_name,
            cursors={
                role: str((target / ROLE_OUTPUT_NAMES[role]).resolve())
                for role in role_data
            },
            source=1,
            is_custom=True,
            kind="ani",
        )

    @staticmethod
    def _is_valid_ani(data: bytes) -> bool:
        if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"ACON":
            return False
        riff_end = struct.unpack_from("<I", data, 4)[0] + 8
        if riff_end > len(data):
            return False

        has_header = False
        has_frame = False
        offset = 12
        while offset + 8 <= riff_end:
            chunk_id = data[offset : offset + 4]
            chunk_size = struct.unpack_from("<I", data, offset + 4)[0]
            chunk_start = offset + 8
            chunk_end = chunk_start + chunk_size
            if chunk_end > riff_end:
                return False
            if chunk_id == b"anih" and chunk_size >= 36:
                has_header = True
            elif (
                chunk_id == b"LIST"
                and chunk_size >= 4
                and data[chunk_start : chunk_start + 4] == b"fram"
            ):
                nested = chunk_start + 4
                while nested + 8 <= chunk_end:
                    nested_id = data[nested : nested + 4]
                    nested_size = struct.unpack_from("<I", data, nested + 4)[0]
                    nested_end = nested + 8 + nested_size
                    if nested_end > chunk_end:
                        return False
                    if nested_id == b"icon" and nested_size >= 6:
                        has_frame = True
                    nested = nested_end + (nested_size % 2)
            offset = chunk_end + (chunk_size % 2)
        return has_header and has_frame

    @staticmethod
    def _read_ani_pack_files(source: Path) -> dict[str, bytes]:
        files: dict[str, bytes] = {}
        total_size = 0
        if source.is_dir():
            candidates = [
                path
                for path in source.rglob("*")
                if path.is_file() and path.suffix.casefold() in {".ani", ".inf"}
            ]
            for path in candidates:
                size = path.stat().st_size
                total_size += size
                if total_size > MAX_ANI_IMPORT_BYTES:
                    raise CursorServiceError("ANI 导入包过大（上限 64 MB）。")
                relative_name = path.relative_to(source).as_posix()
                if relative_name in files:
                    raise CursorServiceError(f"导入包中存在重复文件：{relative_name}")
                files[relative_name] = path.read_bytes()
            return files

        if source.suffix.casefold() != ".zip":
            raise CursorServiceError("请选择 ANI 文件夹或 ZIP 压缩包。")

        with zipfile.ZipFile(source) as archive:
            for info in archive.infolist():
                normalized = info.filename.replace("\\", "/")
                parts = PurePosixPath(normalized).parts
                if (
                    PurePosixPath(normalized).is_absolute()
                    or ".." in parts
                    or (parts and ":" in parts[0])
                ):
                    raise CursorServiceError("ZIP 中包含不安全的路径。")
                if info.is_dir():
                    continue
                suffix = PurePosixPath(normalized).suffix.casefold()
                if suffix not in {".ani", ".inf"}:
                    continue
                total_size += info.file_size
                if total_size > MAX_ANI_IMPORT_BYTES:
                    raise CursorServiceError("ANI 导入包过大（上限 64 MB）。")
                data = archive.read(info)
                if len(data) != info.file_size:
                    raise CursorServiceError(f"ZIP 文件读取不完整：{info.filename}")
                if normalized in files:
                    raise CursorServiceError(f"ZIP 中存在重复文件：{normalized}")
                files[normalized] = data
        return files

    @staticmethod
    def _theme_name_from_inf(data: bytes | None) -> str | None:
        if not data:
            return None
        encodings = (
            ("utf-16",) if data.startswith((b"\xff\xfe", b"\xfe\xff")) else ()
        ) + ("utf-8-sig", "gb18030", "latin-1")
        for encoding in encodings:
            try:
                text = data.decode(encoding)
            except UnicodeDecodeError:
                continue
            match = re.search(
                r'^\s*SCHEME_NAME\s*=\s*"?([^"\r\n]+)',
                text,
                flags=re.IGNORECASE | re.MULTILINE,
            )
            if match:
                return match.group(1).strip()
        return None

    def _available_import_folder(self, display_name: str) -> str:
        base = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", display_name).strip(" .")
        base = base[:80] or "ani-theme"
        candidate = base
        index = 2
        while (self.imported_themes_dir / candidate).exists():
            candidate = f"{base}-{index}"
            index += 1
        return candidate

    def _available_import_name(self, display_name: str) -> str:
        existing = {
            theme.name.casefold() for theme in self.list_imported_themes()
        }
        if display_name.casefold() not in existing:
            return display_name
        index = 2
        while f"{display_name} ({index})".casefold() in existing:
            index += 1
        return f"{display_name} ({index})"

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
        cursor_size = self.current_cursor_size()
        cursors = theme.resolved_cursors(cursor_size)
        missing = theme.missing_files(cursor_size)
        if missing:
            names = "\n".join(str(path) for path in missing[:5])
            raise CursorServiceError(f"以下指针文件不存在：\n{names}")

        self.ensure_initial_backup()
        before = self._read_managed_values()
        previous_scheme = self._read_user_scheme(theme.name)

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
                    path = cursors[role]
                    value_type = (
                        winreg.REG_EXPAND_SZ if "%" in path else winreg.REG_SZ
                    )
                    winreg.SetValueEx(key, role, 0, value_type, path)

            self._write_user_scheme(theme.name, cursors)
            self._reload_system_cursors()
        except Exception as exc:
            try:
                self._restore_managed_values(before)
            except Exception:
                pass
            try:
                self._restore_user_scheme(theme.name, previous_scheme)
            except Exception:
                pass
            try:
                self._reload_system_cursors()
            except Exception:
                pass
            raise CursorServiceError(f"应用鼠标指针失败：{exc}") from exc

        if remember:
            self.save_selected_theme(theme)

    @staticmethod
    def _read_user_scheme(name: str) -> tuple[str, int] | None:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                USER_SCHEMES_KEY,
                0,
                winreg.KEY_QUERY_VALUE,
            ) as key:
                value, value_type = winreg.QueryValueEx(key, name)
            return str(value), int(value_type)
        except FileNotFoundError:
            return None

    @staticmethod
    def _write_user_scheme(name: str, cursors: dict[str, str]) -> None:
        value = ",".join(cursors[role] for role in CURSOR_ROLES)
        value_type = winreg.REG_EXPAND_SZ if "%" in value else winreg.REG_SZ
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            USER_SCHEMES_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, name, 0, value_type, value)

    @staticmethod
    def _restore_user_scheme(name: str, previous: tuple[str, int] | None) -> None:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            USER_SCHEMES_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            if previous is None:
                try:
                    winreg.DeleteValue(key, name)
                except FileNotFoundError:
                    pass
            else:
                value, value_type = previous
                winreg.SetValueEx(key, name, 0, value_type, value)

    @staticmethod
    def current_cursor_size() -> int:
        """Return the current Windows cursor base size in pixels."""
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                ACTIVE_CURSORS_KEY,
                0,
                winreg.KEY_QUERY_VALUE,
            ) as key:
                value, _value_type = winreg.QueryValueEx(key, CURSOR_SIZE_VALUE)
            size = int(value)
        except (FileNotFoundError, TypeError, ValueError):
            size = CURSOR_SIZE_MIN
        return max(CURSOR_SIZE_MIN, min(CURSOR_SIZE_MAX, size))

    def set_cursor_size(self, size: int) -> None:
        """Set the Windows cursor base size and reload active cursors."""
        if not CURSOR_SIZE_MIN <= size <= CURSOR_SIZE_MAX:
            raise ValueError(
                f"指针大小必须在 {CURSOR_SIZE_MIN} 到 {CURSOR_SIZE_MAX} 像素之间。"
            )
        if (size - CURSOR_SIZE_MIN) % CURSOR_SIZE_STEP:
            raise ValueError(f"指针大小必须以 {CURSOR_SIZE_STEP} 像素为步长。")

        self.ensure_initial_backup()
        before = self._read_managed_values()
        previous_size = int(
            before.get(CURSOR_SIZE_VALUE, {}).get("value") or CURSOR_SIZE_MIN
        )
        try:
            with winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER,
                ACTIVE_CURSORS_KEY,
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                winreg.SetValueEx(
                    key,
                    CURSOR_SIZE_VALUE,
                    0,
                    winreg.REG_DWORD,
                    size,
                )
            self._set_system_cursor_size(size)
        except Exception as exc:
            try:
                self._restore_managed_values(before)
                self._set_system_cursor_size(previous_size)
            except Exception:
                pass
            raise CursorServiceError(f"调整鼠标指针大小失败：{exc}") from exc

    def ensure_initial_backup(self) -> None:
        if self.backup_path.exists():
            return
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(
            self.backup_path,
            {"version": 2, "values": self._read_managed_values()},
        )

    def restore_initial_backup(self) -> None:
        if not self.backup_path.exists():
            raise CursorServiceError("尚未创建原始指针备份。")

        try:
            payload = self._read_json(self.backup_path)
            values = payload["values"]
            if not isinstance(values, dict):
                raise ValueError("备份 values 格式无效")
            self._restore_managed_values(
                values,
                preserve_missing_size=int(payload.get("version", 1)) < 2,
            )
            size_item = values.get(CURSOR_SIZE_VALUE)
            if size_item is not None:
                self._set_system_cursor_size(int(size_item["value"]))
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
    def _restore_managed_values(
        values: dict[str, dict[str, Any]],
        *,
        preserve_missing_size: bool = False,
    ) -> None:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            ACTIVE_CURSORS_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            for name in MANAGED_VALUE_NAMES:
                item = values.get(name)
                if item is None:
                    if preserve_missing_size and name == CURSOR_SIZE_VALUE:
                        continue
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
    def _set_system_cursor_size(size: int) -> None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        function = user32.SystemParametersInfoW
        function.argtypes = [
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_uint,
        ]
        function.restype = ctypes.c_bool

        if not function(SPI_SETCURSORBASESIZE, 0, size, SPIF_UPDATEINIFILE):
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
