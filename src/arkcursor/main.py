"""QMcursor application entry point."""

from __future__ import annotations

import argparse
import os
import sys

from arkcursor.services.cursor_service import CursorService, CursorServiceError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Windows 鼠标指针样式工具")
    parser.add_argument(
        "--startup",
        action="store_true",
        help="静默重新应用上次选择的样式；若启用了物理摇摆则托盘常驻",
    )
    return parser


def apply_at_startup(service: CursorService | None = None) -> int:
    cursor_service = service or CursorService()
    theme = cursor_service.load_selected_theme()
    if theme is None:
        return 0

    try:
        cursor_service.apply_theme(theme, remember=False)
    except CursorServiceError:
        return 1
    return 0


def _physics_enabled_at_startup() -> bool:
    from arkcursor.services.physics_cursor_service import PhysicsCursorService

    cursor_service = CursorService()
    return PhysicsCursorService(cursor_service.data_dir).load_enabled()


def run_gui(*, start_hidden: bool = False) -> int:
    from PySide6.QtWidgets import QApplication

    from arkcursor.ui.physics_tray_host import PhysicsTrayHost

    app = QApplication(sys.argv[:1])
    app.setApplicationName("QMcursor")
    app.setOrganizationName("QMcursor")
    # Keep running in tray while physics overlay is active.
    app.setQuitOnLastWindowClosed(False)

    host = PhysicsTrayHost()
    app.aboutToQuit.connect(host.stop)

    if start_hidden:
        if host.start():
            return app.exec()
        # Preference says physics on, but it failed — open settings instead.

    host.open_settings()
    return app.exec()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if os.name != "nt":
        print("QMcursor 仅支持 Windows。", file=sys.stderr)
        return 2

    if args.startup:
        code = apply_at_startup()
        if code != 0:
            return code
        if _physics_enabled_at_startup():
            return run_gui(start_hidden=True)
        return 0

    return run_gui(start_hidden=False)


if __name__ == "__main__":
    raise SystemExit(main())
