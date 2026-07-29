from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QGuiApplication, QImage

from arkcursor.models.theme import CURSOR_ROLES, CursorTheme
from arkcursor.services.physics_cursor_service import (
    PhysicsCursorError,
    PhysicsCursorService,
    is_shell_cover_band,
)
from arkcursor.ui.physics_overlay import (
    ensure_overlay_topmost,
    hang_fraction,
    hotspot_fraction,
    resolve_arrow_image_path,
    resolve_cursor_image_path,
)


@pytest.fixture(scope="module")
def qapp() -> QGuiApplication:
    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication([])
    return app


def test_resolve_cursor_image_path_prefers_sibling_png(tmp_path: Path) -> None:
    png = tmp_path / "arrow.png"
    cur = tmp_path / "arrow.cur"
    png.write_bytes(b"fake")
    cur.write_bytes(b"fake")

    assert resolve_cursor_image_path(str(cur)) == png
    assert resolve_cursor_image_path(str(png)) == png
    assert resolve_arrow_image_path(str(cur)) == png


def test_resolve_cursor_image_path_missing() -> None:
    assert resolve_cursor_image_path("") is None
    assert resolve_cursor_image_path(r"C:\missing\arrow.cur") is None


def test_physics_preference_roundtrip(tmp_path: Path) -> None:
    service = PhysicsCursorService(tmp_path)
    assert service.load_enabled() is False

    service.save_enabled(True)
    assert service.load_enabled() is True

    service.save_enabled(False)
    assert service.load_enabled() is False


def test_catalog_for_theme_requires_arrow_png(tmp_path: Path) -> None:
    cur = tmp_path / "arrow.cur"
    cur.write_bytes(b"not-a-real-cur")
    theme = CursorTheme(
        name="仅 CUR",
        cursors={role: str(cur) if role == "Arrow" else "" for role in CURSOR_ROLES},
        is_custom=True,
    )
    service = PhysicsCursorService(tmp_path)

    with pytest.raises(PhysicsCursorError, match="PNG"):
        service._catalog_for_theme(theme, 48)


def test_catalog_falls_back_missing_roles_to_arrow(
    tmp_path: Path,
    qapp: QGuiApplication,
) -> None:
    del qapp
    arrow = tmp_path / "arrow.png"
    image = QImage(32, 32, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    for y in range(8):
        for x in range(8):
            image.setPixelColor(x, y, QColor(255, 0, 0, 255))
    assert image.save(str(arrow))

    theme = CursorTheme(
        name="部分 PNG",
        cursors={
            role: str(arrow) if role == "Arrow" else "" for role in CURSOR_ROLES
        },
        is_custom=True,
    )
    service = PhysicsCursorService(tmp_path)
    catalog = service._catalog_for_theme(theme, 48)

    assert set(catalog) == set(CURSOR_ROLES)
    assert catalog["Hand"].pixmap is catalog["Arrow"].pixmap
    assert catalog["Hand"].hotspot != catalog["Arrow"].hotspot


def test_load_pendant_asset_from_theme_dir(
    tmp_path: Path,
    qapp: QGuiApplication,
) -> None:
    del qapp
    arrow = tmp_path / "arrow.png"
    pendant = tmp_path / "pendant.png"
    arrow_image = QImage(32, 32, QImage.Format.Format_ARGB32)
    arrow_image.fill(QColor(0, 0, 0, 0))
    for y in range(10):
        for x in range(10):
            arrow_image.setPixelColor(x, y, QColor(255, 0, 0, 255))
    assert arrow_image.save(str(arrow))

    pendant_image = QImage(20, 40, QImage.Format.Format_ARGB32)
    pendant_image.fill(QColor(0, 0, 0, 0))
    for y in range(4, 36):
        for x in range(6, 14):
            pendant_image.setPixelColor(x, y, QColor(255, 200, 50, 255))
    assert pendant_image.save(str(pendant))

    theme = CursorTheme(
        name="挂坠主题",
        cursors={
            role: str(arrow) if role == "Arrow" else "" for role in CURSOR_ROLES
        },
        is_custom=True,
    )
    service = PhysicsCursorService(tmp_path)
    catalog = service._catalog_for_theme(theme, 48)
    assert "Arrow" in catalog
    assert service._pendant is not None
    assert service._pendant.pixmap.width() > 0
    assert 0.0 <= service._pendant.pivot[0] <= 1.0
    assert 0.0 <= service._pendant.pivot[1] <= 1.0


def test_load_pendant_asset_optional(
    tmp_path: Path,
    qapp: QGuiApplication,
) -> None:
    del qapp
    arrow = tmp_path / "arrow.png"
    image = QImage(32, 32, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    image.setPixelColor(2, 2, QColor(255, 0, 0, 255))
    assert image.save(str(arrow))

    theme = CursorTheme(
        name="无挂坠",
        cursors={
            role: str(arrow) if role == "Arrow" else "" for role in CURSOR_ROLES
        },
        is_custom=True,
    )
    service = PhysicsCursorService(tmp_path)
    service._catalog_for_theme(theme, 48)
    assert service._pendant is None


def test_hang_fraction_bottom_center(qapp: QGuiApplication) -> None:
    del qapp
    image = QImage(20, 20, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    for y in range(4, 16):
        for x in range(5, 15):
            image.setPixelColor(x, y, QColor(255, 255, 255, 255))

    hx, hy = hang_fraction(image, "center")
    assert 0.4 < hx < 0.6
    assert hy > 0.65


def test_catalog_includes_role_hang(
    tmp_path: Path,
    qapp: QGuiApplication,
) -> None:
    del qapp
    arrow = tmp_path / "arrow.png"
    image = QImage(32, 32, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    for y in range(4, 28):
        for x in range(4, 28):
            image.setPixelColor(x, y, QColor(255, 0, 0, 255))
    assert image.save(str(arrow))

    theme = CursorTheme(
        name="挂点",
        cursors={
            role: str(arrow) if role == "Arrow" else "" for role in CURSOR_ROLES
        },
        is_custom=True,
    )
    service = PhysicsCursorService(tmp_path)
    catalog = service._catalog_for_theme(theme, 48)
    assert 0.0 <= catalog["Arrow"].hang[0] <= 1.0
    assert 0.0 <= catalog["Arrow"].hang[1] <= 1.0
    assert catalog["SizeWE"].hang[1] >= catalog["Arrow"].hotspot[1]


def test_hotspot_fraction_northwest(qapp: QGuiApplication) -> None:
    del qapp
    image = QImage(10, 10, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    image.setPixelColor(2, 3, QColor(255, 255, 255, 255))
    image.setPixelColor(8, 8, QColor(255, 255, 255, 255))

    hx, hy = hotspot_fraction(image, "northwest")
    assert hx == pytest.approx(2 / 9)
    assert hy == pytest.approx(3 / 9)

    cx, cy = hotspot_fraction(image, "center")
    assert cx == pytest.approx(5 / 9)
    assert cy == pytest.approx(5.5 / 9)


def test_ensure_overlay_topmost_ignores_null_hwnd() -> None:
    # Must not raise when the overlay has not created a native window yet.
    ensure_overlay_topmost(0)


def test_shell_cover_bands() -> None:
    assert is_shell_cover_band(1) is False  # desktop
    assert is_shell_cover_band(6) is True  # Start (MOGO)
    assert is_shell_cover_band(4) is True  # network / Action Center
    assert is_shell_cover_band(13) is True  # Search
