"""Build and validate a Windows ANI cursor pack from PNG frame directories."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import struct
import sys
from typing import Iterable

from PIL import Image

from build_cursor_theme import BuildError, hotspot_for, remove_chroma


@dataclass(frozen=True)
class AniSpec:
    source_dir: str
    output_name: str
    hotspot_kind: str


SPECS = (
    AniSpec("01-normal-select", "Normal.ani", "northwest"),
    AniSpec("02-help-select", "Help.ani", "northwest"),
    AniSpec("03-working-in-background", "Working.ani", "northwest"),
    AniSpec("04-busy", "Busy.ani", "center"),
    AniSpec("05-precision-select", "Precision.ani", "center"),
    AniSpec("06-text-select", "Text.ani", "center"),
    AniSpec("07-handwriting", "Handwriting.ani", "southwest"),
    AniSpec("08-unavailable", "Unavailable.ani", "center"),
    AniSpec("09-vertical-resize", "Vertical.ani", "center"),
    AniSpec("10-horizontal-resize", "Horizontal.ani", "center"),
    AniSpec("11-diagonal-resize-nwse", "Diagonal1.ani", "center"),
    AniSpec("12-diagonal-resize-nesw", "Diagonal2.ani", "center"),
    AniSpec("13-move", "Move.ani", "center"),
    AniSpec("14-alternate-select", "Alternate.ani", "north"),
    AniSpec("15-link-select", "Link.ani", "north"),
    AniSpec("16-location-select", "Pin.ani", "south"),
    AniSpec("17-person-select", "Person.ani", "center"),
)


def parse_color(value: str) -> tuple[int, int, int]:
    value = value.removeprefix("#")
    if len(value) != 6:
        raise BuildError("背景色必须使用 #RRGGBB。")
    try:
        return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))
    except ValueError as exc:
        raise BuildError("背景色必须使用 #RRGGBB。") from exc


def load_hotspots(path: Path | None) -> dict[str, tuple[int, int]]:
    if path is None:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BuildError(f"热点配置不是有效 JSON：{path}") from exc
    if not isinstance(payload, dict):
        raise BuildError("热点配置必须是对象。")
    hotspots: dict[str, tuple[int, int]] = {}
    for name, value in payload.items():
        if (
            not isinstance(name, str)
            or not isinstance(value, list)
            or len(value) != 2
            or not all(isinstance(item, int) for item in value)
        ):
            raise BuildError(f"热点配置格式错误：{name!r}")
        hotspots[name] = (value[0], value[1])
    return hotspots


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


def indexed_dib_payload(image: Image.Image) -> bytes:
    """Encode hard-edged pixel art as an 8-bit DIB plus a 1-bit mask."""
    image = image.convert("RGBA")
    width, height = image.size
    pixels = list(image.getdata())
    colors = list(
        dict.fromkeys(pixel[:3] for pixel in pixels if pixel[3] >= 128)
    )
    if len(colors) > 255:
        raise BuildError(
            f"8 位 ANI 单帧最多使用 255 种可见颜色，当前为 {len(colors)} 种。"
        )
    color_indexes = {color: index for index, color in enumerate(colors, 1)}

    palette = bytearray(256 * 4)
    for index, (red, green, blue) in enumerate(colors, 1):
        struct.pack_into("<BBBB", palette, index * 4, blue, green, red, 0)

    xor_stride = ((width + 3) // 4) * 4
    mask_stride = ((width + 31) // 32) * 4
    xor_bitmap = bytearray(xor_stride * height)
    and_mask = bytearray(mask_stride * height)
    for output_y, source_y in enumerate(range(height - 1, -1, -1)):
        for x in range(width):
            pixel = pixels[source_y * width + x]
            if pixel[3] >= 128:
                xor_bitmap[output_y * xor_stride + x] = color_indexes[pixel[:3]]
            else:
                and_mask[output_y * mask_stride + x // 8] |= 0x80 >> (x % 8)

    header = struct.pack(
        "<IiiHHIIiiII",
        40,
        width,
        height * 2,
        1,
        8,
        0,
        len(xor_bitmap) + len(and_mask),
        0,
        0,
        256,
        256,
    )
    return header + bytes(palette) + bytes(xor_bitmap) + bytes(and_mask)


def cur_bytes(
    image: Image.Image,
    hotspot: tuple[int, int],
    indexed_8bit: bool = False,
) -> bytes:
    width, height = image.size
    payload = indexed_dib_payload(image) if indexed_8bit else dib_payload(image)
    entry = struct.pack(
        "<BBBBHHII",
        0 if width == 256 else width,
        0 if height == 256 else height,
        0,
        0,
        hotspot[0],
        hotspot[1],
        len(payload),
        22,
    )
    return struct.pack("<HHH", 0, 2, 1) + entry + payload


def riff_chunk(chunk_id: bytes, payload: bytes) -> bytes:
    padding = b"\0" if len(payload) % 2 else b""
    return chunk_id + struct.pack("<I", len(payload)) + payload + padding


def ani_bytes(
    frames: Iterable[tuple[Image.Image, tuple[int, int]]],
    jif_rate: int,
    indexed_8bit: bool = False,
) -> bytes:
    prepared = list(frames)
    if not prepared:
        raise BuildError("ANI 至少需要一帧。")
    width, height = prepared[0][0].size
    icon_chunks = b"".join(
        riff_chunk(b"icon", cur_bytes(image, hotspot, indexed_8bit))
        for image, hotspot in prepared
    )
    header = struct.pack(
        "<9I",
        36,
        len(prepared),
        len(prepared),
        width,
        height,
        8 if indexed_8bit else 32,
        1,
        jif_rate,
        1,
    )
    payload = (
        b"ACON"
        + riff_chunk(b"anih", header)
        + riff_chunk(b"LIST", b"fram" + icon_chunks)
    )
    return b"RIFF" + struct.pack("<I", len(payload)) + payload


def prepare_frame(
    path: Path,
    size: int,
    background: tuple[int, int, int],
    tolerance: int,
) -> Image.Image:
    with Image.open(path) as opened:
        opened.load()
        image = opened.convert("RGBA")
    image = remove_chroma(image, background, tolerance)
    if image.size != (size, size):
        image = image.resize((size, size), Image.Resampling.NEAREST)
    alpha_min, alpha_max = image.getchannel("A").getextrema()
    if alpha_min != 0 or alpha_max == 0:
        raise BuildError(f"PNG 背景不是有效透明通道：{path}")
    return image


def ani_hotspot_for(image: Image.Image, kind: str) -> tuple[int, int]:
    if kind != "south":
        return hotspot_for(image, kind)
    alpha = image.getchannel("A")
    points = [
        (x, y)
        for y in range(image.height)
        for x in range(image.width)
        if alpha.getpixel((x, y)) >= 128
    ]
    if not points:
        raise BuildError("指针没有可见像素。")
    bottom = max(y for _, y in points)
    band = [
        x
        for x, y in points
        if y >= bottom - max(2, image.height // 50)
    ]
    return ((min(band) + max(band)) // 2, bottom)


def build_pack(
    source_root: Path,
    output_root: Path,
    size: int,
    jif_rate: int,
    background: tuple[int, int, int],
    tolerance: int,
    indexed_8bit: bool = False,
    hotspot_overrides: dict[str, tuple[int, int]] | None = None,
) -> None:
    if not 16 <= size <= 256:
        raise BuildError("帧尺寸必须在 16–256 之间。")
    if not 1 <= jif_rate <= 600:
        raise BuildError("JifRate 必须在 1–600 之间。")
    output_root.mkdir(parents=True, exist_ok=True)
    for spec in SPECS:
        frame_dir = source_root / spec.source_dir
        frame_paths = sorted(frame_dir.glob("*.png"))
        if not frame_paths:
            raise BuildError(f"缺少帧目录或 PNG：{frame_dir}")
        images = [
            prepare_frame(path, size, background, tolerance)
            for path in frame_paths
        ]
        overrides = hotspot_overrides or {}
        hotspot = overrides.get(spec.source_dir) or overrides.get(spec.output_name)
        if hotspot is None:
            hotspot = ani_hotspot_for(images[0], spec.hotspot_kind)
        if not (0 <= hotspot[0] < size and 0 <= hotspot[1] < size):
            raise BuildError(f"{spec.source_dir} 热点超出 {size}px 画布：{hotspot}")
        frames = [(image, hotspot) for image in images]
        output = output_root / spec.output_name
        output.write_bytes(ani_bytes(frames, jif_rate, indexed_8bit))
    validate_pack(
        output_root,
        expected_size=size,
        expected_bit_depth=8 if indexed_8bit else 32,
    )


def iter_chunks(
    data: bytes, start: int, end: int
) -> Iterable[tuple[bytes, bytes]]:
    offset = start
    while offset + 8 <= end:
        chunk_id = data[offset : offset + 4]
        size = struct.unpack_from("<I", data, offset + 4)[0]
        payload_start = offset + 8
        payload_end = payload_start + size
        if payload_end > end:
            raise BuildError("RIFF 块越界。")
        yield chunk_id, data[payload_start:payload_end]
        offset = payload_end + (size % 2)
    if offset != end:
        raise BuildError("RIFF 块对齐错误。")


def validate_ani(
    path: Path,
    expected_size: int | None = None,
    expected_bit_depth: int | None = None,
) -> dict[str, int]:
    data = path.read_bytes()
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"ACON":
        raise BuildError(f"不是有效 RIFF ACON：{path}")
    riff_end = struct.unpack_from("<I", data, 4)[0] + 8
    if riff_end != len(data):
        raise BuildError(f"RIFF 长度错误：{path}")
    frame_count = 0
    header_count = None
    width = height = None
    header_bit_depth = None
    hotspots: set[tuple[int, int]] = set()
    frame_bit_depths: set[int] = set()
    for chunk_id, payload in iter_chunks(data, 12, riff_end):
        if chunk_id == b"anih":
            if len(payload) < 36:
                raise BuildError(f"anih 太短：{path}")
            (
                header_size,
                header_count,
                _steps,
                width,
                height,
                header_bit_depth,
                planes,
                _rate,
                flags,
            ) = struct.unpack_from("<9I", payload)
            if (
                header_size != 36
                or planes != 1
                or flags != 1
                or header_bit_depth not in {8, 32}
            ):
                raise BuildError(f"anih 参数错误：{path}")
            if (
                expected_bit_depth is not None
                and header_bit_depth != expected_bit_depth
            ):
                raise BuildError(
                    f"ANI 头位深不是 {expected_bit_depth} 位：{path}"
                )
        elif chunk_id == b"LIST" and payload[:4] == b"fram":
            for nested_id, cursor in iter_chunks(payload, 4, len(payload)):
                if nested_id != b"icon":
                    continue
                if len(cursor) < 22:
                    raise BuildError(f"CUR 帧太短：{path}")
                reserved, cursor_type, count = struct.unpack_from("<HHH", cursor)
                if (reserved, cursor_type, count) != (0, 2, 1):
                    raise BuildError(f"CUR 帧头错误：{path}")
                (
                    entry_width,
                    entry_height,
                    _colors,
                    _reserved,
                    hotspot_x,
                    hotspot_y,
                    payload_size,
                    payload_offset,
                ) = struct.unpack_from("<BBBBHHII", cursor, 6)
                actual_width = entry_width or 256
                actual_height = entry_height or 256
                if payload_offset + payload_size != len(cursor):
                    raise BuildError(f"CUR 数据长度错误：{path}")
                if payload_size < 40:
                    raise BuildError(f"CUR DIB 数据太短：{path}")
                (
                    dib_header_size,
                    dib_width,
                    dib_double_height,
                    dib_planes,
                    dib_bit_depth,
                ) = struct.unpack_from("<IiiHH", cursor, payload_offset)
                if (
                    dib_header_size < 40
                    or dib_width != actual_width
                    or dib_double_height != actual_height * 2
                    or dib_planes != 1
                    or dib_bit_depth not in {8, 32}
                ):
                    raise BuildError(f"CUR DIB 参数错误：{path}")
                if (
                    expected_bit_depth is not None
                    and dib_bit_depth != expected_bit_depth
                ):
                    raise BuildError(
                        f"ANI 帧位深不是 {expected_bit_depth} 位：{path}"
                    )
                if not (0 <= hotspot_x < actual_width and 0 <= hotspot_y < actual_height):
                    raise BuildError(f"热点超出帧范围：{path}")
                if expected_size is not None and (
                    actual_width != expected_size or actual_height != expected_size
                ):
                    raise BuildError(f"ANI 帧尺寸不是 {expected_size}px：{path}")
                hotspots.add((hotspot_x, hotspot_y))
                frame_bit_depths.add(dib_bit_depth)
                frame_count += 1
    if header_count is None or width is None or height is None:
        raise BuildError(f"缺少 anih：{path}")
    if frame_count != header_count or frame_count == 0:
        raise BuildError(f"ANI 帧数不匹配：{path}")
    if len(hotspots) != 1:
        raise BuildError(f"动画帧热点不一致：{path}")
    if len(frame_bit_depths) != 1:
        raise BuildError(f"ANI 帧位深不一致：{path}")
    return {
        "frames": frame_count,
        "width": width,
        "height": height,
        "bit_depth": next(iter(frame_bit_depths)),
        "hotspot_x": next(iter(hotspots))[0],
        "hotspot_y": next(iter(hotspots))[1],
    }


def validate_pack(
    output_root: Path,
    expected_size: int | None = None,
    expected_bit_depth: int | None = None,
) -> dict[str, dict[str, int]]:
    missing = [
        spec.output_name
        for spec in SPECS
        if not (output_root / spec.output_name).is_file()
    ]
    if missing:
        raise BuildError("ANI 包缺少文件：\n" + "\n".join(missing))
    extras = {
        path.name
        for path in output_root.glob("*.ani")
        if path.name not in {spec.output_name for spec in SPECS}
    }
    if extras:
        raise BuildError("ANI 包存在未识别文件：" + ", ".join(sorted(extras)))
    return {
        spec.output_name: validate_ani(
            output_root / spec.output_name,
            expected_size,
            expected_bit_depth,
        )
        for spec in SPECS
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="包含 17 个帧目录的 source 路径")
    parser.add_argument("--output", type=Path, help="ANI package 输出路径")
    parser.add_argument("--size", type=int, default=32)
    parser.add_argument("--jif-rate", type=int, default=6)
    parser.add_argument("--background", default="#FF00FF")
    parser.add_argument("--tolerance", type=int, default=96)
    parser.add_argument(
        "--hotspots",
        type=Path,
        help="可选 JSON：按源目录名或 ANI 文件名覆盖固定热点坐标。",
    )
    parser.add_argument(
        "--indexed-8bit",
        action="store_true",
        help="使用硬边 8 位索引色和 1 位透明掩码，适合像素风 ANI。",
    )
    parser.add_argument("--validate-only", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.validate_only:
            report = validate_pack(args.validate_only, expected_size=args.size)
        else:
            if args.input is None or args.output is None:
                parser.error("--input 和 --output 都是必需参数。")
            build_pack(
                args.input,
                args.output,
                args.size,
                args.jif_rate,
                parse_color(args.background),
                args.tolerance,
                args.indexed_8bit,
                load_hotspots(args.hotspots),
            )
            report = validate_pack(
                args.output,
                expected_size=args.size,
                expected_bit_depth=8 if args.indexed_8bit else 32,
            )
        for name, info in report.items():
            print(
                f"{name}: {info['frames']} 帧, "
                f"{info['width']}x{info['height']}, {info['bit_depth']} 位, "
                f"热点 ({info['hotspot_x']}, {info['hotspot_y']})"
            )
        return 0
    except (BuildError, OSError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
