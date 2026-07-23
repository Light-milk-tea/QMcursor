"""Main ArkCursor window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
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
from arkcursor.services.cursor_service import CursorService, CursorServiceError
from arkcursor.ui.cursor_preview import CursorPreview


class MainWindow(QMainWindow):
    def __init__(
        self,
        cursor_service: CursorService | None = None,
        autostart_service: AutostartService | None = None,
    ) -> None:
        super().__init__()
        self.cursor_service = cursor_service or CursorService()
        self.autostart_service = autostart_service or AutostartService()
        self.themes: list[CursorTheme] = []
        self._updating_autostart = False

        self.setWindowTitle("ArkCursor 鼠标指针")
        self.resize(880, 560)
        self.setMinimumSize(720, 460)
        self._build_ui()
        self._refresh_current_theme()
        self._load_themes()

    def _build_ui(self) -> None:
        root = QWidget(self)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(12)

        title = QLabel("鼠标指针样式")
        title.setObjectName("title")
        description = QLabel(
            "选择 Windows 已安装的指针方案。应用前会自动备份当前设置。"
        )
        description.setWordWrap(True)
        self.current_theme_label = QLabel()
        self.current_theme_label.setObjectName("currentTheme")

        self.theme_list = QListWidget()
        self.theme_list.setAlternatingRowColors(True)
        self.theme_list.currentRowChanged.connect(self._show_theme_details)

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
        root_layout.addWidget(self.autostart_checkbox)
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
            QListWidget, QTableWidget {
                background: white;
                border: 1px solid #d8dce3;
                border-radius: 7px;
            }
            QListWidget::item { padding: 9px; }
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

    def _load_themes(self) -> None:
        try:
            self.themes = self.cursor_service.list_themes()
        except OSError as exc:
            self._show_error("读取指针方案失败", str(exc))
            self.themes = []

        self.theme_list.clear()
        for theme in self.themes:
            display_name = friendly_theme_name(theme.name)
            item = QListWidgetItem(display_name)
            item.setToolTip(f"系统方案名称：{theme.name}")
            self.theme_list.addItem(item)

        enabled = bool(self.themes)
        self.theme_list.setEnabled(enabled)
        self.apply_button.setEnabled(enabled)

        if enabled:
            selected = self.cursor_service.load_selected_theme()
            selected_name = selected.name.casefold() if selected else ""
            row = next(
                (
                    index
                    for index, theme in enumerate(self.themes)
                    if theme.name.casefold() == selected_name
                ),
                0,
            )
            self.theme_list.setCurrentRow(row)
            self.status_label.setText(f"已找到 {len(self.themes)} 个可用方案")
        else:
            self.details.setRowCount(0)
            self.status_label.setText("未找到可用的 Windows 指针方案")

    def _show_theme_details(self, row: int) -> None:
        if row < 0 or row >= len(self.themes):
            self.details.setRowCount(0)
            return

        theme = self.themes[row]
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
        row = self.theme_list.currentRow()
        if row < 0 or row >= len(self.themes):
            return

        theme = self.themes[row]
        self.apply_button.setEnabled(False)
        try:
            self.cursor_service.apply_theme(theme)
        except CursorServiceError as exc:
            self._show_error("应用失败", str(exc))
            self.status_label.setText("应用失败，原设置已尝试恢复")
        else:
            self.status_label.setText(
                f"已应用：{friendly_theme_name(theme.name)}"
            )
            self._refresh_current_theme()
        finally:
            self.apply_button.setEnabled(True)

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
        except CursorServiceError as exc:
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

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)
