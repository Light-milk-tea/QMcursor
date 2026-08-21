"""Main QMcursor window."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
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

from qmcursor.models.theme import (
    CURSOR_ROLES,
    ROLE_LABELS,
    CursorTheme,
    friendly_theme_name,
)
from qmcursor.resources import app_icon, app_icon_png_path
from qmcursor.services.autostart_service import AutostartService
from qmcursor.services.cursor_service import (
    CURSOR_SIZE_MAX,
    CURSOR_SIZE_MIN,
    CURSOR_SIZE_STEP,
    CursorService,
    CursorServiceError,
)
from qmcursor.services.physics_cursor_service import (
    PhysicsCursorError,
    PhysicsCursorService,
)
from qmcursor.ui.cursor_preview import CursorPreview
from qmcursor.ui.physics_overlay import resolve_cursor_image_path
from qmcursor.ui.theme_style import main_window_stylesheet

QM_CUSTOM_CATEGORY = "QMcursor 自制指针"
WIREFRAME_CATEGORY = "线框cursor"


def theme_category(theme: CursorTheme) -> str:
    """Return the exclusive UI category for a cursor theme."""
    if theme.category:
        return theme.category
    if theme.is_custom:
        return "ANI 指针" if theme.is_animated else QM_CUSTOM_CATEGORY
    cursor_paths = [path for path in theme.cursors.values() if path]
    if cursor_paths and all(path.casefold().endswith(".ani") for path in cursor_paths):
        return "ANI 指针"
    return "系统指针"


def theme_supports_physics(theme: CursorTheme) -> bool:
    """Physical wobble is only available for bundled QMcursor PNG/CUR themes."""
    return theme_category(theme) == QM_CUSTOM_CATEGORY


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
        self._physics_tree_item: QTreeWidgetItem | None = None
        self._background_handoff: Callable[[], None] | None = None

        self.setWindowTitle("QMcursor 鼠标指针")
        self.setWindowIcon(app_icon())
        self.resize(920, 600)
        self.setMinimumSize(760, 500)
        self._build_ui()
        self._setup_tray()
        self._refresh_current_theme()
        self._refresh_cursor_size()
        self._load_themes()
        self._restore_physics_preference()
        self._sync_tray_visibility()

    def _build_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("root")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        header = QWidget()
        header.setObjectName("headerBar")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 12, 16, 12)
        header_layout.setSpacing(12)

        brand_icon = QLabel()
        brand_icon.setFixedSize(44, 44)
        icon_path = app_icon_png_path()
        if icon_path.is_file():
            pixmap = QPixmap(str(icon_path))
            brand_icon.setPixmap(
                pixmap.scaled(
                    44,
                    44,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        brand_icon.setAlignment(Qt.AlignCenter)

        brand_text = QVBoxLayout()
        brand_text.setContentsMargins(0, 0, 0, 0)
        brand_text.setSpacing(2)
        brand_title = QLabel("QMcursor")
        brand_title.setObjectName("brandTitle")
        brand_subtitle = QLabel("鼠标指针样式 · 一键切换与预览")
        brand_subtitle.setObjectName("brandSubtitle")
        brand_text.addWidget(brand_title)
        brand_text.addWidget(brand_subtitle)

        header_layout.addWidget(brand_icon)
        header_layout.addLayout(brand_text, 1)

        section_title = QLabel("选择指针方案")
        section_title.setObjectName("sectionTitle")
        description = QLabel(
            "可选用 Windows 已安装、QMcursor 内置或导入的 ANI 方案。"
            "应用前会自动备份当前设置。"
        )
        description.setObjectName("description")
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
        self.details.setShowGrid(False)
        self.details.setAlternatingRowColors(True)
        header_view = self.details.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.Stretch)
        header_view.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.theme_list)
        splitter.addWidget(self.details)
        splitter.setSizes([280, 600])
        splitter.setChildrenCollapsible(False)

        self.autostart_checkbox = QCheckBox("开机时自动重新应用所选样式")
        self.autostart_checkbox.setChecked(self.autostart_service.is_enabled())
        self.autostart_checkbox.toggled.connect(self._toggle_autostart)

        self.physics_checkbox = QCheckBox("启用物理摇摆（实验）")
        self._physics_default_tooltip = (
            "用叠加层绘制当前主题指针，随移动软跟随、摇摆，并按用途自动换图"
            "（文本选择、链接等）。若主题含 pendant.png，会在指针下方挂坠摇摆。"
            "需要自制主题 PNG（如伊雷娜）。启用后关闭窗口会缩到托盘继续运行；"
            "请从托盘图标选择「退出」才会停止。"
        )
        self.physics_checkbox.setToolTip(self._physics_default_tooltip)
        self.physics_checkbox.setStyleSheet("background: transparent;")
        self.physics_checkbox.toggled.connect(self._toggle_physics)
        self.physics_checkbox.hide()

        self.size_slider = QSlider(Qt.Horizontal)
        size_level_count = (
            (CURSOR_SIZE_MAX - CURSOR_SIZE_MIN) // CURSOR_SIZE_STEP + 1
        )
        self.size_slider.setRange(1, size_level_count)
        self.size_slider.setSingleStep(1)
        self.size_slider.setPageStep(1)
        self.size_slider.setTickInterval(1)
        self.size_slider.setTickPosition(QSlider.NoTicks)
        self.size_slider.valueChanged.connect(self._update_size_label)

        self.size_value_label = QLabel()
        self.size_value_label.setObjectName("sizeValue")
        self.size_value_label.setMinimumWidth(72)
        self.size_value_label.setAlignment(Qt.AlignCenter)

        self.apply_size_button = QPushButton("应用大小")
        self.apply_size_button.clicked.connect(self._apply_cursor_size)

        size_caption = QLabel("指针大小")
        size_caption.setObjectName("sizeCaption")
        size_controls = QHBoxLayout()
        size_controls.setSpacing(10)
        size_controls.addWidget(size_caption)
        size_controls.addWidget(self.size_slider, 1)
        size_controls.addWidget(self.size_value_label)
        size_controls.addWidget(self.apply_size_button)

        self.status_label = QLabel("正在读取系统指针方案……")
        self.status_label.setObjectName("status")

        self.apply_button = QPushButton("应用所选样式")
        self.apply_button.setObjectName("primaryButton")
        self.apply_button.setDefault(True)
        self.apply_button.clicked.connect(self._apply_selected_theme)

        self.restore_button = QPushButton("恢复首次备份")
        self.restore_button.clicked.connect(self._restore_backup)

        self.import_button = QPushButton("导入 ANI 包")
        import_menu = QMenu(self.import_button)
        import_zip_action = import_menu.addAction("从 ZIP 压缩包导入…")
        import_zip_action.triggered.connect(self._import_ani_zip)
        import_directory_action = import_menu.addAction("从文件夹导入…")
        import_directory_action.triggered.connect(self._import_ani_directory)
        self.import_button.setMenu(import_menu)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(self.status_label, 1)
        actions.addWidget(self.import_button)
        actions.addWidget(self.restore_button)
        actions.addWidget(self.apply_button)

        root_layout.addWidget(header)
        root_layout.addWidget(section_title)
        root_layout.addWidget(description)
        root_layout.addWidget(self.current_theme_label)
        root_layout.addWidget(splitter, 1)
        root_layout.addLayout(size_controls)
        root_layout.addWidget(self.autostart_checkbox)
        root_layout.addLayout(actions)
        self.setCentralWidget(root)
        self.setStyleSheet(main_window_stylesheet())

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
        theme = self._selected_theme()
        selected_size = (
            theme.nearest_size(size)
            if theme is not None and theme.is_animated
            else None
        )
        suffix = f" → {selected_size} px ANI" if selected_size is not None else ""
        self.size_value_label.setText(f"{size} px{suffix}")
        self.size_value_label.setMinimumWidth(72 if selected_size is None else 150)
        self.size_value_label.setToolTip(
            f"大小等级 {level} / {self.size_slider.maximum()}"
            + (
                f"；应用该主题时使用最接近的 {selected_size} px ANI 资源"
                if selected_size is not None
                else ""
            )
        )

    def _load_themes(self) -> None:
        try:
            self.themes = self.cursor_service.list_themes()
        except OSError as exc:
            self._show_error("读取指针方案失败", str(exc))
            self.themes = []

        self._detach_physics_checkbox()
        self.theme_list.clear()
        theme_items: dict[int, QTreeWidgetItem] = {}
        categories = (
            ("系统指针", False),
            (QM_CUSTOM_CATEGORY, True),
            ("ANI 指针", True),
            (WIREFRAME_CATEGORY, True),
        )
        for category, expanded in categories:
            category_themes = [
                (index, theme)
                for index, theme in enumerate(self.themes)
                if theme_category(theme) == category
            ]
            if not category_themes:
                continue

            header_item = QTreeWidgetItem(self.theme_list, [category])
            header_item.setFlags(Qt.ItemIsEnabled)
            header_font = header_item.font(0)
            header_font.setBold(True)
            header_item.setFont(0, header_font)
            header_item.setExpanded(expanded)
            if category == QM_CUSTOM_CATEGORY:
                self._attach_physics_checkbox(header_item)

            for index, theme in category_themes:
                display_name = friendly_theme_name(theme.name)
                if theme.is_animated:
                    display_name += "（系统动画）"
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
            self._update_physics_controls(None)
            return

        theme = self.themes[theme_index]
        preview_size = CURSOR_SIZE_MIN + (
            self.size_slider.value() - 1
        ) * CURSOR_SIZE_STEP
        preview_cursors = theme.resolved_cursors(preview_size)
        self.details.setRowCount(len(CURSOR_ROLES))
        for index, role in enumerate(CURSOR_ROLES):
            path = preview_cursors[role]
            display_path = Path(path).name if path else "Windows 默认"
            role_item = QTableWidgetItem(ROLE_LABELS[role])
            path_item = QTableWidgetItem(display_path)
            path_item.setToolTip(path or "由 Windows 使用默认指针")
            self.details.setItem(index, 0, role_item)
            self.details.setCellWidget(index, 1, CursorPreview(role, path))
            self.details.setItem(index, 2, path_item)
            self.details.setRowHeight(index, 52)
        self._update_physics_controls(theme)
        self._update_size_label(self.size_slider.value())

    def _apply_selected_theme(self) -> None:
        current = self.theme_list.currentItem()
        theme_index = current.data(0, Qt.UserRole) if current else None
        if not isinstance(theme_index, int) or not 0 <= theme_index < len(self.themes):
            return

        theme = self.themes[theme_index]
        if theme.is_animated and self.physics_service.is_running:
            self.physics_service.stop()
            self.physics_service.save_enabled(False)
            self._set_physics_checked(False)
            self._sync_tray_visibility()
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

        if theme.is_animated:
            self.status_label.setText(
                f"已应用：{friendly_theme_name(theme.name)}"
                "（Windows 系统动画，可退出 QMcursor）"
            )
        else:
            self.status_label.setText(f"已应用：{friendly_theme_name(theme.name)}")
        self.apply_button.setEnabled(True)

    def _apply_cursor_size(self) -> None:
        size = CURSOR_SIZE_MIN + (
            self.size_slider.value() - 1
        ) * CURSOR_SIZE_STEP
        self.apply_size_button.setEnabled(False)
        try:
            self.cursor_service.set_cursor_size(size)
            selected_theme = self.cursor_service.load_selected_theme()
            if selected_theme is not None and selected_theme.sizes:
                self.cursor_service.apply_theme(selected_theme, remember=False)
            if self.physics_service.is_running:
                self.physics_service.sync_size(size)
        except (CursorServiceError, ValueError, PhysicsCursorError) as exc:
            if isinstance(exc, PhysicsCursorError):
                self._set_physics_checked(False)
            self._show_error("调整大小失败", str(exc))
            self.status_label.setText("调整指针大小失败")
            self._refresh_cursor_size()
        else:
            selected_theme = self.cursor_service.load_selected_theme()
            asset_size = (
                selected_theme.nearest_size(size)
                if selected_theme is not None and selected_theme.is_animated
                else None
            )
            if asset_size is None:
                self.status_label.setText(f"指针大小已调整为 {size} px")
            else:
                self.status_label.setText(
                    f"指针大小已调整为 {size} px，已应用 {asset_size} px ANI"
                )
        finally:
            self.apply_size_button.setEnabled(True)

    def _restore_backup(self) -> None:
        answer = QMessageBox.question(
            self,
            "恢复首次备份",
            "确定恢复首次使用 QMcursor 时的鼠标指针设置吗？",
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

    def _import_ani_zip(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "选择 ANI 主题压缩包",
            "",
            "ZIP 压缩包 (*.zip)",
        )
        if path:
            self._import_ani_path(Path(path))

    def _import_ani_directory(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择 ANI 主题文件夹")
        if path:
            self._import_ani_path(Path(path))

    def _import_ani_path(self, path: Path) -> None:
        self.import_button.setEnabled(False)
        try:
            imported = self.cursor_service.import_ani_pack(path)
            self._load_themes()
            for index, theme in enumerate(self.themes):
                if theme.name.casefold() != imported.name.casefold():
                    continue
                item = self._theme_item_for_index(index)
                if item is not None:
                    self.theme_list.setCurrentItem(item)
                break
        except CursorServiceError as exc:
            self._show_error("导入 ANI 包失败", str(exc))
            self.status_label.setText("ANI 主题导入失败")
        else:
            self.status_label.setText(
                f"已导入：{friendly_theme_name(imported.name)}（尚未应用）"
            )
        finally:
            self.import_button.setEnabled(True)

    def _theme_item_for_index(self, theme_index: int) -> QTreeWidgetItem | None:
        root = self.theme_list.invisibleRootItem()
        for category_index in range(root.childCount()):
            category = root.child(category_index)
            for item_index in range(category.childCount()):
                item = category.child(item_index)
                if item.data(0, Qt.UserRole) == theme_index:
                    return item
        return None

    def _restore_physics_preference(self) -> None:
        if not self.physics_service.load_enabled():
            return
        if self.physics_service.is_running:
            self._set_physics_checked(True)
            self._sync_tray_visibility()
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

    def set_background_handoff(self, callback: Callable[[], None] | None) -> None:
        """When set, closing with physics destroys this window and calls callback."""
        self._background_handoff = callback

    def prepare_external_quit(self) -> None:
        """Allow the window to close without stopping a shared physics service."""
        self._force_quit = True
        self._background_handoff = None

    def _theme_for_physics(self) -> CursorTheme | None:
        current = self.theme_list.currentItem()
        theme_index = current.data(0, Qt.UserRole) if current else None
        if isinstance(theme_index, int) and 0 <= theme_index < len(self.themes):
            candidate = self.themes[theme_index]
            if theme_supports_physics(candidate) and self._theme_has_arrow_png(
                candidate
            ):
                return candidate

        selected = self.cursor_service.load_selected_theme()
        if (
            selected is not None
            and theme_supports_physics(selected)
            and self._theme_has_arrow_png(selected)
        ):
            return selected

        try:
            active = self.cursor_service.current_theme()
        except OSError:
            return None
        if theme_supports_physics(active) and self._theme_has_arrow_png(active):
            return active
        # Applying a custom theme rewrites the Windows scheme without is_custom.
        if not active.is_animated and self._theme_has_arrow_png(active):
            return active
        return None

    def _selected_theme(self) -> CursorTheme | None:
        current = self.theme_list.currentItem()
        theme_index = current.data(0, Qt.UserRole) if current else None
        if isinstance(theme_index, int) and 0 <= theme_index < len(self.themes):
            return self.themes[theme_index]
        return None

    def _attach_physics_checkbox(self, category_item: QTreeWidgetItem) -> None:
        item = QTreeWidgetItem()
        item.setFlags(Qt.ItemIsEnabled)
        category_item.insertChild(0, item)
        item.setSizeHint(0, self.physics_checkbox.sizeHint())
        self.theme_list.setItemWidget(item, 0, self.physics_checkbox)
        self._physics_tree_item = item
        self.physics_checkbox.show()

    def _detach_physics_checkbox(self) -> None:
        if self._physics_tree_item is not None:
            self.theme_list.removeItemWidget(self._physics_tree_item, 0)
            self._physics_tree_item = None
        self.physics_checkbox.setParent(self)
        self.physics_checkbox.hide()

    def _update_physics_controls(self, theme: CursorTheme | None) -> None:
        supported = theme is not None and theme_supports_physics(theme)
        if theme is not None and theme.is_animated and self.physics_service.is_running:
            self.physics_service.stop()
            self.physics_service.save_enabled(False)
            self._set_physics_checked(False)
            self._sync_tray_visibility()
        self.physics_checkbox.setEnabled(supported)
        if supported:
            self.physics_checkbox.setToolTip(self._physics_default_tooltip)
        elif theme is not None and theme.is_animated:
            self.physics_checkbox.setToolTip(
                "该主题由 Windows 原生播放 ANI，关闭 QMcursor 后仍会动画；"
                "它与需要托盘常驻的物理摇摆不能同时启用。"
            )
        else:
            self.physics_checkbox.setToolTip(
                "物理摇摆仅适用于「QMcursor 自制指针」。"
                "请先选择该分类下的主题后再启用。"
            )

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
        icon = app_icon()
        if not icon.isNull():
            return icon
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
        self._unload_heavy_ui()
        self.hide()
        self._tray.setIcon(self._tray_icon())
        self._tray.setToolTip("QMcursor · 物理摇摆运行中")
        self._tray.show()

    def _unload_heavy_ui(self) -> None:
        """Drop theme list / previews so tray-resident mode holds less RAM."""
        self.details.setRowCount(0)
        self._detach_physics_checkbox()
        self.theme_list.clear()
        self.themes.clear()
        app = QApplication.instance()
        if app is not None:
            app.sendPostedEvents(None, 0)
            app.processEvents()

    def _show_from_tray(self) -> None:
        if not self.themes:
            self._load_themes()
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
            handoff = self._background_handoff
            if handoff is not None:
                self._background_handoff = None
                self._tray.hide()
                self._unload_heavy_ui()
                event.accept()
                handoff()
                return
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
