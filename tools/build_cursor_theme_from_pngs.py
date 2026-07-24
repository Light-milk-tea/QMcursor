"""Build and validate a 15-role ArkCursor theme from numbered PNG files."""

from __future__ import annotations

import json
import struct
from collections import deque
from pathlib import Path

from PIL import Image

from build_origami_cursor_theme import save_multi_cur
from build_generated_cursor_trial import crop_visible


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "名侦探光之美少女"
OUTPUT = ROOT / "src" / "arkcursor" / "themes" / "detective_precure"
THEME_NAME = "名侦探光之美少女"
SIZES = (32, 48, 64, 96, 128, 192, 256)

CURSORS = (
    ("01-normal-select.png", "Arrow", "arrow", "top_left"),
    ("02-help-select.png", "Help", "help", "top_left"),
    ("03-working-in-background.png", "AppStarting", "app_starting", "top_left"),
    ("04-busy.png", "Wait", "wait", "center"),
    ("05-precision-select.png", "Crosshair", "crosshair", "center"),
    ("06-text-select.png", "IBeam", "ibeam", "center"),
    ("07-handwriting.png", "NWPen", "pen", "bottom_left"),
    ("08-unavailable.png", "No", "no", "center"),
    ("09-vertical-resize.png", "SizeNS", "size_ns", "center"),
    ("10-horizontal-resize.png", "SizeWE", "size_we", "center"),
    ("11-diagonal-resize-nwse.png", "SizeNWSE", "size_nwse", "center"),
    ("12-diagonal-resize-nesw.png", "SizeNESW", "size_nesw", "center"),
    ("13-move.png", "SizeAll", "size_all", "center"),
    ("14-alternate-select.png", "UpArrow", "up_arrow", "top_center"),
    ("15-link-select.png", "Hand", "hand", "top_center"),
)


def is_checkerboard(pixel: tuple[int, int, int, int]) -> bool:
    """Return whether a pixel can belong to the baked light checkerboard."""
    red, green, blue, _alpha = pixel
    return min(red, green, blue) >= 218 and max(red, green, blue) - min(
        red, green, blue
    ) <= 8


def remove_baked_checkerboard(image: Image.Image) -> Image.Image:
    """Remove only checkerboard-colored pixels connected to the image edge."""
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()
    outside = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    for x in range(width):
        queue.extend(((x, 0), (x, height - 1)))
    for y in range(1, height - 1):
        queue.extend(((0, y), (width - 1, y)))

    while queue:
        x, y = queue.popleft()
        index = y * width + x
        if outside[index] or not is_checkerboard(pixels[x, y]):
            continue
        outside[index] = 1
        if x:
            queue.append((x - 1, y))
        if x + 1 < width:
            queue.append((x + 1, y))
        if y:
            queue.append((x, y - 1))
        if y + 1 < height:
            queue.append((x, y + 1))

    alpha = bytearray(b"\xff") * (width * height)
    for index, is_outside in enumerate(outside):
        if is_outside:
            alpha[index] = 0
    rgba.putalpha(Image.frombytes("L", rgba.size, bytes(alpha)))
    return rgba


def source_hotspot(
    artwork: Image.Image,
    hotspot_kind: str,
) -> tuple[int, int]:
    """Locate the functional tip on opaque artwork instead of its padded box."""
    alpha = artwork.getchannel("A")
    points = [
        (x, y)
        for y in range(artwork.height)
        for x in range(artwork.width)
        if alpha.getpixel((x, y)) >= 128
    ]
    if not points:
        raise ValueError("原稿中没有可用于热点定位的不透明像素")

    if hotspot_kind == "top_left":
        return min(points, key=lambda point: point[0] + point[1])
    if hotspot_kind == "bottom_left":
        return min(points, key=lambda point: point[0] - point[1])
    if hotspot_kind == "top_center":
        top = min(y for _x, y in points)
        band = [x for x, y in points if y <= top + max(2, artwork.height // 50)]
        return ((min(band) + max(band)) // 2, top)
    return (artwork.width // 2, artwork.height // 2)


def fit_artwork(
    artwork: Image.Image,
    size: int,
    source_point: tuple[int, int],
) -> tuple[Image.Image, tuple[int, int]]:
    """Fit artwork with LANCZOS and scale its detected functional hotspot."""
    margin = 0 if size == 256 else max(1, round(size * 0.04))
    source_width, source_height = artwork.size
    source_x, source_y = source_point
    fitted = artwork.copy()
    fitted.thumbnail(
        (size - margin * 2, size - margin * 2),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGBA", (size, size))
    left = (size - fitted.width) // 2
    top = (size - fitted.height) // 2
    canvas.alpha_composite(fitted, (left, top))
    hotspot = (
        min(size - 1, left + round(source_x * fitted.width / source_width)),
        min(size - 1, top + round(source_y * fitted.height / source_height)),
    )
    return canvas, hotspot


def read_cur(path: Path) -> list[tuple[int, int, int, int]]:
    """Return (width, height, hotspot_x, hotspot_y) for every CUR layer."""
    data = path.read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data)
    if (reserved, kind) != (0, 2):
        raise ValueError(f"{path.name} 不是有效 CUR 文件")
    layers = []
    for index in range(count):
        width, height, _colors, _reserved, hot_x, hot_y, _size, _offset = (
            struct.unpack_from("<BBBBHHII", data, 6 + index * 16)
        )
        layers.append((width or 256, height or 256, hot_x, hot_y))
    return layers


def validate(theme: dict[str, object]) -> None:
    cur_files = sorted(OUTPUT.glob("*.cur"))
    if len(cur_files) != 15:
        raise ValueError(f"应生成 15 个 CUR，实际为 {len(cur_files)} 个")

    expected_sizes = [(size, size) for size in SIZES]
    for path in cur_files:
        layers = read_cur(path)
        if [(width, height) for width, height, _x, _y in layers] != expected_sizes:
            raise ValueError(f"{path.name} 的尺寸层不正确")
        for width, height, hot_x, hot_y in layers:
            if not (0 <= hot_x < width and 0 <= hot_y < height):
                raise ValueError(f"{path.name} 的热点越界")

    cursor_map = theme["cursors"]
    assert isinstance(cursor_map, dict)
    if len(cursor_map) != 15:
        raise ValueError("theme.json 必须映射 15 个角色")
    for relative_path in cursor_map.values():
        if not (OUTPUT / str(relative_path)).is_file():
            raise ValueError(f"theme.json 引用不存在：{relative_path}")

    for _source_name, _role, output_name, _hotspot in CURSORS:
        alpha = Image.open(OUTPUT / f"{output_name}.png").getchannel("A")
        low, high = alpha.getextrema()
        if low != 0 or high != 255:
            raise ValueError(f"{output_name}.png 的透明通道无效")


def build() -> None:
    missing = [name for name, *_rest in CURSORS if not (SOURCE / name).is_file()]
    if missing:
        raise FileNotFoundError(f"缺少素材：{', '.join(missing)}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    cursor_map: dict[str, str] = {}
    for source_name, role, output_name, hotspot_kind in CURSORS:
        source = Image.open(SOURCE / source_name)
        artwork = crop_visible(remove_baked_checkerboard(source))
        artwork.save(OUTPUT / f"{output_name}.png", compress_level=0)
        hotspot = source_hotspot(artwork, hotspot_kind)
        layers = [
            fit_artwork(artwork, size, hotspot)
            for size in SIZES
        ]
        save_multi_cur(layers, OUTPUT / f"{output_name}.cur")
        cursor_map[role] = f"{output_name}.cur"

    theme: dict[str, object] = {
        "name": THEME_NAME,
        "source": 1,
        "cursors": cursor_map,
    }
    (OUTPUT / "theme.json").write_text(
        json.dumps(theme, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    validate(theme)
    print(f"已生成并校验主题：{THEME_NAME}")
    print(f"输出目录：{OUTPUT}")
    print("15 个 CUR 均包含 32/48/64/96/128/192/256 px 图层")


if __name__ == "__main__":
    build()
