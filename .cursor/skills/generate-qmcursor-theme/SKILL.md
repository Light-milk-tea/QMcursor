---
name: generate-qmcursor-theme
description: 根据参考图片提炼视觉风格，生成 15 张 Windows 标准鼠标指针 PNG，转换为多分辨率 CUR 并作为完整主题集成到 QMcursor/ArkCursor。用户提到生成指针、参考图制作光标、创建鼠标主题或融入 QMcursor 时使用。
---

# 生成 QMcursor 指针主题

完成从参考图到可用主题的全流程。不得只生成图片或只写 `theme.json`。

## 输入约定

- 项目根目录是包含 `pyproject.toml` 和 `src/arkcursor/` 的目录。
- 生图规范默认读取项目根目录的 `doc/通用鼠标指针生图提示词.md`。
- 转换规范默认读取项目根目录的 `doc/生成指针prompt.txt`。
- 用户提供的工作文件夹应包含 4–5 张参考图片；15 张生成图和 `style-summary.md` 也必须保存到该文件夹。
- 若用户未给工作文件夹，搜索项目中除 `.venv`、`.git`、`src/arkcursor/themes` 外含 4–5 张图片的文件夹。只有不存在或候选多于一个时才询问。
- 从参考图主题或文件夹名推断中文主题名和安全的英文小写目录名；无法可靠推断时一次询问两者。

## 工作流

### 1. 读取并分析

1. 完整读取两份规范文件，不要用本 Skill 的摘要替代原文。
2. 读取工作文件夹内全部参考图片。生成图若已存在，不得误当成原始参考图。
3. 用 3–6 条总结共同视觉规范：主/辅/强调/轮廓色、轮廓与圆角、明暗和材质、核心造型语言。
4. 将总结写入工作文件夹的 `style-summary.md`。
5. 选择参考图色板中没有的高饱和纯色作为临时背景，记录精确十六进制色值。不得要求生图模型直接生成透明背景、棋盘格或透明预览。
6. 造型不得拘泥于系统指针常见的三角形箭头，也不得只给默认箭头换色或添加装饰。优先用参考图中的动物、植物、器物、纹样或抽象元素直接重构指针主体；允许完全脱离传统箭头轮廓，但必须保留清晰的功能方向、操作含义、准确热点及 24/32 px 识别度。

### 2. 逐张生成 15 个 PNG

必须调用图像生成工具生成独立的 1:1 图片，推荐 1024×1024。把全部原始参考图放入每次调用的 `reference_image_paths`。

先只生成 `01-normal-select.png`，读取成图并检查指向左上的方向感、左上热点、安全边距和 24/32 px 识别度。不要求主体呈系统三角箭头形；若成图只是默认箭头加装饰，应重生为由主题元素直接构成的创意造型。确认后，后续每次调用同时引用全部原始参考图和已确认的 `01-normal-select.png`。

后续必须按顺序逐张生成，前一张检查通过后再生成下一张，禁止并行生成或生成 5×3 拼图：

1. `01-normal-select.png`
2. `02-help-select.png`
3. `03-working-in-background.png`
4. `04-busy.png`
5. `05-precision-select.png`
6. `06-text-select.png`
7. `07-handwriting.png`
8. `08-unavailable.png`
9. `09-vertical-resize.png`
10. `10-horizontal-resize.png`
11. `11-diagonal-resize-nwse.png`
12. `12-diagonal-resize-nesw.png`
13. `13-move.png`
14. `14-alternate-select.png`
15. `15-link-select.png`

每次图像描述都要包含：

- 规范文件中该角色的完整功能、方向、几何和热点要求。
- 本次提炼出的视觉规范。
- “不要拘泥于系统三角形箭头，不要只装饰默认箭头；优先让主题元素直接构成具有明确功能方向和热点的创意指针主体。”
- 规范文件“四、每张图片都必须附加的强制要求”。
- “背景为纯色 `<色值>`，完全平坦、单色、无渐变、无纹理、无阴影、无光晕；主体不得使用该颜色。”
- “只生成这一枚指针，不要拼图、文字、编号或标签。”

工具若先把图片写到默认目录，立即移动到工作文件夹并使用严格文件名。不要覆盖用户原有同名文件；存在时先确认它是否是本次可复用成图，否则询问是否重生。

### 3. 视觉校验

每张生成后读取图片并与 `01-normal-select.png` 比较：

- 角色、方向和对称性正确，热点尖端或中心明确且无遮挡。
- 色板、线宽、圆角、光照、材质、主体占比和边距一致。
- 无文字、水印、场景、额外物体、裁切或临时背景上的阴影。

任何一项明显失败都重生该张，不要把偏差带到后续图片。

### 4. 转换并集成

转换脚本依赖 Pillow。优先使用项目虚拟环境；缺少依赖时执行：

```powershell
python -m pip install Pillow
```

从项目根目录执行：

```powershell
python .cursor/skills/generate-qmcursor-theme/scripts/build_cursor_theme.py `
  --input "<工作文件夹>" `
  --theme-name "<中文主题名>" `
  --theme-dir "<英文目录名>" `
  --background "<临时背景色值>"
```

脚本会：

- 严格读取上述 15 个 PNG，也兼容用户明确提供的单张 5×3 合集。
- 从画布边缘连通区域抠除临时纯色，清理边缘溢色并保留 RGBA。
- 保留裁剪后的透明 PNG。
- 生成 32、48、64、96、128、192、256 px 的 32 位未压缩 RGBA CUR。
- 按角色设置热点，并写入 `src/arkcursor/themes/<英文目录名>/theme.json`。
- 重新解析全部输出，校验数量、尺寸层、热点、Alpha 和清单引用。

目标主题目录已存在时脚本会拒绝覆盖。只有用户明确要求覆盖时才加 `--force`；这只覆盖同一目标主题，不得删除其他主题。

### 5. 最终验证

1. 读取输出的 15 张 PNG，确认透明背景和小尺寸可识别性；像素校验不能只靠查看器。
2. 运行脚本的独立校验：

```powershell
python .cursor/skills/generate-qmcursor-theme/scripts/build_cursor_theme.py `
  --validate-only "src/arkcursor/themes/<英文目录名>"
```

3. 运行：

```powershell
python -m pytest
python -m compileall -q src tests
```

4. 检查新文件的 IDE Lint。项目没有配置独立 Lint 命令时，不要虚构命令。
5. 确认 `CursorService.list_bundled_themes()` 能加载新主题。无需改主题列表代码：应用会自动扫描 `src/arkcursor/themes/*/theme.json`。

## 完成报告

简要报告：主题名、参考图/生成 PNG 所在文件夹、主题输出路径、15 个 CUR 是否均含 7 层、Alpha/热点/清单校验结果、测试结果。开发模式下通常重启 QMcursor 后可看到新主题；若程序正在运行，说明需要重启。
