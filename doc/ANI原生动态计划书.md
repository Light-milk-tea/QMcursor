# QMcursor 改为 Mon3tr 形态：实现计划书

> 目标：让用户换上带逐帧动画的指针后，**关掉 QMcursor 仍然在动**，不依赖托盘、叠加层或钩子。
> 手段：把「动态」从程序绘制，改成 Windows 原生播放 `.ani`。
> 日期：2026-08-19
>
> **制作法已更新（2026-08-26）**：新主题动画按 [`Seedance动画指针制作流程.md`](Seedance动画指针制作流程.md) 执行。本文是产品形态计划，不是现行制帧手册。

---

## 1. 要做成什么样

Mon3tr 并不是一款常驻软件，而是：

1. 作者画好多帧图
2. 封装成 `.ani`
3. 用 INF / EXE 写进系统指针方案
4. 之后由 Windows 自己播动画

QMcursor 现在是另一条路：内置多层静态 `.cur`，应用后即可退出；**只有物理摇摆才会常驻**。预览已经能读 ANI，应用主题时也不拒绝 `.ani` 路径，但制作链、内置主题、校验脚本全部按静态 CUR 写死。

「搞成 Mon3tr 这种形式」建议定义成下面这句，而不是整套克隆简易指针制作器：

> QMcursor 仍然是选主题、点应用、关掉的管理器；主题的动态部分改成系统播 ANI。软件用完可以退出。可选再提供「导入别人的 ANI 包 / 导出 INF」方便分发。

不建议第一期做成「导入 GIF、裁图、导出 EXE」的第二个 Simple Cursor Maker。那是作者工具，和现在的用户工具重叠少、工作量大。

### 1.1 明确不做（第一期）

| 不做 | 原因 |
|---|---|
| 用 overlay 模拟 ANI 逐帧 | 必须占后台，和目标相反 |
| 一边播 ANI 一边物理摇摆 | 物理层会藏系统指针，两套动态互斥 |
| 先做 EXE 安装器 | 杀软误报高，INF/ZIP 更干净 |
| 丢掉现有静态多层 CUR | 高分屏清晰度仍是 CUR 的优势，应并存 |

### 1.2 和现有能力的关系

| 能力 | 处理后 |
|---|---|
| 选方案并应用 | 保留，路径可以是 `.ani` 或 `.cur` |
| 关窗口即退出 | 默认如此（与现在「未开物理」一致） |
| 开机再应用 | 保留；仍是短进程写注册表后退出 |
| 指针大小滑条 | ANI 主题改为「换对应尺寸的 ANI 文件」或提示将硬缩放 |
| 物理摇摆 / 挂坠 | 降为高级选项；ANI 主题上禁用或只对静态 CUR/PNG 主题开放 |
| 内置主题全是 `.cur` | 逐步增加 ANI 主题，旧主题继续可用 |

---

## 2. 推荐产品形态

```
画帧（Aseprite / 生图）
    → QMcursor 制作脚本：透明 PNG 序列 → 32 位 ANI（可多尺寸各一份）
    → 主题目录：theme.json + *.ani [+ 预览 PNG]
    → 用户在 QMcursor 里点「应用」
    → 写 HKCU\Control Panel\Cursors（及 Schemes）
    → SPI_SETCURSORS
    → 退出进程
    → Windows 播 ANI
```

用户侧三种用法：

1. **用内置 ANI 主题**：和现在点应用一样，关软件后角色仍会眨眼、忙碌仍会转。
2. **导入现成包**：选择 Mon3tr 那种 zip（ANI + INF，或纯 ANI 目录），登记成自定义主题。
3. **（二期）导出分发包**：生成 `install.inf` + zip，别人不装 QMcursor 也能右键安装。

---

## 3. 技术关键：动态必须交给系统

Windows 指针注册表里的路径可以是 `.cur` 或 `.ani`。`CursorService.apply_theme()` 已经只写路径、再 `SPI_SETCURSORS`，**不区分后缀**。

因此「不占后台的动态」不需要新常驻模块，只需要：

1. 主题清单允许并展示 `.ani`
2. 有合格的 ANI 文件（热点、帧间隔、透明）
3. 应用后按现有逻辑退出
4. 不要为动画去启动 `PhysicsCursorService`

物理摇摆继续走 overlay，和本目标分开。UI 上应写清楚：ANI 主题 = 系统动画，关软件也在；物理摇摆 = 实验功能，必须托盘常驻。

---

## 4. 数据与主题格式

### 4.1 `theme.json` 扩展（向后兼容）

现有字段保留。建议增加：

```json
{
  "name": "Mon3tr",
  "source": 1,
  "kind": "ani",
  "frame_interval_ms": 100,
  "cursors": {
    "Arrow": "arrow.ani",
    "Wait": "wait.ani"
  },
  "sizes": {
    "32": { "Arrow": "32/arrow.ani" },
    "64": { "Arrow": "64/arrow.ani" }
  }
}
```

规则：

- 无 `kind` 时视为现在的静态 CUR（默认）。
- `cursors` 仍是 15 个标准角色；缺文件则该角色回退系统默认。
- `sizes` 可选。用户点「应用大小」时，把对应尺寸的 ANI 路径写进注册表。这样 **调大小也不需要常驻**，只是再应用一次。
- 若只有一份 ANI：大小滑条改为系统 `CursorBaseSize` 硬缩放，并提示画质会下降。
- Win10 的 `Person` / `Pin` 第一期不做；模型仍保持 15 角色。若导入的 INF 带这两项，可忽略或二期再补。

### 4.2 ANI 文件规范（自制主题）

不要照搬 Mon3tr 的 8 位 256 色，除非刻意做像素风。

| 项 | 建议 |
|---|---|
| 容器 | RIFF `ACON`，`anih` + `LIST fram`/`icon` |
| 每帧 | 32 位未压缩 RGBA CUR（与现有 `write_cur` 同种 DIB） |
| 默认画布 | 至少 64×64；像素风可 32×32 |
| 帧间隔 | `JifRate`，默认 6（约 100ms），可按角色覆盖 |
| 热点 | 写入每帧 CUR 头，与现有 `hotspot_for` 规则一致 |
| 透明 | Alpha 通道，不要靠调色板 index 0 |
| 调色 | 真彩色；像素主题可另选 8 位以缩小体积 |
| `rate` / `seq` | 第一期不做变时长/乱序，各帧等间隔 |

单尺寸 ANI 即可工作。若要兼顾清晰和体积：优先做 **32 / 64 / 128** 三档各一套 ANI，而不是在一个 ANI 里塞 7 层（系统播 ANI 时对多层 CUR 的选择不如静态 CUR 稳）。

### 4.3 目录布局示例

```
src/qmcursor/themes/mon3tr_ani/
  theme.json
  arrow.ani
  help.ani
  ...
  preview/arrow_00.png
```

导入外部包时，复制到 `%LOCALAPPDATA%\QMcursor\imported\<name>\`，不写进安装目录，避免升级覆盖。

---

## 5. 代码怎么改

按模块拆，避免一次重写 UI。

### 5.1 主题模型 `models/theme.py`

- `CursorTheme` 增加 `kind: str = "cur"`、`sizes: dict | None`、`frame_interval_ms`。
- `from_dict` / `to_dict` 读写新字段，旧 `theme.json` 原样能加载。
- `missing_files()` 按当前选中尺寸解析路径。
- 仍禁止未知角色名，15 角色集合不变。

### 5.2 应用服务 `services/cursor_service.py`

- `apply_theme` 保持「写注册表 + 刷新」，增加：
  - 按 `current_cursor_size()` 从 `sizes` 里选最接近的一档 ANI
  - 应用成功后 **写入用户 Schemes**（现在只写当前指针，不登记方案名）。这样「鼠标属性」里也能看到 QMcursor 方案，和 Mon3tr INF 一致，卸了软件主题还在。
- `list_bundled_themes` 继续扫 `themes/*/theme.json`，ANI 主题自然出现。
- 新增 `import_ani_pack(zip_or_dir)`：识别 INF + ANI，或扁平 15/17 个 ani 文件名（Normal/Help/Busy… 与 Arrow/Wait… 两套命名都认）。
- 开机 `--startup`：逻辑不变，只是路径可能是 ANI；物理未开则应用完退出。

### 5.3 预览 `ui/cursor_preview.py`

已有 `read_ani_timing` + `LoadCursorFromFileW`。补充：

- 列表里给 ANI 主题一个「动画」标记
- 详情表继续播预览（窗口开着时预览可以动，不代表进程要常驻）

### 5.4 主窗口 `ui/main_window.py`

- 选中 ANI 主题时：禁用物理摇摆，或勾选时提示「将改为静态第一帧且需常驻，不推荐」
- 状态栏区分：「已应用（系统动画，可退出）」/「物理摇摆运行中（托盘常驻）」
- 增加「导入 ANI 包…」
- 大小滑条：有 `sizes` 时显示实际将应用的档位（32/64/128）

### 5.5 物理模块

- `PhysicsCursorService.start`：若主题 `kind == "ani"` 且没有配套 PNG，直接拒绝。
- 不删除物理代码。它和 ANI 是两条产品线，用开关隔离即可。

### 5.6 开机与托盘 `main.py`

- 默认启动仍开设置窗口。
- `--startup`：未开物理则 `apply_at_startup()` 后 `return 0`（已是如此），ANI 无需改启动模型。

---

## 6. 制作链（开发侧）

新建脚本，复用现有抠图、热点、DIB 逻辑：

` .cursor/skills/generate-qmcursor-theme/scripts/build_ani_theme.py`

输入：

- 每角色一个目录：`01-normal-select/00.png, 01.png, …` 或一份 GIF
- 或单帧 PNG（写成 1 帧 ANI，行为等于静态，但格式统一）

处理：

1. 沿用现有纯色抠背景 / 已是透明则跳过
2. 按热点类型算坐标
3. 缩到目标尺寸（LANCZOS）
4. `write_cur` 单帧 → 包进 RIFF ANI
5. 写 `theme.json`
6. `--validate-only`：帧数、尺寸、热点范围、Alpha、清单路径

现有 `build_cursor_theme.py` 继续生成静态 7 层 CUR，两套脚本并存。Skill 文档加一节：用户说「做成 Mon3tr 那种会动、不占后台」时走 ANI 脚本。

像素风可加 `--indexed` 量化到 256 色（复刻 Mon3tr 体积）；默认真彩色。

---

## 7. 导入与导出（用户侧分发）

### 7.1 第一期：导入

能吃下：

- Mon3tr zip：`*.ani` + `install.inf`
- 仅 ANI 的文件夹，文件名可映射到角色

导入后进 `%LOCALAPPDATA%\QMcursor\imported\`，出现在主题列表「已导入」。

### 7.2 第二期：导出 INF + ZIP

生成与 Simple Cursor Maker 同结构的 `install.inf`：

- `CopyFiles` 到 `%WINDIR%\Cursors\<主题名>\`
- `HKCU\...\Schemes` 逗号分隔 15 路径
- 各角色独立键
- 编码用 UTF-16 LE 或明确 GBK，避免 `鼠标` 乱码
- **不生成 EXE 安装器**，除非以后单独评估杀软误报

导出给「没有 QMcursor 的人」用；有 QMcursor 的人只需应用内置/导入主题。

---

## 8. 分阶段

### 第 0 期：验证（约 1 天，不改产品方向）

1. 手写或用脚本把现有某一主题的 `Wait`/`AppStarting` 做成 8 帧 64px ANI
2. 临时改对应 `theme.json` 指向该 ANI
3. 应用 → 退出 QMcursor → 确认忙碌动画仍在
4. 再开物理摇摆，确认应禁用或互斥

通过后再铺正式开发。

### 第 1 期：一等公民 ANI（核心）

- 扩展 `theme.json` 与 `CursorTheme`
- 应用时按尺寸选 ANI，并写入用户 Schemes
- UI：动画标记、导入 zip、ANI 主题禁用物理
- 测试：`apply_theme` 路径为 `.ani`、导入 Mon3tr zip、旧 CUR 主题回归

验收：导入舟-Mon3tr 的 zip，在软件里应用，退出后动画仍在；伊雷娜等旧主题行为不变。

### 第 2 期：制作脚本

- `build_ani_theme.py` + 校验
- Skill 补充
- 用一套试验主题（可先把 Busy/Working 做成循环）证明管线

### 第 3 期：导出 INF/ZIP

- 给已应用或已导入的主题打包
- 文档说明「别人只需右键 INF」

### 第 4 期（可选）

- Person / Pin
- `rate` 变间隔
- 真彩色 / 256 色导出开关
- 若仍要 EXE，用独立、可签名的安装器，不塞进主程序

---

## 9. 风险与取舍

| 风险 | 应对 |
|---|---|
| 高分屏下单尺寸 ANI 发糊 | 做 32/64/128 三档；滑条只切换档，不指望 7 档都清晰 |
| 部分全屏游戏忽略自定义 ANI | 与现在自定义 CUR 相同，文档说明 |
| 写入 `Windows\Cursors` 可能要管理员 | 应用时优先用主题目录绝对路径（QMcursor 现在就是这样），不必拷到系统目录；INF 导出才拷系统目录 |
| 旧主题 + 新字段 | 缺省 `kind=cur`，测试覆盖全部内置 `theme.json` |
| 用户以为物理也会「关了还在」 | UI 文案拆开，ANI 与物理不要合成一个「动态」开关 |
| 体积 | 15 角色 × 12 帧 × 128px 真彩色会明显大于现在的 CUR；Busy 等才多帧，静态角色 1 帧 ANI 或继续用 CUR |

---

## 10. 建议的第一刀代码（第 1 期最小集）

1. `CursorTheme` 增加 `kind` / `sizes`
2. `apply_theme` 解析 ANI 路径 + 写入 `Schemes`
3. 主窗口：导入 Mon3tr zip；ANI 主题禁用物理
4. 测试：`tests/test_ani_theme.py`（清单、导入映射、应用时选尺寸）
5. 用现成 `舟-Mon3tr/_extracted` 做一次手工验收

第 1 期结束后，产品已经是「Mon3tr 那种形式」：**动画在系统里播，QMcursor 可以关掉。** 制作脚本和 INF 导出是增量，不挡这个体验。
