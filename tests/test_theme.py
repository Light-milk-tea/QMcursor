from pathlib import Path

import pytest

from arkcursor.models.theme import (
    CURSOR_ROLES,
    CursorTheme,
    friendly_theme_name,
)


def test_scheme_value_maps_all_standard_roles(tmp_path: Path) -> None:
    paths = [str(tmp_path / f"{index}.cur") for index in range(15)]

    theme = CursorTheme.from_scheme_value(
        "测试主题",
        ",".join(paths),
        2,
        expand_path=lambda value: value,
    )

    assert theme.name == "测试主题"
    assert theme.source == 2
    assert list(theme.cursors) == list(CURSOR_ROLES)
    assert theme.cursors["Arrow"] == paths[0]
    assert theme.cursors["Hand"] == paths[-1]


def test_short_scheme_uses_windows_defaults_for_missing_roles() -> None:
    theme = CursorTheme.from_scheme_value(
        "简短主题",
        "arrow.cur,help.cur",
        1,
        expand_path=lambda value: value,
    )

    assert theme.cursors["Arrow"] == "arrow.cur"
    assert theme.cursors["Help"] == "help.cur"
    assert theme.cursors["Wait"] == ""
    assert theme.cursors["Hand"] == ""


def test_unknown_role_is_rejected() -> None:
    with pytest.raises(ValueError, match="未知鼠标指针角色"):
        CursorTheme("错误主题", {"Unknown": "cursor.cur"})


def test_theme_round_trip() -> None:
    original = CursorTheme("主题", {"Arrow": "", "Hand": ""}, source=2)
    restored = CursorTheme.from_dict(original.to_dict())

    assert restored == original


@pytest.mark.parametrize(
    ("system_name", "display_name"),
    [
        ("Windows Aero", "Windows 默认（现代）"),
        ("Windows Black (extra large)", "黑色指针（特大）"),
        ("Windows Inverted (large)", "反色指针（大）"),
        ("Windows Standard (large)", "经典指针（大）"),
        ("Magnified", "放大指针"),
    ],
)
def test_windows_theme_names_are_localized(
    system_name: str, display_name: str
) -> None:
    assert friendly_theme_name(system_name) == display_name


def test_custom_theme_name_is_preserved() -> None:
    assert friendly_theme_name("动漫主题") == "动漫主题"
