"""Build the rounded ultra-bold paper-crane cursor theme."""

from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image

from build_origami_cursor_theme import save_multi_cur


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "arkcursor-paper-crane-rounded-ultra-bold-transparent.png"
OUTPUT = ROOT / "src" / "arkcursor" / "themes" / "paper_crane_rounded_bold"

SIZES = (32, 48, 64, 96, 128, 192, 256)
GENERATED = (
    ("arrow", "top_left"),
    ("help", "top_left"),
    ("app_starting", "top_left"),
    ("wait", "center"),
    ("crosshair", "center"),
    ("ibeam", "center"),
    ("pen", "bottom_left"),
    ("no", "center"),
    ("size_ns", "center"),
    ("size_we", "center"),
    ("size_nwse", "center"),
    ("size_nesw", "center"),
    ("size_all", "center"),
    ("up_arrow", "top_center"),
    ("hand", "top_center"),
)


def extract_artworks(sheet: Image.Image) -> list[Image.Image]:
    """Group connected artwork into the nearest cell of the 5-by-3 layout."""
    columns, rows = 5, 3
    width, height = sheet.size
    alpha = list(sheet.getchannel("A").get_flattened_data())
    visited = bytearray(width * height)
    masks = [bytearray(width * height) for _ in GENERATED]

    for start, value in enumerate(alpha):
        if value < 8 or visited[start]:
            continue

        queue = deque([start])
        visited[start] = 1
        component: list[int] = []
        left = right = start % width
        top = bottom = start // width

        while queue:
            index = queue.popleft()
            component.append(index)
            x, y = index % width, index // width
            left, right = min(left, x), max(right, x)
            top, bottom = min(top, y), max(bottom, y)

            for neighbor_x, neighbor_y in (
                (x - 1, y - 1), (x, y - 1), (x + 1, y - 1),
                (x - 1, y),                     (x + 1, y),
                (x - 1, y + 1), (x, y + 1), (x + 1, y + 1),
            ):
                if not (0 <= neighbor_x < width and 0 <= neighbor_y < height):
                    continue
                neighbor = neighbor_y * width + neighbor_x
                if alpha[neighbor] >= 8 and not visited[neighbor]:
                    visited[neighbor] = 1
                    queue.append(neighbor)

        if len(component) < 20:
            continue

        center_x = (left + right) / 2
        center_y = (top + bottom) / 2
        target = min(
            range(len(GENERATED)),
            key=lambda index: (
                (center_x / width * columns - (index % columns + 0.5)) ** 2
                + (center_y / height * rows - (index // columns + 0.5)) ** 2
            ),
        )
        for index in component:
            masks[target][index] = alpha[index]

    artworks: list[Image.Image] = []
    for mask in masks:
        artwork = sheet.copy()
        artwork.putalpha(Image.frombytes("L", sheet.size, bytes(mask)))
        artworks.append(artwork)
    return artworks


def crop_visible(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A")
    solid = alpha.point(lambda value: 255 if value >= 8 else 0)
    bounds = solid.getbbox()
    if bounds is None:
        raise ValueError("原稿中没有找到可见主体")
    left, top, right, bottom = bounds
    padding = max(2, round(max(right - left, bottom - top) * 0.01))
    bounds = (
        max(0, left - padding),
        max(0, top - padding),
        min(image.width, right + padding),
        min(image.height, bottom + padding),
    )
    return image.crop(bounds)


def fit_artwork(
    artwork: Image.Image,
    size: int,
    hotspot_kind: str,
) -> tuple[Image.Image, tuple[int, int]]:
    # Keep the source pixels untouched in the 256 px layer. Smaller layers
    # are resized only because Windows requires a matching cursor resolution.
    margin = 0 if size == 256 else max(1, round(size * 0.04))
    fitted = artwork.copy()
    fitted.thumbnail(
        (size - margin * 2, size - margin * 2),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGBA", (size, size))
    left = (size - fitted.width) // 2
    top = (size - fitted.height) // 2
    canvas.alpha_composite(fitted, (left, top))

    if hotspot_kind == "top_left":
        hotspot = (left, top)
    elif hotspot_kind == "top_center":
        hotspot = (left + fitted.width // 2, top)
    elif hotspot_kind == "bottom_left":
        hotspot = (left, min(size - 1, top + fitted.height - 1))
    else:
        hotspot = (
            min(size - 1, left + fitted.width // 2),
            min(size - 1, top + fitted.height // 2),
        )
    return canvas, hotspot


def build() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    previews: list[Image.Image] = []
    cells = extract_artworks(Image.open(SOURCE).convert("RGBA"))

    for cell, (output_name, hotspot_kind) in zip(cells, GENERATED, strict=True):
        artwork = crop_visible(cell)

        artwork.save(OUTPUT / f"{output_name}.png", compress_level=0)
        preview, _hotspot = fit_artwork(artwork, 128, hotspot_kind)
        previews.append(preview)

        cursors = [
            fit_artwork(artwork, size, hotspot_kind)
            for size in SIZES
        ]
        save_multi_cur(cursors, OUTPUT / f"{output_name}.cur")

    sheet = Image.new("RGBA", (512, 512), "#F5F7FA")
    for index, preview in enumerate(previews):
        preview = preview.copy()
        preview.thumbnail((128, 128), Image.Resampling.LANCZOS)
        sheet.alpha_composite(
            preview,
            ((index % 4) * 128, (index // 4) * 128),
        )
    sheet.convert("RGB").save(OUTPUT / "concept.png")


if __name__ == "__main__":
    build()
