"""Build and validate an ArkCursor theme from 15 generated PNG images."""

from __future__ import annotations

import argparse
from collections import Counter, deque
import json
from pathlib import Path
import re
import shutil
import struct
import sys
import tempfile
from typing import Iterable, NamedTuple

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover - depends on the local environment
    raise SystemExit(
        "缺少 Pillow。请先运行：python -m pip install Pillow"
    ) from exc


SIZES = (32, 48, 64, 96, 128, 192, 256)
THEME_DIR_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class CursorSpec(NamedTuple):
    source_name: str
    role: str
    output_name: str
    hotspot_kind: str


SPECS = (
    CursorSpec("01-normal-select", "Arrow", "arrow", "northwest"),
    CursorSpec("02-help-select", "Help", "help", "northwest"),
    CursorSpec(
        "03-working-in-background",
        "AppStarting",
        "app_starting",
        "northwest",
    ),
    CursorSpec("04-busy", "Wait", "wait", "center"),
    CursorSpec("05-precision-select", "Crosshair", "crosshair", "center"),
    CursorSpec("06-text-select", "IBeam", "ibeam", "center"),
    CursorSpec("07-handwriting", "NWPen", "pen", "southwest"),
    CursorSpec("08-unavailable", "No", "no", "center"),
    CursorSpec("09-vertical-resize", "SizeNS", "size_ns", "center"),
    CursorSpec("10-horizontal-resize", "SizeWE", "size_we", "center"),
    CursorSpec(
        "11-diagonal-resize-nwse",
        "SizeNWSE",
        "size_nwse",
        "center",
    ),
    CursorSpec(
        "12-diagonal-resize-nesw",
        "SizeNESW",
        "size_nesw",
        "center",
    ),
    CursorSpec("13-move", "SizeAll", "size_all", "center"),
    CursorSpec("14-alternate-select", "UpArrow", "up_arrow", "north"),
    CursorSpec("15-link-select", "Hand", "hand", "north"),
)


class BuildError(RuntimeError):
    """Raised for invalid input or output."""


def parse_color(value: str) -> tuple[int, int, int] | None:
    if value.casefold() == "auto":
        return None
    normalized = value.removeprefix("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", normalized):
        raise BuildError("背景色必须是 auto 或 #RRGGBB。")
    return tuple(
        int(normalized[index : index + 2], 16) for index in (0, 2, 4)
    )


def project_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "src" / "arkcursor"
        ).is_dir():
            return candidate
    raise BuildError("无法定位 QMcursor 项目根目录。")


def load_sources(input_path: Path) -> list[Image.Image]:
    if input_path.is_dir():
        missing = [
            f"{spec.source_name}.png"
            for spec in SPECS
            if not (input_path / f"{spec.source_name}.png").is_file()
        ]
        if missing:
            raise BuildError(
                "输入目录缺少以下生成图：\n" + "\n".join(missing)
            )
        return [
            open_rgba(input_path / f"{spec.source_name}.png") for spec in SPECS
        ]

    if not input_path.is_file():
        raise BuildError(f"输入不存在：{input_path}")
    sheet = open_rgba(input_path)
    width, height = sheet.size
    if width / height < 1.45 or width / height > 1.9:
        raise BuildError("单文件输入必须是按行排列的 5×3 指针合集。")

    images: list[Image.Image] = []
    for row in range(3):
        top = round(row * height / 3)
        bottom = round((row + 1) * height / 3)
        for column in range(5):
            left = round(column * width / 5)
            right = round((column + 1) * width / 5)
            images.append(sheet.crop((left, top, right, bottom)))
    return images


def open_rgba(path: Path) -> Image.Image:
    try:
        with Image.open(path) as source:
            source.load()
            return source.convert("RGBA")
    except (OSError, ValueError) as exc:
        raise BuildError(f"无法读取 PNG：{path}") from exc


def infer_background(image: Image.Image) -> tuple[int, int, int]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    step = max(1, min(width, height) // 256)
    samples: list[tuple[int, int, int]] = []
    for x in range(0, width, step):
        samples.append(rgb.getpixel((x, 0)))
        samples.append(rgb.getpixel((x, height - 1)))
    for y in range(0, height, step):
        samples.append(rgb.getpixel((0, y)))
        samples.append(rgb.getpixel((width - 1, y)))
    color, count = Counter(samples).most_common(1)[0]
    if count < len(samples) * 0.35:
        raise BuildError(
            "无法可靠识别纯色背景，请用 --background #RRGGBB 明确指定。"
        )
    return color


def has_real_transparency(image: Image.Image) -> bool:
    minimum, maximum = image.getchannel("A").getextrema()
    return minimum == 0 and maximum > 0


def remove_chroma(
    image: Image.Image,
    background: tuple[int, int, int] | None,
    tolerance: int,
) -> Image.Image:
    image = image.convert("RGBA")
    if has_real_transparency(image):
        return image

    key = background or infer_background(image)
    width, height = image.size
    data = list(image.getdata())
    distances = [
        max(
            abs(pixel[0] - key[0]),
            abs(pixel[1] - key[1]),
            abs(pixel[2] - key[2]),
        )
        for pixel in data
    ]

    # Generated backgrounds are noisy, so flood-fill the edge-connected
    # key-colored region instead of relying on per-pixel thresholds alone.
    is_background = bytearray(width * height)
    queue: deque[int] = deque()
    for x in range(width):
        for index in (x, (height - 1) * width + x):
            if not is_background[index] and distances[index] <= tolerance:
                is_background[index] = 1
                queue.append(index)
    for y in range(height):
        for index in (y * width, y * width + width - 1):
            if not is_background[index] and distances[index] <= tolerance:
                is_background[index] = 1
                queue.append(index)
    while queue:
        index = queue.popleft()
        x, y = index % width, index // width
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height:
                neighbor = ny * width + nx
                if (
                    not is_background[neighbor]
                    and distances[neighbor] <= tolerance
                ):
                    is_background[neighbor] = 1
                    queue.append(neighbor)

    # Kept pixels bordering the removed region are anti-aliased blends with
    # the key color; only those get partial alpha and spill correction.
    near_background = bytearray(width * height)
    for index, flag in enumerate(is_background):
        if not flag:
            continue
        x, y = index % width, index // width
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height:
                neighbor = ny * width + nx
                if not is_background[neighbor]:
                    near_background[neighbor] = 1

    full_blend = 255
    output: list[tuple[int, int, int, int]] = []
    for index, (pixel, distance) in enumerate(zip(data, distances)):
        red, green, blue, alpha = pixel
        if is_background[index]:
            output.append((0, 0, 0, 0))
            continue
        if not near_background[index] or distance >= full_blend:
            output.append((red, green, blue, alpha))
            continue

        coverage = max(distance, 1) / full_blend
        new_alpha = max(0, min(255, round(alpha * coverage)))
        if new_alpha == 0:
            output.append((0, 0, 0, 0))
            continue

        # Reverse the blend against the known key color to reduce color spill.
        corrected = []
        for observed, key_channel in zip(
            (red, green, blue), key, strict=True
        ):
            value = (observed - (1.0 - coverage) * key_channel) / coverage
            corrected.append(max(0, min(255, round(value))))
        output.append((*corrected, new_alpha))

    cleaned = Image.new("RGBA", image.size)
    cleaned.putdata(output)
    return cleaned


def crop_with_padding(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        raise BuildError("抠除背景后图像为空，请检查背景色。")
    left, top, right, bottom = bbox
    padding = max(2, round(max(right - left, bottom - top) * 0.025))
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(image.width, right + padding)
    bottom = min(image.height, bottom + padding)
    cropped = image.crop((left, top, right, bottom))

    # Guarantee transparent breathing room even when the source touched an edge.
    framed = Image.new(
        "RGBA",
        (cropped.width + padding * 2, cropped.height + padding * 2),
    )
    framed.alpha_composite(cropped, (padding, padding))
    return framed


def opaque_points(image: Image.Image) -> list[tuple[int, int]]:
    alpha = image.getchannel("A")
    points: list[tuple[int, int]] = []
    for y in range(image.height):
        for x in range(image.width):
            if alpha.getpixel((x, y)) >= 128:
                points.append((x, y))
    if not points:
        raise BuildError("指针没有可见像素。")
    return points


def hotspot_for(image: Image.Image, kind: str) -> tuple[int, int]:
    points = opaque_points(image)
    if kind == "center":
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        return (round((min(xs) + max(xs)) / 2), round((min(ys) + max(ys)) / 2))
    if kind == "northwest":
        return min(points, key=lambda point: (point[0] + point[1], point[1]))
    if kind == "southwest":
        return min(
            points,
            key=lambda point: (
                point[0] + image.height - 1 - point[1],
                point[0],
            ),
        )
    if kind == "north":
        top = min(point[1] for point in points)
        band = [
            point[0]
            for point in points
            if point[1] <= top + max(2, image.height // 50)
        ]
        return ((min(band) + max(band)) // 2, top)
    raise BuildError(f"未知热点类型：{kind}")


def render_frame(
    image: Image.Image,
    hotspot: tuple[int, int],
    size: int,
) -> tuple[Image.Image, tuple[int, int]]:
    margin = 0 if size == 256 else max(1, round(size * 0.04))
    available = size - margin * 2
    maximum = max(image.size)
    scale = min(1.0, available / maximum)
    resized_size = (
        max(1, round(image.width * scale)),
        max(1, round(image.height * scale)),
    )
    resized = image.resize(resized_size, Image.Resampling.LANCZOS)
    frame = Image.new("RGBA", (size, size))
    offset = ((size - resized.width) // 2, (size - resized.height) // 2)
    frame.alpha_composite(resized, offset)
    scaled_hotspot = (
        max(
            0,
            min(
                size - 1,
                offset[0] + round((hotspot[0] + 0.5) * scale - 0.5),
            ),
        ),
        max(
            0,
            min(
                size - 1,
                offset[1] + round((hotspot[1] + 0.5) * scale - 0.5),
            ),
        ),
    )
    return frame, scaled_hotspot


def dib_payload(image: Image.Image) -> bytes:
    width, height = image.size
    flipped = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    xor_bitmap = flipped.tobytes("raw", "BGRA")
    mask_stride = ((width + 31) // 32) * 4
    and_mask = bytes(mask_stride * height)
    header = struct.pack(
        "<IiiHHIIiiII",
        40,
        width,
        height * 2,
        1,
        32,
        0,
        len(xor_bitmap) + len(and_mask),
        0,
        0,
        0,
        0,
    )
    return header + xor_bitmap + and_mask


def write_cur(
    path: Path,
    frames: Iterable[tuple[Image.Image, tuple[int, int]]],
) -> None:
    prepared = [
        (image, hotspot, dib_payload(image)) for image, hotspot in frames
    ]
    header_size = 6 + 16 * len(prepared)
    offset = header_size
    entries = []
    payloads = []
    for image, hotspot, payload in prepared:
        width, height = image.size
        entries.append(
            struct.pack(
                "<BBBBHHII",
                0 if width == 256 else width,
                0 if height == 256 else height,
                0,
                0,
                hotspot[0],
                hotspot[1],
                len(payload),
                offset,
            )
        )
        payloads.append(payload)
        offset += len(payload)
    path.write_bytes(
        struct.pack("<HHH", 0, 2, len(prepared))
        + b"".join(entries)
        + b"".join(payloads)
    )


def build_theme(
    input_path: Path,
    theme_name: str,
    theme_dir: str,
    background: tuple[int, int, int] | None,
    tolerance: int,
    force: bool,
) -> Path:
    if not theme_name.strip():
        raise BuildError("主题名称不能为空。")
    if not THEME_DIR_PATTERN.fullmatch(theme_dir):
        raise BuildError(
            "主题目录名只能包含小写英文字母、数字、下划线和连字符。"
        )
    if not 16 <= tolerance <= 192:
        raise BuildError("色键容差必须在 16–192 之间。")

    root = project_root()
    themes_root = root / "src" / "arkcursor" / "themes"
    themes_root.mkdir(parents=True, exist_ok=True)
    target = themes_root / theme_dir
    if target.exists() and not force:
        raise BuildError(f"目标主题已存在：{target}\n明确覆盖时请加 --force。")

    sources = load_sources(input_path)
    with tempfile.TemporaryDirectory(
        prefix=f".{theme_dir}-", dir=themes_root
    ) as temporary_name:
        temporary = Path(temporary_name)
        cursors: dict[str, str] = {}
        for source, spec in zip(sources, SPECS, strict=True):
            cleaned = remove_chroma(source, background, tolerance)
            cropped = crop_with_padding(cleaned)
            hotspot = hotspot_for(cropped, spec.hotspot_kind)
            png_path = temporary / f"{spec.output_name}.png"
            cur_path = temporary / f"{spec.output_name}.cur"
            cropped.save(png_path, format="PNG", optimize=False)
            frames = [
                render_frame(cropped, hotspot, size) for size in SIZES
            ]
            write_cur(cur_path, frames)
            cursors[spec.role] = cur_path.name

        manifest = {
            "name": theme_name.strip(),
            "source": 1,
            "cursors": cursors,
        }
        (temporary / "theme.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        validate_theme(temporary)
        if target.exists():
            shutil.rmtree(target)
        temporary.replace(target)

    validate_theme(target)
    return target


def read_cur(path: Path) -> list[tuple[int, int, int, int, bool]]:
    data = path.read_bytes()
    if len(data) < 6:
        raise BuildError(f"CUR 文件过短：{path.name}")
    reserved, kind, count = struct.unpack_from("<HHH", data)
    if reserved != 0 or kind != 2:
        raise BuildError(f"不是有效 CUR 文件：{path.name}")
    if len(data) < 6 + count * 16:
        raise BuildError(f"CUR 目录损坏：{path.name}")

    layers = []
    for index in range(count):
        (
            width_byte,
            height_byte,
            _colors,
            _reserved,
            hotspot_x,
            hotspot_y,
            byte_count,
            offset,
        ) = struct.unpack_from("<BBBBHHII", data, 6 + index * 16)
        width = width_byte or 256
        height = height_byte or 256
        if hotspot_x >= width or hotspot_y >= height:
            raise BuildError(f"{path.name} 的热点超出 {width}×{height} 图层。")
        if offset + byte_count > len(data) or byte_count < 40:
            raise BuildError(f"{path.name} 的图层偏移或长度无效。")
        (
            header_size,
            dib_width,
            dib_double_height,
            planes,
            bit_count,
            compression,
            _image_size,
            _x_ppm,
            _y_ppm,
            _used,
            _important,
        ) = struct.unpack_from("<IiiHHIIiiII", data, offset)
        if (
            header_size != 40
            or dib_width != width
            or dib_double_height != height * 2
            or planes != 1
            or bit_count != 32
            or compression != 0
        ):
            raise BuildError(f"{path.name} 含非 32 位未压缩 RGBA 图层。")
        pixel_start = offset + 40
        pixel_end = pixel_start + width * height * 4
        if pixel_end > offset + byte_count:
            raise BuildError(f"{path.name} 的像素数据不完整。")
        alpha_values = data[pixel_start + 3 : pixel_end : 4]
        valid_alpha = bool(alpha_values) and min(alpha_values) == 0
        valid_alpha = valid_alpha and max(alpha_values) > 0
        layers.append((width, height, hotspot_x, hotspot_y, valid_alpha))
    return layers


def validate_png(path: Path) -> None:
    with Image.open(path) as image:
        image.load()
        if image.mode != "RGBA":
            raise BuildError(f"{path.name} 不是 RGBA PNG。")
        minimum, maximum = image.getchannel("A").getextrema()
        if minimum != 0 or maximum == 0:
            raise BuildError(f"{path.name} 没有有效透明通道。")
        corners = (
            image.getpixel((0, 0))[3],
            image.getpixel((image.width - 1, 0))[3],
            image.getpixel((0, image.height - 1))[3],
            image.getpixel((image.width - 1, image.height - 1))[3],
        )
        if any(corners):
            raise BuildError(f"{path.name} 的画布角落不是透明像素。")
        histogram = image.getchannel("A").histogram()
        semi = sum(histogram[1:255])
        if semi > sum(histogram) * 0.2:
            raise BuildError(
                f"{path.name} 半透明像素占比异常，背景可能未抠干净。"
            )


def validate_theme(theme_path: Path) -> dict[str, object]:
    if not theme_path.is_dir():
        raise BuildError(f"主题目录不存在：{theme_path}")
    manifest_path = theme_path / "theme.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildError("theme.json 不存在或格式无效。") from exc

    expected_roles = [spec.role for spec in SPECS]
    cursors = manifest.get("cursors")
    if not isinstance(cursors, dict) or list(cursors) != expected_roles:
        raise BuildError("theme.json 必须按标准顺序映射全部 15 个角色。")

    cur_files = sorted(theme_path.glob("*.cur"))
    png_files = sorted(theme_path.glob("*.png"))
    if len(cur_files) != 15 or len(png_files) != 15:
        raise BuildError("主题必须正好包含 15 个 CUR 和 15 个 PNG。")

    expected_sizes = [(size, size) for size in SIZES]
    for spec in SPECS:
        expected_cur = theme_path / f"{spec.output_name}.cur"
        expected_png = theme_path / f"{spec.output_name}.png"
        if cursors.get(spec.role) != expected_cur.name:
            raise BuildError(f"theme.json 中 {spec.role} 的映射不正确。")
        if not expected_cur.is_file() or not expected_png.is_file():
            raise BuildError(f"缺少 {spec.output_name} 的 CUR 或 PNG。")
        validate_png(expected_png)
        layers = read_cur(expected_cur)
        if [(item[0], item[1]) for item in layers] != expected_sizes:
            raise BuildError(f"{expected_cur.name} 的 7 个尺寸层不正确。")
        if not all(item[4] for item in layers):
            raise BuildError(f"{expected_cur.name} 的 Alpha 通道无效。")

    return {
        "theme_name": str(manifest.get("name", "")),
        "theme_path": str(theme_path.resolve()),
        "cur_count": len(cur_files),
        "png_count": len(png_files),
        "sizes": list(SIZES),
        "hotspots_in_bounds": True,
        "alpha_valid": True,
        "manifest_valid": True,
    }


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="从 15 张 PNG 构建并校验 QMcursor/ArkCursor 主题。"
    )
    parser.add_argument("--input", type=Path, help="15 张 PNG 的目录或 5×3 合集")
    parser.add_argument("--theme-name", help="应用内显示的主题名称")
    parser.add_argument("--theme-dir", help="src/arkcursor/themes 下的目录名")
    parser.add_argument(
        "--background",
        default="auto",
        help="临时纯色背景，格式为 #RRGGBB；默认 auto",
    )
    parser.add_argument(
        "--chroma-tolerance",
        type=int,
        default=96,
        help="纯色背景和边缘溢色容差，默认 96",
    )
    parser.add_argument("--force", action="store_true", help="覆盖同名目标主题")
    parser.add_argument(
        "--validate-only",
        type=Path,
        metavar="THEME_PATH",
        help="仅校验现有主题目录",
    )
    return parser


def main() -> int:
    parser = create_parser()
    args = parser.parse_args()
    try:
        if args.validate_only:
            report = validate_theme(args.validate_only.resolve())
        else:
            if args.input is None or args.theme_name is None or args.theme_dir is None:
                parser.error(
                    "构建时必须同时提供 --input、--theme-name 和 --theme-dir。"
                )
            target = build_theme(
                args.input.resolve(),
                args.theme_name,
                args.theme_dir,
                parse_color(args.background),
                args.chroma_tolerance,
                args.force,
            )
            report = validate_theme(target)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except BuildError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
