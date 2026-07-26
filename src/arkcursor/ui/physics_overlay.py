"""Click-through overlay that draws a soft-follow swaying cursor sprite."""

from __future__ import annotations

import ctypes
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPointF, QRect, Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

user32 = ctypes.windll.user32
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080

# Matches generate-qmcursor-theme hotspot kinds.
ROLE_HOTSPOT_KIND = {
    "Arrow": "northwest",
    "Help": "northwest",
    "AppStarting": "northwest",
    "Wait": "center",
    "Crosshair": "center",
    "IBeam": "center",
    "NWPen": "southwest",
    "No": "center",
    "SizeNS": "center",
    "SizeWE": "center",
    "SizeNWSE": "center",
    "SizeNESW": "center",
    "SizeAll": "center",
    "UpArrow": "north",
    "Hand": "north",
}

RoleResolver = Callable[[], tuple[str, bool]]


@dataclass
class PhysicsConfig:
    stiffness_far: float = 0.55
    stiffness_mid: float = 0.38
    stiffness_near: float = 0.22
    angle_stiffness: float = 0.18
    angle_damping: float = 0.82
    velocity_to_angle: float = 0.0024
    max_angle: float = 0.55
    scale: float = 0.28
    hotspot: tuple[float, float] = (0.12, 0.08)


@dataclass(frozen=True, slots=True)
class RoleSprite:
    pixmap: QPixmap
    hotspot: tuple[float, float]
    scale: float


class PhysicsState:
    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y
        self.angle = 0.0
        self.angular_vel = 0.0
        self.prev_mx = x
        self.prev_my = y


def set_click_through(hwnd: int) -> None:
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(
        hwnd,
        GWL_EXSTYLE,
        style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW,
    )


def load_sprite(path: Path) -> QPixmap:
    image = QImage(str(path))
    if image.isNull():
        raise ValueError(f"无法加载指针图片：{path}")
    if image.format() != QImage.Format.Format_ARGB32:
        image = image.convertToFormat(QImage.Format.Format_ARGB32)
    return QPixmap.fromImage(image)


def resolve_cursor_image_path(cursor_path: str) -> Path | None:
    """Prefer a sibling PNG for a cursor file; fall back to the path itself."""
    if not cursor_path:
        return None
    path = Path(cursor_path)
    if path.suffix.lower() == ".png" and path.is_file():
        return path
    sibling = path.with_suffix(".png")
    if sibling.is_file():
        return sibling
    if path.is_file():
        return path
    return None


def resolve_arrow_image_path(arrow_path: str) -> Path | None:
    """Backward-compatible alias for Arrow path resolution."""
    return resolve_cursor_image_path(arrow_path)


def hotspot_fraction(image: QImage, kind: str) -> tuple[float, float]:
    """Compute hotspot as fractions of width/height from opaque pixels.

    Scans a downscaled ARGB32 buffer via raw bytes — much faster than
    per-pixel QImage.pixel()/QColor calls on large theme PNGs.
    """
    if image.width() <= 0 or image.height() <= 0:
        return (0.5, 0.5)

    source = image
    if source.format() != QImage.Format.Format_ARGB32:
        source = source.convertToFormat(QImage.Format.Format_ARGB32)

    # Fractions are scale-invariant; keep the scan under ~64px.
    max_edge = max(source.width(), source.height())
    if max_edge > 64:
        work = source.scaled(
            64,
            64,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        if work.format() != QImage.Format.Format_ARGB32:
            work = work.convertToFormat(QImage.Format.Format_ARGB32)
    else:
        work = source

    width = work.width()
    height = work.height()
    bytes_per_line = work.bytesPerLine()
    raw = memoryview(work.constBits()).cast("B")

    min_x = width
    min_y = height
    max_x = -1
    max_y = -1
    best_nw = None
    best_nw_score = None
    best_sw = None
    best_sw_score = None

    for y in range(height):
        row = y * bytes_per_line
        for x in range(width):
            # Little-endian ARGB32 is stored as B,G,R,A.
            if raw[row + x * 4 + 3] <= 16:
                continue
            if x < min_x:
                min_x = x
            if y < min_y:
                min_y = y
            if x > max_x:
                max_x = x
            if y > max_y:
                max_y = y
            nw_score = (x + y, y)
            if best_nw_score is None or nw_score < best_nw_score:
                best_nw_score = nw_score
                best_nw = (x, y)
            sw_score = (x + height - 1 - y, x)
            if best_sw_score is None or sw_score < best_sw_score:
                best_sw_score = sw_score
                best_sw = (x, y)

    if max_x < 0 or best_nw is None or best_sw is None:
        return (0.5, 0.5)

    if kind == "center":
        hx = (min_x + max_x) / 2
        hy = (min_y + max_y) / 2
    elif kind == "southwest":
        hx, hy = best_sw
    elif kind == "north":
        top = min_y
        band_limit = top + max(2, height // 50)
        band_min = width
        band_max = -1
        for y in range(top, min(height, band_limit + 1)):
            row = y * bytes_per_line
            for x in range(width):
                if raw[row + x * 4 + 3] <= 16:
                    continue
                if x < band_min:
                    band_min = x
                if x > band_max:
                    band_max = x
        if band_max < 0:
            hx, hy = best_nw
        else:
            hx = (band_min + band_max) / 2
            hy = float(top)
    else:
        # northwest (default)
        hx, hy = best_nw

    return (
        hx / max(width - 1, 1),
        hy / max(height - 1, 1),
    )


class PhysicsOverlay(QWidget):
    def __init__(
        self,
        catalog: dict[str, RoleSprite],
        cfg: PhysicsConfig | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if "Arrow" not in catalog:
            raise ValueError("物理指针目录必须包含 Arrow")
        self.cfg = cfg or PhysicsConfig()
        self._catalog = catalog
        self._role = "Arrow"
        self._role_resolver: RoleResolver | None = None
        self._drawing_enabled = True
        active = catalog["Arrow"]
        self.cfg.scale = active.scale
        self.cfg.hotspot = active.hotspot
        self._sprite = active.pixmap
        self._scaled = active.pixmap
        self._rebuild_scaled()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        screen = QGuiApplication.primaryScreen()
        geo = screen.virtualGeometry() if screen else QRect(0, 0, 1920, 1080)
        self.setGeometry(geo)

        pos = QCursor.pos()
        self.state = PhysicsState(float(pos.x()), float(pos.y()))

        self._timer = QTimer(self)
        self._timer.setInterval(8)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_role_resolver(self, resolver: RoleResolver | None) -> None:
        self._role_resolver = resolver

    def set_catalog(self, catalog: dict[str, RoleSprite]) -> None:
        if "Arrow" not in catalog:
            raise ValueError("物理指针目录必须包含 Arrow")
        self._catalog = catalog
        role = self._role if self._role in catalog else "Arrow"
        self._apply_role(role, force=True)

    def set_role(self, role: str) -> None:
        if role not in self._catalog:
            role = "Arrow"
        self._apply_role(role, force=False)

    def reset_physics(self) -> None:
        pos = QCursor.pos()
        self.state = PhysicsState(float(pos.x()), float(pos.y()))

    def _apply_role(self, role: str, *, force: bool) -> None:
        if not force and role == self._role:
            return
        entry = self._catalog[role]
        self._role = role
        self._sprite = entry.pixmap
        self.cfg.scale = entry.scale
        self.cfg.hotspot = entry.hotspot
        self._rebuild_scaled()
        self.update()

    def _rebuild_scaled(self) -> None:
        width = max(8, int(self._sprite.width() * self.cfg.scale))
        height = max(8, int(self._sprite.height() * self.cfg.scale))
        self._scaled = self._sprite.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        set_click_through(int(self.winId()))

    def _tick(self) -> None:
        if self._role_resolver is not None:
            role, showing = self._role_resolver()
            previous_drawing = self._drawing_enabled
            self._drawing_enabled = showing
            if showing:
                self.set_role(role)
            elif previous_drawing:
                # Clear the last frame when the OS hides the cursor.
                self.update()

        mouse = QCursor.pos()
        mx = float(mouse.x())
        my = float(mouse.y())
        state = self.state
        cfg = self.cfg

        vx = mx - state.prev_mx
        vy = my - state.prev_my
        state.prev_mx = mx
        state.prev_my = my
        speed = math.hypot(vx, vy)

        if not self._drawing_enabled:
            # Keep the soft-follow target glued while hidden to avoid a jump.
            state.x = mx
            state.y = my
            state.angle = 0.0
            state.angular_vel = 0.0
            return

        dx = mx - state.x
        dy = my - state.y
        dist = math.hypot(dx, dy)
        if dist > 80:
            stiffness = cfg.stiffness_far
        elif dist > 24:
            stiffness = cfg.stiffness_mid
        else:
            stiffness = cfg.stiffness_near
        state.x += dx * stiffness
        state.y += dy * stiffness

        impulse = (-vx * cfg.velocity_to_angle) + (
            vy * cfg.velocity_to_angle * 0.35
        )
        state.angular_vel += impulse
        state.angular_vel += -state.angle * cfg.angle_stiffness
        state.angular_vel *= cfg.angle_damping
        state.angle += state.angular_vel
        state.angle = max(-cfg.max_angle, min(cfg.max_angle, state.angle))
        if speed < 0.15 and abs(state.angle) < 0.01:
            state.angle = 0.0
            state.angular_vel = 0.0

        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        if not self._drawing_enabled:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        pixmap = self._scaled
        hotspot_x = pixmap.width() * self.cfg.hotspot[0]
        hotspot_y = pixmap.height() * self.cfg.hotspot[1]
        origin = self.geometry().topLeft()
        painter.translate(
            self.state.x - origin.x(),
            self.state.y - origin.y(),
        )
        painter.rotate(math.degrees(self.state.angle))
        painter.drawPixmap(QPointF(-hotspot_x, -hotspot_y), pixmap)
        painter.end()
