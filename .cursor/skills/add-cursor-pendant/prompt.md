# 挂坠（Charm）生图 Prompt

本文件是挂坠生图的独立规范，不再引用项目 `doc/` 下的旧提示词。

将模板填空后作为图像生成描述；每次调用须把目标主题的参考图与 `arrow.png`（或主指针 PNG）放入 `reference_image_paths`。

---

## 英文主 Prompt（推荐）

```text
A single hanging charm / medallion for a mouse-cursor pendant decoration,
matching the visual style of the provided cursor theme references.

Vertical composition, square 1:1 image, subject centered with safe margin.

Design (charm body ONLY):
- Top: a clear attach point on the top edge of the medallion
  (small gold bail, loop stub, or clean top of the frame — NOT a long chain).
- Main body: a compact ornament that reads the theme
  (emblem, gem, badge, flower, animal mark, artifact fragment, etc.).
- Optional: 1–2 tiny dangling gems/beads under the medallion only
  (short, decorative; do not make a long rigid chain).
- Style: clean anime / game-asset cel shading, crisp outlines, glossy gems,
  consistent with the reference cursor palette and line weight.

CRITICAL — do NOT include:
- A long vertical chain, rope, stick, or multi-link cord above the medallion
  (the app draws a flexible cord in code; a baked chain looks like a stiff pendulum).
- Cursor arrow / hat / full character / scene / text / watermark / labels.
- Transparent background, checkerboard, or transparency preview.

Background: flat solid color <BG_HEX>, completely flat, no gradient, no texture,
no shadow cast on the background. Subject must not use this color.

Only generate this one charm. No collage, no numbers, no UI chrome.
```

将 `<BG_HEX>` 替换为参考图色板中未使用的高饱和纯色（例如 `#FF00FF`、`#00FF00`）。

---

## 中文要点（辅助约束）

- 只要**末端饰物**，不要画上方长链条/棍状连接。
- 顶部要有清晰挂点，方便程序用「北侧」热点做枢轴。
- 造型必须能让人看出属于该主题（色、纹样、器物语言与 `arrow.png` 一致）。
- 小尺寸可读：最终会缩到约指针高度的 0.8–1.0 倍。
- 背景必须是指定纯色，禁止透明底/棋盘格。

---

## 伊雷娜示例（已完成主题可参考）

主题元素：金框圆徽、五角星、粉宝石、下方蓝水滴。  
成品路径：`src/arkcursor/themes/elaina/pendant.png`（仅星徽饰物，无上方长链）。
