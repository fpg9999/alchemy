# ALCHEMY 表现层（外观层）分析报告

> 分析人：appearance-analyst（task-4）　日期：2026-11-19　状态：仅记录，未改仓库
> 仓库：`G:\AI work\deepseek\work1\alchemy`（改动仅限本文件与 `intake/tmp/appearance/`）
> 方法：只读阅读 `docs/T68~T76`、`docs/APPEARANCE.md` 与渲染脚本；用 `alchemy` 内核与渲染脚本做只读探针，
> 在 `intake/tmp/appearance/` 生成验证图（`check_G13_bars.png`、`check_tile_overlap.png`、`t75b_*.png`）。
> 依据标记：`[实测]` = 本次运行输出；`[码]` = 代码行号；`[档]` = 文档行号。仓库文档正被并发修改
> （`git status` 显示 `M docs/APPEARANCE.md`、`M docs/KERNEL_INTAKE.md` 等），行号以 2026-11-19 00:35 的快照为准。
>
> ⚠️ **历史分析件（2026-11-19 晚补注）**：本报告分析时的「内核物性」= 密度/粘性/温度 27 格（`attrs.py` 旧 API）；
> 上游 `c438fef` 已改为**质量/物态/温度**（按层平均，`docs/MATERIAL_AXES.md`，27 格行为表 + 浮力），
> 文中 `alchemy/attrs.py` 行号与 `DENS_W/STICK_W/TEMP_W` 等符号已成历史，结论（外观层与内核零连线等）仍可参考，
> 但涉及具体字段/阈值处需按新 `attrs.py` 重新核对。

---

## 1. 结论摘要

1. **外观层有且只有一个主规范：T75 方块世界**（`docs/APPEARANCE.md:13-14`）。T68→T69→T70→T70b 被明确定性为"前身，不再作为主规范"（`docs/APPEARANCE.md:14`），T75 自己又把属性规则升级为 T75b（`docs/T75_BLOCK_WORLD.md:67-88`，同一文件的 §6）。
2. **谱系是一条连续替代链**：元素字形+家族容器（T68）→ 去掉原子字形的纯轮廓（T69）→ 参数涌现字形（T70）→ 一整块光滑形体（T70b）→ 方块世界（T75/T75b）。T71/T72/T73 是"能力/形态/器官"支线，已被 2026-11-19 的规则改版推翻、不在外观主链上；T76 桥功用标签仍是有效规范但新文档不再引用它。
3. **T75 在上游脚本里已经完整实现**：`t75_tiles.py` 380 行 + `t75_render.py` 188 行 + `t75b_attrs.py` 98 行 + `t75b_render.py` 175 行，产出 6 张图 `images/t75_*.png`、`images/t75b_*.png`。因此 `docs/APPEARANCE.md:59-62` 的"尚未实现"只能读作**内核侧/正式层未实现**，不是仓库里没有代码；措辞有歧义。
4. **内核接口只有一半接通**：`alchemy.attrs.skeleton_units(atoms, edges)`（`alchemy/attrs.py:151-219`）能给出骨架成员、桥成员、尺寸，足以复算"逐骨架三属性"；但它不含原子坐标 `place`、家族与 38 库块形态匹配、融合对、支臂/端帽角色，**不足以直接驱动 T75 的 tile/bridge/cap 绘制**，且没有任何渲染脚本 import 它（全仓库仅 `attrs.py:145` 自己调用、`docs/APPEARANCE.md:55` 与 `docs/KERNEL_INTAKE.md:149` 引用）。
5. **新物性 27 格与能力 聚/散/动 在外观层"零使用"**：没有任何脚本 `import alchemy.attrs / alchemy.ability`；方块着色只按"骨架家族"（7 色，`t68_shapes.py:44-52`）；T75b 的三色条是**该骨架数值 / 36 分子内的 min-max 归一**（`t75b_attrs.py:91-98`、`t75_tiles.py:147-164`），不是 27 格阈值分档；能力三阶没有任何图形表达。
6. **T75b 的数值与文档示例逐位吻合**：G13 骨架① `OP4K H 5.40 V 0.00 T +3.50` 与 `docs/T75_BLOCK_WORLD.md:85` 的示例完全一致 `[实测]`；"桥不计入属性"由 `t75b_attrs.py:51-52`、`t75b_attrs.py:84-86` 落实；114 个骨架中 65 个粘性=0、103 个温度=0 `[实测]`。
7. **发现文档/代码不一致 5 类**（详见 §6）：属性色条文档写"右下角"而代码画在右上角并与块数点争位；"顶部=三价原子数"代码只显示 `N 原子`；混合元素桥被压成单一图形；`draw_molecule` 用 `sk["num"]-1` 当索引；APPEARANCE.md 的"156 张候选物质图谱"与现值 121 种不符。
8. **总体判断**：外观层"规范 + 上游实现 + 图件"三件齐全，真正缺的是 —— ①内核 → 外观的数据适配器；②新属性/能力 → 方块视觉的语法（27 格怎么着色、聚散动怎么画）；③文档同步（APPEARANCE 漏 T71/T72/T73/T75b/T76，T75 仍用"硬度"旧口径）。

---

## 2. 表现层文档谱系：T68 → T69 → T70 → T70b → T75/T75b（→ T76）

时间顺序由 git 历史与文档互相印证：`8877e8d T71-T76 … 方块世界 / 逐骨架属性 / 桥功用标签` 是把 T68~T76 一次性提交；
之后才是 `4a2e4d6`（内核抽出）与 `facb162`（三价轴改密度、能力改类别辐条、27 格物性、能力三阶）。
**因此 T75/T75b 的"硬度"口径早于现行"密度"口径**——这是外观层与内核最大的时间错位。

| 文档 | 解决什么问题 | 关键设定（行号） | 被谁取代 / 现状 |
|---|---|---|---|
| `docs/T68_GLYPH_SYSTEM.md` | 原子级"形状语言"：元素字形 + 骨架家族容器 + 键型语法 三层叠加 | 元素字形表 `T68:26-49`；7 家族与 38 库 `T68:49-90`；键型 S/C/L `T68:92-108`；桥/融合/装饰 `T68:109-149` | 被 T69 取代（去掉原子字形）。**仍有效**：7 家族 × 9 元素的配色与几何（`t68_shapes.py:28-52`）、38 形态库、键型语义、114 条桥的统计 |
| `docs/T69_SKELETON_SHAPES.md` | 去掉元素字形与字母，只留骨架外轮廓；给连接件/端帽固定图形语法 | 家族外形表 `T69:10-24`；融合=边对边焊带 `T69:26-29`；桥 X楔/W腱/A膜 + 多元素分段 `T69:31-41`；端帽与装饰 `T69:43-54`；排版示意 `T69:56-59` | 被 T70 取代。**仍有效**：连接件语义（X 焊死 / W 可拉伸 / A 隔空软连）、端帽 C尖/F方/L椭圆、多元素桥"按链分段、同元素合并、×N 合并"约定 |
| `docs/T70_EMERGENT_GLYPHS.md` | 形状不再手工指派，由块参数（n、nO/nP/nK、deg）经超公式涌现 | 骨架超公式 `T70:7-31`；桥分段生成 `T70:32-38`；端帽触肢 `T70:39-45`；图集与复现 `T70:52-66` | 被 T70b 取代。**仍有效**：参数化字形思路（`t70_glyphs.py:58-152` 的 `block_params`/`skeleton_rf`） |
| `docs/T70B_WHOLE_BODY.md` | 一个分子 = 一个完整形体：先并集成光滑身体，再画内部器官 | 并集蒙版+形态学闭合 `T70B:5-19`；图件 `T70B:20-26`；局限 `T70B:36-40` | 被 T75 方块化取代。**仍有效**：器官/内部结构的表达（T73 在它上面继续；`t70b_body.py:131 draw_body_molecule`） |
| `docs/T71_ABILITIES.md` | 骨架级能力（27 项，文档写 30）+ 生命度 + 固/液/气 + 刚/松/粘分类 | 能力模型 `T71:6-31`；生命度 `T71:32-54`；固液气与刚松粘 `T71:55-61`；物种命名 `T71:62-66` | **未延续**。512/27 能力与分类被 `ABILITY.md` v3/v4 取代（`KERNEL_INTAKE:141-146`）；"30 vs 27"是文档自身陈旧 |
| `docs/T72_ABILITIES_MORPHS.md` | 72 能力 / 9 大类 + 28 种分化形态（7 家族×4） | 能力 `T72:9-28`；形态库 `T72:29-44`；小分子形态 `T72:59-69`；局限"不与几何位置耦合" `T72:76-81` | **未延续**，`KERNEL_INTAKE:145` 明确写"T72 悬空" |
| `docs/T73_MORPH_GEOMETRY.md` | 器官长在哪、长成什么：几何判定 5 特征 + 5 类型；小分子物质化 | 几何判定 `T73:6-30`；形态直接画在身体上 `T73:31-44`；小分子 `T73:45-59`；T73b 自我修正 `T73:85-101` | **未进入 T75**（方块世界不需要器官）；其"形态即器官"思路保留在 `t73_body.py` |
| `docs/T75_BLOCK_WORLD.md` | **现行主规范**：每个骨架压成 1 个单位方块，世界=多格骨牌 | 用户规则 `T75:3-7`；方块内部 `T75:9-18`；连接 `T75:20-31`；三属性 `T75:33-42`；文件与复现 `T75:44-57`；局限 `T75:59-65` | **现行**；§6 是 T75b 修订 `T75:67-88` |
| `docs/T75_BLOCK_WORLD.md` §6（T75b） | 属性从"整个分子"改为"逐骨架"，连接两个骨架的二价桥不计入任何属性 | 逐骨架取值表 `T75:74-81`；呈现方式 `T75:83-88`；用户原话 `T75:67-70` | **现行**（与 T75 同文件，实践中 `t75b_*` 是更晚的一版） |
| `docs/T76_BRIDGE_FUNCTIONS.md` | 桥不参与属性，改做纯功能标签（13 种） | 判定规则 `T76:6-26`；114 条桥分布 `T76:27-41`；例子 `T76:42-48`；局限 `T76:57-61` | **有效但未接入**：新文档不引用它（`KERNEL_INTAKE:177-184`）；外观层也没画这 13 个标签 |
| `docs/APPEARANCE.md` | 2026-11-18 的"外观层定调 + 现状汇总"：不新设计、采用 T75、只记录不实现 | 决定 `APPEARANCE:8-14`；清单 `APPEARANCE:16-26`；主规范 3.1/3.2 `APPEARANCE:28-51`；内核接口 `APPEARANCE:53-57`；未实现 `APPEARANCE:59-62`；前身表 `APPEARANCE:64-71`；排除化学结构图 `APPEARANCE:73-76`；三层现状 `APPEARANCE:78-84` | **现行汇总，但有漏项/歧义**：只列 T68/T69/T70/T70b/T75，未列 T71/T72/T73/T75b/T76；"T75 时间上最新"（`APPEARANCE:26`）忽略 T75b；§3.3 说 `skeleton_units`"足以驱动"（§5 反驳）；§3.4 "未实现"与仓库已有实现冲突 |

**每一代替代的动因与代价**（把"为什么换"记下来，避免再走回头路）：

- T68 → T69：原子字形（三角/圆/多边形/六边形/菱形/圆点）在 40 原子的大分子里太碎、不可读；T69 把"每个原子一个字形"换成"每个骨架一个容器"，代价是丢失原子级可读性（靠面板文字补偿，`T69:53-54`）。
- T69 → T70：家族容器仍需手工为 7 类各画一种外形，且同族分子看起来一样；T70 换成参数化超公式（`n`、`nO/nP/nK`、`deg`），代价是形状不再语义直观、需要图例解释（`T70:69-73` 自陈）。
- T70 → T70b：碎片化的字形拼在一起仍是"一串珠子"；T70b 用并集蒙版+形态学闭合把整个分子并成一个光滑身体，代价是失去方块感、且 2D/圆形器官核心受限（`T70B:36-40`）。
- T70b → T75：用户明确要求"类泰拉瑞亚的方块世界"（`T75:3-7`），骨架必须是方块；代价是同族方块几乎一样、BFS 嵌入是近似而非真实拓扑（`T75:59-65`），这也是 T75b 必须引入逐骨架属性条来增加区分度的原因。
- T75 → T75b：整个分子一个属性无法区分 4 个骨架各自的性质（G13 的 4 个骨架 H 从 2.4 到 10.8），于是改为逐骨架、桥不计（`T75:67-81`），代价是属性不再能直接与"分子整体"对话。

**一句话谱系**：`T68 字形 → T69 轮廓 → T70 涌现 → T70b 整体 → T75 方块 → T75b 逐骨架属性` 是单调替代；
`T71 生命度 / T72 能力-形态 / T73 器官几何` 是被规则改版废掉的支线；`T76 桥功用` 是没接上的旁支；
`APPEARANCE.md` 是 2026-11-18 的汇总快照，不是新规范。

---

## 3. T75 方块世界规范要点

### 3.1 一个方块里放什么（tile 类型表）

| 元素 | 含义 | 规范 | 代码实现 |
|---|---|---|---|
| 方块本体 | 1 个三价连通骨架 = 地图上 1 个单位正方形 | `T75:11`；`APPEARANCE:32` | `t75_tiles.py:166 draw_tile` |
| 外框颜色 | 骨架家族（7 种） | `T75:15`；`APPEARANCE:38` | `t75_tiles.py:19 FAM_COL` ← `t68_shapes.py:44-52` |
| 内部纹样 | 家族图案：纯秩三角 / 纯势圆 / 纯散五角 / 秩势拱 / 秩散盾 / 势散圆角方 / 秩势散六边 | `T75:15` | `t75_tiles.py:109-143 fam_motif`（7 分支，末尾 139-143 为死代码） |
| 右上小方点 | 该骨架由几个 6 级块融合而成（1~2 个） | `T75:16` | `t75_tiles.py:172-176`（点数 = `len(sk["blocks"])`，点 6×6 px、间距 9 px） |
| 底部文字 | 块形态（38 库公式，如 `OP4K`） | `T75:17`；`APPEARANCE:40` | `t75_tiles.py:180-182`（`block_forms[0][:6]`） |
| 顶部小字 | 该骨架的三价原子数 | `T75:18`；`APPEARANCE:41` | `t75_tiles.py:183`（`"%d 原子" % sk["n"]`；数据里 `sk["n"]` 恰等于三价原子数，实测 G13 骨架① `n=6`、`len(idx)=6`） |
| 属性色条 | **T75b**：右下角三条小色条 = 该骨架硬度(红)/粘性(绿)/温度(紫) | `T75:84` | `t75_tiles.py:147-164`（实际画在**右上角**：`bx=x0+0.80s, by=y0+0.13s`，与块数点同角） |

### 3.2 方块之间怎么连（都画在共用边/外缘）

| 连接 | 图形约定 | 规范 | 代码 |
|---|---|---|---|
| 晶 X 桥 | 共用边上短粗浅灰焊块，两侧焊钉（最硬，两块咬死） | `T75:24`；`T69:36` | `t75_tiles.py:192-204` |
| 流 W 桥 | 跨边细长椭圆肌腱 + 中线（可拉伸、可弯） | `T75:25`；`T69:37` | `t75_tiles.py:205-213` |
| 气 A 桥 | 沿共用边的淡青细长薄膜 + 横向褶线（隔空软连） | `T75:26`；`T69:38` | `t75_tiles.py:214-223` |
| 融合（0 级同类键） | 同一骨架内两块 6 级块的焊纹（几条斜刻纹） | `T75:27`；`T69:27-28` | `t75_tiles.py:302-309`（画 4 条竖刻线；全 36 分子只有 G13 骨架② 一处） |
| 一价端帽 | 方块**外缘**小方钉：C 三角钉 / F 方钉 / L 细圆钉 | `T75:28`；`APPEARANCE:51` | `t75_tiles.py:241-264 draw_stud`（统一矩形钉，内部再画 C 三角/F 波线/L 圆点） |
| 方块排布 | 分子 = 多格骨牌；BFS 四邻接嵌入，优先紧贴桥伙伴、整体紧凑 | `T75:30-31` | `t75_tiles.py:54-105 grid_embed`（贪心评分 + 兜底外找空位） |

### 3.3 参数与阈值（可调点）

| 参数 | 值 | 位置 |
|---|---|---|
| 硬度权重（三价） | O 1.20 / P 0.90 / K 0.60 | `T75:35-37`；`t75_attrs.py:11`；`t75b_attrs.py:12` |
| 粘性权重（二价） | X 1.00 / W 1.40 / A 0.40 | `T75:38`；`t75_attrs.py:12`；`t75b_attrs.py:13` |
| 温度权重（一价） | C −2.00 / L +0.50 / F +3.00 | `T75:39`；`t75_attrs.py:13`；`t75b_attrs.py:14` |
| 属性公式 | `Σ 个数 × 权重`，保留 2 位小数；温度负=冷、正=热、0=常温 | `T75:35-39`；`t75_attrs.py:22-32` |
| 方块边长 s | `min((W−2pad)/nq, (H−2pad)/nr)`，可再被 `max_tile` 压小 | `t75_tiles.py:268-277` |
| 色条尺寸 | 宽 0.13s、高 0.045s、行距 0.03s，起点 (0.80s, 0.13s) | `t75_tiles.py:157-164` |
| 桥件尺寸 | X 焊块 0.46s；W 椭圆 0.07s×0.21s；A 膜 0.022s×0.30s | `t75_tiles.py:194-223` |
| 端帽尺寸 | 长 0.15s、宽 0.26s；同边多帽偏移 0.22s | `t75_tiles.py:244-246, 354` |
| 逐骨架参考区间 | 全 36 分子 114 骨架：H 0.9~12.3、V 0~10.8、T −3.5~+6.0 | `[实测]`；`t75b_attrs.py:91-98` |

### 3.4 实例：G13（文档与图件的"样板分子"）

- 分子式 `O3X4CP16W5LK5A3F2`，40 原子、4 个骨架、7 条桥、4 个端帽 `[实测]`；分子级属性 H=21.0、V=12.2、T=4.5 `[实测]`。
- `grid_embed` 结果：骨架 0→(1,1)、1→(1,2)、2→(0,1)、3→(1,0) `[实测]`，即 4 格 L 形多格骨牌。
- 逐骨架属性 `[实测]`（与 `T75:85` 示例一致）：

| 骨架 | 公式 | 家族 | H | V | T | 计入的元素 |
|---|---|---|---|---|---|---|
| ① | OP4K | OPK | 5.40 | 0.00 | +3.50 | 硬:秩1+势4+沌1；温:电1+焰1 |
| ② | O2P8K2 | OPK | 10.80 | 4.00 | 0.00 | 硬:秩2+势8+沌2；粘:流2+气3 |
| ③ | P2K | PK | 2.40 | 0.00 | −2.00 | 硬:势2+沌1；温:冰1 |
| ④ | P2K | PK | 2.40 | 0.00 | +3.00 | 硬:势2+沌1；温:焰1 |

- 结论性观察：G13 的 4 个骨架里有 3 个粘性为 0（桥不计），说明 T75b 的"只有三价元素（桥不计）"分支不是边角情况，而是主流量级（65/114 = 57% 的骨架 V=0）`[实测]`。

### 3.5 文件与图件（T75/T75b）

| 文件 | 行数/大小 | 作用 |
|---|---|---|
| `t75_attrs.py` | 44 行 | 分子级三属性权重表 + `attrs()`/`attrs_of()`/`norm_ranges()` |
| `t75_tiles.py` | 380 行 | 方块图结构、BFS 嵌入、tile/bridge/weld/stud、`draw_molecule()` |
| `t75_render.py` | 188 行 | `page_rules` / `page_molecules`（18 张卡）/ `page_overview`（36 格） |
| `t75b_attrs.py` | 98 行 | `skeleton_attrs(mol)`：逐骨架属性，桥不计 |
| `t75b_render.py` | 175 行 | 逐骨架规则页/分子卡/总览 |
| `images/t75_rules.png` | 1600×1010 | 方块系统说明（A 方块解剖 / B 七家族 / C 连接件 / D 端帽 / E 公式） |
| `images/t75_molecules.png` | 1600×4420 | 18 张大分子的方块形态 + 分子级属性条 |
| `images/t75_overview.png` | 1612×1758 | 36 个稳定大分子总览 |
| `images/t75b_rules.png` / `_molecules.png` / `_overview.png` | 1600×1010 / 1600×4880 / 1612×1758 | 同上的逐骨架属性版 |
| 复现 | — | `python t75_render.py`、`python t75b_render.py`（`T75:56,88`） |

---

## 4. 骨架 → 表现层的数据通路

### 4.1 数据文件

| 文件 | 大小 | 内容 | 谁读 |
|---|---|---|---|
| `t8_forms.json` | 103,930 B | 38 个 level-6 骨架形态库（T68 图册/家族匹配的唯一源） | `t68_atlas.py:21 load_forms`、`t70_glyphs.py:373 library_blocks`、`t72_render.py:150` |
| `t61~t64_hex_layouts.json` | — | 原始六边形布局（T61/T62/T63/T64 四个实验） | `t68_build_data.py:34 LAYOUTS, :280` |
| `t68_pool.json` | 745,503 B | 候选池（含键型、桥、装饰角色分析） | `t68_select.py:84` |
| `t68_data.json` | 267,580 B | **表现层主数据**：36 个稳定大分子 / 1147 原子 / 114 骨架 / 114 桥 / 1 处融合；`meta.sources=[T61,T62,T63,T64]` | 全部渲染脚本（`t69_pieces.py:507-509 load_data`） |
| `t4_catalog_all_validated.json` | 39,150,742 B | 全目录（84,225 条） | `t72_render.py:310`（小分子页） |
| `data/biomes/candidates/_union.json` | — | 候选群系并集 121 种物质 | `examples/render_species_sheets.py:37` |
| `alchemy/data/forms38.json` | 103,930 B | 38 库的内核副本（与 `t8_forms.json` 同 sha256，`KERNEL_INTAKE:43`） | `alchemy` 内核（只做数据，不渲染） |

### 4.2 生成链（谁写谁读）

```
t61~t64_hex_layouts.json ─┐
t8_forms.json ────────────┼─→ t68_build_data.py ─→ t68_pool.json
                          │   (triv_components/bond_type/analyze, t68_build_data.py:39,74,81)
                          └─→ t68_select.py ───→ t68_data.json（36 分子，t68_select.py:187-190）
                                                   │
      ┌────────────────────────────────────────────┼───────────────────────────────┐
      ▼                    ▼                       ▼                               ▼
 t69_pieces.load_data  t71_abilities.load      t72_render._forms            t70_glyphs.library_blocks
 (t69_pieces.py:507)   (t71_abilities.py:372)  (t8_forms.json:150)          (t8_forms.json:373)
      │
      ├→ t69_draw.py → t69_render.py → images/t69_giants_01..18 + overview + legend
      ├→ t70_render.py（复用 t69_bodies/t69_pieces）→ images/t70_*.png
      ├→ t70b_body.py → images/t70b_bodies.png / all36.png
      ├→ t73_body.py / t73_small.py → images/t73_*.png
      ├→ t75_tiles.py → t75_render.py → images/t75_*.png
      └→ t75b_attrs.py → t75b_render.py → images/t75b_*.png；t76_render.py → images/t76_bridge_functions.png
```

要点：**所有外观脚本读的是 `t68_data.json`（或 `t8_forms.json`），不是内核 `alchemy`**；
`t68_data.json` 是 T68 时代一次性算好的"分析结果缓存"，含 `place`（原子坐标）、`skeletons[].idx/num/blocks/block_forms/fusion`、
`bridges[].comps/idx/k`、`decoration.mono/intra/arms/free`、`role` 等外壳脚本必需的字段——这解释了为什么内核 `skeleton_units` 不能直接替换它。

### 4.3 输出、入口命令与耗时

| 命令 | 产物 | 实测耗时 |
|---|---|---|
| `python t75_render.py` | `images/t75_rules.png` + `t75_molecules.png` + `t75_overview.png` | 规则页 <0.1s、18 卡 0.3s、36 格 0.1s（Pillow 12.3.0 / Python 3.12）`[实测]` |
| `python t75b_render.py` | `images/t75b_rules.png` + `t75b_molecules.png` + `t75b_overview.png` | 0.0 / 0.3 / 0.1 s `[实测]` |
| 单分子 `draw_molecule(G13)` | 900×640 验证图 | 0.06 s `[实测]` |
| `python t76_render.py` | `images/t76_bridge_functions.png`（1600×1330） | 未跑（同类页约 0.1~0.3s） |
| `python t69_render.py` / `t70_render.py` / `t71_render.py` / `t72_render.py` / `t73_render.py` | 各自图件（见 §7 表） | 同量级（几十秒内） |
| `python examples/render_species_sheets.py` | `images/biome_candidates/species_01..04.png` + `index` + `legend`（6 张） | 未跑；依赖 Pillow |

运行环境：带 Pillow 的解释器在
`C:\Users\123\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`（Python 3.12.14 / Pillow 12.3.0）`[实测]`；
仓库根目录的 `python` 是 3.11 且无 Pillow。Windows 控制台需 `PYTHONIOENCODING=utf-8`，否则中文 `print` 会 UnicodeEncodeError（`KERNEL_INTAKE:25`）。

### 4.4 内核侧通路（与外观层的现状）

- 内核 `alchemy/attrs.py:151-219 skeleton_units(atoms, edges)`：骨架 = 三价原子连通块；**跨两个骨架的二价桥同时属于这两个骨架**（进 `members` 与 `bridge_members`）；`size` = 三价原子数。
- `alchemy/data/forms38.json` 就是 `t8_forms.json` 的同 sha256 副本（`KERNEL_INTAKE:43`），所以 38 库数据已在内核。
- 但**没有任何渲染脚本 import `alchemy`**；`skeleton_units` 目前只被 `attrs_of`（`alchemy/attrs.py:145`）内部调用，
  供测试/文档使用（`tests/test_attrs.py`、`docs/TRAITS.md:105` 的用法示例）。
- `docs/APPEARANCE.md:53-57` 把 `skeleton_units` 当作"唯一输入"，`docs/KERNEL_INTAKE.md:147-150` 把它当作"唯一依赖"——
  两者都成立的前提是**另写一个适配器**，把 `{members, atoms, size, bridge_members}` 还原成 `t75_tiles` 需要的分子 dict（见 §5.3 G1）。

### 4.5 各图件的内容与读法（按代际）

| 图件 | 画的是什么 | 读者能从中确认什么 | 与后续规范的关系 |
|---|---|---|---|
| `t68_glyphs.png` / `t68_families.png` / `t68_library38.png` | 元素字形、7 家族容器、38 个 level-6 骨架 | 形状语言的"字母表"与"词库" | 数据事实层（38 库）仍是 T75 的 `block_forms` 来源 |
| `t68_connect.png` | 键型 S/C/L、桥、融合、装饰的图例 | 114 条桥的键型语义 | T75 的 X/W/A 桥图形继承自这里的语义 |
| `t69_overview.png` / `t69_giants_01..18.png` | 每个分子 = 若干骨架容器 + 连接件 + 端帽 | 36 分子全部可画、115 块全在 38 库内（`T69:24`） | 被 T70/T70b 取代，但"连接件三分 + 端帽三形"沿用 |
| `t70_skeletons38.png` / `t70_bridges.png` / `t70_terminals.png` | 超公式生成的骨架/桥/端帽 | 生成式语法可覆盖全部骨架 | 被 T70b 取代 |
| `t70b_bodies.png` / `t70b_all36.png` | 36 个"一整块光滑身体" | 形体优先的表达 | 被 T75 取代 |
| `t71_*` / `t72_*` / `t73_*` | 能力、形态、器官、小分子物质化 | 能力-形态-器官的表达尝试 | 未进入 T75；T73 的"形态即器官"思路留在 `t73_body.py` |
| `t75_rules.png` / `t75_molecules.png` / `t75_overview.png` | 方块解剖、18 张分子卡、36 格总览 | 方块世界的当前位置 | 现行（分子级属性口径） |
| `t75b_*.png` | 同上但逐骨架属性条 + 逐骨架列表 | 现行属性口径（桥不计） | 现行（逐骨架口径） |
| `t76_bridge_functions.png` | 13 个桥功用标签及分布 | 桥的"功能"维度 | 未接入方块世界 |
| `biome_candidates/species_*.png` | 46 种目录内物质的六边形原子结构图 | 原子/键/摆放核对 | **不是外观层**（`APPEARANCE:73-76`），两套并存 |

### 4.6 复现注意（实测踩到的）

- 必须用带 Pillow 的 Python（`C:\Users\123\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`，3.12.14 / Pillow 12.3.0）；仓库根 `python` = 3.11 无 Pillow，直接跑会 `ModuleNotFoundError: PIL` `[实测]`。
- 所有脚本以仓库根为工作目录（`t68_shapes.py:24` 硬编码 `G:\AI work\deepseek\work1\alchemy`，`t69_pieces.py:19 HERE` 取脚本目录）；从别处运行会把图写到意外位置。
- 图片文件名是相对路径（`images/t75_rules.png`），脚本用当前工作目录解析；本次探针把输出改写到 `intake/tmp/appearance/` 才避免写仓库。
- 整页渲染很快（3 页 < 0.5s），瓶颈不在渲染而在数据：`t68_data.json` 仅 267 KB，加载可忽略；但 `t4_catalog_all_validated.json` 39 MB（`t72_render.py:310`）加载会明显变慢。

---

## 5. 新属性 / 能力 → 表现层的衔接现状

### 5.1 已实现（真正接通的部分）

| 项 | 状态 | 证据 |
|---|---|---|
| 物性 = 密度/粘性/温度 27 格（内核） | ✅ 已实现 | `alchemy/attrs.py:45-52`（DENS_W/STICK_W/TEMP_W）、`:64 N_CELLS=27`、`:67-71` 阈值、`:233-255 cell_of/property_of`、`:258-269 grid`；`docs/TRAITS.md:32-66` |
| 逐骨架 硬度/粘性/温度（外观，T75b） | ✅ 已实现 | `t75b_attrs.py:26-88`；`t75_tiles.py:371-376`（色条）；`t75b_render.py:93-144`（卡片逐骨架列表） |
| 分子级三属性（外观，T75 旧版） | ✅ 已实现 | `t75_attrs.py:22-44`；`t75_render.py:104-151`（卡片） |
| 家族着色 / 家族纹样 / 7 家族 | ✅ 已实现 | `t68_shapes.py:44-52`；`t75_tiles.py:19,109-143` |
| 38 库块形态文字（OP4K 等） | ✅ 已实现 | `t68_data.json` 的 `skeletons[].block_forms`；`t75_tiles.py:180-182` |
| 桥类型图形（X/W/A）+ 融合焊纹 + 端帽 | ✅ 已实现（大体） | `t75_tiles.py:188-264` |
| 内核 512 能力历史接口 | ✅ 保留但冻结 | `alchemy/ability.py:48-140`；`docs/ABILITY.md:9,114-125` |
| 内核 v3 聚/散/动 + v4 九项次级三阶 | ✅ 已实现 API | `alchemy/ability.py:143-324`；`docs/ABILITY.md:14-86` |

### 5.2 预留但无消费者（接口在、图形语法不在）

| 项 | 预留位置 | 现状 |
|---|---|---|
| `skeleton_units` → 方块 | `alchemy/attrs.py:151-219`；`docs/APPEARANCE.md:53-57` | 无调用方、无适配器；字段不足以驱动绘制（G1/G4/G5/G6） |
| `attrs_of(...)["skeletons"]` | `alchemy/attrs.py:124-147` | 同上 |
| 27 格 `cell_of/property_of/grid` | `alchemy/attrs.py:233-269`；`docs/TRAITS.md:58-116` | 外观层零使用：没有"密度低/中/高→颜色/纹样"的映射 |
| 能力 v3 `scores/profile/abilities_of` | `alchemy/ability.py:179-324`；`docs/ABILITY.md:27-86` | 外观层零使用：方块/桥/端帽没有任何"聚/散/动"或九项次级能力的图形变量 |
| T76 桥功用 13 标签 | `t76_bridge_fn.py:8-118`；`docs/T76_BRIDGE_FUNCTIONS.md:6-41` | 只有文字统计页 `t76_bridge_functions.png`，方块世界没把"定距隔空/多点编织/刚性焊接"画成不同桥形 |

### 5.3 缺口清单（按修复优先级）

| # | 缺口 | 具体表现 | 影响 |
|---|---|---|---|
| G1 | **内核→外观适配器缺失** | `skeleton_units` 只给 `members/atoms/size/bridge_members`；`t75_tiles` 需要 `place`（坐标）、`skeletons[].idx/num/blocks/block_forms/fusion`、`bridges[].comps`、`decoration.mono/intra/arms/free`、`role`（见 `t68_data.json` 实测结构） | 内核无法直接出图；外观层只能继续依赖 `t68_data.json` 缓存 |
| G2 | **27 格物性没有视觉语法** | tile 颜色=家族（`t75_tiles.py:19`），与密度/粘性/温度档位无关；色条是 min-max 归一（`t75b_attrs.py:91-98`），不是 `(10,16)/(6,11)/(3,6)` 阈值（`alchemy/attrs.py:67-71`） | 用户新关注的 27 格"看不见"；跨分子不可比（每 36 分子重标定） |
| G3 | **能力三阶没有图形表达** | 全仓库无 `alchemy.ability` 消费方；T71/T72 的旧能力页已废；9 项次级能力（结构支撑/刚性/粘合/分化/吸附/切割/储能/移动/信号）无任何形状/颜色/符号位 | 能力维度在表现层完全缺席 |
| G4 | **坐标/方向缺失** | T75 端帽方向依赖 `mol["place"]`（`t75_tiles.py:315-341 cell_of`）；内核不存坐标，只能纯图形重排或另算布局 | 端帽朝向、融合块相对位置、原六边形布局无法还原 |
| G5 | **家族/块形态匹配未入内核** | `family` 由三价组合推导（`t69_bodies.py:36 family_of`），`block_forms` 要查 38 库（`t8_forms.json`）；内核 `forms38.json` 有数据但没接口 | 适配器需重写这套匹配逻辑，否则方块无纹样/无文字 |
| G6 | **融合对识别缺失** | 融合 = 同一骨架内两块 6 级块之间的 0 级同类键（`T69:26-29`），`t68_data.json` 的 `n_fusion_bonds/fusion` 是 T68 管线算好的；`skeleton_units` 不区分 0 级键 | 全目录唯一 1 处融合（G13 骨架②）画不出来 |
| G7 | **无三价原子的分子无表现** | `skeleton_units` 对无三价原子返回 `[]`（`alchemy/attrs.py:181-182`）；`t75_tiles` 没有 0 方块分支；小分子（F2/XA/CL 等）只能走 `t73_small.py` 旧路 | T75 方块世界只覆盖"有骨架的大分子"，与"元素→…→分子"全链不闭合 |
| G8 | **混合元素桥分段未实现** | `draw_bridge_on_edge` 以 `"X" in els` 优先级坍塌为单一图形（`t75_tiles.py:191-223`）；T69 要求"按链顺序分段、同元素合并"（`T69:40`）；T68 统计 114 条桥里 56 条是"混合"（`T68:131-134`） | 约一半桥的组成信息在图上丢失 |
| G9 | **文档不同步** | APPEARANCE 未提 T75b/T76/T71-73；T75 仍写"硬度"（早于 `facb162` 的"密度"改版）；"156 张候选物质图谱"（`APPEARANCE:75`）与现值不符 | 读者会得到过期口径 |

### 5.4 适配器最小伪代码（建议，未实现）

内核已经能给出"骨架视图"，但 T75 绘制需要的是"带坐标与装饰角色的分子视图"。最小适配器可以这样写：

```python
# 输入：atoms, edges（来自 alchemy.core.catalog 或 molecule dict）
units = skeleton_units(atoms, edges)          # 每单元: members / atoms / size / bridge_members
# 1) 骨架对象: idx = members 中的三价原子; 家族 = fam_of_mol_atoms(三价元素集合)
# 2) 桥对象: 一个原子出现在多个单元的 bridge_members 中 → 它就是跨单元桥;
#    多原子桥链: 沿非三价原子邻接展开, 两端各触一个单元 → comps = [sk_a, sk_b]
# 3) 端帽/支臂: members 中非三价且不在任何 bridge_members 的原子 = 挂在单骨架上的装饰;
#    其中一价(C/L/F) = 端帽, 二价(X/W/A) = 支臂/骨架内桥
# 4) 6 级块与块形态: 用 t8_forms.json 的 38 库匹配(三价原子子集 + 键型), 得到 block_forms
# 5) 融合: 同一代码块内两个子块之间的 0 级同类三价键 → n_fusion_bonds
# 6) 坐标: 内核没有 → 只能 grid_embed 纯图 BFS 重排; 需要"原布局方向"的端帽方向需另算
```

关键结论：第 1~5 步都可由内核数据 + 38 库完成；**第 6 步（坐标）是硬缺口**，内核 attrs 不保存任何几何信息，而 `t75_tiles.py:315-341` 的端帽方向、`t75_tiles.py:302-309` 的融合位置都依赖 `t68_data.json` 的 `place`。这意味着"内核单一数据源出图"要么接受纯图重排（丢原布局），要么把 `place` 一并纳入内核接口。

**估算工作量**：适配器 150~250 行；27 格视觉映射（表格 + 3 个绘制函数）50~100 行；能力视觉位（若做）100 行量级；文档同步 1 天。均属"有规范、缺实现"，不是研究性工作。

---

## 6. 矛盾、过期说明与风险

### 6.1 文档 vs 代码

| # | 文档说法 | 代码实际 | 级别 |
|---|---|---|---|
| D1 | T75b：色条在**右下角**（`T75:84`） | `t75_tiles.py:157-158`：`bx=x0+0.80s, by=y0+0.13s` → **右上角**；与块数点（`t75_tiles.py:172-176`，y0+7px 起）同角，小尺寸（overview `max_tile=42`）时重叠 | 中（视觉缺陷） |
| D2 | 顶部小字 = **三价原子数**（`T75:18`；`APPEARANCE:41`；`t75_render.py:43` 自己这么写） | `t75_tiles.py:183` 打印 `"%d 原子" % sk["n"]`；数据里 `sk["n"]` 确实等于三价原子数（G13 ① n=6=len(idx)），但标签语义是"原子"不是"三价原子" | 低（措辞） |
| D3 | 融合 = "几条斜刻纹"（`T75:27`）；`APPEARANCE:50` 写"焊纹" | `t75_tiles.py:302-309` 画的是 4 条**竖**刻线；另外 `fam_motif` 末尾 `n3` 中心点计算完**从不绘制**（`t75_tiles.py:139-143` 死代码） | 低 |
| D4 | 端帽 = C 三角钉 / F 方钉 / L 细圆钉（`T75:28`） | 三者都是矩形钉（`t75_tiles.py:247-253`），F 只多一条波线、L 是钉内画小圆点；不是"三角/方/细圆"三种外形 | 低 |
| D5 | 混合桥按元素分段拼接（`T69:40`、`T69:41` ×N 合并） | `t75_tiles.py:191-223` 按 `"X"→elif "W"→else A` 坍塌为单一图形；`t68_data.json` 中 G13 桥 `kind="C 铰接桥"` 但 T75 只用二价元素判断 | 中 |
| D6 | `APPEARANCE:75`：`render_species_sheets.py` 产出"156 张候选物质图谱" | `_union.json` 实测 `n_union=121`、`species=121`；脚本自述"只取目录内 46 种"（`examples/render_species_sheets.py:4`）；`images/biome_candidates/` 只有 6 张 PNG | 低（数字过期） |
| D7 | `APPEARANCE:26`"T75 是时间上最新的一份" | 同文件 §6 的 T75b（`T75:67-88`）是 T75 之后的修订；git 提交顺序 `8877e8d` 一次性含 T71-T76 | 低 |
| D8 | `APPEARANCE:21` T69"去掉元素字形与字母" | T69 只去掉逐原子字母，仍保留块短组成文字与 ①②③ 序号（`T69:23`、`T69:53-54`） | 低 |
| D9 | `APPEARANCE:55-57`：`skeleton_units`"足以驱动"方块画法 | 缺坐标/家族/块形态/融合/装饰角色（§5.3 G1/G4/G5/G6），只能驱动"每骨架一方块 + 桥"的**抽象层**，画不出 T75 具体图 | 中（结论过强） |
| D10 | `APPEARANCE:59-62`"尚未实现…上游已有实现（t75_tiles.py / t75_render.py），内核侧暂不重复实现" | 仓库里确已实现且已出图（6 张）；"未实现"只对内核侧成立 | 中（易误读） |

### 6.2 口径过期（时间线导致）

- **硬度 vs 密度**：T75/T75b 写"硬度"（`T75:7,36`；`t75_attrs.py:4`；`t75b_attrs.py:2`），而现行内核叫"密度"（`alchemy/attrs.py:45 DENS_W`；`docs/TRAITS.md:14-31` 说明为什么硬度换成密度：目录里有 254 个"刚性液体"样本）。外观层没有跟上这次改名/改义。
- **权重两套**：T75 用 1.20/0.90/0.60 等"三位数权重"（`t75_attrs.py:11-13`）；内核用 3/2/1 整数（`alchemy/attrs.py:45-52`），阈值 10/16、6/11、3/6（`:67-71`）。两者**数值不可直接互换**（比例 2.5:1.5:1 vs 3:2:1，且温度符号约定一致但量级不同），且没有换算表/文档说明。
- **逐骨架 vs 整分子**：T75b 是逐骨架（`T75:67-81`）；内核 `attrs_of` 是整分子（`alchemy/attrs.py:109-121`）+ 附带骨架分解（`:145`）。`KERNEL_INTAKE:177-184` 明确把"T75b 逐骨架"标为被整分子口径取代——但外观图件仍按逐骨架画（`t75b_*`），两套口径并存且都"现行"。
- **能力口径**：`docs/ABILITY.md` 同时保留 512 历史（`:9,114-125`）与 v3/v4 现行（`:14-86`），§5 状态表（`:191-200`）仍写"512 已冻结"，§6 又把"512 vs 收紧"列为待确认——文档自身自相矛盾；外观层没有任何能力表达，所以暂时无实体冲突，但一旦要做就会撞上口径问题。
- **T71 的 30 vs 27**：`docs/T71_ABILITIES.md:6` 标题写"30 项"（正文实列 27 项），`KERNEL_INTAKE:141-146` 指出实际 27。
- **KERNEL_INTAKE 行数过期**：模块地图写 `ability.py` 155 行、`attrs.py` 252 行（`KERNEL_INTAKE:37-51`），实测现文件 343 行 / 269 行（v3/v4 与 27 格是之后的 `facb162` 加入的）。引用行数时需注意快照。

### 6.3 代码风险

| 风险 | 位置 | 说明 |
|---|---|---|
| `sk["num"]-1` 当索引 | `t75_tiles.py:304` | `cell` 以 0..n-1 枚举为键；依赖 `num == i+1`。数据当前满足（G13 num 1..4），但换数据/换排序即错位 |
| 文本二次绘制 | `t75_tiles.py:281`（labels=False）与 `:361-370`（再画一遍） | 同一逻辑两处维护，易漂移 |
| 未使用导入/死代码 | `t75_tiles.py:14 import t75_attrs as AT`（draw_molecule 未用）、`:139-143` 死代码、`t75_render.py:66` 循环内 `S.Canvas(10,10)` 空对象 | 不影响输出，但增加阅读成本 |
| 同角争位 | `t75_tiles.py:157-158` vs `:172-176` | 见 D1；小 tile（42px）时色条 3 行与点数点重叠（可打开 `intake/tmp/appearance/check_tile_overlap.png` 复核） |
| 权重表三份拷贝 | `t75_attrs.py:11-13`、`t75b_attrs.py:12-14`、内核 `alchemy/attrs.py:45-52` | 调参需改三处，且两套量纲 |
| 依赖 Windows 字体/路径 | `t68_shapes.py:24-26`（硬编码 `G:\...` 与 `C:\Windows\Fonts\msyh*`） | 跨机器/CI 不可复现；`t69_render.py:18` 用 `WINDIR` 稍好 |
| 文档并发修改 | `git status`：`M docs/APPEARANCE.md`、`M docs/KERNEL_INTAKE.md`、`M TRANSFER.md`、`?? docs/INTAKE_R2.md` | 本报告行号以当前快照为准，提交后可能偏移 |

### 6.4 未决问题（供 lead 决策）

1. T75 的"硬度"是否直接改名"密度"并复用内核权重（3/2/1），还是保留外观独立权重（1.2/0.9/0.6）并加换算说明？
2. 逐骨架属性（T75b）与整分子属性（内核）谁是正式口径？图件要不要两套并存？
3. 27 格要不要给方块加视觉编码（边框粗细/底色/角标），还是仅在卡片显示数值？
4. 能力 聚/散/动 是否需要一个"非方块"的表现位（如方块内辐条/桥的颜色），还是明确"能力层不在外观层表达"？
5. T76 的 13 个桥功用标签要不要替换/补充 T75 的 X/W/A 三分？两者目前互不相识。

### 6.5 核实范围与未核实项（诚实边界）

**已核实（本次跑过/读到行）**：
- `alchemy.attrs` 的 27 格实现与 `skeleton_units` 输出结构（实测 `attrs_of("OXC")`、`skeleton_units` 5 单元案例）；
- `t75_tiles`/`t75_render`/`t75b_attrs`/`t75b_render` 全部关键函数与常量行号；
- `t68_data.json` 的 36 分子 / 1147 原子 / 114 骨架 / 114 桥 / 1 融合与 `meta.sources`；
- G13 逐骨架属性、`grid_embed` 结果、逐骨架 H/V/T 区间、V=0/T=0 计数；
- 渲染耗时与图件尺寸（用 PIL 读 `images/*.png`）；
- `examples/render_species_sheets.py` 读 `_union.json`（121 种，非 APPEARANCE 所称 156）；
- git 历史顺序（`8877e8d` → `4a2e4d6` → `facb162`）。

**未核实 / 未跑**：
- T68~T73 各脚本的整页重跑（只读代码与已有图，未重新执行 `t68_atlas.py`、`t69_render.py`、`t70_render.py`、`t71_render.py`、`t72_render.py`、`t73_render.py`、`t76_render.py`）；
- 内核测试 106 例未重跑（`KERNEL_INTAKE:79-91` 声称 106/106 PASS、21~27s，属转述）；
- `alchemy.ability` 的 v3/v4 只做代码阅读与 `__all__` 核对，未做数值复算；
- `images/biome_candidates` 的 156 vs 121 只查了 `_union.json` 与目录，未查历史版本；
- T74 分类规则（`docs/T74_CLASSIFICATION.md`）未读，只从 `KERNEL_INTAKE` 转述其被 phase+ability+attrs 取代。

---

## 7. 关键数字与文件路径表

### 7.1 关键数字

| 数字 | 含义 | 来源 |
|---|---|---|
| 9 | 元素数（3 三价 O/P/K + 3 二价 X/W/A + 3 一价 C/L/F） | `t68_shapes.py:34-36` |
| 7 | 骨架家族（O/P/K/OP/OK/PK/OPK） | `t68_shapes.py:44-52`；`T68:49-62` |
| 38 | level-6 骨架形态库 | `t8_forms.json`（103,930 B）；`T68:69-90` |
| 36 | 稳定大分子（T61 13 / T64 12 / T62 8 / T63 3） | `t68_data.json meta`；`T69:62` |
| 1147 / 114 / 114 / 1 | 原子 / 骨架 / 桥 / 融合分子数 | `t68_data.json meta` `[实测]`；`T68:131-134` |
| 115 | 6 级块数（114 骨架中 G13 ② 由 2 块融合） | `T69:24`；`[实测]` G13 骨架② `blocks` 长度 2 |
| 56 / 114 | 混合元素桥占比（S9/C45/L4/mixed56；按键端 S63/C121/L44） | `T68:131-134` |
| 27 | 物性格子数（3 属性 × 3 档） | `alchemy/attrs.py:64`；`docs/TRAITS.md:58-85` |
| (10,16)/(6,11)/(3,6) | 密度/粘性/温度阈值 | `alchemy/attrs.py:67-71` |
| 3/2/1 | 内核属性权重（O3/K2/P1；X3/W2/A1；F3/L2/C1） | `alchemy/attrs.py:45-52` |
| 1.20/0.90/0.60；1.00/1.40/0.40；−2.00/+0.50/+3.00 | T75 外观权重 | `t75_attrs.py:11-13`；`t75b_attrs.py:12-14` |
| 512 / 3 / 9 / 3 | 冻结能力数 / 主方向数 / 次级能力数 / 阶数 | `alchemy/ability.py:48-58,240-266`；`docs/ABILITY.md` |
| 13 | T76 桥功用标签数 | `t76_bridge_fn.py:8`；`T76:6-26` |
| 18 / 36 | T75 分子卡 / 总览格数 | `t75_render.py:93-94,156-158` |
| 65/114、103/114 | 粘性=0、温度=0 的骨架数 | `[实测]` |
| H 0.9~12.3 / V 0~10.8 / T −3.5~+6.0 | 逐骨架实测区间 | `[实测]`；`t75b_attrs.py:91-98` |
| H21.0 V12.2 T4.5 | G13 分子级属性 | `[实测]` |
| 1600×1010 / 1600×4420 / 1612×1758 / 1600×4880 | t75/t75b 图件尺寸 | `[实测]` PIL |
| 0.06s / 0.3s | 单分子绘制 / 18 卡整页 | `[实测]` |

### 7.2 路径表（路径:行）

**文档**
- `docs/APPEARANCE.md:3-4` 定稿与状态；`:8-14` 决定（T75 唯一主规范、前身定义）；`:16-26` 文档清单；`:28-51` 主规范 3.1/3.2；`:53-57` 内核接口；`:59-62` 尚未实现；`:64-71` 前身表；`:73-76` 化学结构图排除；`:78-84` 三层现状。
- `docs/T75_BLOCK_WORLD.md:3-7` 用户规则；`:9-18` 方块内部表；`:20-31` 连接表与 polyomino；`:33-42` 三属性表与权重；`:44-57` 文件与复现；`:59-65` 局限；`:67-88` T75b 逐骨架属性。
- `docs/T68_GLYPH_SYSTEM.md:11-25` 三层结构；`:26-49` 元素字形；`:49-68` 家族容器；`:69-90` 38 库；`:92-108` 键型；`:109-149` 融合/桥/装饰；`:150-176` 卡片与复现；`:178-188` 局限。
- `docs/T69_SKELETON_SHAPES.md:10-24` 家族外形表；`:26-29` 融合；`:31-41` 连接件与分段规则；`:43-54` 端帽与装饰；`:56-62` 排版与数据复核。
- `docs/T70_EMERGENT_GLYPHS.md:7-31` 超公式；`:32-38` 桥梁分段；`:39-45` 端帽；`:52-66` 图集与复现；`:69-73` 局限。
- `docs/T70B_WHOLE_BODY.md:5-19` 并集蒙版做法；`:20-26` 图件；`:27-35` 复现；`:36-40` 局限。
- `docs/T71_ABILITIES.md:6-31` 能力模型；`:32-54` 生命度；`:55-61` 固液气/刚松粘；`:62-66` 物种命名；`:92-97` 局限。
- `docs/T72_ABILITIES_MORPHS.md:9-28` 72 能力；`:29-44` 28 形态；`:45-58` 图件；`:59-69` 小分子；`:76-81` 局限。
- `docs/T73_MORPH_GEOMETRY.md:6-30` 几何判定；`:31-44` 形态画在身体上；`:45-59` 小分子物质化；`:61-77` 文件与复现；`:85-101` T73b 修正。
- `docs/T76_BRIDGE_FUNCTIONS.md:6-26` 判定规则；`:27-41` 分布；`:42-48` 例子；`:49-56` 图件；`:57-61` 局限。
- `docs/ABILITY.md:14-86` v3/v4 现行；`:90-125` 规则与 512 历史；`:126-158` 分布；`:191-200` 三层职责；`:201-207` 待确认。
- `docs/TRAITS.md:7-31` 硬度→密度；`:32-43` 三轴三属性；`:44-57` 两套坐标；`:58-85` 阈值与 27 格；`:87-100` 实例；`:102-118` 用法。
- `docs/KERNEL_INTAKE.md:35-55` 模块地图；`:58-77` 四入口；`:79-91` 测试；`:141-150` 能力与外观；`:152-163` 性状；`:175-186` 旧阶段承接；`:197-224` 风险与待办。
- `docs/REPO_SLIM.md:9-24` 仓库体积；`docs/SYNC.md:183-189` 自动推送钩子。

**代码**
- `alchemy/attrs.py:45-52` DENS_W/STICK_W/TEMP_W；`:64` N_CELLS；`:67-71` THRESHOLDS；`:109-147` molecule_attrs/attrs_of；`:151-219` skeleton_units；`:233-269` cell_of/property_of/grid。
- `alchemy/ability.py:48-58` 512；`:162-190` CATEGORY_AXES/score；`:240-324` 九项次级/三阶/profile/abilities_of。
- `alchemy/__init__.py:41-71` 导入 core/biome/phase；`:75-90` `__all__` 不含 attrs/ability。
- `t68_shapes.py:24-26` 硬编码 BASE/字体；`:28-52` ORDER/元素色/7 家族；`:216-233` glyph_radius/atom_poly；`:402-520` Canvas/fit_layout/draw_molecule。
- `t68_atlas.py:21-46` load_forms/form_place/draw_form；`:100-317` 四页图册。
- `t68_cards.py:14-21` DATA/CARDS_PER_PAGE/N_PAGE；`:92-240` render_card 与分页。
- `t68_build_data.py:28-34` TRI/DIV/MONO/LAYOUTS；`:39-81` triv_components/bond_type/analyze；`:273-310` main 写 t68_pool.json。
- `t68_select.py:30-83` SELECT/主流程；`:187-190` 写 t68_data.json。
- `t69_bodies.py:18-68` blocks_of/body_radius/Body/Skeleton；`:104-180` 布局与桥间隙。
- `t69_pieces.py:507-509` load_data 读 t68_data.json；`:513-546` BOSS_H/boss_geom/boss_poly。
- `t69_draw.py:244-440` 连接件/装饰/整分子绘制。
- `t69_render.py:17` PER_PAGE=2；`:57-112` 卡片/总览/图例。
- `t70_glyphs.py:58-152` block_params/skeleton_rf/draw_skeleton；`:368-383` library_blocks 读 t8_forms.json。
- `t70_render.py:19-262` 五页图。
- `t70b_body.py:131-420` draw_body_molecule/page_bodies/page_all。
- `t71_render.py:16-333` 能力/骨架/物种/画廊页；`:352,439,484` 重复定义。
- `t72_render.py:45-120` organ_traits/molecule_traits/能力页；`:149-153` 读 t8_forms.json。
- `t73_organs.py:56-120` features/assign/analyze；`t73_body.py:42-235` draw_organ_body；`t73_small.py:128-254` draw_substance/page_small。
- `t75_attrs.py:11-44` 权重/attrs/norm_ranges；`t75b_attrs.py:12-98` 逐骨架；`t75_tiles.py:34-105` skeleton_graph/grid_embed；`:109-143` fam_motif；`:147-164` 色条；`:166-184` draw_tile；`:188-264` 桥/焊/钉；`:268-380` draw_molecule。
- `t75_render.py:28-84` 规则页；`:88-153` 分子卡；`:156-178` 总览；`t75b_render.py:20-175` 同上逐骨架版。
- `t76_bridge_fn.py:8-118` FUNCS/classify/stats/fanout；`t76_render.py:40-124` 单页。
- `examples/render_species_sheets.py:1-20` 用途（化学结构图，非外观层）；`:37` 读 `_union.json`。
- `tests/run_all.py`、`tests/test_attrs.py`、`tests/test_ability.py`（内核测试，106 例）。

**数据与图件**
- `t8_forms.json`（103,930 B）、`t61~t64_hex_layouts.json`、`t68_pool.json`（745,503 B）、`t68_data.json`（267,580 B）、`alchemy/data/forms38.json`（103,930 B，同 sha256）。
- `images/t68_library38.png`、`t68_glyphs.png`、`t68_families.png`、`t68_connect.png`、`t68_card_*.png`；
  `images/t69_overview.png`、`t69_legend.png`、`t69_giants_01..18.png`；
  `images/t70_skeletons38.png`、`t70_bridges.png`、`t70_terminals.png`、`t70_molecules.png`；
  `images/t70b_bodies.png`、`t70b_all36.png`；
  `images/t71_abilities.png`、`t71_skeletons38.png`、`t71_organisms.png`、`t71_gallery.png`；
  `images/t72_abilities.png`、`t72_morphs.png`、`t72_blocks38.png`、`t72_species.png`、`t72_small.png`；
  `images/t73_inorganic.png`、`t73_organic.png`、`t73_organs.png`、`t73_rules.png`、`t73_small.png`；
  `images/t75_rules.png`、`t75_molecules.png`、`t75_overview.png`；
  `images/t75b_rules.png`、`t75b_molecules.png`、`t75b_overview.png`；
  `images/t76_bridge_functions.png`；
  `images/biome_candidates/species_01..04.png`、`species_index.png`、`species_legend.png`。
- 本次验证产物（未入库）：`intake/tmp/appearance/check_G13_bars.png`、`check_tile_overlap.png`、`t75b_rules.png`、`t75b_molecules.png`、`t75b_overview.png`、`probe.py`。

---

## 附：给后续工作的最小行动清单（建议）

1. 写 `appearance_adapter.py`（或内核 `alchemy/appearance.py`）：`skeleton_units` + 38 库 → 还原 `{skeletons, bridges, decoration, blocks}`；先解决 G1/G5/G6。
2. 定义"27 格 → 方块视觉"映射表（建议：边框粗细/内侧色带/角标三选一），先在 `t75b` 上试一版。
3. 明确能力层是否进入外观；若进，定义 聚/散/动 三条辐条的图形位（与 `TRAITS.md:44-57` 的"径向给物性、角向给能力"一致）。
4. 统一属性权重口径（外观 1.2/0.9/0.6 vs 内核 3/2/1），或写换算与适用域。
5. 修正 D1/D5 两处视觉缺陷，并在 `APPEARANCE.md` 补 T75b/T76/T71-73 与"已实现/未实现"的准确边界。
