"""Native Windows cursor preview widget, including animated cursors."""

from __future__ import annotations

import ctypes
import struct
from ctypes import wintypes
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from qmcursor.models.theme import CURSOR_ROLES, ROLE_LABELS, CursorTheme

SYSTEM_CURSOR_IDS = {
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

DI_NORMAL = 0x0003
DIB_RGB_COLORS = 0
BI_RGB = 0


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class RGBQUAD(ctypes.Structure):
    _fields_ = [
        ("rgbBlue", wintypes.BYTE),
        ("rgbGreen", wintypes.BYTE),
        ("rgbRed", wintypes.BYTE),
        ("rgbReserved", wintypes.BYTE),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", RGBQUAD * 1),
    ]


def read_ani_timing(path: str) -> tuple[int, int]:
    """Return ANI step count and approximate frame interval in milliseconds."""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return 1, 100

    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"ACON":
        return 1, 100

    offset = 12
    while offset + 8 <= len(data):
        chunk_id = data[offset : offset + 4]
        chunk_size = struct.unpack_from("<I", data, offset + 4)[0]
        chunk_start = offset + 8
        if (
            chunk_id == b"anih"
            and chunk_size >= 36
            and chunk_start + 36 <= len(data)
        ):
            values = struct.unpack_from("<9I", data, chunk_start)
            frame_count = max(1, values[2] or values[1])
            jiffies = values[7] or 6
            interval = max(40, round(jiffies * 1000 / 60))
            return frame_count, interval
        offset = chunk_start + chunk_size + (chunk_size % 2)

    return 1, 100


class CursorPreview(QWidget):
    """Render a cursor handle into a small native DIB."""

    def __init__(
        self,
        role: str,
        cursor_path: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(58, 48)
        self.setToolTip("动态指针会自动播放")
        self._cursor_handle: int | None = None
        self._owns_handle = False
        self._frame = 0
        self._frame_count = 1
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._next_frame)

        self._load_cursor(role, cursor_path)
        if cursor_path.lower().endswith(".ani"):
            self._frame_count, interval = read_ani_timing(cursor_path)
            if self._frame_count > 1:
                self._timer.start(interval)

    def _load_cursor(self, role: str, cursor_path: str) -> None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        if cursor_path:
            load_from_file = user32.LoadCursorFromFileW
            load_from_file.argtypes = [wintypes.LPCWSTR]
            load_from_file.restype = wintypes.HANDLE
            handle = load_from_file(cursor_path)
            self._owns_handle = bool(handle)
        else:
            load_system = user32.LoadCursorW
            load_system.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
            load_system.restype = wintypes.HANDLE
            cursor_id = SYSTEM_CURSOR_IDS.get(role, SYSTEM_CURSOR_IDS["Arrow"])
            handle = load_system(None, ctypes.c_void_p(cursor_id))
            self._owns_handle = False

        self._cursor_handle = int(handle) if handle else None

    def _next_frame(self) -> None:
        self._frame = (self._frame + 1) % self._frame_count
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        if not self._cursor_handle:
            painter.setPen(Qt.gray)
            painter.drawText(self.rect(), Qt.AlignCenter, "无法预览")
            return

        image = self._render_frame(40)
        if image is None:
            painter.setPen(Qt.gray)
            painter.drawText(self.rect(), Qt.AlignCenter, "无法预览")
            return

        pixmap = QPixmap.fromImage(image)
        left = (self.width() - pixmap.width()) // 2
        top = (self.height() - pixmap.height()) // 2
        painter.drawPixmap(left, top, pixmap)

    def _render_frame(self, size: int) -> QImage | None:
        gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        user32 = ctypes.WinDLL("user32", use_last_error=True)

        gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
        gdi32.CreateCompatibleDC.restype = wintypes.HDC
        gdi32.CreateDIBSection.argtypes = [
            wintypes.HDC,
            ctypes.POINTER(BITMAPINFO),
            wintypes.UINT,
            ctypes.POINTER(ctypes.c_void_p),
            wintypes.HANDLE,
            wintypes.DWORD,
        ]
        gdi32.CreateDIBSection.restype = wintypes.HBITMAP
        gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
        gdi32.SelectObject.restype = wintypes.HGDIOBJ
        gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
        gdi32.DeleteObject.restype = wintypes.BOOL
        gdi32.DeleteDC.argtypes = [wintypes.HDC]
        gdi32.DeleteDC.restype = wintypes.BOOL
        user32.DrawIconEx.argtypes = [
            wintypes.HDC,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
            wintypes.HBRUSH,
            wintypes.UINT,
        ]
        user32.DrawIconEx.restype = wintypes.BOOL

        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = size
        info.bmiHeader.biHeight = -size
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = BI_RGB

        dc = gdi32.CreateCompatibleDC(None)
        bits = ctypes.c_void_p()
        bitmap = gdi32.CreateDIBSection(
            dc, ctypes.byref(info), DIB_RGB_COLORS, ctypes.byref(bits), None, 0
        )
        if not dc or not bitmap or not bits.value:
            if bitmap:
                gdi32.DeleteObject(bitmap)
            if dc:
                gdi32.DeleteDC(dc)
            return None

        old_bitmap = gdi32.SelectObject(dc, bitmap)
        try:
            # Match preview-card background (#FAFBFC) so the glyph sits on the tile.
            background = b"\xFC\xFB\xFA\xFF" * (size * size)
            ctypes.memmove(bits, background, len(background))
            drawn = user32.DrawIconEx(
                dc,
                0,
                0,
                self._cursor_handle,
                size,
                size,
                self._frame,
                None,
                DI_NORMAL,
            )
            if not drawn:
                return None
            data = bytearray(ctypes.string_at(bits, size * size * 4))
            # Classic monochrome .cur files clear the DIB alpha channel when
            # DrawIconEx applies their AND/XOR masks. Qt then treats the whole
            # preview as transparent, so make this already-composited image
            # fully opaque.
            data[3::4] = b"\xFF" * (size * size)
            return QImage(
                bytes(data),
                size,
                size,
                size * 4,
                QImage.Format_ARGB32,
            ).copy()
        finally:
            gdi32.SelectObject(dc, old_bitmap)
            gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(dc)

    def shutdown(self) -> None:
        self._timer.stop()
        self._release_cursor()

    def closeEvent(self, event) -> None:
        self.shutdown()
        super().closeEvent(event)

    def _release_cursor(self) -> None:
        if self._cursor_handle and self._owns_handle:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.DestroyCursor.argtypes = [wintypes.HANDLE]
            user32.DestroyCursor.restype = wintypes.BOOL
            user32.DestroyCursor(self._cursor_handle)
        self._cursor_handle = None

    def __del__(self) -> None:
        try:
            self._release_cursor()
        except Exception:
            pass


class RolePreviewCard(QFrame):
    """One cursor role: live preview plus a short label."""

    def __init__(
        self,
        role: str,
        cursor_path: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("previewCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        preview = CursorPreview(role, cursor_path, self)
        self._preview = preview

        title = QLabel(ROLE_LABELS.get(role, role))
        title.setObjectName("roleTitle")
        title.setAlignment(Qt.AlignCenter)

        display_path = Path(cursor_path).name if cursor_path else "系统默认"
        file_label = QLabel(display_path)
        file_label.setObjectName("roleFile")
        file_label.setAlignment(Qt.AlignCenter)
        file_label.setToolTip(cursor_path or "由 Windows 使用默认指针")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(6)
        layout.addWidget(preview, 0, Qt.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(file_label)

    def shutdown(self) -> None:
        self._preview.shutdown()


class ThemePreviewPanel(QWidget):
    """Scrollable preview gallery for every cursor role in a theme."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._columns = 3
        self._cards: list[RolePreviewCard] = []

        self._empty = QLabel("从左侧选择一套指针方案，即可预览每种用途。")
        self._empty.setObjectName("emptyState")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setWordWrap(True)

        self._container = QWidget()
        self._grid = QGridLayout(self._container)
        self._grid.setContentsMargins(12, 8, 12, 12)
        self._grid.setSpacing(10)
        self._grid.setAlignment(Qt.AlignTop)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setWidget(self._container)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._empty)
        layout.addWidget(self._scroll, 1)
        self.show_empty()

    def show_empty(self, message: str | None = None) -> None:
        self.clear()
        if message:
            self._empty.setText(message)
        self._empty.show()
        self._scroll.hide()

    def show_theme(self, theme: CursorTheme, preview_size: int) -> None:
        self.clear()
        preview_cursors = theme.resolved_cursors(preview_size)
        for index, role in enumerate(CURSOR_ROLES):
            card = RolePreviewCard(role, preview_cursors[role], self._container)
            row, column = divmod(index, self._columns)
            self._grid.addWidget(card, row, column)
            self._cards.append(card)
        self._empty.hide()
        self._scroll.show()

    def clear(self) -> None:
        for card in self._cards:
            card.shutdown()
            self._grid.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        width = self._scroll.viewport().width() if self._scroll.isVisible() else self.width()
        columns = 4 if width >= 640 else 3 if width >= 440 else 2
        if columns != self._columns and self._cards:
            self._columns = columns
            self._reflow()
        else:
            self._columns = columns

    def _reflow(self) -> None:
        for card in self._cards:
            self._grid.removeWidget(card)
        for index, card in enumerate(self._cards):
            row, column = divmod(index, self._columns)
            self._grid.addWidget(card, row, column)
