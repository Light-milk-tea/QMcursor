from qmcursor.models.theme import CursorTheme
from qmcursor.ui.main_window import (
    category_item_label,
    theme_category,
    theme_display_name,
    theme_matches_query,
    theme_preview_meta,
    theme_supports_physics,
)


def test_installed_ani_scheme_uses_ani_category() -> None:
    theme = CursorTheme(
        "系统安装的 ANI",
        {"Arrow": r"C:\Windows\Cursors\Normal.ani"},
        is_custom=False,
        kind="ani",
    )

    assert theme_category(theme) == "QM新版指针"


def test_bundled_cur_theme_uses_qmcursor_category() -> None:
    theme = CursorTheme(
        "内置 CUR",
        {"Arrow": "arrow.cur"},
        is_custom=True,
        kind="cur",
    )

    assert theme_category(theme) == "QM旧版指针"


def test_static_windows_scheme_uses_system_category() -> None:
    theme = CursorTheme(
        "Windows Aero",
        {"Arrow": r"C:\Windows\Cursors\aero_arrow.cur"},
        is_custom=False,
        kind="cur",
    )

    assert theme_category(theme) == "系统指针"


def test_windows_scheme_with_only_busy_ani_stays_in_system_category() -> None:
    theme = CursorTheme(
        "Windows 默认（现代）",
        {
            "Arrow": r"C:\Windows\Cursors\aero_arrow.cur",
            "AppStarting": r"C:\Windows\Cursors\aero_working.ani",
            "Wait": r"C:\Windows\Cursors\aero_busy.ani",
        },
        is_custom=False,
        kind="ani",
    )

    assert theme_category(theme) == "系统指针"


def test_only_qmcursor_custom_themes_support_physics() -> None:
    custom = CursorTheme(
        "内置 CUR",
        {"Arrow": "arrow.cur"},
        is_custom=True,
        kind="cur",
    )
    system = CursorTheme(
        "Windows Aero",
        {"Arrow": r"C:\Windows\Cursors\aero_arrow.cur"},
        is_custom=False,
        kind="cur",
    )
    ani = CursorTheme(
        "系统安装的 ANI",
        {"Arrow": r"C:\Windows\Cursors\Normal.ani"},
        is_custom=False,
        kind="ani",
    )
    custom_ani = CursorTheme(
        "导入的 ANI",
        {"Arrow": "arrow.ani"},
        is_custom=True,
        kind="ani",
    )

    assert theme_supports_physics(custom) is True
    assert theme_supports_physics(system) is False
    assert theme_supports_physics(ani) is False
    assert theme_supports_physics(custom_ani) is False


def test_myrtle_ani_uses_old_category_without_physics() -> None:
    theme = CursorTheme(
        "桃金娘",
        {"Arrow": "arrow.ani"},
        is_custom=True,
        kind="ani",
    )

    assert theme_category(theme) == "QM旧版指针"
    assert theme_supports_physics(theme) is False


def test_mon3tr_windows_scheme_uses_wireframe_category() -> None:
    theme = CursorTheme(
        "mon3tr鼠标",
        {"Arrow": r"C:\Cursors\mon3tr\Normal.ani"},
        is_custom=False,
        kind="ani",
    )

    assert theme_category(theme) == "线框cursor"
    assert theme_supports_physics(theme) is False


def test_explicit_category_overrides_heuristic() -> None:
    theme = CursorTheme(
        "线框示例",
        {"Arrow": "arrow.ani"},
        is_custom=True,
        kind="ani",
        category="线框cursor",
    )

    assert theme_category(theme) == "线框cursor"
    assert theme_supports_physics(theme) is False


def test_theme_display_name_marks_native_ani() -> None:
    static = CursorTheme("伊蕾娜", {"Arrow": "arrow.cur"}, is_custom=True, kind="cur")
    animated = CursorTheme(
        "伊蕾娜Seedance",
        {"Arrow": "arrow.ani"},
        is_custom=True,
        kind="ani",
    )

    assert theme_display_name(static) == "伊蕾娜"
    assert theme_display_name(animated) == "伊蕾娜Seedance（系统动画）"


def test_category_item_label_shows_expand_state() -> None:
    assert category_item_label("系统指针", False) == "▶  系统指针"
    assert category_item_label("系统指针", True) == "▼  系统指针"


def test_theme_matches_query_uses_friendly_and_raw_names() -> None:
    theme = CursorTheme(
        "Windows Aero",
        {"Arrow": r"C:\Windows\Cursors\aero_arrow.cur"},
        is_custom=False,
        kind="cur",
    )

    assert theme_matches_query(theme, "")
    assert theme_matches_query(theme, "默认")
    assert theme_matches_query(theme, "aero")
    assert not theme_matches_query(theme, "伊蕾娜")


def test_theme_preview_meta_describes_theme_kind() -> None:
    custom = CursorTheme("伊蕾娜", {"Arrow": "arrow.cur"}, is_custom=True, kind="cur")
    ani = CursorTheme("伊蕾娜Seedance", {"Arrow": "arrow.ani"}, is_custom=True, kind="ani")
    system = CursorTheme(
        "Windows Aero",
        {"Arrow": r"C:\Windows\Cursors\aero_arrow.cur"},
        is_custom=False,
        kind="cur",
    )

    assert "物理摇摆" in theme_preview_meta(custom)
    assert "原生动画" in theme_preview_meta(ani)
    assert "系统方案" in theme_preview_meta(system)
