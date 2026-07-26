"""Standalone physics-cursor feel test (thin wrapper around ArkCursor modules).

Run from repo root:
  python tools/physics_cursor_prototype.py
  python tools/physics_cursor_prototype.py --image src/arkcursor/themes/elaina/arrow.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from PySide6.QtGui import QAction, QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon  # noqa: E402

from arkcursor.models.theme import CURSOR_ROLES, CursorTheme  # noqa: E402
from arkcursor.services.physics_cursor_service import (  # noqa: E402
    PhysicsCursorError,
    PhysicsCursorService,
)


def _default_theme() -> CursorTheme:
    arrow = ROOT / "src" / "arkcursor" / "themes" / "elaina" / "arrow.png"
    if not arrow.is_file():
        matches = sorted((ROOT / "src" / "arkcursor" / "themes").glob("*/arrow.png"))
        if not matches:
            raise FileNotFoundError("未找到 arrow.png")
        arrow = matches[0]
    cursors = {role: "" for role in CURSOR_ROLES}
    cursors["Arrow"] = str(arrow)
    return CursorTheme(name="prototype", cursors=cursors, is_custom=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Physics cursor feel prototype")
    parser.add_argument("--image", type=Path, default=None, help="PNG sprite")
    parser.add_argument("--size", type=int, default=48, help="Cursor size in px")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.image is not None:
        cursors = {role: "" for role in CURSOR_ROLES}
        cursors["Arrow"] = str(args.image.resolve())
        theme = CursorTheme(name="prototype", cursors=cursors, is_custom=True)
    else:
        theme = _default_theme()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    service = PhysicsCursorService()
    try:
        service.start(theme, args.size)
    except PhysicsCursorError as exc:
        print(exc, file=sys.stderr)
        return 1

    tray = QSystemTrayIcon(QIcon(theme.cursors["Arrow"]), app)
    menu = QMenu()
    quit_action = QAction("退出", menu)
    menu.addAction(quit_action)
    tray.setContextMenu(menu)
    tray.setToolTip("Physics Cursor Prototype")
    tray.show()

    def shutdown() -> None:
        service.stop()
        tray.hide()
        app.quit()

    quit_action.triggered.connect(shutdown)
    tray.activated.connect(
        lambda reason: shutdown()
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick
        else None
    )
    app.aboutToQuit.connect(service.stop)

    print("物理指针原型运行中。托盘右键退出。", flush=True)
    try:
        return app.exec()
    finally:
        service.stop()


if __name__ == "__main__":
    raise SystemExit(main())
