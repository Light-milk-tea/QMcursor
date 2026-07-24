"""Build and validate the 光之美少女新版 ArkCursor theme."""

from __future__ import annotations

import json
import struct
from pathlib import Path

from PIL import Image

from build_origami_cursor_theme import save_multi_cur


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "素材" / "光之美少女新版"
OUTPUT = ROOT / "src" / "arkcursor" / "themes" / "precure_new"
THEME_NAME = "光之美少女新版"
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


def remove_green_screen(image: Image.Image) -> Image.Image:
    """Turn chroma green, including enclosed holes, into feathered alpha."""
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()

    cleaned = bytearray()
    for y in range(height):
        for x in range(width):
            red, green, blue, source_alpha = pixels[x, y]
            dominance = green - max(red, blue)
            if green < 60 or dominance < 24:
                cleaned.extend((red, green, blue, source_alpha))
                continue

            alpha = max(0, min(255, round((80 - dominance) * 255 / 56)))
            alpha = round(alpha * source_alpha / 255)
            if alpha == 0:
                cleaned.extend((0, 0, 0, 0))
            else:
                # Suppress green spill in the antialiased transition pixels.
                cleaned.extend((red, min(green, max(red, blue)), blue, alpha))

    return Image.frombytes("RGBA", rgba.size, bytes(cleaned))


def crop_visible(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A")
    bounds = alpha.point(lambda value: 255 if value >= 2 else 0).getbbox()
    if bounds is None:
        raise ValueError("原稿中没有找到可见主体")
    left, top, right, bottom = bounds
    padding = max(2, round(max(right - left, bottom - top) * 0.01))
    return image.crop(
        (
            max(0, left - padding),
            max(0, top - padding),
            min(image.width, right + padding),
            min(image.height, bottom + padding),
        )
    )


def source_hotspot(
    artwork: Image.Image,
    hotspot_kind: str,
) -> tuple[int, int]:
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
    margin = 0 if size == 256 else max(1, round(size * 0.04))
    source_width, source_height = artwork.size
    fitted = artwork.copy()
    fitted.thumbnail(
        (size - margin * 2, size - margin * 2),
        Image.Resampling.LANCZOS,
    )
    left = (size - fitted.width) // 2
    top = (size - fitted.height) // 2
    canvas = Image.new("RGBA", (size, size))
    canvas.alpha_composite(fitted, (left, top))
    hotspot = (
        min(size - 1, left + round(source_point[0] * fitted.width / source_width)),
        min(size - 1, top + round(source_point[1] * fitted.height / source_height)),
    )
    return canvas, hotspot


def read_cur(path: Path) -> list[tuple[int, int, int, int]]:
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
    png_files = sorted(OUTPUT.glob("*.png"))
    if len(cur_files) != 15 or len(png_files) != 15:
        raise ValueError(
            f"应生成 15 个 CUR 和 15 个 PNG，实际为 "
            f"{len(cur_files)} 个 CUR、{len(png_files)} 个 PNG"
        )

    expected_sizes = [(size, size) for size in SIZES]
    for path in cur_files:
        layers = read_cur(path)
        if [(width, height) for width, height, _x, _y in layers] != expected_sizes:
            raise ValueError(f"{path.name} 的尺寸层不正确")
        if any(not (0 <= x < width and 0 <= y < height)
               for width, height, x, y in layers):
            raise ValueError(f"{path.name} 的热点越界")

    cursor_map = theme["cursors"]
    if not isinstance(cursor_map, dict) or len(cursor_map) != 15:
        raise ValueError("theme.json 必须映射 15 个角色")
    for relative_path in cursor_map.values():
        if not (OUTPUT / str(relative_path)).is_file():
            raise ValueError(f"theme.json 引用不存在：{relative_path}")

    for path in png_files:
        image = Image.open(path)
        if image.mode != "RGBA":
            raise ValueError(f"{path.name} 不是 RGBA PNG")
        low, high = image.getchannel("A").getextrema()
        if low != 0 or high != 255:
            raise ValueError(f"{path.name} 的透明通道无效")


def build() -> None:
    missing = [name for name, *_rest in CURSORS if not (SOURCE / name).is_file()]
    if missing:
        raise FileNotFoundError(f"缺少素材：{', '.join(missing)}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    cursor_map: dict[str, str] = {}
    for source_name, role, output_name, hotspot_kind in CURSORS:
        artwork = crop_visible(
            remove_green_screen(Image.open(SOURCE / source_name))
        )
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
