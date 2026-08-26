from pathlib import Path

import pytest

from qmcursor.models.theme import (
    CURSOR_ROLES,
    CursorTheme,
    friendly_theme_name,
    is_classic_system_scheme,
    is_hidden_scheme,
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


def test_ani_theme_resolves_nearest_size_and_round_trips(tmp_path: Path) -> None:
    arrow_32 = str(tmp_path / "32" / "arrow.ani")
    arrow_64 = str(tmp_path / "64" / "arrow.ani")
    original = CursorTheme(
        "动态主题",
        {"Arrow": arrow_32},
        kind="ani",
        sizes={32: {"Arrow": arrow_32}, 64: {"Arrow": arrow_64}},
        frame_interval_ms=100,
    )

    assert original.is_animated is True
    assert original.nearest_size(48) == 32
    assert original.nearest_size(60) == 64
    assert original.resolved_cursors(60)["Arrow"] == arrow_64
    assert CursorTheme.from_dict(original.to_dict()) == original


def test_scheme_with_ani_path_is_detected_as_animated() -> None:
    theme = CursorTheme.from_scheme_value(
        "系统动态主题",
        r"C:\Cursors\Normal.ani",
        1,
        expand_path=lambda value: value,
    )

    assert theme.kind == "ani"
    assert theme.is_animated is True


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


@pytest.mark.parametrize(
    ("system_name", "kept"),
    [
        ("Windows Aero", True),
        ("Windows Black", False),
        ("Windows Inverted", False),
        ("Windows Standard", False),
        ("Windows Aero L", False),
        ("Windows Aero XL)", False),
        ("Windows Black (large)", False),
        ("Windows Inverted (extra large)", False),
        ("Windows Standard (large)", False),
        ("Magnified", False),
    ],
)
def test_classic_system_schemes_exclude_size_variants(
    system_name: str, kept: bool
) -> None:
    assert is_classic_system_scheme(system_name) is kept


def test_mls_cursor_scheme_is_hidden_as_wireframe_duplicate() -> None:
    assert is_hidden_scheme("mls__cursor") is True
    assert is_hidden_scheme("线框·魔理莎") is False
