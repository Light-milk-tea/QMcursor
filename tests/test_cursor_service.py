import json
from pathlib import Path

import pytest

import arkcursor.services.cursor_service as cursor_module
from arkcursor.models.theme import CURSOR_ROLES, CursorTheme
from arkcursor.services.cursor_service import (
    CURSOR_SIZE_VALUE,
    CursorService,
    CursorServiceError,
)


class FakeRegistryKey:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


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
    reload_calls = 0

    monkeypatch.setattr(service, "ensure_initial_backup", lambda: None)
    monkeypatch.setattr(service, "_read_managed_values", lambda: previous)
    monkeypatch.setattr(
        service, "_restore_managed_values", lambda values: restored.append(values)
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
        "粉白 Fluent 精致版",
        "纸鹤圆润超粗体",
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


def test_retired_cursor_themes_are_not_listed() -> None:
    names = {theme.name for theme in CursorService.list_bundled_themes()}

    assert names.isdisjoint(
        {
            "粉白像素（概念版）",
            "纸鹤与风铃",
            "纸鹤与风铃（生图试用版）",
        }
    )
