"""Build and validate the Taffy ArkCursor theme from transparent PNG files."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from build_cursor_theme_from_pngs import (
    CURSORS,
    SIZES,
    crop_visible,
    fit_artwork,
    read_cur,
    source_hotspot,
)
from build_origami_cursor_theme import save_multi_cur


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "素材" / "塔菲"
OUTPUT = ROOT / "src" / "arkcursor" / "themes" / "taffy"
THEME_NAME = "塔菲"


def validate(theme: dict[str, object]) -> None:
    """Validate cursor count, layers, hotspots, alpha, and manifest paths."""
    cur_files = sorted(OUTPUT.glob("*.cur"))
    if len(cur_files) != 15:
        raise ValueError(f"应生成 15 个 CUR，实际为 {len(cur_files)} 个")

    expected_sizes = [(size, size) for size in SIZES]
    for path in cur_files:
        layers = read_cur(path)
        if [(width, height) for width, height, _x, _y in layers] != expected_sizes:
            raise ValueError(f"{path.name} 的尺寸层不正确")
        if any(
            not (0 <= hot_x < width and 0 <= hot_y < height)
            for width, height, hot_x, hot_y in layers
        ):
            raise ValueError(f"{path.name} 的热点越界")

    cursor_map = theme["cursors"]
    if not isinstance(cursor_map, dict) or len(cursor_map) != 15:
        raise ValueError("theme.json 必须映射 15 个角色")
    for relative_path in cursor_map.values():
        if not (OUTPUT / str(relative_path)).is_file():
            raise ValueError(f"theme.json 引用不存在：{relative_path}")

    for _source_name, _role, output_name, _hotspot in CURSORS:
        with Image.open(OUTPUT / f"{output_name}.png") as image:
            if image.mode != "RGBA" or image.getchannel("A").getextrema() != (0, 255):
                raise ValueError(f"{output_name}.png 的透明通道无效")


def build() -> None:
    """Create the 15 PNG/CUR pairs and their ArkCursor manifest."""
    missing = [name for name, *_rest in CURSORS if not (SOURCE / name).is_file()]
    if missing:
        raise FileNotFoundError(f"缺少素材：{', '.join(missing)}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    cursor_map: dict[str, str] = {}
    for source_name, role, output_name, hotspot_kind in CURSORS:
        with Image.open(SOURCE / source_name) as source:
            artwork = crop_visible(source.convert("RGBA"))
        artwork.save(OUTPUT / f"{output_name}.png", compress_level=0)
        source_point = source_hotspot(artwork, hotspot_kind)
        layers = [
            fit_artwork(artwork, size, source_point)
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
