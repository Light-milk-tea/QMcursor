---
name: generate-ani-cursor-theme
description: 按 Seedance 流程为 QMcursor 制作角色动态光标：先确认高清 concept 静帧，再用 Seedance 图生视频生成分层闲置，抽 16 帧做成 128×128、32 位 ANI。禁止 Prompt B 拆层派生、禁止真像素量化稿当正式帧。用户提到生成动态光标、ANI 指针、Seedance 动画或角色像素光标时使用。
---

# 生成 Mon3tr / 魔理沙式 ANI 光标

完成从角色参考图到可导入 QMcursor 的 17 角色 ANI 包。不得生成旧式 15 PNG / 多层 CUR 主题。

## 唯一规范

开始前完整读取：

1. `doc/Seedance动画指针制作流程.md`
2. `doc/ANI动态鼠标指针制作标准流程.md`

若两者有差异，以第一份为准：先确认高清 concept 静帧，再 Seedance 图生视频，再抽 16 帧做成 128×128、32 位 ANI。禁止 Prompt B、禁止 `build_assets.py` 猜层派生续帧，禁止把最近邻量化 PNG 当正式帧。

`doc/Mon3tr魔理沙风格ANI光标生成提示词.md` 只作构图参考，不要执行其中的 A2 / Prompt B。

## 输入

- 项目根目录包含 `pyproject.toml` 与 `src/qmcursor/`。
- 用户提供主题工作目录；目录中应有 4–6 张角色参考图。
- 从文件夹名和参考图推断中文主题名；无法判断时只询问一次。
- 使用本地 Mon3tr、魔理沙 ANI 抽帧作为构图与动画基准，不复制其角色像素。

## 固定输出

- 先做通 `Normal`；完整主题再补其余角色。
- 动态角色：每角色 16 张 `128×128` RGBA PNG。
- Alpha 仅 0/255；高清缩小用 LANCZOS。
- 动态 ANI：128×128、32 位、16 帧、`JifRate=6`。
- 功能态可用静帧。
- `style-summary.md`、`hotspots.json`、`concept/`、`source/`、`preview/`、`package/`。
- 不要为新主题写上千行 `build_assets.py` 派生续帧。

## 动画预览反馈（强制）

动画每次改好后要给我一个gif预览。

- 每一轮动画修改完成并通过当轮验证后，都必须重新生成并在回复中直接展示最新 GIF。
- Normal 和其他所有动态角色都适用；中间改进版本也不得省略。
- 不得只提供 PNG、帧表、文件路径或文字说明来代替 GIF。
- GIF 必须使用本轮正式帧、固定调色板、最近邻放大和约 100ms/帧，避免预览自身产生闪色或模糊。

## 工作流

按 `doc/Seedance动画指针制作流程.md` 的 S0–S5 执行。不要执行旧 A2 / Prompt B。

### 1. 分析角色与基准

1. 读取全部原始参考图；不得把旧生成图当原始参考。
2. 解码或读取 Mon3tr、魔理沙成品帧，记录：
   - 角色态与功能态的分工。
   - 主体占比、热点位置和负空间。
   - 1px 轮廓、色数、像素密度；魔理沙的眼白/眼眶/中缝构造，以及描边是统一近黑还是材质暗色。
   - 哪些角色真正运动，哪些角色复用静态帧。
3. 写 `style-summary.md`：
   - 20–30 色预备色板。
   - 3–5 个角色识别元素。
   - 眼睛构造（魔理沙式或桃金娘式）和描边策略。
   - 普通选择的热点器物与人物位置。
   - 可动部件和动作节奏。
   - 画布档先标为「待用户选择」。

### 2. 只确认普通选择静帧

1. GenerateImage 出高清 Q 版指针 concept，保存 `concept/01-normal-select-concept.png`。
2. 用户未确认静帧前，禁止 Seedance，禁止抽帧，禁止制作其余角色。

### 3. 制作 Normal 十六帧

1. 把已确认静帧交给用户用 Seedance 图生视频；提示词用文档第 3 节模板（分层闲置，禁止钟摆）。
2. 从采用的视频均匀抽 16 帧。
3. 边缘洪水抠棋盘；按左上锚点对齐，不要用软塌帽尖。
4. LANCZOS 整只角色装进 128×128；硬 Alpha；热点 16 帧相同。
5. 绿底 GIF 约 100ms/帧展示给用户。确认前禁止打 ANI、禁止替换系统指针。

### 4. 制作其余角色

先做通 Normal。再按文档第 8 节：`Working` / `Busy` 可另出视频；`Help` / `Link` 等能复用就加静帧附件；功能态静帧即可。

### 5. 写热点配置

在工作目录写 `hotspots.json`。下列坐标是 **128×128** 量级示例；必须按实际可见左上尖端修正。

```json
{
  "01-normal-select": [7, 22],
  "02-help-select": [7, 22],
  "03-working-in-background": [7, 22],
  "04-busy": [64, 64],
  "05-precision-select": [64, 64],
  "06-text-select": [64, 64],
  "07-handwriting": [18, 110],
  "08-unavailable": [12, 12],
  "09-vertical-resize": [64, 64],
  "10-horizontal-resize": [64, 64],
  "11-diagonal-resize-nwse": [64, 64],
  "12-diagonal-resize-nesw": [64, 64],
  "13-move": [64, 64],
  "14-alternate-select": [64, 12],
  "15-link-select": [10, 18],
  "16-location-select": [10, 18],
  "17-person-select": [10, 18]
}
```

### 6. 构建 ANI

从项目根目录执行：

```powershell
python .cursor/skills/generate-qmcursor-theme/scripts/build_ani_theme.py `
  --input "<工作目录>/source" `
  --output "<工作目录>/package" `
  --size 128 `
  --jif-rate 6 `
  --hotspots "<工作目录>/hotspots.json"
```

正式帧已是 128 透明 PNG 时不要加 `--indexed-8bit`。

在 `package/theme.inf` 写入：

```ini
[Strings]
SCHEME_NAME="<中文主题名>"
```

### 7. 验证

必须验证：

- 动态角色：每角色 16 张 128×128 PNG，硬 Alpha，棋盘已抠。
- 整只角色在画布内；热点全帧一致，锚在左上尖端。
- 动态 ANI：RIFF `ACON`、32 位、16 帧、`JifRate=6`、128×128。
- `LoadCursorFromFileW` 可加载。
- 试做可只应用普通选择；完整包再补其余角色。
- `python -m pytest`
- `python -m compileall -q src tests`

## 完成报告

报告：

- 主题名、工作目录、128×128 / 16 帧 / 32 位。
- 普通选择 concept 与绿底 GIF。
- ANI 热点、Windows 加载与导入结果。
- 默认不主动替换系统指针；用户明确要求后再应用。
