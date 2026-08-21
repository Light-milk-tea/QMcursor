"""Native Windows cursor preview widget, including animated cursors."""

from __future__ import annotations

import ctypes
import struct
from ctypes import wintypes
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

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
            # Match main window page background (#F4F5F7) for preview cells.
            background = b"\xF7\xF5\xF4\xFF" * (size * size)
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

    def closeEvent(self, event) -> None:
        self._release_cursor()
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
