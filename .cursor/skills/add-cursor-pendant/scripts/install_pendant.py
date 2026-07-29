"""Chroma-key a generated pendant image and install it as theme pendant.png.

Run from repo root:

  python .cursor/skills/add-cursor-pendant/scripts/install_pendant.py `
    --input path/to/pendant-raw.png `
    --theme-dir src/arkcursor/themes/elaina `
    --background #FF00FF

  python .cursor/skills/add-cursor-pendant/scripts/install_pendant.py `
    --validate-only src/arkcursor/themes/elaina
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[4]
BUILD_SCRIPTS = (
    ROOT / ".cursor" / "skills" / "generate-qmcursor-theme" / "scripts"
)
if str(BUILD_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(BUILD_SCRIPTS))

from build_cursor_theme import parse_color, remove_chroma  # noqa: E402


class InstallError(RuntimeError):
    pass


def install_pendant(
    source: Path,
    theme_dir: Path,
    background: tuple[int, int, int],
    *,
    tolerance: int = 40,
    target_height: int = 256,
    force: bool = False,
) -> Path:
    if not source.is_file():
        raise InstallError(f"找不到输入图：{source}")
    theme_dir = theme_dir.resolve()
    if not theme_dir.is_dir():
        raise InstallError(f"主题目录不存在：{theme_dir}")
    if not (theme_dir / "theme.json").is_file():
        raise InstallError(f"目录缺少 theme.json：{theme_dir}")

    destination = theme_dir / "pendant.png"
    if destination.exists() and not force:
        raise InstallError(
            f"已存在 {destination}。确认覆盖时请加 --force。"
        )

    image = Image.open(source).convert("RGBA")
    cleaned = remove_chroma(image, background, tolerance)

    # Clear enclosed chroma pockets (e.g. filled ring centers) that flood-fill misses.
    pixels = cleaned.load()
    width, height = cleaned.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            if (
                abs(r - background[0]) <= tolerance
                and abs(g - background[1]) <= tolerance
                and abs(b - background[2]) <= tolerance
            ):
                pixels[x, y] = (0, 0, 0, 0)

    bbox = cleaned.getbbox()
    if bbox is None:
        raise InstallError("抠除背景后图像为空，请检查 --background。")

    pad = 8
    cropped = cleaned.crop(
        (
            max(0, bbox[0] - pad),
            max(0, bbox[1] - pad),
            min(width, bbox[2] + pad),
            min(height, bbox[3] + pad),
        )
    )
    out_h = max(64, int(target_height))
    out_w = max(32, int(cropped.width * (out_h / max(cropped.height, 1))))
    resized = cropped.resize((out_w, out_h), Image.Resampling.LANCZOS)
    destination.parent.mkdir(parents=True, exist_ok=True)
    resized.save(destination)
    return destination


def validate_pendant(theme_dir: Path) -> list[str]:
    errors: list[str] = []
    path = theme_dir / "pendant.png"
    if not path.is_file():
        return [f"缺少 {path}"]
    image = Image.open(path).convert("RGBA")
    if image.width < 16 or image.height < 16:
        errors.append("pendant.png 尺寸过小。")
    alpha = image.getchannel("A")
    minimum, maximum = alpha.getextrema()
    if maximum <= 16:
        errors.append("pendant.png 几乎全透明。")
    if minimum >= 250:
        errors.append("pendant.png 似乎没有透明背景（可能未抠图）。")
    # Prefer taller-than-wide charms.
    if image.width > image.height * 1.35:
        errors.append("挂坠过宽，建议竖构图饰物。")
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install theme pendant.png for QMcursor physics charm"
    )
    parser.add_argument("--input", type=Path, help="Generated raw pendant image")
    parser.add_argument(
        "--theme-dir",
        type=Path,
        help="Target theme directory containing theme.json",
    )
    parser.add_argument(
        "--background",
        default="#FF00FF",
        help="Chroma key color used when generating the image",
    )
    parser.add_argument("--chroma-tolerance", type=int, default=40)
    parser.add_argument("--height", type=int, default=256)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing pendant.png",
    )
    parser.add_argument(
        "--validate-only",
        type=Path,
        help="Only validate theme_dir/pendant.png",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.validate_only is not None:
            errors = validate_pendant(args.validate_only)
            if errors:
                print("校验失败：", file=sys.stderr)
                for item in errors:
                    print(f"- {item}", file=sys.stderr)
                return 1
            print(f"OK: {args.validate_only / 'pendant.png'}")
            return 0

        if args.input is None or args.theme_dir is None:
            raise InstallError("安装模式需要 --input 与 --theme-dir。")

        destination = install_pendant(
            args.input,
            args.theme_dir,
            parse_color(args.background),
            tolerance=args.chroma_tolerance,
            target_height=args.height,
            force=args.force,
        )
        errors = validate_pendant(args.theme_dir)
        if errors:
            print(f"已写入 {destination}，但校验有警告：", file=sys.stderr)
            for item in errors:
                print(f"- {item}", file=sys.stderr)
            return 1
        print(f"已安装：{destination}")
        return 0
    except (InstallError, ValueError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
