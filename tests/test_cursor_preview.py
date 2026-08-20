import struct
from pathlib import Path

from qmcursor.ui.cursor_preview import read_ani_timing


def test_read_ani_timing(tmp_path: Path) -> None:
    header = struct.pack("<9I", 36, 4, 6, 32, 32, 32, 1, 3, 1)
    chunk = b"anih" + struct.pack("<I", len(header)) + header
    payload = b"ACON" + chunk
    ani_file = tmp_path / "preview.ani"
    ani_file.write_bytes(b"RIFF" + struct.pack("<I", len(payload)) + payload)

    frame_count, interval = read_ani_timing(str(ani_file))

    assert frame_count == 6
    assert interval == 50


def test_non_ani_uses_static_defaults(tmp_path: Path) -> None:
    cursor_file = tmp_path / "preview.cur"
    cursor_file.write_bytes(b"not-an-ani")

    assert read_ani_timing(str(cursor_file)) == (1, 100)
