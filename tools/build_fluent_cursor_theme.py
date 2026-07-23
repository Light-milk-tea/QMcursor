"""Build the multi-resolution Fluent pink cursor theme from its concept sheet."""

from __future__ import annotations

import argparse
import shutil
import struct
from pathlib import Path

from PIL import Image


CURSORS = (
    ("arrow", (0.0, 0.0)),
    ("help", (0.0, 0.0)),
    ("app_starting", (0.0, 0.0)),
    ("wait", (0.5, 0.5)),
    ("crosshair", (0.5, 0.5)),
    ("ibeam", (0.5, 0.5)),
    ("pen", (0.03, 0.74)),
    ("no", (0.5, 0.5)),
    ("size_ns", (0.5, 0.5)),
    ("size_we", (0.5, 0.5)),
    ("size_nwse", (0.5, 0.5)),
    ("size_nesw", (0.5, 0.5)),
    ("size_all", (0.5, 0.5)),
    ("up_arrow", (0.5, 0.0)),
    ("hand", (0.38, 0.0)),
)
SIZES = (24, 32, 48, 64)


def remove_green_screen(image: Image.Image) -> Image.Image:
    """Recover antialiased pink/white artwork composited over bright green."""
    source = image.convert("RGB")
    output = Image.new("RGBA", source.size)
    source_pixels = source.load()
    output_pixels = output.load()

    for y in range(source.height):
        for x in range(source.width):
            red, green, blue = source_pixels[x, y]
            if red <= 8:
                continue

            alpha = max(0, min(255, round((red - 8) * 255 / 247)))
            alpha_ratio = alpha / 255
            foreground_green = round(
                (green - 255 * (1 - alpha_ratio)) / alpha_ratio
            )
            foreground_blue = round(blue / alpha_ratio)
            output_pixels[x, y] = (
                255,
                max(0, min(255, foreground_green)),
                max(0, min(255, foreground_blue)),
                alpha,
            )

    # The generated green background contains a few low-red pixels. They are
    # nearly transparent after keying, but using them for the crop would move
    # the CUR hotspot away from the visible arrow tip.
    solid_alpha = output.getchannel("A").point(
        lambda alpha: 255 if alpha >= 40 else 0
    )
    bounds = solid_alpha.getbbox()
    if bounds is None:
        raise ValueError("单元格中没有找到可用图标")
    return output.crop(bounds)


def fit_cursor(
    source: Image.Image,
    size: int,
    hotspot_ratio: tuple[float, float],
) -> tuple[Image.Image, tuple[int, int]]:
    margin = max(1, round(size / 32))
    image = source.copy()
    image.thumbnail((size - margin * 2, size - margin * 2), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (size, size))
    left = (size - image.width) // 2
    top = (size - image.height) // 2
    canvas.alpha_composite(image, (left, top))
    hotspot = (
        round(left + (image.width - 1) * hotspot_ratio[0]),
        round(top + (image.height - 1) * hotspot_ratio[1]),
    )
    return canvas, hotspot


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
                image.width,
                image.height,
                0,
                0,
                hotspot[0],
                hotspot[1],
                len(payload),
                offset,
            )
        )
        offset += len(payload)

    directory = struct.pack("<HHH", 0, 2, len(images))
    path.write_bytes(directory + entries + b"".join(payloads))


def build(source: Path, output: Path) -> None:
    sheet = Image.open(source)
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, output / "concept.png")
    cell_width = sheet.width // 4
    cell_height = sheet.height // 4

    for index, (name, hotspot_ratio) in enumerate(CURSORS):
        column = index % 4
        row = index // 4
        box = (
            column * cell_width,
            row * cell_height,
            (column + 1) * cell_width,
            (row + 1) * cell_height,
        )
        artwork = remove_green_screen(sheet.crop(box))
        cursors = [
            fit_cursor(artwork, size, hotspot_ratio)
            for size in SIZES
        ]
        cursors[-1][0].save(output / f"{name}.png")
        save_multi_cur(cursors, output / f"{name}.cur")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build(args.source, args.output)


if __name__ == "__main__":
    main()
