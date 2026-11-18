# ALCHEMY 文件索引（2026-11-18 更新）

> **新对话/新接手：先读 HANDOFF.md、README.md、TRANSFER.md、NEW_CHAT_PROMPT.md。**
> 本文件是历史/主题索引；最新结论与交接以 HANDOFF.md 为准。

---

# alchemy 工作区索引（自动整理于 2026-11-13 10:58）

## 目录结构
- `docs/`：全部研究报告（T4~T70b、HANDOFF、PROJECT_HANDOFF 等）；`docs/templates/` 报告模板
- `images/`：全部图片（结构图、反应矩阵、循环图、统计图、T68~T70b 大分子图册等）
- `archive/old_scripts/`：历史探索脚本，已按阶段分子文件夹（`t3/` `t4p/` `late/` `early/`）
- `archive/old_data/`：历史数据，已按主题分子文件夹（`t3/` `scope/` `catalog/` `finite/` `minimal/` `misc/`）
- `tools/`：跨电脑传输工具（`make_transfer_archive.py`、`pack_transfer_data.py`）
- 根目录：核心模拟器 + 权威数据 + 各阶段脚本/数据 + `unpack_data.py` + 本索引

## 核心代码（根目录 + 内核包）

- **`alchemy/`（内核包，纯标准库，2026-11-18 入库）**：规则 1~11 大锅反应 / 摆放 / 目录 / 分类的正式实现，四入口
  `simulate` / `embed`+`validate` / `get_catalog` / `classify`；`core/` 为 elements/canon/geometry/reactor/catalog/classify，
  上层为 `phase`（三轴判相）/`ability`（512 能力）/`attrs`（三数值性状）/`biome`（群系物种表）；`rules=8|9|11` 单份参数化；
  见 `alchemy/README.md`、`docs/KERNEL_INTAKE.md`；测试 `tests/run_all.py`（106 项）
- `pot_all.py`：规则 1~8 通用模拟器（历史，已由 `alchemy` 覆盖）
- `pot_v2.py`：严格摆放校验（embed_mol2 / validate_place；历史，对应内核 `alchemy.embed/validate`）
- `pot_v3.py`：历史口径（规则 1~9；正式口径已改为规则 1~11）
- `pot_v4.py`：规则 1~11 根目录实现（历史/兼容；正式实现在 `alchemy/core/reactor.py`）
- `t4_*`~`t13_*`：各阶段扫描/分析脚本（文件名前缀=任务编号）

## 权威数据（根目录 + 内核）

- `alchemy/data/forms38.json`：38 三价骨架库（内核版，与根 `t8_forms.json` 字节级相同，103,930B）
- `alchemy/data/biome_names.json`：物种中文名映射（754B）
- `data/biomes/`：群系模板物种表 `t55_kinetic`/`t56_kinetic`/`t57_area`/`t58`/`t59_phaseA|B`/`t62_phaseA|B`/`t63_phase1~4`
  各含 `.csv`(17 列)+`.json`，`_catalogue.json`（12 条模板 × 20 字段描述性目录），`candidates/`（T55·T57·T63S4·T62B·T59B 各 `.csv` +
  `_union.csv`/`_union.json` 121 种 × 34 字段）；根 `t67_catalog.json` 仍是 32 群系总目录（A10/B11/C7/D4）
- `t4_catalog_all_validated.json`：84,225 条物质目录（**100% 规则 1~11 口径**）；`t4_catalog_index.json` 索引
- `substances.json`（29 聚素）、`t9_single_trivalent.json`（单三价）、`t8_forms.json`（38 三价骨架）
- `t10_skeletons.json`（7 骨架模块）、`t11_*.json`（二元反应/循环）、
  `t12a_chains.json`（反应链）、`t12b_*.json` + `t12b_pairs.jsonl`（7.73M 对）、
  `t12c_*.json`（全目录采样、140/108 原子纪录）、`t12b_catalog_gap.json`（212 补充产物）

## 主要报告（docs/）

- **2026-11-18 内核入库新文档**：`THREE_AXES_FINAL.md`（三轴判相 v4 定稿）、`PHASE_RULE.md`（物相规则 v1/v2）、
  `CALIBER_DIVERGENCE.md`（规则 1~8/1~9/1~11 口径分歧审计）、`ABILITY.md`（512 能力）、`APPEARANCE.md`（外观，仅记录）、
  `TRAITS.md`（硬度/黏性/温度三数值）、`BIOME_SPEC.md`（群系物种规格）、`BIOME_CANDIDATES.md`（候选群系清单）、
  `SYNC.md`（同步约定）、`KERNEL_INTAKE.md`（本次整理分析总报告）
- `T12_FINAL_REPORT.md`：二元反应总报告（最新）
- `T12A_CHAINS.md` / `T12B_PAIRWISE.md` / `T12C_LARGE_SAMPLE.md`：三条主线
- `T11_BINARY_REACTIONS.md` / `T11B_REACTION_CYCLES.md`：二元反应与循环
- `T10_SKELETONS.md`、`T9_SINGLE_TRIVALENT.md`、`T9_NONE_ALL.md`、`T8_TRIVALENT_FORMS.md`：结构研究
- `PROJECT_HANDOFF.md`、`HANDOFF.md`：规则与交接
- `T13_BIG_SEARCH.md`：更大分子搜索（进行中/待生成）

## 整理记录
- 删除：64 个（_patch/_scratch/日志/重复大文件等）
- 移入 docs：17 个；images：16 个
- 移入 archive/old_scripts：42 个；archive/old_data：10 个
- 保留根目录：174 个
- **2026-11-18 二次整理（T68~T70b 完成后，详见 `docs/CLEANUP_LOG.md`）**：删除根目录 26 个 `*.log`、
  `__pycache__/`、`images/` 中 12 张临时调试图、工作区根目录约 181MB 的 2026-11-14 旧 ZIP/bundle/sha/推送日志；
  `archive/old_scripts`、`archive/old_data` 按阶段/主题分子文件夹（见 `archive/README.md`）；
  传输工具移入 `tools/`；`t60_report_template.md` 移入 `docs/templates/` 并修正 `t60_fill_report.py` 的模板路径。

## 最新补充
- **内核入库（2026-11-18，最新）**：`alchemy/` 内核包（11 模块 + data，纯标准库）；`tests/`（106 项全绿）；
  `examples/`（`demo_kernel.py` 四入口演示、`build_biome_candidates.py` 复算候选群系、`render_species_sheets.py` 46 种物种图）；
  `data/biomes/`（12 组模板物种表 + 5 个候选 + `_union` 121 种）；`images/biome_candidates/`（索引图/图例/4 页物种图）；
  9 份规则文档；整理分析 `docs/KERNEL_INTAKE.md`；推送记录见 `TRANSFER.md` §6（kernel 提交 `4a2e4d6`）
- images/t13_140_atom_reaction.png：140 原子最大分子纪录的产生反应图（含两个反应物与产物结构）
- docs/T13_BIG_SEARCH.md：更大分子搜索与尺寸上界验证（已完成）
- 	13_new_record.json：最新已验证纪录 155 原子结构；	13_big_search.json：1544 个候选全量
- images/t13_scatter.png：投料规模 vs 最大产物尺寸散点图
- images/t19_level6_library38.png：6 级中间态骨架完整字典（38 种）
- docs/T20_DIVALENT_FORMS.md + images/t20_divalent_forms.png、images/t20_bridge_types.png：二价元素 9 种存在形式与三种桥的机械性质
- docs/T21_NATURAL_RULE.md：自然环境「端帽交换」反应（仅 1 价端帽版）
- docs/T22_NATURAL_CAPS_V2.md：修正版——端帽含 2 价双键端帽（7,359 个新分子式、端帽↔桥转换）
- docs/T23_NATURAL_STABILITY_RULES.md：自然环境稳定化反应规则（白名单版，已修正）
- docs/T24_ENERGY_RULE.md：键能规则——每根键释放 2 单位 ⇒ 只有 S→L 端帽迁移（反应率约 1.6%）
- docs/T25_ENERGY_ONLY.md：去掉端帽/单对限制后 ⇒ 退化为 S→L 单向弛豫（51.3% 分子会变松、骨架破坏）
- docs/T26_GROUND_STATE_RULE.md：e=1 + 分子内键型弛豫 ⇒ 每根键到唯一基态、无新物质（94.7% 分子会弛豫）
- docs/T27_BREAK_RULE.md：自然环境分解规则 v1（按元素距离/键级断裂）
- docs/T28_RULE_V2.md：分解规则 v2（全局选类、每元素对断一根、价数分级、几何、能量规则）
- images/t28_bond_hierarchy.png、images/t28_decomposition_process.png、images/t28_energy_rule.png：规则分级、分解流程、能量模型图
- 	19_big_forms.json（超大分子 6 级块）、	19_extended_forms.json（扩展枚举）
- 复核脚本：	12_verify_big.py（140/108 原子严格摆放复核）、	12_theory.py（幂等性）
- **T39（2026-11-15）骨架库复核**：`t39_library_verify.py`、`t39_render.py`、`docs/T39_SKELETON_LIBRARY_VERIFY.md`、`t39_library_verify.json`、`t39_t15_rescan.json`、`images/t39_library_outside.png`
  - 发现 `wl_key` 不是同构不变量（T38 的库外例子全为假阳性；T15 的 695→671）；
  - 真·库外 6 级块仅 `O3P5K2` 一族（三价 ≤10 穷举）；671 个终态形态 = 库内块融合（670/670 宿主结构定理通过，不算库外）。
- **T55（2026-11-16）2D 粒子环境实验**：`natural_engine.py`（T35 判定 + pot_v4 规则 1~11 完全反应 +
  t28 不完全反应 + 自分解）；`t55_kinetic_env.py`（10000×10000 反射边界、9000 个聚素单质、
  初速 38197/分钟、每次碰撞 -0.2%、1000→0°C）、`t55_control_no_chem.json`（500 次穿越验证：
  9000/9000 达标，min 696.7）、`t55_sensitivity.py`（T0=6/8/12/20°C 敏感性）、`t55_analysis.py`/`t55_render.py`、
  `docs/T55_KINETIC_ENV.md`、`docs/T55_ENGINE_AUDIT.md`、`images/t55_*.png`（8 张）；
  结论：主实验快速退火到 99.5% `OXC`；温度标度敏感性下出现不完全反应/自分解/新物质。
- **T61（2026-11-17）T59 最后两次实验全部大分子六边形棋盘格**：`docs/T61_HEX_LARGE.md`、
  `t61_hex_layouts.py`、`t61_refix.py`、`t61_render.py`、`t61_hex_layouts.json`、
  `t61_hex_manifest.json`、`images/t61_hex_*.png`（13 张）；T59A/B 全部 ≥5 原子大分子
  66 种（9 中等 + 57 巨型），66/66 严格六边形摆放并 validate 通过；中等 1 页 + 巨型 10 页
  + 索引 + 图例。
- **T60（2026-11-17）全系列总汇报**：`docs/T60_SERIES_SUMMARY.md`、`t60_top20_data.json`、
  `t60_top20_extract.py`、`t60_fill_report.py`、`t60_render.py`、`t60_figures_manifest.json`；
  T55~T59 各实验对比 + 每轮 top20 图摆盘（`images/t60_top20_*.png` 8 张）+ 67 种重要物质图鉴
  （`t60_important_1/2.png`）+ 全系列总览（`t60_series_overview.png`）+ top20 数量条形；
  跨系列结论：温度尺度、F+元素配比决定终态、面积是动力学旋钮、区域/cap 决定退火干净度、
  cap60 后真实稳定核心 9~13 种。
- **T59（2026-11-17）九元素两阶段实验 + fast_pot 加速**：`fast_pot.py`（增量并查集+分层筛选，
  与 pot_v4 等价，F 3.6~6.3×，审计 27,315 向量 0 差异）、`natural_engine.set_fast`、
  `t59_mixture.py`、`t59_two_phase.py`、`t59_analysis.py`、`t59_render.py`、
  `t59_loads.json`、`t59_phaseA_result.json`、`t59_stateA.json`、`t59_phaseB_result.json`、
  `t59_stateB.json`、`t59_control_A.json`、`t59_analysis.json`、`docs/T59_TWO_PHASE.md`、
  `docs/T59_FAST_ENGINE_AUDIT.md`、`images/t59_*.png`（11 张，含 top30 结构图）；
  L 400000→60000（面积 1/44.4×）；A 120 种/三价最多 → 27,431 分子/43 种结构；
  整理后加 batchB、重置 1000°C → 38,609 分子/230,133 原子/67 种结构；两阶段守恒；
  top30 = 11 常规 + 19 巨型（39/40 原子）；两阶段运行 207+324 秒。
  补充 cap=60 高保真对照：A 9 种结构/最大 18、B 13 种/最大 60（3 个 59/60 巨型）、
  capped 仅 0.01~0.03%——cap40 的 43/67 种与 19 个 top30 巨型主要是人工边界。
- **T58（2026-11-16）九元素随机物质库大投料实验**：`t58_nine_elements.py`、`t58_analysis.py`、
  `t58_render.py`、`t58_mixture.json`、`t58_result.json`、`t58_control_no_chem.json`、
  `docs/T58_NINE_ELEMENTS.md`、`images/t58_*.png`（11 张）；从 84,225 目录随机抽 44 种物质
  （2~12 原子、九元素全覆盖）、14000 分子/73216 原子（史上最大）、L=400000²；
  终态 15,823 分子、**937 种分子式、99 种元素组合、1,927 种目录外新物质**；
  尺寸双峰（2 原子 11,252 + 6~20 原子 4,571）；capped（>20 原子保护）占 21.8%（末段 25.8%）；
  穿越 14000/14000 全部 ≥500（min 730.3）。
- **T57（2026-11-16）全部29种聚素 + 面积模型实验**：`t57_all29_area.py`、`t57_sensitivity.py`、
  `t57_analysis.py`、`t57_render.py`、`t57_area_result.json`、`t57_area_control.json`、
  `t57_uniform_result.json`、`t57_design.json`、`t57_sensitivity.json`、
  `docs/T57_ALL29_AREA.md`、`images/t57_*.png`（11 张）；面积∝原子数、数量∝1/面积、
  面积加权碰撞截面；主实验与固定半径对照都收敛到 OXC 80.9%+OX2C 19.0%（平均 3.197 vs 3.200、
  终态最大 8、≥5 原子 17 vs 29）——面积是动力学旋钮，不改变 F+配比决定的热力学终态；
  低温窗口 T0=12°C 才保留大分子（平均 4.09、26.3% ≥5 原子、18 种分子式、7 新物质）。
- **T56（2026-11-16）价数比例 + 散素六元素实验**：`t56_ratio_6elem.py`、`t56_sensitivity.py`、
  `t56_analysis.py`、`t56_render.py`、`t56_kinetic_result.json`、`t56_control_no_chem.json`、
  `t56_sensitivity.json`、`docs/T56_RATIO_6ELEM.md`、`images/t56_*.png`（10 张）；价数比
  3价<2价<1价（原子 3200:5600:9600=1:1.75:3）+ 散素 K/A/F，退火到同价跨类双原子盐
  CF/XA/OK（99.6%），演化峰值 36 原子/终态 22 原子，120 种目录外新分子式（117 种 >16 原子）。
- **T45（2026-11-16）规则 10/11 纳入**：`pot_v4.py`（规则 1~11）、`t50_scan_block_ambiguity.py`、`docs/T45_RULES_10_11.md`
  - ≤11 三价全组合全分支：6 级骨架歧义 0、库外块 0；O3P5K2 库外变体被规则 11 排除；
  - 目录结构影响：14,615/84,225（17.4%）结构与 pot_v3 不同（分子式不变），数据迁移待做。

- **T68（2026-11-17）大分子骨架形状语言 + 36 个稳定大分子图册**：`t68_shapes.py`（元素字形/家族容器/键型语法/
  桥与融合语法绘制库）、`t68_build_data.py`、`t68_select.py`、`t68_cards.py`、`t68_atlas.py`、`t68_stats.py`、
  `t68_stats2.py`；数据 `t68_pool.json`、`t68_data.json`；报告 `docs/T68_GLYPH_SYSTEM.md`（形状语言）、
  `docs/T68_GIANT_ATLAS.md`（36 分子图册）；图 `images/t68_giants_01~18.png`（2 卡/页共 18 页）、
  `t68_overview.png`（6×6 总览）、`t68_glyphs.png`、`t68_families.png`、`t68_library38.png`、`t68_connect.png`。
  36 个 ≥14 原子稳定大分子 = 1147 原子 / 114 骨架 / 115 个 6 级块 / 114 桥（S 9·C 45·L 4·混合 56）；
  38 库外块 0、pot_v4 稳定复核 36/36；0 级融合键仅 G13 1 根 P–P。
- **T69（2026-11-17）大分子骨架形状语言·连接件与端帽（元素隐去版）**：`t69_bodies.py`（块/骨架/星形布局）、
  `t69_pieces.py`（X 楔块 / W 肌腱 / A 薄膜 / C·F·L 端帽 / 支臂 / 铆钉）、`t69_draw.py`（容器、焊带、连接件、
  装饰、面板）、`t69_render.py`（36 卡 18 页 + 总览 + 图例）；报告 `docs/T69_SKELETON_SHAPES.md`；
  图 `images/t69_giants_01~18.png`、`images/t69_overview.png`、`images/t69_legend.png`。
  要点：骨架 = 7 家族容器（去掉元素字形）、融合 = 边对边 + 焊带（仅 G13 1 例）、二价桥按 X/W/A 形状化、
  多元素桥按元素顺序分段拼接、同骨架对多条桥合并标 xN、端帽 C 尖三角 / F 软四边形 / L 细椭圆。

- **T70（2026-11-18）生成式形状语言（骨架 / 桥梁 / 端帽）**：`t70_glyphs.py`（超公式晶核 + 焊核 / 编织腱 / 褶皱膜 /
  冰刺 / 飘带 / 螺旋丝生成器）、`t70_render.py`（4 张图）；报告 `docs/T70_EMERGENT_GLYPHS.md`；
  图 `images/t70_skeletons38.png`（38 个骨架块）、`t70_bridges.png`、`t70_terminals.png`、`t70_molecules.png`。
  思路：同一函数族按"元素计数 → 对称瓣数/圆润度/锐度、度数谱 → 相位/晶脉、哈希 → 个体指纹"生成外形，
  同类骨架风格一致、个体互不相同；T68/T69 的手工固定多边形方案作废（T69 图件保留为历史版本）。

- **T70b（2026-11-18）大分子整体图**：`t70b_body.py`（把所有骨架块/桥/端帽并进同一蒙版 → 闭运算得到单一外轮廓 →
  渐变填充 + 一条外轮廓 + 内膜 + 体内器官核/骨纹/脉络），报告 `docs/T70B_WHOLE_BODY.md`，
  图 `images/t70b_bodies.png`（4 例）、`images/t70b_all36.png`（36 个）。解决"大分子看起来像零散零件拼凑"的问题。

- **T71（2026-11-18）骨架能力与涌现生命**：`t71_abilities.py`（30 项能力 / 材料层元素能力 / 6 种分化形态 /
  固液气判定 / 结构门控生命度 / 物种命名）、`t71_render.py`（4 张图）；报告 `docs/T71_ABILITIES.md`；
  图 `images/t71_abilities.png`、`t71_skeletons38.png`、`t71_organisms.png`、`t71_gallery.png`。
  结果：36 个稳定大分子 → 有机生命 14 / 拟生命 12 / 活性无机物 7 / 无机晶体 3。
  刚性/松散/粘性暂用 S/C/L 键占比推断，等同事正式分类规则上传后替换 `t71_abilities.softness()`。

- **T72（2026-11-18）能力系统 72 项 + 骨架分化形态 28 种**：`t72_abilities.py`（72 能力/9 大类、按元素占比算强度、
  家族签名加成）、`t72_morphs.py`（7 家族 × 4 形态 = 28、每块按组成+编号长 3 种）、`t72_render.py`（5 张图）；
  报告 `docs/T72_ABILITIES_MORPHS.md`；图 `images/t72_abilities.png`、`t72_morphs.png`、`t72_blocks38.png`、
  `t72_species.png`、`t72_small.png`。

- **T73（2026-11-18）器官形态的几何判定 + 小分子物质化**：`t73_organs.py`（凸包/离心距离/载荷/触肢数 →
  承力型/感受抓握型/表面型/内脏型/过渡型，每家族一套对应形态）、`t70b_body.draw_body_molecule(auto_organs=True)`
  （器官形态真的长在身体表面，带颈、统一配色）、`t73_small.py`（元素字形+键带+端帽并成一个身体，再按 S/C/L/X
  加表面纹理）、`t73_render.py`（规则页 + 6 张分化形体卡）；报告 `docs/T73_MORPH_GEOMETRY.md`；
  图 `images/t73_rules.png`、`t73_organs.png`、`t73_small.png`。

- **T73b（2026-11-18）修正**：强化"分化形态就是器官整个外形"——新增 `t73_body.py`（用 28 形态的整张剪影
  替代骨架块，桥接器官打包压叠 0.56/融合 0.42 连成一身体，端帽/支臂并入蒙版，只留一条外轮廓）。
  `t73_render.page_organs` 已切换；图 `images/t73_organs.png` 更新。

- **T74（2026-11-18）分类规则订正**：`t74_rules.py`——固/液/气按 X>W>A 数量；刚/粘/松按 O>P>K 数量；
  高温/低温/导电按一价 C>L>F 数量；有机/无机按能力与结构（T71 结构门控生命度 ≥5 有机、3~5 活性无机、<3 无机晶体），
  不再用"有没有端帽"判断。报告 `docs/T74_CLASSIFICATION.md`，无机大分子图 `images/t73_inorganic.png` 已按新规则重算
  （18 个大分子无机：活性 13 + 晶体 5）。

- **T75（2026-11-18）方块世界改造**：`t75_attrs.py`（硬度=三价 O1.2/P0.9/K0.6、粘性=二价 X1.0/W1.4/A0.4、
  温度=一价 C−2.0/L0.5/F3.0，均为数值属性）、`t75_tiles.py`（每个骨架 = 1 个单位方块；BFS 四邻接嵌成多格骨牌；
  方块内部家族纹样；共用边上画 X 焊块 / W 肌腱 / A 薄膜 / 融合焊纹；外缘小方钉=一价端帽）、
  `t75_render.py`（规则页 + 18 张方块分子卡 + 36 个总览）；报告 `docs/T75_BLOCK_WORLD.md`；
  图 `images/t75_rules.png`、`t75_molecules.png`、`t75_overview.png`。

- **T75b（2026-11-18）逐骨架属性**：`t75b_attrs.py` 的 `skeleton_attrs(mol)` 为每个骨架单独算 硬度（三价）/
  粘性（挂在它身上的二价）/ 温度（挂在它身上的一价），**连接两个骨架的二价桥不计入任何属性**；
  方块右下角三色小条与卡片右侧逐骨架表展示。图 `images/t75b_rules.png`、`t75b_molecules.png`、`t75b_overview.png`。


- **T71~T76（2026-11-18）能力/形态/方块世界/桥功用**：
  `t71_abilities.py` + `t71_render.py`（30 项能力、6 分化形态、结构门控生命度，36 分子 14/12/7/3）、
  `t72_abilities.py` + `t72_morphs.py` + `t72_render.py`（72 项能力 × 9 类、28 种分化形态、小分子 12 例）、
  `t73_organs.py` + `t73_body.py` + `t73_small.py` + `t73_render.py`（器官按位置/朝向选形态，形态直接代替器官外形；
  小分子物质形态）、`t74_rules.py`（固液气/刚粘松/热电/有机无机判定）、
  `t75_attrs.py` + `t75_tiles.py` + `t75_render.py`（方块世界：每个骨架 = 1 单位方块）、
  `t75b_attrs.py` + `t75b_render.py`（属性按每个骨架算，桥不计入）、
  `t76_bridge_fn.py` + `t76_render.py`（桥的 13 种功用标签，114 条桥分布）。
  报告：`docs/T71_ABILITIES.md`、`T72_ABILITIES_MORPHS.md`、`T73_MORPH_GEOMETRY.md`、`T74_CLASSIFICATION.md`、
  `T75_BLOCK_WORLD.md`、`T76_BRIDGE_FUNCTIONS.md`；图：`images/t71_*` ~ `images/t76_*`。
