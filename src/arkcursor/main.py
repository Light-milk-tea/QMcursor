"""ArkCursor application entry point."""

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
        help="静默重新应用上次选择的样式并退出",
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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if os.name != "nt":
        print("ArkCursor 仅支持 Windows。", file=sys.stderr)
        return 2

    if args.startup:
        return apply_at_startup()

    from PySide6.QtWidgets import QApplication

    from arkcursor.ui.main_window import MainWindow

    app = QApplication(sys.argv[:1])
    app.setApplicationName("ArkCursor")
    app.setOrganizationName("ArkCursor")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
