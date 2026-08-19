---
name: generate-ani-cursor-theme
description: 按 Mon3tr 与魔理沙光标的形态分布、硬边像素和动画节奏，生成 17 角色、48×48、8 位、8 帧 Windows 原生 ANI 光标包。用户提到生成动态光标、ANI 指针、Mon3tr 风格、魔理沙光标风格或角色像素光标时使用。
---

# 生成 Mon3tr / 魔理沙式 ANI 光标

完成从角色参考图到可导入 QMcursor 的 17 角色 ANI 包。不得生成旧式 15 PNG / 多层 CUR 主题。

## 唯一规范

开始前完整读取：

1. `doc/Mon3tr魔理沙风格ANI光标生成提示词.md`
2. `doc/ANI动态鼠标指针制作标准流程.md`

若两者有差异，以第一份文件的 48×48、8 位、每角色 8 帧要求为准。

不得寻找、恢复或使用已经删除的旧静态 CUR 提示词与旧 Skill。

## 输入

- 项目根目录包含 `pyproject.toml` 与 `src/arkcursor/`。
- 用户提供主题工作目录；目录中应有 4–6 张角色参考图。
- 从文件夹名和参考图推断中文主题名；无法判断时只询问一次。
- 使用本地 Mon3tr、魔理沙 ANI 抽帧作为构图与动画基准，不复制其角色像素。

## 固定输出

- 17 个角色。
- 每角色 8 张 48×48 RGBA PNG。
- Alpha 仅 0/255，1px 硬描边，固定调色板。
- 17 个 48×48、8 位 ANI。
- `JifRate=6`，约 100ms/帧。
- `style-summary.md`、`hotspots.json`、`build_assets.py`、`source/`、`preview/`、`package/`。

## 工作流

### 1. 分析角色与基准

1. 读取全部原始参考图；不得把旧生成图当原始参考。
2. 解码或读取 Mon3tr、魔理沙成品帧，记录：
   - 角色态与功能态的分工。
   - 主体占比、热点位置和负空间。
   - 1px 轮廓、色数、像素密度。
   - 哪些角色真正运动，哪些角色复用静态帧。
3. 写 `style-summary.md`：
   - 20–30 色固定色板。
   - 3–5 个角色识别元素。
   - 普通选择的热点器物与人物位置。
   - 可动部件和动作节奏。

### 2. 只生成普通选择关键帧

1. 使用新 Prompt 的“普通选择关键帧生图 Prompt”。
2. 必须调用图像生成工具，`reference_image_paths` 包含：
   - 全部角色参考图。
   - Mon3tr / 魔理沙关键帧参考。
3. 生图描述必须包含：
   - 按逻辑 48×48 像素格设计并最近邻放大。
   - 角色与功能尖端一体化。
   - 禁止独立默认箭头加缩小立绘。
   - 纯色临时背景，主体不使用背景色。
4. 将概念图压回 48×48，清理成固定色板和硬 Alpha。
5. 检查：
   - 功能尖端清楚且可作为热点。
   - 脸与双眼完整对称。
   - 角色和道具不粘成无法辨认的色团。
   - 原生 48px 下可读。
6. 生成原尺寸和最近邻放大预览，展示给用户确认。
7. 未确认前禁止制作其余角色。

### 3. 制作 Normal 八帧

1. 将关键帧拆成头、眼、嘴、耳朵/帽子、头发/尾巴、身体、衣摆、道具、粒子等像素层。
2. 用逐像素编辑或主题专用 `build_assets.py` 制作 8 帧。
3. 热点尖端保持绝对静止；其他部件围绕热点呼吸、眨眼或轻动。
4. 禁止对 8 帧分别调用生图工具。
5. 输出 `preview/01-normal-select.gif` 和帧表，检查首尾循环。

### 4. 制作其余十六个角色

按新 Prompt 的角色表执行。

角色态应有有效动画：

- Help
- Working
- Unavailable
- Link
- Pin
- Person

功能态：

- Busy 使用主题核心做 8 帧循环。
- Precision 只做轻微中心脉冲。
- Text、Handwriting、四种 Resize、Move、Alternate 可将静态帧复用 8 次。

每个角色完成后先检查方向、热点、色板和 48px 可读性，再继续下一个。

### 5. 写热点配置

在工作目录写 `hotspots.json`：

```json
{
  "01-normal-select": [2, 5],
  "02-help-select": [2, 5],
  "03-working-in-background": [2, 5],
  "04-busy": [24, 24],
  "05-precision-select": [24, 24],
  "06-text-select": [23, 24],
  "07-handwriting": [7, 41],
  "08-unavailable": [5, 5],
  "09-vertical-resize": [24, 24],
  "10-horizontal-resize": [24, 24],
  "11-diagonal-resize-nwse": [24, 24],
  "12-diagonal-resize-nesw": [24, 24],
  "13-move": [24, 24],
  "14-alternate-select": [24, 5],
  "15-link-select": [4, 7],
  "16-location-select": [4, 7],
  "17-person-select": [4, 7]
}
```

坐标必须按实际可见尖端修正；示例不是无条件固定值。

### 6. 构建 ANI

从项目根目录执行：

```powershell
python .cursor/skills/generate-qmcursor-theme/scripts/build_ani_theme.py `
  --input "<工作目录>/source" `
  --output "<工作目录>/package" `
  --size 48 `
  --jif-rate 6 `
  --indexed-8bit `
  --hotspots "<工作目录>/hotspots.json"
```

在 `package/theme.inf` 写入：

```ini
[Strings]
SCHEME_NAME="<中文主题名>"
```

### 7. 验证

必须验证：

- 17 个目录 × 8 帧，共 136 张 PNG。
- 48×48、硬 Alpha、无色键污染、可见色不超过 255。
- 角色态至少 4 个不同有效帧。
- 同一角色热点全帧一致。
- 17 个 ANI 均为 RIFF `ACON`、8 位、8 帧、`JifRate=6`。
- `LoadCursorFromFileW` 可加载全部 ANI。
- QMcursor 隔离导入传统 15 角色成功；Pin / Person 保留在包中。
- `python -m pytest`
- `python -m compileall -q src tests`
- 检查新改文件的 IDE Lint。

## 完成报告

报告：

- 主题名与工作目录。
- 普通选择预览。
- 17 角色、136 帧、17 ANI 是否完整。
- 位深、帧率、热点、Alpha 与 Windows 加载结果。
- QMcursor 导入和测试结果。
- 默认不主动替换用户当前系统指针；用户明确要求后再应用。
