from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QGuiApplication, QImage

from arkcursor.models.theme import CURSOR_ROLES, CursorTheme
from arkcursor.services.physics_cursor_service import (
    PhysicsCursorError,
    PhysicsCursorService,
)
from arkcursor.ui.physics_overlay import (
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
