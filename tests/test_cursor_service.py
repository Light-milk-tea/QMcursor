import json
from pathlib import Path
import struct
import zipfile

import pytest

import qmcursor.services.cursor_service as cursor_module
from qmcursor.main import apply_at_startup
from qmcursor.models.theme import CURSOR_ROLES, CursorTheme
from qmcursor.services.cursor_service import (
    CURSOR_SIZE_VALUE,
    CursorService,
    CursorServiceError,
)


class FakeRegistryKey:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def valid_ani_bytes() -> bytes:
    header = struct.pack("<9I", 36, 1, 1, 32, 32, 32, 1, 6, 1)
    anih = b"anih" + struct.pack("<I", len(header)) + header
    cursor_header = struct.pack("<HHH", 0, 2, 0)
    icon = b"icon" + struct.pack("<I", len(cursor_header)) + cursor_header
    frame_list = b"LIST" + struct.pack("<I", 4 + len(icon)) + b"fram" + icon
    payload = b"ACON" + anih + frame_list
    return b"RIFF" + struct.pack("<I", len(payload)) + payload


def test_expand_cursor_path_expands_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SystemRoot", r"C:\Windows")

    result = CursorService.expand_cursor_path(
        r'"%SystemRoot%\Cursors\aero_arrow.cur"'
    )

    assert result == r"C:\Windows\Cursors\aero_arrow.cur"


def test_initial_backup_is_created_only_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CursorService(tmp_path)
    snapshot = {
        "Arrow": {
            "value": r"C:\Windows\Cursors\aero_arrow.cur",
            "type": cursor_module.winreg.REG_SZ,
        }
    }
    monkeypatch.setattr(service, "_read_managed_values", lambda: snapshot)

    service.ensure_initial_backup()
    first_payload = json.loads(service.backup_path.read_text(encoding="utf-8"))
    assert first_payload["values"] == snapshot

    monkeypatch.setattr(
        service,
        "_read_managed_values",
        lambda: pytest.fail("不应覆盖已有备份"),
    )
    service.ensure_initial_backup()


def test_apply_failure_restores_previous_registry_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CursorService(tmp_path)
    previous = {
        "": {"value": "原方案", "type": cursor_module.winreg.REG_SZ},
        "Arrow": {"value": "", "type": cursor_module.winreg.REG_SZ},
    }
    restored: list[dict] = []
    restored_schemes: list[tuple[str, tuple[str, int] | None]] = []
    reload_calls = 0

    monkeypatch.setattr(service, "ensure_initial_backup", lambda: None)
    monkeypatch.setattr(service, "_read_managed_values", lambda: previous)
    previous_scheme = ("old.cur", cursor_module.winreg.REG_SZ)
    monkeypatch.setattr(service, "_read_user_scheme", lambda name: previous_scheme)
    monkeypatch.setattr(
        service, "_restore_managed_values", lambda values: restored.append(values)
    )
    monkeypatch.setattr(
        service,
        "_restore_user_scheme",
        lambda name, value: restored_schemes.append((name, value)),
    )
    monkeypatch.setattr(
        cursor_module.winreg,
        "CreateKeyEx",
        lambda *args, **kwargs: FakeRegistryKey(),
    )
    monkeypatch.setattr(
        cursor_module.winreg,
        "SetValueEx",
        lambda *args, **kwargs: None,
    )

    def reload_cursors() -> None:
        nonlocal reload_calls
        reload_calls += 1
        if reload_calls == 1:
            raise OSError("模拟刷新失败")

    monkeypatch.setattr(service, "_reload_system_cursors", reload_cursors)

    with pytest.raises(CursorServiceError, match="应用鼠标指针失败"):
        service.apply_theme(CursorTheme("测试", {}, source=2))

    assert restored == [previous]
    assert restored_schemes == [("测试", previous_scheme)]
    assert reload_calls == 2


def test_selected_theme_state_round_trip(tmp_path: Path) -> None:
    service = CursorService(tmp_path)
    theme = CursorTheme("已选主题", {"Arrow": ""}, source=2)

    service.save_selected_theme(theme)

    assert service.load_selected_theme() == theme
    service.clear_selected_theme()
    assert service.load_selected_theme() is None


def test_current_cursor_size_reads_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cursor_module.winreg,
        "OpenKey",
        lambda *args, **kwargs: FakeRegistryKey(),
    )
    monkeypatch.setattr(
        cursor_module.winreg,
        "QueryValueEx",
        lambda key, name: (80, cursor_module.winreg.REG_DWORD),
    )

    assert CursorService.current_cursor_size() == 80


def test_set_cursor_size_writes_registry_and_reloads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CursorService(tmp_path)
    writes: list[tuple[str, int, int]] = []
    size_updates: list[int] = []
    monkeypatch.setattr(service, "ensure_initial_backup", lambda: None)
    monkeypatch.setattr(service, "_read_managed_values", lambda: {})
    monkeypatch.setattr(
        cursor_module.winreg,
        "CreateKeyEx",
        lambda *args, **kwargs: FakeRegistryKey(),
    )
    monkeypatch.setattr(
        cursor_module.winreg,
        "SetValueEx",
        lambda key, name, reserved, value_type, value: writes.append(
            (name, value_type, value)
        ),
    )
    monkeypatch.setattr(
        service,
        "_set_system_cursor_size",
        lambda size: size_updates.append(size),
    )

    service.set_cursor_size(72)

    assert writes == [(CURSOR_SIZE_VALUE, cursor_module.winreg.REG_DWORD, 72)]
    assert size_updates == [72]


def test_set_cursor_size_rejects_unsupported_step(tmp_path: Path) -> None:
    service = CursorService(tmp_path)

    with pytest.raises(ValueError, match="步长"):
        service.set_cursor_size(81)


@pytest.mark.parametrize(
    "theme_name",
    (
        "伊雷娜",
        "塔菲新版",
    ),
)
def test_bundled_cursor_themes_are_available(theme_name: str) -> None:
    themes = CursorService.list_bundled_themes()

    theme = next(item for item in themes if item.name == theme_name)
    assert Path(theme.cursors["Arrow"]).name == "arrow.cur"
    assert Path(theme.cursors["Wait"]).name == "wait.cur"
    assert Path(theme.cursors["Hand"]).name == "hand.cur"
    assert all(theme.cursors[role] for role in CURSOR_ROLES)
    assert theme.missing_files() == []


def test_bundled_myrtle_ani_theme_is_available() -> None:
    themes = CursorService.list_bundled_themes()

    theme = next(item for item in themes if item.name == "桃金娘")
    assert theme.kind == "ani"
    assert theme.is_animated is True
    assert Path(theme.cursors["Arrow"]).name == "arrow.ani"
    assert Path(theme.cursors["Wait"]).name == "wait.ani"
    assert Path(theme.cursors["Hand"]).name == "hand.ani"
    assert all(theme.cursors[role] for role in CURSOR_ROLES)
    assert theme.missing_files() == []


def test_bundled_angelina_static_theme_is_available() -> None:
    themes = CursorService.list_bundled_themes()

    theme = next(item for item in themes if item.name == "安洁莉娜小人")
    assert theme.kind == "cur"
    assert theme.is_animated is False
    assert theme.frame_interval_ms is None
    assert Path(theme.cursors["Arrow"]).name == "arrow.cur"
    assert theme.cursors["Wait"] == ""
    assert theme.sizes is None
    assert theme.missing_files() == []


def test_retired_cursor_themes_are_not_listed() -> None:
    names = {theme.name for theme in CursorService.list_bundled_themes()}

    assert names.isdisjoint(
        {
            "粉白像素（概念版）",
            "纸鹤与风铃",
            "纸鹤与风铃（生图试用版）",
            "塔菲",
            "雷电将军",
            "安洁莉娜",
            "安洁莉娜 (2)",
        }
    )


def test_import_ani_directory_maps_mon3tr_names(tmp_path: Path) -> None:
    service = CursorService(tmp_path / "data")
    source = tmp_path / "pack"
    source.mkdir()
    (source / "Normal.ani").write_bytes(valid_ani_bytes())
    (source / "Busy.ani").write_bytes(valid_ani_bytes())
    (source / "Person.ani").write_bytes(valid_ani_bytes())
    (source / "install.inf").write_text(
        '[Strings]\nSCHEME_NAME = "测试动态主题"\n',
        encoding="utf-8",
    )

    imported = service.import_ani_pack(source)

    assert imported.name == "测试动态主题"
    assert imported.kind == "ani"
    assert Path(imported.cursors["Arrow"]).name == "arrow.ani"
    assert Path(imported.cursors["Wait"]).name == "wait.ani"
    assert imported.cursors["Hand"] == ""
    assert all("Person" not in theme.cursors for theme in [imported])
    discovered = service.list_imported_themes()
    assert [theme.name for theme in discovered] == ["测试动态主题"]
    assert discovered[0].missing_files() == []


def test_import_ani_zip_rejects_traversal(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../Normal.ani", valid_ani_bytes())

    with pytest.raises(CursorServiceError, match="不安全"):
        CursorService(tmp_path / "data").import_ani_pack(archive_path)


def test_import_rejects_invalid_ani_container(tmp_path: Path) -> None:
    source = tmp_path / "broken"
    source.mkdir()
    (source / "Normal.ani").write_bytes(b"RIFF\x04\x00\x00\x00ACON")

    with pytest.raises(CursorServiceError, match="不是有效"):
        CursorService(tmp_path / "data").import_ani_pack(source)


def test_apply_ani_theme_selects_size_and_registers_scheme(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CursorService(tmp_path / "data")
    arrow_32 = tmp_path / "32" / "arrow.ani"
    arrow_64 = tmp_path / "64" / "arrow.ani"
    arrow_32.parent.mkdir()
    arrow_64.parent.mkdir()
    arrow_32.write_bytes(valid_ani_bytes())
    arrow_64.write_bytes(valid_ani_bytes())
    theme = CursorTheme(
        "多尺寸动画",
        {"Arrow": str(arrow_32)},
        kind="ani",
        sizes={
            32: {"Arrow": str(arrow_32)},
            64: {"Arrow": str(arrow_64)},
        },
    )
    writes: list[tuple[str, int, object]] = []
    monkeypatch.setattr(service, "current_cursor_size", lambda: 60)
    monkeypatch.setattr(service, "ensure_initial_backup", lambda: None)
    monkeypatch.setattr(service, "_read_managed_values", lambda: {})
    monkeypatch.setattr(service, "_read_user_scheme", lambda name: None)
    monkeypatch.setattr(service, "_reload_system_cursors", lambda: None)
    monkeypatch.setattr(
        cursor_module.winreg,
        "CreateKeyEx",
        lambda *args, **kwargs: FakeRegistryKey(),
    )
    monkeypatch.setattr(
        cursor_module.winreg,
        "SetValueEx",
        lambda key, name, reserved, value_type, value: writes.append(
            (name, value_type, value)
        ),
    )

    service.apply_theme(theme)

    assert ("Arrow", cursor_module.winreg.REG_SZ, str(arrow_64)) in writes
    scheme_write = next(item for item in writes if item[0] == theme.name)
    assert str(arrow_64) in str(scheme_write[2]).split(",")[0]
    assert service.load_selected_theme() == theme


def test_startup_reapplies_saved_ani_theme() -> None:
    theme = CursorTheme("开机动画", {}, kind="ani")
    calls: list[tuple[CursorTheme, bool]] = []

    class StartupService:
        @staticmethod
        def load_selected_theme() -> CursorTheme:
            return theme

        @staticmethod
        def apply_theme(selected: CursorTheme, *, remember: bool = True) -> None:
            calls.append((selected, remember))

    assert apply_at_startup(StartupService()) == 0
    assert calls == [(theme, False)]
