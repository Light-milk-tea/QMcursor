"""Bundled application assets."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon


def resources_dir() -> Path:
    return Path(__file__).resolve().parent


def app_icon_png_path() -> Path:
    return resources_dir() / "app_icon.png"


def app_icon_path() -> Path:
    """Prefer multi-size ICO; fall back to PNG."""
    ico = resources_dir() / "app_icon.ico"
    if ico.is_file():
        return ico
    return app_icon_png_path()


def app_icon() -> QIcon:
    path = app_icon_path()
    if path.is_file():
        return QIcon(str(path))
    return QIcon()
