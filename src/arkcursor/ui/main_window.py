"""Main QMcursor window."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QSplitter,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from arkcursor.models.theme import (
    CURSOR_ROLES,
    ROLE_LABELS,
    CursorTheme,
    friendly_theme_name,
)
from arkcursor.services.autostart_service import AutostartService
from arkcursor.services.cursor_service import (
    CURSOR_SIZE_MAX,
    CURSOR_SIZE_MIN,
    CURSOR_SIZE_STEP,
    CursorService,
    CursorServiceError,
)
from arkcursor.services.physics_cursor_service import (
    PhysicsCursorError,
    PhysicsCursorService,
)
from arkcursor.ui.cursor_preview import CursorPreview
from arkcursor.ui.physics_overlay import resolve_cursor_image_path


class MainWindow(QMainWindow):
    def __init__(
        self,
        cursor_service: CursorService | None = None,
        autostart_service: AutostartService | None = None,
        physics_service: PhysicsCursorService | None = None,
    ) -> None:
        super().__init__()
        self.cursor_service = cursor_service or CursorService()
        self.autostart_service = autostart_service or AutostartService()
        self.physics_service = physics_service or PhysicsCursorService(
            self.cursor_service.data_dir
        )
        self.themes: list[CursorTheme] = []
        self._updating_autostart = False
        self._updating_physics = False
        self._force_quit = False

        self.setWindowTitle("ArkCursor 鼠标指针")
        self.resize(880, 560)
        self.setMinimumSize(720, 460)
        self._build_ui()
        self._setup_tray()
        self._refresh_current_theme()
        self._refresh_cursor_size()
        self._load_themes()
        self._restore_physics_preference()
        self._sync_tray_visibility()

    def _build_ui(self) -> None:
        root = QWidget(self)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(12)

        title = QLabel("鼠标指针样式")
        title.setObjectName("title")
        description = QLabel(
            "选择 Windows 已安装或 ArkCursor 内置的指针方案。"
            "应用前会自动备份当前设置。"
        )
        description.setWordWrap(True)
        self.current_theme_label = QLabel()
        self.current_theme_label.setObjectName("currentTheme")

        self.theme_list = QTreeWidget()
        self.theme_list.setHeaderHidden(True)
        self.theme_list.setIndentation(18)
        self.theme_list.setAlternatingRowColors(True)
        self.theme_list.currentItemChanged.connect(self._show_theme_details)

        self.details = QTableWidget(0, 3)
        self.details.setHorizontalHeaderLabels(["用途", "事件指针预览", "指针文件"])
        self.details.verticalHeader().setVisible(False)
        self.details.setEditTriggers(QTableWidget.NoEditTriggers)
        self.details.setSelectionMode(QTableWidget.NoSelection)
        header = self.details.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.theme_list)
        splitter.addWidget(self.details)
        splitter.setSizes([260, 580])

        self.autostart_checkbox = QCheckBox("开机时自动重新应用所选样式")
        self.autostart_checkbox.setChecked(self.autostart_service.is_enabled())
        self.autostart_checkbox.toggled.connect(self._toggle_autostart)

        self.physics_checkbox = QCheckBox("启用物理摇摆（实验）")
        self.physics_checkbox.setToolTip(
            "用叠加层绘制当前主题指针，随移动软跟随、摇摆，并按用途自动换图"
            "（文本选择、链接等）。若主题含 pendant.png，会在指针下方挂坠摇摆。"
            "需要自制主题 PNG（如伊雷娜）。启用后关闭窗口会缩到托盘继续运行；"
            "请从托盘图标选择「退出」才会停止。"
        )
        self.physics_checkbox.toggled.connect(self._toggle_physics)

        self.size_slider = QSlider(Qt.Horizontal)
        size_level_count = (
            (CURSOR_SIZE_MAX - CURSOR_SIZE_MIN) // CURSOR_SIZE_STEP + 1
        )
        self.size_slider.setRange(1, size_level_count)
        self.size_slider.setSingleStep(1)
        self.size_slider.setPageStep(1)
        self.size_slider.setTickInterval(1)
        self.size_slider.setTickPosition(QSlider.TicksBelow)
        self.size_slider.valueChanged.connect(self._update_size_label)

        self.size_value_label = QLabel()
        self.size_value_label.setMinimumWidth(72)
        self.size_value_label.setAlignment(Qt.AlignCenter)

        self.apply_size_button = QPushButton("应用大小")
        self.apply_size_button.clicked.connect(self._apply_cursor_size)

        size_controls = QHBoxLayout()
        size_controls.addWidget(QLabel("指针大小"))
        size_controls.addWidget(self.size_slider, 1)
        size_controls.addWidget(self.size_value_label)
        size_controls.addWidget(self.apply_size_button)

        self.status_label = QLabel("正在读取系统指针方案……")
        self.status_label.setObjectName("status")

        self.apply_button = QPushButton("应用所选样式")
        self.apply_button.setDefault(True)
        self.apply_button.clicked.connect(self._apply_selected_theme)

        self.restore_button = QPushButton("恢复首次备份")
        self.restore_button.clicked.connect(self._restore_backup)

        actions = QHBoxLayout()
        actions.addWidget(self.status_label, 1)
        actions.addWidget(self.restore_button)
        actions.addWidget(self.apply_button)

        root_layout.addWidget(title)
        root_layout.addWidget(description)
        root_layout.addWidget(self.current_theme_label)
        root_layout.addWidget(splitter, 1)
        root_layout.addLayout(size_controls)
        root_layout.addWidget(self.autostart_checkbox)
        root_layout.addWidget(self.physics_checkbox)
        root_layout.addLayout(actions)
        self.setCentralWidget(root)

        self.setStyleSheet(
            """
            QMainWindow { background: #f5f6f8; }
            QLabel#title { font-size: 24px; font-weight: 700; }
            QLabel#currentTheme {
                padding: 9px 12px;
                color: #1e3a8a;
                background: #e8efff;
                border: 1px solid #c9d8ff;
                border-radius: 6px;
                font-weight: 600;
            }
            QLabel#status { color: #4b5563; }
            QTreeWidget, QTableWidget {
                background: white;
                border: 1px solid #d8dce3;
                border-radius: 7px;
            }
            QTreeWidget::item { padding: 7px; }
            QPushButton {
                padding: 7px 14px;
                border: 1px solid #c7ccd4;
                border-radius: 6px;
                background: white;
            }
            QPushButton:default {
                color: white;
                background: #2563eb;
                border-color: #2563eb;
            }
            """
        )

    def _refresh_current_theme(self) -> None:
        try:
            theme = self.cursor_service.current_theme()
            display_name = friendly_theme_name(theme.name)
            self.current_theme_label.setText(f"目前指针样式：{display_name}")
            self.current_theme_label.setToolTip(
                f"Windows 系统方案名称：{theme.name}"
            )
        except OSError as exc:
            self.current_theme_label.setText("目前指针样式：读取失败")
            self.current_theme_label.setToolTip(str(exc))

    def _refresh_cursor_size(self) -> None:
        try:
            size = self.cursor_service.current_cursor_size()
        except OSError as exc:
            self.size_slider.setEnabled(False)
            self.apply_size_button.setEnabled(False)
            self.size_value_label.setText("读取失败")
            self.size_value_label.setToolTip(str(exc))
            return
        level = round((size - CURSOR_SIZE_MIN) / CURSOR_SIZE_STEP) + 1
        self.size_slider.setValue(level)
        self._update_size_label(level)

    def _update_size_label(self, level: int) -> None:
        size = CURSOR_SIZE_MIN + (level - 1) * CURSOR_SIZE_STEP
        self.size_value_label.setText(f"{size} px")
        self.size_value_label.setToolTip(
            f"大小等级 {level} / {self.size_slider.maximum()}"
        )

    def _load_themes(self) -> None:
        try:
            self.themes = self.cursor_service.list_themes()
        except OSError as exc:
            self._show_error("读取指针方案失败", str(exc))
            self.themes = []

        self.theme_list.clear()
        theme_items: dict[int, QTreeWidgetItem] = {}
        for category, is_custom in (("系统指针", False), ("自制指针", True)):
            category_themes = [
                (index, theme)
                for index, theme in enumerate(self.themes)
                if theme.is_custom is is_custom
            ]
            if not category_themes:
                continue

            header_item = QTreeWidgetItem(self.theme_list, [category])
            header_item.setFlags(Qt.ItemIsEnabled)
            header_font = header_item.font(0)
            header_font.setBold(True)
            header_item.setFont(0, header_font)
            header_item.setExpanded(is_custom)

            for index, theme in category_themes:
                display_name = friendly_theme_name(theme.name)
                item = QTreeWidgetItem(header_item, [display_name])
                item.setData(0, Qt.UserRole, index)
                item.setToolTip(0, f"方案名称：{theme.name}")
                theme_items[index] = item

        enabled = bool(self.themes)
        self.theme_list.setEnabled(enabled)
        self.apply_button.setEnabled(enabled)

        if enabled:
            selected = self.cursor_service.load_selected_theme()
            selected_name = selected.name.casefold() if selected else ""
            theme_index = next(
                (
                    index
                    for index, theme in enumerate(self.themes)
                    if theme.name.casefold() == selected_name
                ),
                0,
            )
            self.theme_list.setCurrentItem(theme_items[theme_index])
            self.status_label.setText(f"已找到 {len(self.themes)} 个可用方案")
        else:
            self.details.setRowCount(0)
            self.status_label.setText("未找到可用的 Windows 指针方案")

    def _show_theme_details(
        self,
        current: QTreeWidgetItem | None,
        previous: QTreeWidgetItem | None = None,
    ) -> None:
        del previous
        theme_index = current.data(0, Qt.UserRole) if current else None
        if not isinstance(theme_index, int) or not 0 <= theme_index < len(self.themes):
            self.details.setRowCount(0)
            return

        theme = self.themes[theme_index]
        self.details.setRowCount(len(CURSOR_ROLES))
        for index, role in enumerate(CURSOR_ROLES):
            path = theme.cursors[role]
            display_path = Path(path).name if path else "Windows 默认"
            role_item = QTableWidgetItem(ROLE_LABELS[role])
            path_item = QTableWidgetItem(display_path)
            path_item.setToolTip(path or "由 Windows 使用默认指针")
            self.details.setItem(index, 0, role_item)
            self.details.setCellWidget(index, 1, CursorPreview(role, path))
            self.details.setItem(index, 2, path_item)
            self.details.setRowHeight(index, 52)

    def _apply_selected_theme(self) -> None:
        current = self.theme_list.currentItem()
        theme_index = current.data(0, Qt.UserRole) if current else None
        if not isinstance(theme_index, int) or not 0 <= theme_index < len(self.themes):
            return

        theme = self.themes[theme_index]
        self.apply_button.setEnabled(False)
        try:
            self.cursor_service.apply_theme(theme)
        except CursorServiceError as exc:
            self._show_error("应用失败", str(exc))
            self.status_label.setText("应用失败，原设置已尝试恢复")
            self.apply_button.setEnabled(True)
            return

        self._refresh_current_theme()
        if self.physics_service.is_running:
            try:
                self.physics_service.sync_theme(
                    theme, self.cursor_service.current_cursor_size()
                )
            except PhysicsCursorError as exc:
                self._set_physics_checked(False)
                self.physics_service.save_enabled(False)
                self._show_error("物理摇摆已关闭", str(exc))
                self.status_label.setText(
                    f"已应用：{friendly_theme_name(theme.name)}（物理摇摆已关闭）"
                )
                self.apply_button.setEnabled(True)
                return

        self.status_label.setText(f"已应用：{friendly_theme_name(theme.name)}")
        self.apply_button.setEnabled(True)

    def _apply_cursor_size(self) -> None:
        size = CURSOR_SIZE_MIN + (
            self.size_slider.value() - 1
        ) * CURSOR_SIZE_STEP
        self.apply_size_button.setEnabled(False)
        try:
            self.cursor_service.set_cursor_size(size)
            if self.physics_service.is_running:
                self.physics_service.sync_size(size)
        except (CursorServiceError, ValueError, PhysicsCursorError) as exc:
            if isinstance(exc, PhysicsCursorError):
                self._set_physics_checked(False)
            self._show_error("调整大小失败", str(exc))
            self.status_label.setText("调整指针大小失败")
            self._refresh_cursor_size()
        else:
            self.status_label.setText(f"指针大小已调整为 {size} px")
        finally:
            self.apply_size_button.setEnabled(True)

    def _restore_backup(self) -> None:
        answer = QMessageBox.question(
            self,
            "恢复首次备份",
            "确定恢复首次使用 ArkCursor 时的鼠标指针设置吗？",
        )
        if answer != QMessageBox.Yes:
            return

        try:
            self.cursor_service.restore_initial_backup()
            if self.physics_service.is_running:
                theme = self._theme_for_physics()
                if theme is None:
                    raise PhysicsCursorError("恢复后无法找到可用于物理摇摆的主题。")
                self.physics_service.sync_theme(
                    theme, self.cursor_service.current_cursor_size()
                )
        except (CursorServiceError, PhysicsCursorError) as exc:
            if isinstance(exc, PhysicsCursorError):
                self._set_physics_checked(False)
                self.physics_service.stop()
                self.physics_service.save_enabled(False)
            self._show_error("恢复失败", str(exc))
        else:
            self.status_label.setText("已恢复首次备份")
            self._refresh_current_theme()

    def _toggle_autostart(self, enabled: bool) -> None:
        if self._updating_autostart:
            return
        try:
            self.autostart_service.set_enabled(enabled)
        except OSError as exc:
            self._updating_autostart = True
            self.autostart_checkbox.setChecked(not enabled)
            self._updating_autostart = False
            self._show_error("开机启动设置失败", str(exc))
        else:
            state = "开启" if enabled else "关闭"
            self.status_label.setText(f"已{state}开机自动应用")

    def _toggle_physics(self, enabled: bool) -> None:
        if self._updating_physics:
            return
        if not enabled:
            self.physics_service.stop()
            self.physics_service.save_enabled(False)
            self.status_label.setText("已关闭物理摇摆")
            self._sync_tray_visibility()
            return

        theme = self._theme_for_physics()
        if theme is None:
            self._set_physics_checked(False)
            self._show_error(
                "无法启用物理摇摆",
                "请先选择或应用带有 PNG 预览图的自制主题（如伊雷娜）。",
            )
            return

        try:
            self.physics_service.start(
                theme, self.cursor_service.current_cursor_size()
            )
            self.physics_service.save_enabled(True)
        except PhysicsCursorError as exc:
            self._set_physics_checked(False)
            self._show_error("无法启用物理摇摆", str(exc))
            return
        self.status_label.setText(
            f"已启用物理摇摆：{friendly_theme_name(theme.name)}"
            "（关闭窗口后仍在托盘运行）"
        )
        self._sync_tray_visibility()

    def _restore_physics_preference(self) -> None:
        if not self.physics_service.load_enabled():
            return
        theme = self._theme_for_physics()
        if theme is None:
            self.physics_service.save_enabled(False)
            return
        try:
            self.physics_service.start(
                theme, self.cursor_service.current_cursor_size()
            )
        except PhysicsCursorError:
            self.physics_service.save_enabled(False)
            return
        self._set_physics_checked(True)
        self.status_label.setText(
            f"已恢复物理摇摆：{friendly_theme_name(theme.name)}"
        )
        self._sync_tray_visibility()

    def _theme_for_physics(self) -> CursorTheme | None:
        current = self.theme_list.currentItem()
        theme_index = current.data(0, Qt.UserRole) if current else None
        if isinstance(theme_index, int) and 0 <= theme_index < len(self.themes):
            candidate = self.themes[theme_index]
            if self._theme_has_arrow_png(candidate):
                return candidate

        selected = self.cursor_service.load_selected_theme()
        if selected is not None and self._theme_has_arrow_png(selected):
            return selected

        try:
            active = self.cursor_service.current_theme()
        except OSError:
            return None
        if self._theme_has_arrow_png(active):
            return active
        return None

    @staticmethod
    def _theme_has_arrow_png(theme: CursorTheme) -> bool:
        path = resolve_cursor_image_path(theme.cursors.get("Arrow", ""))
        return path is not None and path.suffix.lower() == ".png"

    def _set_physics_checked(self, checked: bool) -> None:
        self._updating_physics = True
        self.physics_checkbox.setChecked(checked)
        self._updating_physics = False

    def _setup_tray(self) -> None:
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(self._tray_icon())
        self._tray.setToolTip("QMcursor")
        menu = QMenu()
        show_action = QAction("打开 QMcursor", menu)
        show_action.triggered.connect(self._show_from_tray)
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
        bundled = (
            Path(__file__).resolve().parents[1] / "themes" / "elaina" / "arrow.png"
        )
        if bundled.is_file():
            return QIcon(str(bundled))
        return self.windowIcon()

    def _sync_tray_visibility(self) -> None:
        if self.physics_service.is_running:
            self._tray.setIcon(self._tray_icon())
            self._tray.setToolTip("QMcursor · 物理摇摆运行中")
            self._tray.show()
        elif not self.isVisible():
            self._tray.setToolTip("QMcursor")
            self._tray.show()
        else:
            self._tray.hide()

    def retreat_to_tray(self) -> None:
        """Hide the settings window; keep physics overlay alive."""
        self.hide()
        self._tray.setIcon(self._tray_icon())
        self._tray.setToolTip("QMcursor · 物理摇摆运行中")
        self._tray.show()

    def _show_from_tray(self) -> None:
        self.showNormal()
        self.activateWindow()
        self.raise_()
        self._sync_tray_visibility()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._show_from_tray()

    @staticmethod
    def _relaunch_command() -> list[str]:
        if getattr(sys, "frozen", False):
            return [str(Path(sys.executable).resolve())]
        python = Path(sys.executable).resolve()
        project_root = Path(__file__).resolve().parents[3]
        launcher = project_root / "run.py"
        return [str(python), str(launcher)]

    def _restart_app(self) -> None:
        was_enabled = self.physics_checkbox.isChecked()
        self.physics_service.stop()
        self.physics_service.save_enabled(was_enabled)
        command = self._relaunch_command()
        cwd = str(Path(command[-1]).resolve().parent) if not getattr(sys, "frozen", False) else None
        try:
            subprocess.Popen(
                command,
                cwd=cwd,
                close_fds=True,
            )
        except OSError as exc:
            self.physics_service.save_enabled(was_enabled)
            if was_enabled:
                theme = self._theme_for_physics()
                if theme is not None:
                    try:
                        self.physics_service.start(
                            theme, self.cursor_service.current_cursor_size()
                        )
                    except PhysicsCursorError:
                        pass
            self._show_error("无法重启 QMcursor", str(exc))
            return
        self._quit_app()

    def _quit_app(self) -> None:
        self._force_quit = True
        was_enabled = self.physics_checkbox.isChecked()
        self.physics_service.stop()
        # Keep preference so next launch / 开机启动 can restore the overlay.
        self.physics_service.save_enabled(was_enabled)
        self._tray.hide()
        self.close()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._force_quit and self.physics_service.is_running:
            event.ignore()
            self.retreat_to_tray()
            self.status_label.setText("已最小化到托盘，挂坠/物理摇摆继续运行")
            return

        if not self._force_quit:
            self.physics_service.stop()
        self._tray.hide()
        super().closeEvent(event)
        if not self._force_quit:
            app = QApplication.instance()
            if app is not None:
                app.quit()

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)
