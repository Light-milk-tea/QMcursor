# ArkCursor

ArkCursor 是一个基于 PySide6 的 **Windows 专用** 鼠标指针主题切换器（读写注册表 `Control Panel\Cursors`）。项目结构、依赖与运行方式见 `README.md`、`pyproject.toml` 和 `启动ArkCursor.bat`。

## Cursor Cloud specific instructions

Cloud VM 是 **Linux**，而本应用只能在 **Windows** 上完整运行。以下为非显而易见的注意事项：

- **平台限制**：`src/arkcursor/services/cursor_service.py` 与 `services/autostart_service.py` 在模块顶层 `import winreg`（Windows 专有）。因此 GUI（`run.py` / `启动ArkCursor.bat`）以及这两个服务在 Linux 上**无法导入或运行**——这是应用设计使然，不是环境搭建失败。核心的指针切换功能必须在 Windows 上验证。

- **虚拟环境**：更新脚本会在 `.venv` 中安装依赖。请统一使用 `.venv/bin/python`（例如 `.venv/bin/python -m pytest`）。

- **测试（在 Linux 上）**：只有 `tests/test_theme.py` 与 `tests/test_cursor_preview.py` 可运行/通过。`tests/test_cursor_service.py` 依赖 `winreg`，在 Linux 上会**收集报错（ModuleNotFoundError: winreg），属预期现象**。可跑跨平台子集：
  `.venv/bin/python -m pytest tests/test_theme.py tests/test_cursor_preview.py`

- **PySide6 系统库**：`PySide6.QtGui/QtWidgets` 需要 Qt 运行库（`libEGL.so.1` 等）。相关系统包（`libegl1`、`libgl1`、`libxkbcommon0`、`libxcb-*` 等）已装入 VM 快照，无需重复安装。无显示时可用 `QT_QPA_PLATFORM=offscreen`。

- **Lint**：仓库未配置任何 linter（无 ruff/flake8/black/pylint 配置），当前没有 lint 步骤可执行。

- **构建**：开发态即 `pip install -e ".[dev]"`（更新脚本已做）。`[build]` 组的 PyInstaller 用于打包 **Windows** 可执行文件，在 Linux 上打包无意义。

- **`tools/` 主题生成脚本**：依赖 `Pillow` 且读取被 `.gitignore` 排除、未提交的素材目录（如 `名侦探光之美少女/`），默认无法在此环境运行。
