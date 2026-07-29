# QMcursor

Windows 上换鼠标指针样式的小工具。选一套喜欢的主题，点应用就行；也能改大小、开机自动套用。

![伊雷娜](doc/previews/elaina.png)
![塔菲](doc/previews/taffy.png)
![光之美少女新版](doc/previews/precure_new.png)
![雷电将军新版](doc/previews/raiden-q-dango-01-mid.png)

## 能做什么

- 切换 Windows 已安装的指针方案，或使用软件自带的主题
- 调节指针大小
- 开机时自动重新应用你上次选的样式
- 应用前会备份当前设置，出问题可以一键恢复
- **物理摇摆**：指针会软跟随鼠标晃一晃；主题里如果有 `pendant.png`，还会在指针下面挂一条会晃的挂坠
- 开了物理摇摆后，关掉窗口会缩到右下角托盘，挂坠继续跟着；要彻底关掉，请托盘右键选「退出」

## 环境要求

- Windows

## 怎么用

1. 打开 [Releases](https://github.com/Light-milk-tea/QMcursor/releases)，下载最新的 `QMcursor-windows.zip`
2. 解压到任意目录
3. 双击其中的 `QMcursor.exe` 启动

请保持 `QMcursor.exe` 与同目录下的 `_internal` 文件夹在一起，不要只单独复制 exe。

## 自带主题

部分预览：

| 主题 | 预览 |
|------|------|
| 伊雷娜 | ![伊雷娜](doc/previews/elaina.png) |
| 塔菲 | ![塔菲](doc/previews/taffy.png) |
| 塔菲新版 | ![塔菲新版](doc/previews/taffy-new-01-normal-select.png) |
| 光之美少女新版 | ![光之美少女新版](doc/previews/precure_new.png) |
| 雷电将军新版 | ![雷电将军新版](doc/previews/raiden-q-dango-01-mid.png) |


伊雷娜主题已带挂坠，开启物理摇摆就能看到：
![伊雷娜挂坠](doc/previews/elaina_pendant.png)


## 开发相关

需要 Python 3.11 或更新。在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe run.py
```

也可双击 `启动QMcursor.bat`（会自动建虚拟环境并启动）。

运行测试：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

项目结构大致是：

- `src/arkcursor/`：程序代码和内置主题
- `tests/`：测试
- `doc/`：生图与说明文档
- `run.py`：开发启动入口

## 说明

- 只支持 Windows
- 物理摇摆靠透明叠加层实现，属于实验功能，个别全屏游戏或特殊软件里可能表现一般
- 本仓库地址：https://github.com/Light-milk-tea/QMcursor
