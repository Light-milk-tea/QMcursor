"""Build the deterministic Origami & Wind Chime cursor theme.

The generated concept images are used as art direction only.  Every cursor is
redrawn with Pillow primitives so the complete set shares the same palette,
stroke width, geometry, and small-size readability.
"""

from __future__ import annotations

import math
import struct
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw


BASE = 128
SUPERSAMPLE = 4
SIZES = (24, 32, 48, 64)

NAVY = "#24324A"
BLUE = "#79BEE8"
RED = "#E85D4A"
CREAM = "#FFF8E8"
TRANSPARENT = (0, 0, 0, 0)

Point = tuple[float, float]
Painter = Callable[["Canvas"], None]


class Canvas:
    def __init__(self) -> None:
        side = BASE * SUPERSAMPLE
        self.image = Image.new("RGBA", (side, side), TRANSPARENT)
        self.draw = ImageDraw.Draw(self.image)

    @staticmethod
    def _point(point: Point) -> tuple[int, int]:
        return tuple(round(value * SUPERSAMPLE) for value in point)

    def polygon(
        self,
        points: list[Point],
        fill: str,
        *,
        outline: str = NAVY,
        width: float = 5,
    ) -> None:
        scaled = [self._point(point) for point in points]
        self.draw.polygon(scaled, fill=fill)
        if outline and width:
            self.draw.line(
                scaled + [scaled[0]],
                fill=outline,
                width=round(width * SUPERSAMPLE),
                joint="curve",
            )

    def line(
        self,
        points: list[Point],
        fill: str,
        width: float,
        *,
        joint: str = "curve",
    ) -> None:
        self.draw.line(
            [self._point(point) for point in points],
            fill=fill,
            width=round(width * SUPERSAMPLE),
            joint=joint,
        )

    def ellipse(
        self,
        box: tuple[float, float, float, float],
        *,
        fill: str | None = None,
        outline: str | None = NAVY,
        width: float = 5,
    ) -> None:
        scaled = tuple(round(value * SUPERSAMPLE) for value in box)
        self.draw.ellipse(
            scaled,
            fill=fill,
            outline=outline,
            width=round(width * SUPERSAMPLE),
        )

    def rounded_rectangle(
        self,
        box: tuple[float, float, float, float],
        radius: float,
        *,
        fill: str,
        outline: str = NAVY,
        width: float = 5,
    ) -> None:
        scaled = tuple(round(value * SUPERSAMPLE) for value in box)
        self.draw.rounded_rectangle(
            scaled,
            radius=round(radius * SUPERSAMPLE),
            fill=fill,
            outline=outline,
            width=round(width * SUPERSAMPLE),
        )

    def finish(self) -> Image.Image:
        return self.image.resize(
            (BASE, BASE),
            Image.Resampling.LANCZOS,
        )


def rotate(point: Point, angle: float, center: Point = (64, 64)) -> Point:
    radians = math.radians(angle)
    cosine, sine = math.cos(radians), math.sin(radians)
    x, y = point[0] - center[0], point[1] - center[1]
    return (
        center[0] + x * cosine - y * sine,
        center[1] + x * sine + y * cosine,
    )


def arrow_body(canvas: Canvas, *, compact: bool = False) -> None:
    if compact:
        body = [(9, 7), (78, 58), (55, 62), (72, 95), (57, 103), (40, 70), (20, 87)]
        fold = [(17, 17), (68, 55), (47, 58), (26, 72)]
    else:
        body = [(10, 7), (91, 68), (63, 72), (84, 110), (66, 119), (46, 80), (22, 101)]
        fold = [(18, 18), (80, 65), (53, 68), (28, 84)]
    canvas.polygon(body, CREAM, width=6)
    canvas.polygon(fold, BLUE, width=3.5)
    canvas.line([body[0], body[1]], NAVY, 5.5)


def paint_arrow(canvas: Canvas) -> None:
    arrow_body(canvas)


def paint_help(canvas: Canvas) -> None:
    arrow_body(canvas, compact=True)
    canvas.line([(84, 62), (101, 62), (108, 68), (108, 76), (96, 84), (96, 91)], NAVY, 8)
    canvas.ellipse((91, 101, 101, 111), fill=RED, width=3)


def spinner(canvas: Canvas, center: Point, radius: float, count: int = 6) -> None:
    cx, cy = center
    for index in range(count):
        angle = index * 360 / count
        outer = rotate((cx, cy - radius), angle, center)
        left = rotate((cx - 6, cy - radius + 13), angle, center)
        inner = rotate((cx, cy - radius + 22), angle, center)
        right = rotate((cx + 7, cy - radius + 11), angle, center)
        canvas.polygon(
            [outer, right, inner, left],
            BLUE if index % 2 == 0 else CREAM,
            width=3.5,
        )


def paint_app_starting(canvas: Canvas) -> None:
    arrow_body(canvas, compact=True)
    spinner(canvas, (95, 92), 27, 6)


def paint_wait(canvas: Canvas) -> None:
    spinner(canvas, (64, 64), 49, 8)
    canvas.ellipse((54, 54, 74, 74), fill=RED, width=4)


def paint_crosshair(canvas: Canvas) -> None:
    canvas.line([(64, 12), (64, 116)], NAVY, 7)
    canvas.line([(12, 64), (116, 64)], NAVY, 7)
    canvas.line([(64, 18), (64, 110)], CREAM, 2.5)
    canvas.line([(18, 64), (110, 64)], CREAM, 2.5)
    canvas.polygon([(64, 48), (80, 64), (64, 80), (48, 64)], BLUE, width=4)
    canvas.ellipse((59, 59, 69, 69), fill=RED, width=2)


def paint_ibeam(canvas: Canvas) -> None:
    canvas.line([(38, 16), (90, 16)], NAVY, 8)
    canvas.line([(64, 16), (64, 112)], NAVY, 8)
    canvas.line([(38, 112), (90, 112)], NAVY, 8)
    canvas.polygon([(38, 10), (52, 16), (38, 22)], RED, width=2.5)
    canvas.polygon([(90, 106), (76, 112), (90, 118)], BLUE, width=2.5)


def paint_pen(canvas: Canvas) -> None:
    canvas.polygon([(20, 102), (35, 70), (86, 19), (109, 42), (58, 93)], CREAM, width=5)
    canvas.polygon([(35, 70), (58, 93), (20, 102)], BLUE, width=4)
    canvas.polygon([(86, 19), (101, 11), (117, 27), (109, 42)], RED, width=4)
    canvas.line([(31, 89), (92, 29)], NAVY, 3.5)
    canvas.ellipse((22, 91, 31, 100), fill=NAVY, outline=NAVY, width=1)


def paint_no(canvas: Canvas) -> None:
    canvas.ellipse((18, 18, 110, 110), outline=NAVY, width=15)
    canvas.ellipse((25, 25, 103, 103), outline=BLUE, width=7)
    canvas.line([(27, 25), (104, 103)], NAVY, 20)
    canvas.line([(29, 27), (102, 101)], RED, 11)
    canvas.polygon([(16, 19), (37, 21), (25, 35)], CREAM, width=3)
    canvas.polygon([(111, 109), (90, 107), (103, 94)], CREAM, width=3)


def double_arrow(canvas: Canvas, angle: float) -> None:
    shaft = [rotate((64, 28), angle), rotate((64, 100), angle)]
    canvas.line(shaft, NAVY, 12)
    canvas.line(shaft, CREAM, 5)
    for tip_y, base_y in ((10, 35), (118, 93)):
        points = [(64, tip_y), (45, base_y), (57, base_y), (57, 52 if tip_y < 64 else 76),
                  (71, 52 if tip_y < 64 else 76), (71, base_y), (83, base_y)]
        canvas.polygon([rotate(point, angle) for point in points], BLUE, width=4)
    canvas.polygon(
        [rotate(point, angle) for point in [(64, 55), (73, 64), (64, 73), (55, 64)]],
        RED,
        width=3,
    )


def paint_size_ns(canvas: Canvas) -> None:
    double_arrow(canvas, 0)


def paint_size_we(canvas: Canvas) -> None:
    double_arrow(canvas, 90)


def paint_size_nwse(canvas: Canvas) -> None:
    double_arrow(canvas, -45)


def paint_size_nesw(canvas: Canvas) -> None:
    double_arrow(canvas, 45)


def paint_size_all(canvas: Canvas) -> None:
    canvas.line([(64, 19), (64, 109)], NAVY, 11)
    canvas.line([(19, 64), (109, 64)], NAVY, 11)
    canvas.line([(64, 23), (64, 105)], CREAM, 4)
    canvas.line([(23, 64), (105, 64)], CREAM, 4)
    for angle in (0, 90, 180, 270):
        points = [(64, 7), (48, 30), (57, 30), (57, 43), (71, 43), (71, 30), (80, 30)]
        canvas.polygon([rotate(point, angle) for point in points], BLUE, width=3.5)
    canvas.polygon([(64, 50), (78, 64), (64, 78), (50, 64)], RED, width=4)


def paint_up_arrow(canvas: Canvas) -> None:
    canvas.polygon(
        [(64, 8), (99, 48), (78, 44), (78, 111), (50, 111), (50, 44), (29, 48)],
        CREAM,
        width=6,
    )
    canvas.polygon([(64, 14), (91, 44), (70, 39), (64, 60), (58, 39), (37, 44)], BLUE, width=3.5)
    canvas.polygon([(50, 93), (64, 106), (78, 93), (78, 112), (50, 112)], RED, width=3)


def paint_hand(canvas: Canvas) -> None:
    canvas.rounded_rectangle((49, 9, 68, 77), 9, fill=CREAM, width=5)
    canvas.rounded_rectangle((67, 37, 84, 75), 8, fill=CREAM, width=5)
    canvas.rounded_rectangle((82, 43, 98, 77), 8, fill=CREAM, width=5)
    canvas.rounded_rectangle((96, 49, 111, 81), 7, fill=CREAM, width=5)
    canvas.polygon([(50, 62), (38, 49), (27, 55), (43, 82), (52, 103), (92, 106), (108, 79), (62, 69)], CREAM, width=5)
    canvas.polygon([(47, 94), (65, 103), (94, 96), (88, 119), (48, 119)], BLUE, width=4)
    canvas.polygon([(65, 103), (80, 96), (88, 119), (73, 112)], RED, width=3)


CURSORS: tuple[tuple[str, Painter, Point], ...] = (
    ("arrow", paint_arrow, (10, 7)),
    ("help", paint_help, (9, 7)),
    ("app_starting", paint_app_starting, (9, 7)),
    ("wait", paint_wait, (64, 64)),
    ("crosshair", paint_crosshair, (64, 64)),
    ("ibeam", paint_ibeam, (64, 64)),
    ("pen", paint_pen, (22, 98)),
    ("no", paint_no, (64, 64)),
    ("size_ns", paint_size_ns, (64, 64)),
    ("size_we", paint_size_we, (64, 64)),
    ("size_nwse", paint_size_nwse, (64, 64)),
    ("size_nesw", paint_size_nesw, (64, 64)),
    ("size_all", paint_size_all, (64, 64)),
    ("up_arrow", paint_up_arrow, (64, 8)),
    ("hand", paint_hand, (58, 9)),
)


def dib_data(image: Image.Image) -> bytes:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    xor_data = bytearray()
    and_data = bytearray()
    for y in range(height - 1, -1, -1):
        mask_row = bytearray((width + 7) // 8)
        for x in range(width):
            red, green, blue, alpha = rgba.getpixel((x, y))
            xor_data.extend((blue, green, red, alpha))
            if alpha < 8:
                mask_row[x // 8] |= 0x80 >> (x % 8)
        and_data.extend(mask_row)
        and_data.extend(b"\0" * ((4 - len(mask_row) % 4) % 4))
    header = struct.pack(
        "<IiiHHIIiiII",
        40,
        width,
        height * 2,
        1,
        32,
        0,
        len(xor_data),
        0,
        0,
        0,
        0,
    )
    return header + xor_data + and_data


def save_multi_cur(
    images: list[tuple[Image.Image, tuple[int, int]]],
    path: Path,
) -> None:
    payloads = [dib_data(image) for image, _hotspot in images]
    offset = 6 + 16 * len(images)
    entries = bytearray()
    for (image, hotspot), payload in zip(images, payloads, strict=True):
        entries.extend(
            struct.pack(
                "<BBBBHHII",
                0 if image.width == 256 else image.width,
                0 if image.height == 256 else image.height,
                0,
                0,
                hotspot[0],
                hotspot[1],
                len(payload),
                offset,
            )
        )
        offset += len(payload)
    path.write_bytes(
        struct.pack("<HHH", 0, 2, len(images))
        + entries
        + b"".join(payloads)
    )


def render(painter: Painter) -> Image.Image:
    canvas = Canvas()
    painter(canvas)
    return canvas.finish()


def build(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    previews: list[Image.Image] = []
    for name, painter, hotspot in CURSORS:
        artwork = render(painter)
        artwork.save(output / f"{name}.png")
        previews.append(artwork)
        cursors = []
        for size in SIZES:
            image = artwork.resize((size, size), Image.Resampling.LANCZOS)
            scaled_hotspot = (
                min(size - 1, round(hotspot[0] * size / BASE)),
                min(size - 1, round(hotspot[1] * size / BASE)),
            )
            cursors.append((image, scaled_hotspot))
        save_multi_cur(cursors, output / f"{name}.cur")

    sheet = Image.new("RGBA", (BASE * 4, BASE * 4), "#F5F7FA")
    for index, preview in enumerate(previews):
        sheet.alpha_composite(
            preview,
            ((index % 4) * BASE, (index // 4) * BASE),
        )
    sheet.convert("RGB").save(output / "concept.png")


if __name__ == "__main__":
    build(
        Path(__file__).resolve().parents[1]
        / "src"
        / "arkcursor"
        / "themes"
        / "origami_wind_chime"
    )
