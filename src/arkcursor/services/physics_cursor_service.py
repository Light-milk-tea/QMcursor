"""Orchestrate the physics cursor overlay on top of ArkCursor themes."""

from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
from typing import Any

from ctypes import wintypes

from PySide6.QtGui import QPixmap

from arkcursor.models.theme import CURSOR_ROLES, CursorTheme
from arkcursor.ui.physics_overlay import (
    PhysicsConfig,
    PhysicsOverlay,
    ROLE_HOTSPOT_KIND,
    RoleSprite,
    hotspot_fraction,
    load_sprite,
    resolve_cursor_image_path,
)

user32 = ctypes.WinDLL("user32", use_last_error=True)
SPI_SETCURSORS = 0x0057
CURSOR_SHOWING = 0x00000001

# OCR_* / IDC_* share these ids for the standard scheme roles.
ROLE_TO_OCR = {
    "Arrow": 32512,
    "IBeam": 32513,
    "Wait": 32514,
    "Crosshair": 32515,
    "UpArrow": 32516,
    "NWPen": 32631,
    "SizeNWSE": 32642,
    "SizeNESW": 32643,
    "SizeWE": 32644,
    "SizeNS": 32645,
    "SizeAll": 32646,
    "No": 32648,
    "Hand": 32649,
    "AppStarting": 32650,
    "Help": 32651,
}


class CURSORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hCursor", wintypes.HANDLE),
        ("ptScreenPos", wintypes.POINT),
    ]


user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
user32.LoadCursorW.restype = wintypes.HANDLE
user32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
user32.GetCursorInfo.restype = wintypes.BOOL
user32.SetSystemCursor.argtypes = [wintypes.HANDLE, ctypes.c_uint]
user32.SetSystemCursor.restype = wintypes.BOOL
user32.CopyIcon.argtypes = [wintypes.HANDLE]
user32.CopyIcon.restype = wintypes.HANDLE
user32.DestroyCursor.argtypes = [wintypes.HANDLE]
user32.DestroyCursor.restype = wintypes.BOOL
user32.DestroyIcon.argtypes = [wintypes.HANDLE]
user32.DestroyIcon.restype = wintypes.BOOL
user32.CreateCursor.argtypes = [
    wintypes.HINSTANCE,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_void_p,
    ctypes.c_void_p,
]
user32.CreateCursor.restype = wintypes.HANDLE
user32.SystemParametersInfoW.argtypes = [
    ctypes.c_uint,
    ctypes.c_uint,
    ctypes.c_void_p,
    ctypes.c_uint,
]
user32.SystemParametersInfoW.restype = wintypes.BOOL


class PhysicsCursorError(RuntimeError):
    """User-facing physics cursor error."""


class PhysicsCursorService:
    def __init__(self, data_dir: Path | None = None) -> None:
        local_app_data = os.environ.get("LOCALAPPDATA")
        default_dir = (
            Path(local_app_data) / "ArkCursor"
            if local_app_data
            else Path.home() / "AppData" / "Local" / "ArkCursor"
        )
        self.data_dir = Path(data_dir) if data_dir else default_dir
        self.state_path = self.data_dir / "physics.json"
        self._overlay: PhysicsOverlay | None = None
        self._system_hidden = False
        self._handle_to_role: dict[int, str] = {}
        self._blank_templates: list[int] = []
        # Cached decoded theme assets (pixmap + hotspot), keyed by fingerprint.
        self._asset_fingerprint: str | None = None
        self._assets: dict[str, tuple[QPixmap, tuple[float, float]]] | None = None

    @property
    def is_running(self) -> bool:
        return self._overlay is not None

    def load_enabled(self) -> bool:
        if not self.state_path.exists():
            return False
        try:
            payload = self._read_json(self.state_path)
            return bool(payload.get("enabled", False))
        except (OSError, ValueError, json.JSONDecodeError, TypeError):
            return False

    def save_enabled(self, enabled: bool) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(self.state_path, {"version": 1, "enabled": bool(enabled)})

    def start(self, theme: CursorTheme, cursor_size: int) -> None:
        catalog = self._catalog_for_theme(theme, cursor_size)
        if self._overlay is None:
            self._overlay = PhysicsOverlay(catalog, PhysicsConfig())
            self._overlay.set_role_resolver(self.resolve_active_role)
            self._overlay.show()
        else:
            self._overlay.set_catalog(catalog)
            self._overlay.reset_physics()

        if not self._hide_system_cursors():
            self.stop()
            raise PhysicsCursorError("无法隐藏系统光标，物理摇摆未能启动。")
        self._system_hidden = True

    def sync_theme(self, theme: CursorTheme, cursor_size: int) -> None:
        if not self.is_running:
            return
        catalog = self._catalog_for_theme(theme, cursor_size)
        assert self._overlay is not None
        self._overlay.set_catalog(catalog)
        if not self._hide_system_cursors():
            self.stop()
            raise PhysicsCursorError("重新隐藏系统光标失败，已关闭物理摇摆。")
        self._system_hidden = True

    def sync_size(self, cursor_size: int) -> None:
        """Cheap path: only rescale cached assets after a size change."""
        if not self.is_running or self._assets is None:
            return
        assert self._overlay is not None
        self._overlay.set_catalog(self._catalog_from_assets(self._assets, cursor_size))
        if not self._hide_system_cursors():
            self.stop()
            raise PhysicsCursorError("重新隐藏系统光标失败，已关闭物理摇摆。")
        self._system_hidden = True

    def stop(self) -> None:
        if self._overlay is not None:
            self._overlay.close()
            self._overlay.deleteLater()
            self._overlay = None
        self._handle_to_role.clear()
        self._asset_fingerprint = None
        self._assets = None
        if self._system_hidden:
            self._restore_system_cursors()
            self._system_hidden = False
        self._destroy_blank_templates()

    def resolve_active_role(self) -> tuple[str, bool]:
        """Return (role, cursor_showing) for the current system cursor."""
        info = CURSORINFO()
        info.cbSize = ctypes.sizeof(CURSORINFO)
        if not user32.GetCursorInfo(ctypes.byref(info)):
            return "Arrow", True
        showing = bool(info.flags & CURSOR_SHOWING)
        handle = int(info.hCursor or 0)
        role = self._handle_to_role.get(handle, "Arrow")
        return role, showing

    def _catalog_for_theme(
        self,
        theme: CursorTheme,
        cursor_size: int,
    ) -> dict[str, RoleSprite]:
        fingerprint = self._theme_fingerprint(theme)
        if self._assets is None or self._asset_fingerprint != fingerprint:
            self._assets = self._load_theme_assets(theme)
            self._asset_fingerprint = fingerprint
        return self._catalog_from_assets(self._assets, cursor_size)

    def _load_theme_assets(
        self,
        theme: CursorTheme,
    ) -> dict[str, tuple[QPixmap, tuple[float, float]]]:
        arrow_path = resolve_cursor_image_path(theme.cursors.get("Arrow", ""))
        if arrow_path is None or arrow_path.suffix.lower() != ".png":
            raise PhysicsCursorError(
                "物理摇摆需要普通选择指针的 PNG。"
                "请先应用带预览 PNG 的自制主题（如伊雷娜）。"
            )

        sprites: dict[str, QPixmap] = {}
        hotspot_cache: dict[tuple[str, str], tuple[float, float]] = {}
        arrow_sprite = load_sprite(arrow_path)
        sprites[str(arrow_path.resolve())] = arrow_sprite

        assets: dict[str, tuple[QPixmap, tuple[float, float]]] = {}
        for role in CURSOR_ROLES:
            image_path = resolve_cursor_image_path(theme.cursors.get(role, ""))
            if image_path is not None and image_path.suffix.lower() == ".png":
                key = str(image_path.resolve())
                pixmap = sprites.get(key)
                if pixmap is None:
                    pixmap = load_sprite(image_path)
                    sprites[key] = pixmap
            else:
                key = str(arrow_path.resolve())
                pixmap = arrow_sprite

            kind = ROLE_HOTSPOT_KIND.get(role, "northwest")
            cache_key = (key, kind)
            hotspot = hotspot_cache.get(cache_key)
            if hotspot is None:
                hotspot = hotspot_fraction(pixmap.toImage(), kind)
                hotspot_cache[cache_key] = hotspot
            assets[role] = (pixmap, hotspot)
        return assets

    @staticmethod
    def _catalog_from_assets(
        assets: dict[str, tuple[QPixmap, tuple[float, float]]],
        cursor_size: int,
    ) -> dict[str, RoleSprite]:
        catalog: dict[str, RoleSprite] = {}
        for role, (pixmap, hotspot) in assets.items():
            edge = max(pixmap.width(), pixmap.height(), 1)
            scale = max(0.05, float(cursor_size) / float(edge))
            catalog[role] = RoleSprite(
                pixmap=pixmap,
                hotspot=hotspot,
                scale=scale,
            )
        return catalog

    @staticmethod
    def _theme_fingerprint(theme: CursorTheme) -> str:
        parts = [theme.name]
        for role in CURSOR_ROLES:
            path = resolve_cursor_image_path(theme.cursors.get(role, ""))
            if path is None or not path.is_file():
                parts.append(f"{role}:")
                continue
            try:
                stat = path.stat()
                parts.append(f"{role}:{path.resolve()}:{stat.st_mtime_ns}:{stat.st_size}")
            except OSError:
                parts.append(f"{role}:{path}")
        return "|".join(parts)

    @staticmethod
    def _make_blank_cursor(*, hotspot_x: int, hotspot_y: int) -> int:
        """Create a fully transparent 32x32 cursor with a unique hotspot tag."""
        width = height = 32
        hx = max(0, min(width - 1, hotspot_x))
        hy = max(0, min(height - 1, hotspot_y))
        stride = ((width + 15) // 16) * 2
        and_mask = (ctypes.c_ubyte * (stride * height))(*([0xFF] * (stride * height)))
        xor_mask = (ctypes.c_ubyte * (stride * height))(*([0x00] * (stride * height)))
        handle = user32.CreateCursor(
            None, hx, hy, width, height, and_mask, xor_mask
        )
        return int(handle or 0)

    def _ensure_blank_templates(self) -> bool:
        if self._blank_templates:
            return True
        templates: list[int] = []
        for index, _role in enumerate(CURSOR_ROLES):
            handle = self._make_blank_cursor(
                hotspot_x=index % 32,
                hotspot_y=(index * 3) % 32,
            )
            if not handle:
                for existing in templates:
                    user32.DestroyCursor(existing)
                return False
            templates.append(handle)
        self._blank_templates = templates
        return True

    def _destroy_blank_templates(self) -> None:
        for handle in self._blank_templates:
            user32.DestroyCursor(handle)
        self._blank_templates.clear()

    def _hide_system_cursors(self) -> bool:
        """Replace each system role with a unique blank cursor and map handles."""
        if not self._ensure_blank_templates():
            return False

        self._handle_to_role.clear()
        ok_any = False
        for role, template in zip(CURSOR_ROLES, self._blank_templates, strict=True):
            ocr_id = ROLE_TO_OCR[role]
            copied = user32.CopyIcon(template)
            if not copied:
                continue
            if user32.SetSystemCursor(copied, ocr_id):
                ok_any = True
            else:
                user32.DestroyIcon(copied)

        if not ok_any:
            return False

        for role, ocr_id in ROLE_TO_OCR.items():
            handle = user32.LoadCursorW(None, ctypes.c_void_p(ocr_id))
            if handle:
                self._handle_to_role[int(handle)] = role
        return bool(self._handle_to_role)

    @staticmethod
    def _restore_system_cursors() -> None:
        user32.SystemParametersInfoW(SPI_SETCURSORS, 0, None, 0)

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
