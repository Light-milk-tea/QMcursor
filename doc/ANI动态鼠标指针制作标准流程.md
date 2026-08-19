# ANI 动态鼠标指针制作标准流程

本文说明如何制作一套类似 Mon3tr、由 Windows 原生播放的动态鼠标指针，并将其导入 QMcursor。目标是让指针在关闭 QMcursor 后仍能继续播放，不依赖托盘、叠加层或后台进程。

适用范围：

- Windows 10 / 11
- Windows 10 / 11 的完整 17 个标准指针角色
- 逐帧 PNG 制作的 RIFF `ACON` 动态指针（`.ani`）
- 像素风、扁平风、手绘风等完整主题

不包含：

- QMcursor 的物理摇摆和挂坠效果
- EXE 安装器制作

> 项目标准：从本规范生效起，后续新制作的指针主题必须完整提供 17 个角色。除传统 15 个角色外，必须包含位置选择 `Pin` 和人员选择 `Person`，不得因为它们触发频率较低而省略。

---

## 1. 最终交付物

一套完整主题至少应包含：

```text
主题工作目录/
  style-summary.md
  source/
    01-normal-select/
      00.png
      01.png
      ...
    02-help-select/
      00.png
      ...
    ...
    15-link-select/
      00.png
      ...
    16-location-select/
      00.png
      ...
    17-person-select/
      00.png
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
```

用于 QMcursor 导入时，可以直接选择 `package` 文件夹，也可以将其中内容压缩为 ZIP。

---

## 2. 推荐工具

### 绘制和动画

- 像素风：Aseprite、LibreSprite
- 矢量或扁平风：Illustrator、Inkscape、Figma
- 手绘：Photoshop、Krita、Clip Studio Paint
- AI 辅助生图：先生成高分辨率母版，再人工统一风格、方向和热点

### 图像处理

- Pillow：裁剪、透明处理、缩放、像素校验
- ImageMagick：批量检查或转换

### ANI 制作

- 专用 ANI 编辑器
- 自定义脚本：透明 PNG → 单帧 CUR → RIFF `ACON` ANI

当前 QMcursor 已支持导入和应用 ANI，但尚未提供内置的“PNG 序列转 ANI”制作界面或正式制作脚本。因此在制作脚本完成前，需要使用外部 ANI 工具或单独的转换脚本。

---

## 3. 第一步：建立视觉规范

准备 4–5 张能代表目标主题的参考图，先整理一份 `style-summary.md`，至少记录：

1. 主色、辅色、强调色和轮廓色
2. 像素、扁平、手绘、复古、科技等整体风格
3. 轮廓粗细、圆角、阴影、材质和光照方向
4. 主体占画布的比例和安全边距
5. 可重复使用的主题元素，例如角色耳朵、武器、植物、纹样或装置
6. 动画语言，例如眨眼、呼吸、摇尾、旋转、闪烁或形变

设计要求：

- 不要只给系统箭头换色或贴装饰。
- 可以用角色、动物、植物或器物直接构成指针主体。
- 必须保留清晰的操作方向和热点。
- 缩小到 24×24 或 32×32 后仍能快速识别。
- 同一套指针必须保持一致的色板、线宽、材质和视觉重量。
- 功能尖端必须锐利、清晰，不能被动画或装饰遮挡。

---

## 4. 第二步：设计完整 17 个标准角色

先完成静态关键帧，再开始动画。推荐先设计并确认 `01-normal-select`，将其作为其余角色的风格基准。

| 序号 | 工作目录 | ANI 文件 | Windows 角色 | 几何与热点要求 |
|---:|---|---|---|---|
| 01 | `01-normal-select` | `Normal.ani` | `Arrow` | 指向左上，左上操作尖端为热点 |
| 02 | `02-help-select` | `Help.ani` | `Help` | 保留普通选择主体，帮助附件不得遮挡左上热点 |
| 03 | `03-working-in-background` | `Working.ani` | `AppStarting` | 保留普通选择主体，附加进行中动效，热点仍在左上 |
| 04 | `04-busy` | `Busy.ani` | `Wait` | 围绕中心组织，不附带箭头，中心为热点 |
| 05 | `05-precision-select` | `Precision.ani` | `Crosshair` | 十字准星严格对称，中心为热点 |
| 06 | `06-text-select` | `Text.ani` | `IBeam` | 清晰垂直 I 形，中心为热点 |
| 07 | `07-handwriting` | `Handwriting.ani` | `NWPen` | 右上指向左下，左下笔尖为热点 |
| 08 | `08-unavailable` | `Unavailable.ani` | `No` | 禁止符号清楚，中心为热点 |
| 09 | `09-vertical-resize` | `Vertical.ani` | `SizeNS` | 上下双向箭头，中心为热点 |
| 10 | `10-horizontal-resize` | `Horizontal.ani` | `SizeWE` | 左右双向箭头，中心为热点 |
| 11 | `11-diagonal-resize-nwse` | `Diagonal1.ani` | `SizeNWSE` | 左上—右下双向箭头，中心为热点 |
| 12 | `12-diagonal-resize-nesw` | `Diagonal2.ani` | `SizeNESW` | 右上—左下双向箭头，中心为热点 |
| 13 | `13-move` | `Move.ani` | `SizeAll` | 上下左右四向对称，中心为热点 |
| 14 | `14-alternate-select` | `Alternate.ani` | `UpArrow` | 垂直向上，顶部尖端为热点 |
| 15 | `15-link-select` | `Link.ani` | `Hand` | 食指向上，指尖为热点 |
| 16 | `16-location-select` | `Pin.ani` | `Pin` | 清晰的位置标记或定位选择造型，定位尖端为热点 |
| 17 | `17-person-select` | `Person.ani` | `Person` | 清晰的人员选择造型，保留明确且稳定的选择热点 |

推荐顺序：

1. 完成并确认普通选择。
2. 基于普通选择制作帮助和后台运行。
3. 完成忙碌、精确选择、文本选择等独立造型。
4. 最后完成四种缩放、移动、链接、位置和人员选择。

---

## 5. 第三步：规划动画

### 5.1 先决定哪些角色真正需要多帧

不必让全部 17 个角色都做复杂动画。推荐优先级：

| 优先级 | 角色 | 推荐动画 |
|---|---|---|
| 高 | `Arrow` | 眨眼、呼吸、耳朵或尾巴轻动 |
| 高 | `AppStarting` | 主体静止，附加元素循环运动 |
| 高 | `Wait` | 环形旋转、脉冲、循环形变 |
| 中 | `Help`、`Hand`、`No`、`SizeAll`、`Pin`、`Person` | 短促反馈或轻微动作 |
| 低 | `IBeam`、`Crosshair`、四种 Resize | 保持功能骨架稳定，仅做轻微明暗或装饰变化 |

静态角色也可以制作成单帧 ANI，或者继续使用 CUR。完整主题不要求每个角色都有明显动作。

### 5.2 帧数和速度

建议默认值：

- 普通循环：6–8 帧
- 忙碌或后台运行：8–12 帧
- 短反馈：4–6 帧
- 默认帧间隔：约 100ms
- ANI `JifRate`：6，即 `6 / 60` 秒
- 常见循环时长：600–1200ms

避免：

- 帧数很多但相邻帧差异极小
- 低于约 40ms 的高频闪烁
- 循环首尾位置、亮度或轮廓突然跳变
- 整个主体大幅移动，导致用户误判点击位置

### 5.3 热点稳定性

热点是实际点击坐标。动画过程中，热点必须保持固定：

- 每一帧使用相同画布尺寸。
- 每一帧 CUR 头写入相同热点坐标。
- 围绕热点设计动画，不要让功能尖端漂移。
- 如果角色有摇摆或形变，操作尖端应保持不动，其他部分围绕它运动。

热点不稳定是动态指针最严重的可用性问题之一。

---

## 6. 第四步：绘制和整理 PNG 帧

### 6.1 母版尺寸

推荐两种路线：

#### 像素风路线

- 直接按 32×32 或 64×64 绘制
- 使用最近邻缩放
- 控制颜色数量和轮廓像素
- 可采用 8 位索引色减小体积

#### 高清路线

- 使用 512×512、1024×1024 或更高分辨率母版
- 最终输出 32、64、128 三个尺寸档
- 缩小时使用高质量 LANCZOS，并人工修正小尺寸轮廓
- ANI 内帧优先使用 32 位 RGBA

### 6.2 透明背景

最终 PNG 必须是真实 RGBA 透明背景：

- 背景区域 Alpha 必须为 0。
- 主体边缘保留正常抗锯齿 Alpha。
- 不得使用白底、灰底或画出来的棋盘格。
- 若生图阶段使用纯色背景，必须通过图像处理真正抠除背景和边缘溢色。

### 6.3 文件命名

每个角色目录中的帧按播放顺序命名：

```text
00.png
01.png
02.png
03.png
...
```

要求：

- 使用固定宽度编号，避免 `1.png`、`10.png`、`2.png` 排序错误。
- 同一角色的所有帧尺寸完全一致。
- 不混用 JPG、WebP 等有损或不同 Alpha 行为的格式。
- 不在正式帧目录中放缩略图、拼图或参考图。

---

## 7. 第五步：生成 ANI

Windows ANI 是 RIFF 容器，标准结构至少包括：

```text
RIFF ... ACON
  anih
  LIST fram
    icon
    icon
    ...
```

每个 `icon` 块中是一帧带热点的 CUR 数据。

推荐技术规范：

| 项目 | 标准 |
|---|---|
| 容器 | RIFF `ACON` |
| 帧数据 | 带热点的 CUR |
| 位深 | 默认 32 位 RGBA；像素风可选 8 位索引色 |
| 帧尺寸 | 单个 ANI 内保持一致 |
| 帧间隔 | 默认 `JifRate = 6`，约 100ms |
| 帧顺序 | 按文件名顺序循环 |
| `rate` 块 | 基础版本不使用 |
| `seq` 块 | 基础版本不使用 |
| 热点 | 每帧相同且位于图像范围内 |

标准转换过程：

1. 读取角色目录中的 PNG 帧。
2. 验证帧数、尺寸、RGBA 和透明背景。
3. 根据角色规则确定热点。
4. 将每帧编码为单尺寸 CUR。
5. 将 CUR 帧写入 ANI 的 `LIST fram/icon`。
6. 写入帧数、步骤数和 `JifRate`。
7. 重新解析 ANI，确认容器、帧数、热点和时序正确。

不要直接把普通 PNG 字节塞进 `icon` 块；ANI 帧应是合法的 CUR/ICO 图像数据。

---

## 8. 第六步：尺寸策略

### 8.1 最小可用方案

制作一套单尺寸 ANI：

- Mon3tr 类像素风：32×32
- 普通高清主题：建议至少 64×64

优点是制作和导入简单；缺点是 Windows 放大时可能模糊。

### 8.2 推荐方案

分别制作 32、64、128 三套 ANI：

```text
theme/
  32/
    arrow.ani
    wait.ani
    ...
  64/
    arrow.ani
    wait.ani
    ...
  128/
    arrow.ani
    wait.ani
    ...
  theme.json
```

不要优先在一个 ANI 的每帧中塞入多层 CUR。Windows 对 ANI 内多分辨率帧的选择不如静态 CUR 稳定，QMcursor 的标准方案是按系统指针大小切换到最接近的一套 ANI。

当前 QMcursor 的“导入 ANI 包”适合扁平的单尺寸包。多尺寸主题需要由后续制作脚本生成规范 `theme.json`，或作为内置主题按目录集成。

不要把现有高清 CUR 主题机械封装为单帧 ANI。Windows 的旧式 ANI 加载链可能
先将单尺寸帧栅格化到较小尺寸，再随系统指针大小放大，导致半透明抗锯齿边缘和
细节发糊。原有静态主题继续使用多分辨率 CUR；只有按 ANI 播放特点专门设计和
验证的动态主题才使用 ANI。

---

## 9. 第七步：打包并导入 QMcursor

### 9.1 单尺寸导入包

将 17 个 ANI 放在同一文件夹，使用 Mon3tr 命名或 Windows 角色命名：

```text
Normal.ani
Help.ani
Working.ani
Busy.ani
...
Link.ani
Pin.ani
Person.ani
```

操作步骤：

1. 启动新版 `QMcursor.exe`。
2. 点击“导入 ANI 包”。
3. 选择 ZIP 压缩包或 ANI 文件夹。
4. 在“自制指针”中选择带“系统动画”标记的主题。
5. 检查 17 个角色的预览和文件名。
6. 点击“应用所选样式”。
7. 关闭 QMcursor，确认动画仍由 Windows 播放。

QMcursor 会将导入内容复制到：

```text
%LOCALAPPDATA%\ArkCursor\imported\<主题名>\
```

导入过程不会执行包内 EXE 或 INF，也不会把文件写入 `C:\Windows\Cursors`。

### 9.2 `theme.json` 示例

多尺寸或内置主题可使用：

```json
{
  "name": "原创动态主题",
  "source": 1,
  "kind": "ani",
  "frame_interval_ms": 100,
  "cursors": {
    "Arrow": "64/arrow.ani",
    "Help": "64/help.ani",
    "AppStarting": "64/app_starting.ani",
    "Wait": "64/wait.ani"
  },
  "sizes": {
    "32": {
      "Arrow": "32/arrow.ani",
      "Wait": "32/wait.ani"
    },
    "64": {
      "Arrow": "64/arrow.ani",
      "Wait": "64/wait.ani"
    },
    "128": {
      "Arrow": "128/arrow.ani",
      "Wait": "128/wait.ani"
    }
  }
}
```

正式完整主题应为全部 17 个角色提供路径；缺失角色会回退到 Windows 默认指针。

当前 QMcursor 代码模型仍只登记传统 15 个角色，导入时会保留主题包的制作要求，但暂时忽略 `Pin.ani` 和 `Person.ani`。这是需要后续补齐的软件兼容缺口，不代表制作时可以省略这两个文件。QMcursor 扩展到 17 角色后，主题资产无需返工即可直接启用。

---

## 10. 第八步：质量验证

### 10.1 每个 PNG 帧

- [ ] 是 PNG，具有真实 Alpha 通道
- [ ] 背景 Alpha 为 0
- [ ] 主体没有被裁切
- [ ] 抗锯齿边缘没有纯色溢边
- [ ] 与同角色其他帧画布尺寸一致
- [ ] 与整套主题色板、线宽和材质一致
- [ ] 在 24×24 和 32×32 下仍能识别

### 10.2 每个 ANI

- [ ] 文件头是 RIFF `ACON`
- [ ] 包含合法 `anih`
- [ ] 包含 `LIST fram` 和至少一个 `icon`
- [ ] 实际帧数与设计帧数一致
- [ ] 每帧热点相同且在范围内
- [ ] 播放顺序正确
- [ ] 循环首尾自然
- [ ] 帧间隔符合设计
- [ ] Windows 能通过 `LoadCursorFromFileW` 加载

### 10.3 整套主题

- [ ] 17 个标准角色映射正确
- [ ] `Pin` 与 `Person` 均有独立 ANI，未错误复用其他角色文件
- [ ] 两种对角线调整方向没有互换
- [ ] `Arrow`、`NWPen`、`Hand` 的操作尖端准确
- [ ] `Wait`、准星和调整类的中心热点准确
- [ ] 文件名能被 QMcursor 识别
- [ ] QMcursor 中预览正常
- [ ] 应用后 Windows 各种指针状态切换正常
- [ ] 关闭 QMcursor 后动画继续
- [ ] 物理摇摆在 ANI 主题下被禁用
- [ ] 125%、150%、200% 显示缩放下进行过检查
- [ ] 文本编辑、浏览器链接、窗口缩放和忙碌状态均实测

---

## 11. 常见问题

### 指针动画正常，但点击位置不准

热点设置错误或不同帧热点不一致。重新检查每帧 CUR 头中的热点坐标。

### 指针播放时上下抖动

各帧主体没有对齐到同一热点，或裁剪时每帧使用了不同边界。应先统一画布，再围绕固定热点放置主体。

### 放大后很模糊

使用了单一 32px ANI。应增加 64px、128px 档位，而不是只依赖系统硬缩放。

### 动画边缘出现绿色、白色或黑色轮廓

抠图后存在背景溢色，或 Alpha 与 RGB 边缘处理不正确。需要清除透明区域颜色污染并重新输出 RGBA。

### QMcursor 导入后没有出现主题

检查：

- ANI 是否为有效 RIFF `ACON`
- 文件名是否符合标准映射
- ZIP 是否包含不安全路径或重复角色
- 包中是否至少有一个可识别 ANI

### 关闭 QMcursor 后动画停止

确认使用的是“系统动画”ANI 主题，而不是“物理摇摆”。ANI 应直接写入 Windows 指针方案；物理摇摆必须托盘常驻。

### 全屏游戏中恢复成默认指针

部分游戏会自行绘制光标或忽略 Windows 自定义指针。这不是 ANI 文件本身能够完全解决的问题。

---

## 12. 推荐的实际制作节奏

为了降低返工，建议按以下里程碑推进：

### 里程碑 1：验证造型

只制作 `Arrow` 的一张静态母版，验证风格、方向、热点和小尺寸识别度。

### 里程碑 2：验证动画

将 `Arrow` 做成 6–8 帧 ANI，在 Windows 中确认循环、热点和关闭 QMcursor 后继续播放。

### 里程碑 3：验证状态切换

制作 `AppStarting` 和 `Wait`，确认 Windows 能在普通、后台运行和忙碌状态之间正确切换。

### 里程碑 4：完成 17 个角色

先完成静态结构，再为必要角色增加动画，不要一开始就同时制作全部复杂动画。即使 `Pin` 和 `Person` 只做单帧 ANI，也必须作为独立角色交付。

### 里程碑 5：补多尺寸

单尺寸主题稳定后，再制作 32、64、128 三档，避免在造型尚未确认时重复三倍工作。

### 里程碑 6：最终打包

完成文件名、主题清单、导入、应用、退出播放和高分屏测试，再发布 ZIP。未经授权的参考素材不得随 QMcursor 内置或再次分发。

