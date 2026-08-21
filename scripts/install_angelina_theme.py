"""Install the bundled Angelina theme as a static multi-size CUR (no animation)."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
WORK = Path(r"C:\Users\轻茗\Desktop\安洁莉娜小人光标")
SOURCE_HD = WORK / "concept" / "01-normal-select-hd-mon3tr-head-v2.png"
SOURCE_STATIC = WORK / "source" / "01-normal-select" / "00.png"
THEME = ROOT / "src" / "qmcursor" / "themes" / "angelina"
IMPORTED = Path.home() / "AppData" / "Local" / "QMcursor" / "imported" / "安洁莉娜小人"
BUILDER = (
    ROOT
    / ".cursor"
    / "skills"
    / "generate-qmcursor-theme"
    / "scripts"
    / "build_ani_theme.py"
)
SIZES = (32, 48, 64, 96, 128, 256)


def load_static_builder():
    spec = importlib.util.spec_from_file_location("build_ani_theme", BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 CUR 构建器：{BUILDER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    sys.path.insert(0, str(BUILDER.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return sys.modules["build_cursor_theme"]


def top_left_plane_mask(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A")
    width, height = image.size
    search_width = width // 3
    search_height = height // 3
    seen: set[tuple[int, int]] = set()
    components: list[set[tuple[int, int]]] = []
    for y in range(search_height):
        for x in range(search_width):
            start = (x, y)
            if start in seen or alpha.getpixel(start) < 16:
                continue
            component = {start}
            seen.add(start)
            pending = [start]
            while pending:
                px, py = pending.pop()
                for nx in range(px - 1, px + 2):
                    for ny in range(py - 1, py + 2):
                        neighbor = (nx, ny)
                        if (
                            0 <= nx < search_width
                            and 0 <= ny < search_height
                            and neighbor not in seen
                            and alpha.getpixel(neighbor) >= 16
                        ):
                            seen.add(neighbor)
                            component.add(neighbor)
                            pending.append(neighbor)
            components.append(component)
    if not components:
        raise RuntimeError("无法识别左上角纸飞机。")
    airplane = max(components, key=len)
    mask = Image.new("L", image.size, 0)
    pixels = mask.load()
    for x, y in airplane:
        pixels[x, y] = 255
    return mask


def clear_cyan_pockets(image: Image.Image) -> Image.Image:
    out = image.copy()
    pixels = out.load()
    width, height = out.size
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = pixels[x, y]
            is_cyan_pocket = (
                alpha > 0
                and not (x < width // 3 and y < height // 4)
                and green > red + 25
                and blue > red + 25
                and abs(green - blue) < 50
                and green > 80
                and blue > 80
            )
            if is_cyan_pocket:
                pixels[x, y] = (0, 0, 0, 0)
    return out


def load_foreground(static_builder) -> Image.Image:
    image = Image.open(SOURCE_HD).convert("RGBA")
    foreground = static_builder.remove_chroma(
        image,
        background=(0, 255, 255),
        tolerance=96,
    )
    return clear_cyan_pockets(foreground)


def cleanup_animation_assets(foreground: Image.Image) -> None:
    frame_dir = WORK / "source" / "01-normal-select"
    frame_dir.mkdir(parents=True, exist_ok=True)
    for path in frame_dir.glob("*.png"):
        if path.name != "00.png":
            path.unlink()
    foreground.save(frame_dir / "00.png")

    preview = WORK / "preview"
    preview.mkdir(parents=True, exist_ok=True)
    for name in (
        "01-normal-select.gif",
        "01-normal-select-sheet.png",
        "01-normal-select-diff.png",
        "01-normal-select-sheet-hd.png",
    ):
        path = preview / name
        if path.exists():
            path.unlink()
    small = foreground.resize((256, 256), Image.Resampling.LANCZOS)
    board = Image.new("RGB", (256, 256), (182, 210, 184))
    pixels = board.load()
    for y in range(256):
        for x in range(256):
            if ((x // 16) + (y // 16)) % 2:
                pixels[x, y] = (146, 184, 152)
    board.paste(small, mask=small.split()[-1])
    board.save(preview / "01-normal-select-static.png")


def main() -> None:
    static_builder = load_static_builder()
    foreground = load_foreground(static_builder)
    plane_mask = top_left_plane_mask(foreground)

    if THEME.exists():
        shutil.rmtree(THEME)
    THEME.mkdir(parents=True, exist_ok=True)

    frames: list[tuple[Image.Image, tuple[int, int]]] = []
    for size in SIZES:
        frame = foreground.resize((size, size), Image.Resampling.LANCZOS)
        resized_mask = plane_mask.resize(frame.size, Image.Resampling.LANCZOS)
        bounds = resized_mask.point(lambda value: 255 if value >= 64 else 0).getbbox()
        if bounds is None:
            raise RuntimeError(f"{size}px 纸飞机蒙版为空。")
        hotspot = (bounds[0], bounds[1])
        frames.append((frame, hotspot))
        print(f"{size}px 热点：{hotspot}")

    cursor_path = THEME / "arrow.cur"
    static_builder.write_cur(cursor_path, frames)
    frames[-1][0].save(THEME / "arrow.png")

    manifest = {
        "name": "安洁莉娜小人",
        "source": 1,
        "is_custom": True,
        "kind": "cur",
        "cursors": {
            "Arrow": "arrow.cur",
            "Help": "",
            "AppStarting": "",
            "Wait": "",
            "Crosshair": "",
            "IBeam": "",
            "NWPen": "",
            "No": "",
            "SizeNS": "",
            "SizeWE": "",
            "SizeNWSE": "",
            "SizeNESW": "",
            "SizeAll": "",
            "UpArrow": "",
            "Hand": "",
        },
    }
    (THEME / "theme.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    cleanup_animation_assets(foreground)

    if IMPORTED.parent.is_dir():
        if IMPORTED.exists():
            shutil.rmtree(IMPORTED)
        shutil.copytree(THEME, IMPORTED)
        print(f"已同步导入目录：{IMPORTED}")

    print(f"已写入静态主题：{THEME}")


if __name__ == "__main__":
    main()
