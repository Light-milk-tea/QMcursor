# ArkCursor

ArkCursor 是一个 Windows 专用的 PySide6 鼠标指针样式切换工具。当前版本读取电脑中已经安装的 Windows 指针方案，支持各类事件指针预览、动态 `.ani` 播放、一键应用、首次设置备份、恢复以及开机自动重新应用。

## 环境要求

- Windows 10 或 Windows 11
- Python 3.11 或更高版本
- 不需要管理员权限

## 安装与运行

在 PowerShell 中进入项目目录：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python run.py
```

首次点击“应用所选样式”时，程序会将当前指针配置备份到：

```text
%LOCALAPPDATA%\ArkCursor\backup.json
```

“恢复首次备份”会恢复这份配置。程序只修改当前 Windows 用户的 `HKCU\Control Panel\Cursors`，并调用 Windows API 立即刷新指针。

## 开机自动应用

勾选界面中的“开机时自动重新应用所选样式”即可。程序会在当前用户的启动项中写入 ArkCursor，并在登录时使用 `--startup` 静默应用最后选择的主题，然后立即退出，不会常驻后台。

也可以手动验证静默模式：

```powershell
python run.py --startup
```

## 运行测试

```powershell
python -m pip install -e ".[dev]"
python -m pytest
```

## 打包 Windows EXE

```powershell
python -m pip install -e ".[build]"
pyinstaller --noconfirm --onefile --windowed --name ArkCursor run.py
```

生成文件位于 `dist\ArkCursor.exe`。打包后的开机启动项会直接引用该 EXE。

## 后续添加自定义主题

底层主题模型已经按 Windows 的 15 种标准指针角色组织。后续可增加如下目录：

```text
themes/
  anime-theme/
    theme.json
    arrow.cur
    hand.cur
    wait.ani
```

自定义主题应使用 `.cur` 或 `.ani` 文件，并在 `theme.json` 中提供各角色到文件的映射。应用流程仍复用现有的备份、注册表写入和系统刷新逻辑。
