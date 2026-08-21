"""Lightweight tray resident: physics overlay only, no settings window."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from qmcursor.resources import app_icon
from qmcursor.services.cursor_service import CursorService
from qmcursor.services.physics_cursor_service import (
    PhysicsCursorError,
    PhysicsCursorService,
)
from qmcursor.ui.physics_overlay import resolve_cursor_image_path


class PhysicsTrayHost:
    """Keep the swaying cursor/pendant alive with minimal UI resident memory."""

    def __init__(
        self,
        cursor_service: CursorService | None = None,
        physics_service: PhysicsCursorService | None = None,
    ) -> None:
        self.cursor_service = cursor_service or CursorService()
        self.physics_service = physics_service or PhysicsCursorService(
            self.cursor_service.data_dir
        )
        self._window = None
        self._tray = QSystemTrayIcon()
        self._setup_tray()

    def start(self) -> bool:
        """Start physics from saved preference. Returns False if unavailable."""
        if not self.physics_service.load_enabled():
            return False
        theme = self.cursor_service.load_selected_theme()
        if theme is None:
            return False
        path = resolve_cursor_image_path(theme.cursors.get("Arrow", ""))
        if path is None or path.suffix.lower() != ".png":
            return False
        try:
            size = self.cursor_service.current_cursor_size()
        except OSError:
            size = 48
        try:
            if not self.physics_service.is_running:
                self.physics_service.start(theme, size)
        except PhysicsCursorError:
            return False
        self._tray.setIcon(self._tray_icon())
        self._tray.setToolTip("QMcursor · 物理摇摆运行中")
        self._tray.show()
        return True

    def stop(self) -> None:
        self.physics_service.stop()
        self._tray.hide()

    def _setup_tray(self) -> None:
        menu = QMenu()
        show_action = QAction("打开 QMcursor", menu)
        show_action.triggered.connect(self.open_settings)
        restart_action = QAction("重启 QMcursor", menu)
        restart_action.triggered.connect(self._restart_app)
        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(show_action)
        menu.addAction(restart_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)

    def _tray_icon(self) -> QIcon:
        theme = self.cursor_service.load_selected_theme()
        if theme is not None:
            path = resolve_cursor_image_path(theme.cursors.get("Arrow", ""))
            if path is not None and path.is_file():
                return QIcon(str(path))
        icon = app_icon()
        if not icon.isNull():
            return icon
        return QIcon()

    def open_settings(self) -> None:
        from qmcursor.ui.main_window import MainWindow

        if self._window is not None:
            self._window.showNormal()
            self._window.activateWindow()
            self._window.raise_()
            return

        # Hide host tray while the settings window owns its own tray icon.
        self._tray.hide()
        window = MainWindow(
            cursor_service=self.cursor_service,
            physics_service=self.physics_service,
        )
        window.set_background_handoff(self._on_window_retreated)
        self._window = window
        window.show()

    def _on_window_retreated(self) -> None:
        """Settings closed: drop the heavy window, keep overlay + slim tray."""
        window = self._window
        self._window = None
        if window is not None:
            window.deleteLater()
        self._tray.setIcon(self._tray_icon())
        self._tray.setToolTip("QMcursor · 物理摇摆运行中")
        self._tray.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.open_settings()

    @staticmethod
    def _relaunch_command() -> list[str]:
        if getattr(sys, "frozen", False):
            return [str(Path(sys.executable).resolve())]
        python = Path(sys.executable).resolve()
        project_root = Path(__file__).resolve().parents[3]
        return [str(python), str(project_root / "run.py")]

    def _restart_app(self) -> None:
        was_enabled = self.physics_service.load_enabled()
        self.physics_service.stop()
        self.physics_service.save_enabled(was_enabled)
        command = self._relaunch_command()
        cwd = (
            None
            if getattr(sys, "frozen", False)
            else str(Path(command[-1]).resolve().parent)
        )
        try:
            subprocess.Popen(command, cwd=cwd, close_fds=True)
        except OSError:
            if was_enabled:
                self.start()
            return
        self._quit_app()

    def _quit_app(self) -> None:
        was_enabled = self.physics_service.load_enabled()
        window = self._window
        self._window = None
        if window is not None:
            window.prepare_external_quit()
            window.close()
            window.deleteLater()
        self.physics_service.stop()
        self.physics_service.save_enabled(was_enabled)
        self._tray.hide()
        app = QApplication.instance()
        if app is not None:
            app.quit()
