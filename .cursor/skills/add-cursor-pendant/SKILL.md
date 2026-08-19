---
name: add-cursor-pendant
description: 为 QMcursor/ArkCursor 已有指针主题生成并安装挂坠（pendant.png），启用物理摇摆时在指针下以柔性绳索悬挂摇摆。用户提到挂坠、pendant、吊饰、指针装饰、给主题加挂件时使用。
---

# 为指针主题添加挂坠

为**已存在**的主题目录生成末端饰物 `pendant.png` 并安装。运行时无需改 Python：物理摇摆开启且主题含 `pendant.png` 时自动加载。

绳索由程序用 Verlet + 平滑曲线绘制；**素材里不要画长链条/棍状连杆**，否则会像摆钟。

## 输入约定

- 项目根目录含 `pyproject.toml` 与 `src/arkcursor/`。
- 目标为主题目录：`src/arkcursor/themes/<英文目录名>/`，须已有 `theme.json` 与可用 `arrow.png`。
- 用户指定主题名/目录；未指定时列出 `src/arkcursor/themes/*/theme.json` 供选择。
- 挂坠生图规范只读取同目录 [prompt.md](prompt.md)，不依赖项目 `doc/` 下的旧提示词。

## 工作流

### 1. 确认主题与风格

1. 完整阅读同目录 [prompt.md](prompt.md)。
2. 读取目标主题的 `theme.json`、`arrow.png`，以及用户工作文件夹中的参考图（若有）。
3. 用 2–4 条总结挂坠应继承的视觉规范：主色/金属色/宝石色、线宽、纹样或器物语言。
4. 选定临时纯色背景（参考图色板中没有的高饱和色，如 `#FF00FF`），记录精确十六进制值。

### 2. 生成挂坠原图

1. 使用同目录 [prompt.md](prompt.md) 中的英文主 Prompt，填入 `<BG_HEX>`。
2. 调用图像生成工具：1:1，推荐 1024×1024；`reference_image_paths` 包含全部参考图与该主题 `arrow.png`。
3. **强制造型约束**（失败则重生）：
   - 只要末端饰物（徽章/宝石/纹样吊坠），竖构图、居中、安全边距。
   - 顶部有清晰挂点（小环残段或徽顶），**不要**上方长链、绳、棍。
   - 可有 1–2 颗贴在徽下的短坠饰，勿做成整段硬直摆锤。
   - 禁止指针箭头、完整角色、场景、文字、水印、透明底/棋盘格。
   - 背景为指定纯色平面。
4. 生成后按文档「中文约束清单」自检；通过后向用户展示并询问是否采用。未获确认前不要覆盖主题内已有 `pendant.png`。

### 3. 抠图并安装

优先用项目虚拟环境与 Pillow。从项目根目录执行：

```powershell
python .cursor/skills/add-cursor-pendant/scripts/install_pendant.py `
  --input "<原图路径>" `
  --theme-dir "src/arkcursor/themes/<英文目录名>" `
  --background "<临时背景色>"
```

目标已有 `pendant.png` 且用户确认覆盖时加 `--force`。

脚本会：边缘连通抠除纯色、清理封闭色块、紧裁、缩到约 256px 高，写入 `theme_dir/pendant.png`。

校验：

```powershell
python .cursor/skills/add-cursor-pendant/scripts/install_pendant.py `
  --validate-only "src/arkcursor/themes/<英文目录名>"
```

### 4. 验证运行时

1. 确认 `src/arkcursor/themes/<目录>/pendant.png` 存在且背景透明。
2. 无需改 `theme.json` 或服务代码：`PhysicsCursorService` 会从 Arrow 同级目录加载 `pendant.png`。
3. 提醒用户：启用「物理摇摆」并应用该主题；若程序已在跑，用托盘「重启 QMcursor」或重启应用。
4. 快速自检：普通选择下挂点贴图形下方；左右甩动绳子呈弧线；切换到水平调整等角色时挂坠不猛跳。

## 运行时要点（勿重复造轮子）

| 项 | 行为 |
|---|---|
| 加载路径 | `<theme_dir>/pendant.png`（与 `arrow.png` 同级） |
| 枢轴 | 对挂坠图做 `hang_fraction`/`hotspot_fraction(..., "north")`，取顶部挂点 |
| 绳索 | Overlay 内柔性绳 + 金色曲线；角色切换时整绳平移防拽跳 |
| 尺寸 | 默认 `height_ratio=0.85`（相对指针尺寸）；一般不必改代码 |
| 无文件 | 该主题无挂坠，其它主题不受影响 |

相关实现：`src/arkcursor/services/physics_cursor_service.py`（`_load_pendant_asset`）、`src/arkcursor/ui/physics_overlay.py`（绳索与绘制）。

## 完成报告

简要说明：主题名与目录、原图来源、背景色、是否覆盖、校验结果、用户是否需重启。给出 `pendant.png` 路径。

## 反例

- 把长链条画进 PNG，再整图刚体旋转 → 像摆钟（已否决）。
- 只改 UI 文案不写 `pendant.png`。
- 为挂坠去改 15 个 CUR（挂坠不进系统光标文件）。
- 未询问就 `--force` 覆盖用户已有挂坠。
