"""Cursor theme model shared by built-in and future custom themes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

CURSOR_ROLES = (
    "Arrow",
    "Help",
    "AppStarting",
    "Wait",
    "Crosshair",
    "IBeam",
    "NWPen",
    "No",
    "SizeNS",
    "SizeWE",
    "SizeNWSE",
    "SizeNESW",
    "SizeAll",
    "UpArrow",
    "Hand",
)

ROLE_LABELS = {
    "Arrow": "普通选择",
    "Help": "帮助选择",
    "AppStarting": "后台运行",
    "Wait": "忙",
    "Crosshair": "精确选择",
    "IBeam": "文本选择",
    "NWPen": "手写",
    "No": "不可用",
    "SizeNS": "垂直调整",
    "SizeWE": "水平调整",
    "SizeNWSE": "对角线调整 1",
    "SizeNESW": "对角线调整 2",
    "SizeAll": "移动",
    "UpArrow": "候选选择",
    "Hand": "链接选择",
}

THEME_NAME_LABELS = {
    "magnified": "放大指针",
    "windows aero": "Windows 默认（现代）",
    "windows aero l": "Windows 默认（大）",
    "windows aero xl)": "Windows 默认（特大）",
    "windows black": "黑色指针（标准）",
    "windows black (large)": "黑色指针（大）",
    "windows black (extra large)": "黑色指针（特大）",
    "windows inverted": "反色指针（标准）",
    "windows inverted (large)": "反色指针（大）",
    "windows inverted (extra large)": "反色指针（特大）",
    "windows standard": "经典指针（标准）",
    "windows standard (large)": "经典指针（大）",
    "windows standard (extra large)": "经典指针（特大）",
}


def friendly_theme_name(name: str) -> str:
    """Return an easy-to-understand Chinese label for Windows themes."""
    return THEME_NAME_LABELS.get(name.strip().casefold(), name)


@dataclass(frozen=True, slots=True)
class CursorTheme:
    """A complete Windows cursor scheme."""

    name: str
    cursors: Mapping[str, str]
    source: int = 2
    is_custom: bool = False

    def __post_init__(self) -> None:
        unknown = set(self.cursors) - set(CURSOR_ROLES)
        if unknown:
            raise ValueError(f"未知鼠标指针角色：{', '.join(sorted(unknown))}")

        normalized = {role: str(self.cursors.get(role, "")) for role in CURSOR_ROLES}
        object.__setattr__(self, "cursors", normalized)

    def missing_files(self) -> list[Path]:
        """Return non-empty cursor paths that are unavailable."""
        return [
            Path(path)
            for path in self.cursors.values()
            if path and not Path(path).is_file()
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source": self.source,
            "is_custom": self.is_custom,
            "cursors": dict(self.cursors),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CursorTheme":
        cursors = data.get("cursors")
        if not isinstance(cursors, Mapping):
            raise ValueError("主题数据缺少 cursors 映射。")

        return cls(
            name=str(data.get("name", "未命名主题")),
            source=int(data.get("source", 1)),
            cursors={str(key): str(value) for key, value in cursors.items()},
            is_custom=bool(data.get("is_custom", False)),
        )

    @classmethod
    def from_scheme_value(
        cls,
        name: str,
        value: str,
        source: int,
        *,
        expand_path,
    ) -> "CursorTheme":
        """Parse the comma-delimited value used by Windows scheme keys."""
        values = [part.strip() for part in value.split(",")]
        values.extend([""] * (len(CURSOR_ROLES) - len(values)))
        cursors = {
            role: expand_path(path) if path else ""
            for role, path in zip(CURSOR_ROLES, values, strict=False)
        }
        return cls(name=name, cursors=cursors, source=source)
