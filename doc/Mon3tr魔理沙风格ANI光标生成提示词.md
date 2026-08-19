# Mon3tr / 魔理沙式 ANI 动态光标生成提示词

本文件是 QMcursor 新建角色动态光标时的唯一生图与制作要求。

目标不是制作 15 张高分辨率静态图，也不是给系统箭头换色。目标是学习 Mon3tr 与魔理沙光标的形态分布、像素语言和动画节奏，制作可由 Windows 原生播放的完整 17 角色 ANI 光标包。

## 一、固定交付规格

- 角色数：17
- 正式帧：48×48 RGBA 像素图
- 每角色：8 帧
- ANI 位深：8 位索引色 + 1 位透明掩码
- 透明度：Alpha 只能为 0 或 255
- 帧间隔：`JifRate=6`，约 100ms/帧，循环约 800ms
- 轮廓：1px 硬描边
- 缩放：只允许最近邻；禁止 LANCZOS、抗锯齿和半透明毛边
- 最终文件：`Normal.ani` 至 `Pin.ani` / `Person.ani` 共 17 个

图像生成工具通常输出 1024×1024。此时必须明确要求“按逻辑 48×48 像素格设计，再以最近邻放大展示”。生成图只能作为关键帧草图；正式帧必须回到 48×48 像素格清理、减色并固定热点。

## 二、输入

制作前读取：

1. 目标角色或主题的 4–6 张参考图。
2. Mon3tr 与魔理沙 ANI 的抽帧或帧表，用于学习构图、功能分布、像素密度和动作幅度。
3. 当前工作目录中的已有 `style-summary.md`、源帧或旧主题；旧图只能作为反例或角色资料，不能继续旧构图。

先输出并写入 `style-summary.md`：

- 角色识别元素：发型、耳朵、帽子、服装、武器、装置或代表性能力。
- 固定色板：轮廓、肤色、主色、辅色、强调色；角色态建议 20–30 色。
- 角色态与功能态分别采用哪些元素。
- 普通选择的热点器物、人物位置和可动部件。
- 各角色的动画语言。

## 三、必须学习的形态分布

### 1. 角色态

`Normal`、`Help`、`Working`、`Unavailable`、`Link`、`Pin`、`Person` 应优先使用完整、可辨识的 Q 版角色。

- 角色头大身小，脸部完整，双眼对称。
- 标志性道具、武器、手势或能量尖端承担功能指向。
- 角色紧邻功能尖端的右下方或下方，二者形成一个整体轮廓。
- 禁止“左上独立系统三角箭头 + 右下缩小立绘”。
- 禁止把角色立绘直接缩小粘贴。
- 不使用孤立头发、无脸头像或无法识别的人体碎片。

普通选择应学习魔理沙“扫帚尖 + 角色”和 Mon3tr“主题生物/装置直接构成指针”的思路：热点是角色动作或器物的一部分，不是额外贴上去的默认箭头。

### 2. 功能态

`Busy`、`Precision`、`Text`、`Handwriting`、四种 `Resize`、`Move`、`Alternate` 以功能骨架优先。

- 可使用帽子、耳朵、核心装置、武器切面或能力纹样做主题化。
- 不强行把完整角色塞进每一种功能指针。
- 准星、I 梁、双向箭头和四向箭头必须一眼可读。
- 功能骨架保持静止时，可以将同一帧复用 8 次；不要为了“动态”而闪烁换色。

## 四、17 个角色设计要求

1. `01-normal-select` / `Normal.ani`
   - 左上功能尖端为热点。
   - 角色与器物一体化，画面占比接近 Mon3tr / 魔理沙。
   - 8 帧有效动画：呼吸、眨眼、嘴型、耳朵/头发/衣摆/道具轻动。
   - 热点尖端全程不动。

2. `02-help-select` / `Help.ani`
   - 保留普通选择的指向结构。
   - 用角色动作、提示气泡、能力符号或道具反馈表达“帮助”。
   - 不得只贴一个孤立大问号。

3. `03-working-in-background` / `Working.ani`
   - 保留普通选择主体和热点。
   - 用环绕粒子、旋转附件、尾巴、能量环或道具节奏表达后台运行。

4. `04-busy` / `Busy.ani`
   - 中心热点，无普通箭头。
   - 学习魔理沙“帽子”与 Mon3tr“主题核心”的思路，用标志性器物或生物局部做中心循环。
   - 8 帧挤压、旋转、脉冲或形变，首尾自然。

5. `05-precision-select` / `Precision.ani`
   - 对称十字准星，中心热点。
   - 只做轻微中心脉冲；不得让准星骨架位移。

6. `06-text-select` / `Text.ani`
   - 清晰 I 梁，中心热点。
   - 可用主题色高光，通常保持静态。

7. `07-handwriting` / `Handwriting.ani`
   - 右上到左下的笔、杖、剑、羽毛或主题器物。
   - 左下尖端为热点，通常保持静态。

8. `08-unavailable` / `Unavailable.ani`
   - 可学习魔理沙 Master Spark：角色施放光束、封锁或拒绝动作。
   - 必须一眼表达“不可用”，不能只是普通选择换色。
   - 热点可位于左上功能尖端；8 帧做能量或动作循环。

9. `09-vertical-resize` / `Vertical.ani`
   - 垂直上下双向箭头，中心热点，静态。

10. `10-horizontal-resize` / `Horizontal.ani`
    - 水平左右双向箭头，中心热点，静态。

11. `11-diagonal-resize-nwse` / `Diagonal1.ani`
    - 左上—右下双向箭头，中心热点，静态。

12. `12-diagonal-resize-nesw` / `Diagonal2.ani`
    - 右上—左下双向箭头，中心热点，静态。

13. `13-move` / `Move.ani`
    - 上下左右四向箭头，中心热点，静态。

14. `14-alternate-select` / `Alternate.ani`
    - 向上指向，顶部尖端为热点，静态。

15. `15-link-select` / `Link.ani`
    - 角色使用手指、道具或能力指向热点。
    - 8 帧呼吸、眨眼和轻微动作。

16. `16-location-select` / `Pin.ani`
    - 复用 Link 的角色姿态，加入明确位置标记或定位能力附件。
    - 热点继续位于指向尖端，附件不得抢占热点。

17. `17-person-select` / `Person.ani`
    - 复用 Link 的角色姿态，加入明确人员标记或角色互动附件。
    - 热点继续位于指向尖端。

## 五、普通选择关键帧生图 Prompt

将以下模板中的方括号替换为本主题内容，并把全部角色参考图、Mon3tr / 魔理沙抽帧放入 `reference_image_paths`。

```text
设计一枚 [主题名/角色名] 的 Windows 普通选择动态光标关键帧。

严格按逻辑 48×48 像素网格设计，再以最近邻放大到 1:1 方形大图。
复古硬边像素画，1px 深色轮廓，20–30 色，平涂，无抗锯齿，
无半透明、无渐变、无柔光、无阴影、无高分辨率插画细节。

构图学习 Mon3tr 与魔理沙光标：
- 左上是清晰锐利的功能尖端和点击热点；
- 热点由 [标志性武器/器物/能力/生物部位] 直接构成；
- 超 Q 版完整角色紧邻热点右下方，头大身小，脸和双眼完整对称；
- 角色与热点器物形成一个连续整体，不是独立系统箭头加缩小立绘；
- 主体接近填满 48×48，但四周保留 1–2 像素安全边距；
- 缩到原生 48px 时仍能识别 [列出 3–5 个角色特征]。

固定色板：[主色、辅色、强调色、轮廓色]。
背景为纯色 [BG_HEX]，完全平坦、单色、无纹理、无光晕；
主体禁止使用该背景色。

只生成这一枚普通选择关键帧。
不要拼图、帧表、文字、编号、标签、水印、场景或 UI 边框。
不要默认白色/黑色系统三角箭头。
不要把角色立绘直接缩小粘贴到箭头旁。
```

生成后必须先压到 48×48 检查。大图好看但 48px 糊成一团，视为失败并重新生成。

## 六、关键帧确认与逐帧制作

1. 只先完成 `Normal` 静态关键帧。
2. 抠除纯色背景，量化到固定色板，Alpha 二值化。
3. 生成 48px 原图和最近邻放大的预览图。
4. 向用户展示并确认；未确认不得继续全套。
5. 确认后再制作 Normal 的 8 帧。
6. 动画使用像素部件分层或逐像素编辑；不要对 8 帧分别调用生图模型，避免角色漂移。
7. 每帧使用相同画布和热点。功能尖端不动，其他部件围绕它运动。
8. 再按顺序完成其余 16 个角色。

## 七、工作目录与文件结构

```text
主题工作目录/
  style-summary.md
  build_assets.py
  hotspots.json
  source/
    01-normal-select/00.png ... 07.png
    02-help-select/00.png ... 07.png
    ...
    17-person-select/00.png ... 07.png
  preview/
    01-normal-select.gif
    01-normal-select-sheet.png
    ...
  package/
    Normal.ani
    Help.ani
    Working.ani
    Busy.ani
    Precision.ani
    Text.ani
    Handwriting.ani
    Unavailable.ani
    Vertical.ani
    Horizontal.ani
    Diagonal1.ani
    Diagonal2.ani
    Move.ani
    Alternate.ani
    Link.ani
    Pin.ani
    Person.ani
    theme.inf
```

`hotspots.json` 记录每个角色的固定像素坐标。坐标由实际可见尖端决定，不得机械套用中心或旧静态 CUR 规则。

示例：

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

## 八、ANI 构建

使用：

```powershell
python .cursor/skills/generate-qmcursor-theme/scripts/build_ani_theme.py `
  --input "<主题工作目录>/source" `
  --output "<主题工作目录>/package" `
  --size 48 `
  --jif-rate 6 `
  --indexed-8bit `
  --hotspots "<主题工作目录>/hotspots.json"
```

不得回退到旧的 15 PNG、多分辨率 CUR、32 位软边或 LANCZOS 工作流。

## 九、强制验证

- 正好 17 个角色目录、每目录正好 8 张 PNG。
- 所有帧均为 48×48 RGBA。
- Alpha 只含 0/255；透明区域无品红、白边、黑边污染。
- 角色态色数不超过 255，推荐 20–30 色。
- 同一角色全部帧热点相同且位于可见功能尖端。
- Normal、Help、Working、Busy、Unavailable、Link、Pin、Person 至少有 4 个不同有效帧。
- Text、Handwriting、Resize、Move、Alternate 允许 8 帧相同。
- ANI 是合法 RIFF `ACON`，包含 8 个 CUR 帧，8 位，`JifRate=6`。
- `LoadCursorFromFileW` 能加载全部 17 个 ANI。
- QMcursor 能导入并应用传统 15 角色；Pin / Person 仍随包保留。
- 应用后关闭 QMcursor，动画仍由 Windows 播放。

## 十、禁止事项

- 禁止使用已删除的旧静态指针 Prompt 或旧 Skill。
- 禁止生成 15 张高分辨率静态 PNG 后直接转 CUR。
- 禁止多分辨率 CUR、32 位软边 ANI、LANCZOS 缩放。
- 禁止默认系统箭头加角色贴纸。
- 禁止所有角色都采用同一个箭头再叠问号/转圈。
- 禁止每帧重新生图造成脸、衣服、比例和热点漂移。
- 禁止半透明像素、抗锯齿、色键溢色和无意义闪烁。
