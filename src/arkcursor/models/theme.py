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
    kind: str = "cur"
    sizes: Mapping[int, Mapping[str, str]] | None = None
    frame_interval_ms: int | None = None

    def __post_init__(self) -> None:
        unknown = set(self.cursors) - set(CURSOR_ROLES)
        if unknown:
            raise ValueError(f"未知鼠标指针角色：{', '.join(sorted(unknown))}")

        normalized = {role: str(self.cursors.get(role, "")) for role in CURSOR_ROLES}
        object.__setattr__(self, "cursors", normalized)

        kind = self.kind.strip().casefold()
        if kind not in {"cur", "ani"}:
            raise ValueError(f"未知主题类型：{self.kind}")
        object.__setattr__(self, "kind", kind)

        normalized_sizes: dict[int, dict[str, str]] = {}
        for raw_size, raw_cursors in (self.sizes or {}).items():
            try:
                size = int(raw_size)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"无效的主题尺寸：{raw_size}") from exc
            if size <= 0 or not isinstance(raw_cursors, Mapping):
                raise ValueError(f"无效的主题尺寸配置：{raw_size}")
            string_cursors = {
                str(role): str(path) for role, path in raw_cursors.items() if path
            }
            unknown = set(string_cursors) - set(CURSOR_ROLES)
            if unknown:
                raise ValueError(
                    f"未知鼠标指针角色：{', '.join(sorted(str(x) for x in unknown))}"
                )
            normalized_sizes[size] = string_cursors
        object.__setattr__(self, "sizes", normalized_sizes or None)

        if self.frame_interval_ms is not None:
            interval = int(self.frame_interval_ms)
            if interval <= 0:
                raise ValueError("动画帧间隔必须大于 0。")
            object.__setattr__(self, "frame_interval_ms", interval)

    @property
    def is_animated(self) -> bool:
        paths = list(self.cursors.values())
        if self.sizes:
            paths.extend(
                path
                for cursors in self.sizes.values()
                for path in cursors.values()
            )
        return self.kind == "ani" or any(
            path.casefold().endswith(".ani") for path in paths if path
        )

    def nearest_size(self, size: int) -> int | None:
        """Return the nearest explicitly provided asset size."""
        if not self.sizes:
            return None
        return min(self.sizes, key=lambda candidate: (abs(candidate - size), candidate))

    def resolved_cursors(self, size: int | None = None) -> dict[str, str]:
        """Resolve the role paths for a requested cursor size."""
        resolved = dict(self.cursors)
        if size is not None:
            selected_size = self.nearest_size(size)
            if selected_size is not None and self.sizes is not None:
                resolved.update(self.sizes[selected_size])
        return resolved

    def missing_files(self, size: int | None = None) -> list[Path]:
        """Return non-empty cursor paths that are unavailable."""
        return [
            Path(path)
            for path in self.resolved_cursors(size).values()
            if path and not Path(path).is_file()
        ]

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "source": self.source,
            "is_custom": self.is_custom,
            "kind": self.kind,
            "cursors": dict(self.cursors),
        }
        if self.sizes:
            payload["sizes"] = {
                str(size): dict(cursors)
                for size, cursors in sorted(self.sizes.items())
            }
        if self.frame_interval_ms is not None:
            payload["frame_interval_ms"] = self.frame_interval_ms
        return payload

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
            kind=str(data.get("kind", "cur")),
            sizes=data.get("sizes") if isinstance(data.get("sizes"), Mapping) else None,
            frame_interval_ms=(
                int(data["frame_interval_ms"])
                if data.get("frame_interval_ms") is not None
                else None
            ),
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
        kind = "ani" if any(path.casefold().endswith(".ani") for path in cursors.values()) else "cur"
        return cls(name=name, cursors=cursors, source=source, kind=kind)
