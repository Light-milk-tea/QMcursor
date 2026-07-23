"""Build the bundled pink pixel cursor files from the generated concept sheet.

Requires Pillow and is only needed when regenerating the design assets.
"""

from __future__ import annotations

import argparse
import shutil
import struct
from collections import deque
from pathlib import Path

from PIL import Image


CURSORS = {
    "arrow": ((72, 354, 270, 654), (1, 1)),
    "hand": ((380, 354, 610, 654), (16, 1)),
    "wait": ((710, 374, 970, 654), (16, 16)),
}

REMAINING_CURSORS = (
    ("help", (1, 1)),
    ("app_starting", (1, 1)),
    ("crosshair", (16, 16)),
    ("ibeam", (16, 16)),
    ("pen", (30, 30)),
    ("no", (16, 16)),
    ("size_ns", (16, 16)),
    ("size_we", (16, 16)),
    ("size_nwse", (16, 16)),
    ("size_nesw", (16, 16)),
    ("size_all", (16, 16)),
    ("up_arrow", (16, 1)),
)


def _is_pink(pixel: tuple[int, int, int, int]) -> bool:
    red, green, blue, _alpha = pixel
    return red > 190 and red - max(green, blue) > 35


def remove_checkerboard(image: Image.Image) -> Image.Image:
    """Keep pink outlines and the white regions enclosed by those outlines."""
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()
    pink = {
        (x, y)
        for y in range(height)
        for x in range(width)
        if _is_pink(pixels[x, y])
    }

    outside: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque()
    for x in range(width):
        queue.extend(((x, 0), (x, height - 1)))
    for y in range(height):
        queue.extend(((0, y), (width - 1, y)))

    while queue:
        point = queue.popleft()
        x, y = point
        if point in outside or point in pink:
            continue
        outside.add(point)
        if x:
            queue.append((x - 1, y))
        if x + 1 < width:
            queue.append((x + 1, y))
        if y:
            queue.append((x, y - 1))
        if y + 1 < height:
            queue.append((x, y + 1))

    cleaned = Image.new("RGBA", rgba.size)
    output = cleaned.load()
    for y in range(height):
        for x in range(width):
            point = (x, y)
            if point in pink:
                red, green, blue, _alpha = pixels[x, y]
                output[x, y] = (red, green, blue, 255)
            elif point not in outside:
                output[x, y] = (255, 255, 255, 255)

    bounds = cleaned.getbbox()
    if bounds is None:
        raise ValueError("裁剪区域中没有找到粉色指针")
    return cleaned.crop(bounds)


def fit_cursor(image: Image.Image, size: int = 32) -> Image.Image:
    image.thumbnail((size - 2, size - 2), Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", (size, size))
    left = 1 if image.width >= size - 2 else (size - image.width) // 2
    canvas.alpha_composite(image, (left, 1))
    return canvas


def save_cur(
    image: Image.Image,
    path: Path,
    hotspot: tuple[int, int],
) -> None:
    """Write a single 32-bit Windows CUR image."""
    rgba = image.convert("RGBA")
    width, height = rgba.size
    xor_data = bytearray()
    and_data = bytearray()

    for y in range(height - 1, -1, -1):
        mask_row = bytearray((width + 7) // 8)
        for x in range(width):
            red, green, blue, alpha = rgba.getpixel((x, y))
            xor_data.extend((blue, green, red, alpha))
            if alpha == 0:
                mask_row[x // 8] |= 0x80 >> (x % 8)
        and_data.extend(mask_row)
        and_data.extend(b"\0" * ((4 - len(mask_row) % 4) % 4))

    bitmap_header = struct.pack(
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
    image_data = bitmap_header + xor_data + and_data
    directory = struct.pack("<HHH", 0, 2, 1)
    entry = struct.pack(
        "<BBBBHHII",
        width,
        height,
        0,
        0,
        hotspot[0],
        hotspot[1],
        len(image_data),
        22,
    )
    path.write_bytes(directory + entry + image_data)


def build(source: Path, output: Path) -> None:
    sheet = Image.open(source)
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, output / "concept.png")

    for name, (box, hotspot) in CURSORS.items():
        image = fit_cursor(remove_checkerboard(sheet.crop(box)))
        image.save(output / f"{name}.png")
        save_cur(image, output / f"{name}.cur", hotspot)


def build_remaining(source: Path, output: Path) -> None:
    sheet = Image.open(source)
    shutil.copyfile(source, output / "remaining_concept.png")

    cell_width = sheet.width // 4
    cell_height = sheet.height // 3
    for index, (name, hotspot) in enumerate(REMAINING_CURSORS):
        column = index % 4
        row = index // 4
        box = (
            column * cell_width,
            row * cell_height,
            (column + 1) * cell_width,
            (row + 1) * cell_height,
        )
        image = remove_checkerboard(sheet.crop(box))
        if name == "size_nesw":
            image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        image = fit_cursor(image)
        image.save(output / f"{name}.png")
        save_cur(image, output / f"{name}.cur", hotspot)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--remaining-source", type=Path)
    args = parser.parse_args()
    build(args.source, args.output)
    if args.remaining_source:
        build_remaining(args.remaining_source, args.output)


if __name__ == "__main__":
    main()
