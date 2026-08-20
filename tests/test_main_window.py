from qmcursor.models.theme import CursorTheme
from qmcursor.ui.main_window import theme_category, theme_supports_physics


def test_installed_ani_scheme_uses_ani_category() -> None:
    theme = CursorTheme(
        "系统安装的 ANI",
        {"Arrow": r"C:\Windows\Cursors\Normal.ani"},
        is_custom=False,
        kind="ani",
    )

    assert theme_category(theme) == "ANI 指针"


def test_bundled_cur_theme_uses_qmcursor_category() -> None:
    theme = CursorTheme(
        "内置 CUR",
        {"Arrow": "arrow.cur"},
        is_custom=True,
        kind="cur",
    )

    assert theme_category(theme) == "QMcursor 自制指针"


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
