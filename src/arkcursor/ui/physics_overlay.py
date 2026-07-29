"""Click-through overlay that draws a soft-follow swaying cursor sprite."""

from __future__ import annotations

import ctypes
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPointF, QRect, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QCursor,
    QGuiApplication,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

user32 = ctypes.windll.user32
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
# Re-assert topmost periodically so tray menus / toasts cannot bury the overlay.
_TOPMOST_REASSERT_TICKS = 8
DWMWA_EXCLUDED_FROM_PEEK = 12

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
    # Flexible hanging cord + charm (Verlet rope).
    cord_segments: int = 7
    cord_length_ratio: float = 1.35
    cord_gravity: float = 0.55
    cord_damping: float = 0.985
    cord_iterations: int = 4
    cord_width: float = 1.7


@dataclass(frozen=True, slots=True)
class RoleSprite:
    pixmap: QPixmap
    hotspot: tuple[float, float]
    scale: float
    # Cord attach point as fractions of the sprite (from opaque geometry).
    hang: tuple[float, float] = (0.5, 0.94)


@dataclass(frozen=True, slots=True)
class PendantSprite:
    """Optional charm drawn at the end of a flexible hanging cord."""

    pixmap: QPixmap
    pivot: tuple[float, float]
    height_ratio: float = 0.85


class CordState:
    """Multi-point hanging cord simulated with Verlet integration."""

    def __init__(self, segments: int) -> None:
        count = max(3, segments + 1)
        self.x = [0.0] * count
        self.y = [0.0] * count
        self.px = [0.0] * count
        self.py = [0.0] * count
        self.initialized = False

    def reset(self, anchor_x: float, anchor_y: float, spacing: float) -> None:
        for i in range(len(self.x)):
            self.x[i] = anchor_x
            self.y[i] = anchor_y + i * spacing
            self.px[i] = self.x[i]
            self.py[i] = self.y[i]
        self.initialized = True

    def translate(self, dx: float, dy: float) -> None:
        """Move the whole cord rigidly (used when hang point retargets)."""
        if not self.initialized:
            return
        for i in range(len(self.x)):
            self.x[i] += dx
            self.y[i] += dy
            self.px[i] += dx
            self.py[i] += dy

    def pin_and_step(
        self,
        anchor_x: float,
        anchor_y: float,
        *,
        spacing: float,
        gravity: float,
        damping: float,
        iterations: int,
    ) -> None:
        if not self.initialized:
            self.reset(anchor_x, anchor_y, spacing)
            return

        n = len(self.x)
        self.x[0] = anchor_x
        self.y[0] = anchor_y
        self.px[0] = anchor_x
        self.py[0] = anchor_y

        for i in range(1, n):
            cx = self.x[i]
            cy = self.y[i]
            vx = (cx - self.px[i]) * damping
            vy = (cy - self.py[i]) * damping
            self.px[i] = cx
            self.py[i] = cy
            self.x[i] = cx + vx
            self.y[i] = cy + vy + gravity

        for _ in range(max(1, iterations)):
            self.x[0] = anchor_x
            self.y[0] = anchor_y
            for i in range(1, n):
                dx = self.x[i] - self.x[i - 1]
                dy = self.y[i] - self.y[i - 1]
                dist = math.hypot(dx, dy) or 0.0001
                factor = (spacing - dist) / dist
                # Anchor is fixed; bias correction onto the free end.
                if i == 1:
                    ox = dx * factor
                    oy = dy * factor
                    self.x[i] += ox
                    self.y[i] += oy
                else:
                    ox = dx * factor * 0.5
                    oy = dy * factor * 0.5
                    self.x[i - 1] -= ox
                    self.y[i - 1] -= oy
                    self.x[i] += ox
                    self.y[i] += oy
            self.x[0] = anchor_x
            self.y[0] = anchor_y


class PhysicsState:
    def __init__(self, x: float, y: float, cord_segments: int = 7) -> None:
        self.x = x
        self.y = y
        self.angle = 0.0
        self.angular_vel = 0.0
        self.prev_mx = x
        self.prev_my = y
        self.cord = CordState(cord_segments)


def ensure_overlay_topmost(hwnd: int) -> None:
    """Keep the fake cursor above other topmost UI (tray menus, balloons, etc.).

    Real OS cursors paint above every window; our sprite lives in a normal
    topmost layered window, so competitors can cover it unless we re-assert.
    """
    if hwnd == 0:
        return
    user32.SetWindowPos(
        hwnd,
        HWND_TOPMOST,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
    )


def _exclude_from_aero_peek(hwnd: int) -> None:
    """Stop Win+D / taskbar peek from swallowing the overlay."""
    if hwnd == 0:
        return
    try:
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_EXCLUDED_FROM_PEEK,
            ctypes.byref(value),
            ctypes.sizeof(value),
        )
    except (AttributeError, OSError, ValueError):
        pass


def set_click_through(hwnd: int) -> None:
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(
        hwnd,
        GWL_EXSTYLE,
        style
        | WS_EX_LAYERED
        | WS_EX_TRANSPARENT
        | WS_EX_TOOLWINDOW
        | WS_EX_TOPMOST,
    )
    _exclude_from_aero_peek(hwnd)
    ensure_overlay_topmost(hwnd)


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


def hang_fraction(image: QImage, kind: str) -> tuple[float, float]:
    """Cord attach point from opaque bounds (fractions of width/height).

    Most roles hang from the bottom-center of the drawn art. Pen-like
    southwest tips hang from the body center so the charm is not glued to
    the writing point.
    """
    if image.width() <= 0 or image.height() <= 0:
        return (0.5, 0.94)

    source = image
    if source.format() != QImage.Format.Format_ARGB32:
        source = source.convertToFormat(QImage.Format.Format_ARGB32)

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
    for y in range(height):
        row = y * bytes_per_line
        for x in range(width):
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

    if max_x < 0:
        return (0.5, 0.94)

    box_w = max(max_x - min_x, 1)
    box_h = max(max_y - min_y, 1)
    if kind == "southwest":
        hx = min_x + box_w * 0.55
        hy = min_y + box_h * 0.38
    elif kind == "northwest":
        hx = min_x + box_w * 0.58
        hy = max_y - box_h * 0.10
    elif kind == "north":
        hx = min_x + box_w * 0.50
        hy = max_y - box_h * 0.08
    else:
        hx = min_x + box_w * 0.50
        hy = max_y - box_h * 0.05

    return (
        hx / max(width - 1, 1),
        hy / max(height - 1, 1),
    )


def _smooth_cord_path(points: list[QPointF]) -> QPainterPath:
    """Build a cubic path through cord points for a flowing curve."""
    path = QPainterPath()
    if not points:
        return path
    if len(points) == 1:
        path.moveTo(points[0])
        return path
    if len(points) == 2:
        path.moveTo(points[0])
        path.lineTo(points[1])
        return path

    path.moveTo(points[0])
    for i in range(1, len(points) - 1):
        mid = QPointF(
            (points[i].x() + points[i + 1].x()) * 0.5,
            (points[i].y() + points[i + 1].y()) * 0.5,
        )
        path.quadTo(points[i], mid)
    path.quadTo(points[-2], points[-1])
    return path


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
        self._pendant: PendantSprite | None = None
        self._pendant_scaled: QPixmap | None = None
        self._cursor_size = 48
        active = catalog["Arrow"]
        self.cfg.scale = active.scale
        self.cfg.hotspot = active.hotspot
        self._hang = active.hang
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
        self.state = PhysicsState(
            float(pos.x()),
            float(pos.y()),
            self.cfg.cord_segments,
        )

        self._hwnd = 0
        self._topmost_tick = 0

        self._timer = QTimer(self)
        # 16ms (~60 FPS) is enough for sway and uses less CPU than 8ms.
        self._timer.setInterval(16)
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
        edge = max(self._scaled.width(), self._scaled.height(), 1)
        self._cursor_size = max(8, int(edge))
        self._rebuild_pendant_scaled()

    def set_pendant(
        self,
        pendant: PendantSprite | None,
        *,
        cursor_size: int | None = None,
    ) -> None:
        self._pendant = pendant
        if cursor_size is not None:
            self._cursor_size = max(8, int(cursor_size))
        self._rebuild_pendant_scaled()
        self.state.cord.initialized = False
        self.update()

    def set_role(self, role: str) -> None:
        if role not in self._catalog:
            role = "Arrow"
        self._apply_role(role, force=False)

    def reset_physics(self) -> None:
        pos = QCursor.pos()
        self.state = PhysicsState(
            float(pos.x()),
            float(pos.y()),
            self.cfg.cord_segments,
        )

    def _apply_role(self, role: str, *, force: bool) -> None:
        if not force and role == self._role:
            return
        previous_anchor = None
        if (
            self._pendant_scaled is not None
            and self.state.cord.initialized
            and self._scaled is not None
        ):
            previous_anchor = self._anchor_screen()

        entry = self._catalog[role]
        self._role = role
        self._sprite = entry.pixmap
        self.cfg.scale = entry.scale
        self.cfg.hotspot = entry.hotspot
        self._hang = entry.hang
        self._rebuild_scaled()

        if previous_anchor is not None:
            # Retarget hang point without yanking the flexible cord.
            new_anchor = self._anchor_screen()
            self.state.cord.translate(
                new_anchor[0] - previous_anchor[0],
                new_anchor[1] - previous_anchor[1],
            )
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

    def _rebuild_pendant_scaled(self) -> None:
        pendant = self._pendant
        if pendant is None:
            self._pendant_scaled = None
            return
        height = max(14, int(self._cursor_size * pendant.height_ratio))
        width = max(
            8,
            int(pendant.pixmap.width() * (height / max(pendant.pixmap.height(), 1))),
        )
        self._pendant_scaled = pendant.pixmap.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def _anchor_screen(self) -> tuple[float, float]:
        """World-space hang point on the current role sprite.

        Derived from opaque art (`hang`) relative to the click hotspot, so each
        role looks attached naturally. Role swaps translate the whole cord
        rigidly in `_apply_role` to avoid a yank.
        """
        pixmap = self._scaled
        hotspot_x = pixmap.width() * self.cfg.hotspot[0]
        hotspot_y = pixmap.height() * self.cfg.hotspot[1]
        local_x = pixmap.width() * self._hang[0] - hotspot_x
        local_y = pixmap.height() * self._hang[1] - hotspot_y
        cos_a = math.cos(self.state.angle)
        sin_a = math.sin(self.state.angle)
        ax = self.state.x + local_x * cos_a - local_y * sin_a
        ay = self.state.y + local_x * sin_a + local_y * cos_a
        return ax, ay

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._hwnd = int(self.winId())
        set_click_through(self._hwnd)

    def _reassert_topmost_if_needed(self) -> None:
        self._topmost_tick += 1
        if self._topmost_tick < _TOPMOST_REASSERT_TICKS:
            return
        self._topmost_tick = 0
        hwnd = self._hwnd or int(self.winId())
        self._hwnd = hwnd
        ensure_overlay_topmost(hwnd)

    def _tick(self) -> None:
        self._reassert_topmost_if_needed()

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
            state.cord.initialized = False
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

        if self._pendant_scaled is not None:
            anchor_x, anchor_y = self._anchor_screen()
            spacing = max(
                3.0,
                (self._cursor_size * cfg.cord_length_ratio)
                / max(cfg.cord_segments, 1),
            )
            state.cord.pin_and_step(
                anchor_x,
                anchor_y,
                spacing=spacing,
                gravity=cfg.cord_gravity,
                damping=cfg.cord_damping,
                iterations=cfg.cord_iterations,
            )

        self.update()

    def _draw_cord_and_charm(
        self,
        painter: QPainter,
        origin_x: float,
        origin_y: float,
    ) -> None:
        pendant = self._pendant_scaled
        charm = self._pendant
        if pendant is None or charm is None or not self.state.cord.initialized:
            return

        points = [
            QPointF(x - origin_x, y - origin_y)
            for x, y in zip(self.state.cord.x, self.state.cord.y, strict=True)
        ]
        path = _smooth_cord_path(points)

        # Soft gold cord with a light highlight — reads as a flexible line.
        base_width = max(1.2, self.cfg.cord_width * (self._cursor_size / 48.0))
        shadow = QPen(QColor(60, 35, 20, 90), base_width + 1.4)
        shadow.setCapStyle(Qt.PenCapStyle.RoundCap)
        shadow.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.strokePath(path, shadow)

        cord = QPen(QColor(232, 190, 96, 235), base_width)
        cord.setCapStyle(Qt.PenCapStyle.RoundCap)
        cord.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.strokePath(path, cord)

        highlight = QPen(QColor(255, 240, 190, 160), max(0.8, base_width * 0.45))
        highlight.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.strokePath(path, highlight)

        # Tiny beads along the curve for chain glitter without rigid links.
        bead_color = QColor(244, 205, 110, 220)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bead_color)
        for i, point in enumerate(points[1:-1], start=1):
            if i % 2 == 0:
                continue
            radius = max(1.1, base_width * 0.85)
            painter.drawEllipse(point, radius, radius)

        tip = points[-1]
        prev = points[-2]
        angle = math.degrees(math.atan2(tip.y() - prev.y(), tip.x() - prev.x()))
        # Charm art hangs "down"; rotate from +Y so tip tangent feels natural.
        hang_angle = angle - 90.0
        pivot_x = pendant.width() * charm.pivot[0]
        pivot_y = pendant.height() * charm.pivot[1]

        painter.save()
        painter.translate(tip)
        painter.rotate(hang_angle)
        painter.drawPixmap(QPointF(-pivot_x, -pivot_y), pendant)
        painter.restore()

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
        origin_x = float(origin.x())
        origin_y = float(origin.y())

        if self._pendant_scaled is not None:
            self._draw_cord_and_charm(painter, origin_x, origin_y)

        painter.translate(
            self.state.x - origin_x,
            self.state.y - origin_y,
        )
        painter.rotate(math.degrees(self.state.angle))
        painter.drawPixmap(QPointF(-hotspot_x, -hotspot_y), pixmap)
        painter.end()
