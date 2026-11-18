# data/biomes 数据谱系与候选群系统计复核（task-3）

- 仓库：`G:\AI work\deepseek\work1\alchemy`，远端最新提交 **4a2e4d6**（工作区干净，只读操作，未改动仓库内任何文件）
- 环境：Windows，Python 3.11.3（无 PIL）
- 临时脚本与原始输出（可复跑）：`G:\AI work\deepseek\work1\intake\tmp\`
  - `inspect_biomes.py` / `recompute_stats.py` / `lineage.py` / `repro.py`
  - 输出：`out_stats.txt`、`out_lineage.txt`、`out_repro.txt`、`out_cat.txt`
- 约定：所有 Python 脚本显式 `encoding="utf-8"`，输出写入 UTF-8 文件后再读取（PowerShell 控制台 GBK，中文直接打印会乱码，仅为显示问题）。

---

## 0. 结论速览

| # | 结论 | 状态 |
|---|---|---|
| 1 | `data/biomes/_catalogue.json` 是**12 条实验模板的描述性目录**（20 字段），**不是** 32 群系目录；32 群系（A10/B11/C7/D4）的载体是 `t67_catalog.json` + `docs/T67_BIOME_CATALOG.md` | ⚠ 命名易误判 |
| 2 | `_catalogue.json` 可由 `alchemy.biome.template_catalogue` 从 12 个根 `*_result.json` **完全复现**（顺序 + 20 字段，0 差异，14.1 s） | ✔ |
| 3 | 文档 `docs/THREE_AXES_FINAL.md` §8.2 的 46 种目录内物质统计（概念族/物态/能量/10 种物性名）**逐项复现一致**，0 差异 | ✔ |
| 4 | §8.3 的 5 个群系"按质量"物态占比**逐项复现一致**；口径实际是 `atom_abundance`（原子数占比） | ✔（附口径说明） |
| 5 | `candidates/_union.csv` 与 `_union.json` **同源一致**（121 行同序、共有列逐格相等；差异仅为扁平化/格式化） | ✔ |
| 6 | `examples/build_biome_candidates.py` **可在当前数据上跑通**（26.4 s）：5 个 CSV **逐字节相同**，`docs/BIOME_CANDIDATES.md` **逐行相同**；`_union.json` 仅 5 行不同（旧机器绝对路径） | ✔ |
| 7 | `examples/render_species_sheets.py` 依赖 **PIL（未安装）** + Windows 字体 + 写仓库目录 → 本环境**不能实跑**，只做源码审读；既有 4 张 PNG 与代码公式吻合 | ⚠ 依赖缺失 |
| 8 | `data/biomes/t*.csv|json` 是**旧内核快照**：13 个物种的 `shape/label` 是旧值「孤核」，当前内核给出「链」（计数/丰度一致） | ⚠ 数据漂移 |
| 9 | `_union.json` 的 5 个 `spec.source` 是旧机器绝对路径 `D:\Alchemistry DeepSeek工作区\alchemy\...` | ⚠ 可移植性 |
| 10 | `docs/BIOME_SPEC.md:98` 给出的 `_catalogue.json` 复现命令用 `glob('t*_result.json')`，现在会匹配 **50** 个结果文件（应为 12 个） | ⚠ 文档过期 |

---

## 1. 数据谱系

### 1.1 两条互不相干的目录

| 目录 | 文件 | 规模/内容 | 谁生成 |
|---|---|---|---|
| **实验模板目录**（本任务 §1 对象） | `data/biomes/_catalogue.json`（6,073 B） | **12 条**实验模板 × **20 字段**的描述性指标；按 `effective_species` 升序 | `alchemy.biome.template_catalogue()`（`alchemy/biome.py:519-533`） |
| **生态群系总目录**（32 群系） | `t67_catalog.json`（42 KB）+ `docs/T67_BIOME_CATALOG.md` | **32 个**生态群系（T64 12 + T65 10 + T66 10），29 字段，含 `cat` 分类 | `t67_catalog.py` 从 t64/t65/t66 的 `*_analysis.json` 汇总（`docs/T67_BIOME_CATALOG.md:3`） |

> **这是本任务最容易误判的一点**：`data/biomes/_catalogue.json` 里没有 A/B/C/D 分类，也没有 32 条。32 群系的 A10/B11/C7/D4 在 `t67_catalog.json` 的 `category_counts` 与 `biomes[].cat` 中，`docs/T67_BIOME_CATALOG.md` §0 明确写「A 单主型 10 个、B 主辅型 11 个、C 双主型 7 个、D 多主型 4 个」。

### 1.2 32 群系目录实测（脚本 `lineage.py` + 直接读取）

```
$ python -X utf8 -c "...json.load(open('t67_catalog.json'))..."
meta: {"experiment": "T67", "title": "生态群系总目录（T64 12 + T65 10 + T66 10 = 32 群系）",
       "date": "2026-11-17",
       "category_rule": "top1_share>=0.90 A单主；0.50~0.90 B主辅；0.40~0.50 C双主；<0.40 D多主",
       "note": "聚合度=终态原子/分子；专一性=top1分子数/终态分子数；capped 为合并>40原子弹性截断"}
category_counts: {'A': 10, 'B': 11, 'C': 7, 'D': 4}
round_counts:    {'T64': 12, 'T65': 10, 'T66': 10}
len(biomes): 32
cat dist: {'A': 10, 'B': 11, 'D': 4, 'C': 7}
ids: ['B01'...'B12', 'C01'...'C10', 'E01'...'E10']
```

- 结论：**A10/B11/C7/D4 共 32 成立**，但成立对象是 `t67_catalog.json`，不是 `data/biomes/_catalogue.json`。
- 每群系字段（29 个）：`round, id, name, tag, n_elements, elements, trivalent, L, total_atoms, final_N, species, mean_atoms, max_atoms, capped, capped_share, new_substances, effective_species, top1, top1_count, top1_share, groups{poly,dyn,scat,mixed}, hold_activity, trivalent_util, conversion, runtime_s, cat, cluster, capped_heavy, mixed_share`。
- 首条示例：`B01 聚素平原 / 对照组·经典聚素三元素 / elements [O,X,C] / trivalent [O] / L 17000 / total_atoms 12000 / final_N 3980 / species 9 / top1 OXC (3957, top1_share 0.994221) / cat A`。

### 1.3 `_catalogue.json` 字段结构（12 条，字段完全一致）

字段（20）：`name, source, ratio, L, T0, minutes, n_species, n_molecules, n_atoms, max_natoms, mean_natoms, n_ge5, dominance, top1, top2_mass_share, top5_mass_share, shannon_bits, effective_species, singleton_fraction, rare_fraction`。

- `ratio`：九元素投料比例 dict（仅 `t62_phaseA`/`t62_phaseB` 非空，均 ≈ 0.111；其余 `null`，因为 `load_result` 只从实验 JSON 的 `load_summary.element_shares` 取，`alchemy/biome.py:142`）。
- `T0` 一律 1000，`minutes` 一律 1000；`L` 有 10000/30000/60000/400000 四档。
- `dominance` = 第 1 名物种的 `atom_abundance`（`alchemy/biome.py:487,508`），`top2_mass_share`/`top5_mass_share` 同口径。

12 条实测（`intake/tmp/out_cat.txt:1-12`）：

| # | name | 物种 | 分子 | 原子 | maxN | mean | ≥5原子 | dominance | top1 | top2 | 等效物种 | 单例 | L |
|--:|---|--:|--:|--:|--:|--:|--:|--:|---|--:|--:|--:|--:|
| 1 | t55_kinetic | 9 | 5,974 | 18,000 | 8 | 3.01 | 6 | 0.9908 | OXC | 0.9931 | 1.0 | 0.000 | 10000 |
| 2 | t57_area | 4 | 12,054 | 38,532 | 8 | 3.20 | 2 | 0.7588 | OXC | 0.9966 | 1.6 | 0.000 | 10000 |
| 3 | t63_phase1 | 4 | 12,032 | 38,532 | 8 | 3.20 | 2 | 0.7571 | OXC | 0.9926 | 1.7 | 0.000 | 30000 |
| 4 | t56_kinetic | 22 | 9,020 | 18,400 | 22 | 2.04 | 17 | 0.5162 | CF | 0.8103 | 2.8 | 0.455 | 10000 |
| 5 | t62_phaseB | 43 | 51,937 | 230,046 | 40 | 4.43 | 34 | 0.7437 | OXCPWKA | 0.9557 | 2.8 | 0.372 | 60000 |
| 6 | t63_phase2 | 7 | 11,129 | 54,532 | 9 | 4.90 | 4 | 0.5930 | O2X2C2F2 | 0.8805 | 3.1 | 0.000 | 30000 |
| 7 | t62_phaseA | 43 | 34,476 | 150,019 | 40 | 4.35 | 35 | 0.7112 | LF | 0.9147 | 3.4 | 0.349 | 60000 |
| 8 | t63_phase3 | 5 | 20,082 | 70,532 | 5 | 3.51 | 1 | 0.4046 | XCF | 0.6831 | 3.6 | 0.000 | 30000 |
| 9 | t63_phase4 | 14 | 17,227 | 86,532 | 40 | 5.02 | 11 | 0.6185 | F2 | 0.7692 | 4.5 | 0.214 | 30000 |
| 10 | t59_phaseB | 67 | 38,609 | 230,133 | 40 | 5.96 | 63 | 0.3327 | CF | 0.6202 | 6.2 | 0.806 | 60000 |
| 11 | t59_phaseA | 43 | 27,431 | 150,103 | 40 | 5.47 | 39 | 0.3720 | CF | 0.6250 | 6.3 | 0.791 | 60000 |
| 12 | t58 | 937 | 15,823 | 73,216 | 20 | 4.63 | 918 | 0.0894 | WA | 0.1755 | 20.6 | 0.749 | 400000 |

12 条文件的排列顺序正好等于 `effective_species` 升序 —— 与 `template_catalogue` 的排序键一致（`alchemy/biome.py:532`）。

### 1.4 `data/biomes/t*.{csv,json}`（12 组，逐模板明细）

| 文件组 | CSV 列/JSON 结构 | 规模 | 与根结果文件一致？ |
|---|---|---|---|
| t55_kinetic / t56_kinetic / t57_area / t58 / t59_phaseA / t59_phaseB / t62_phaseA / t62_phaseB / t63_phase1~4 | CSV 固定 **17 列**（`formula,label,natoms,count,abundance,atom_abundance,reserve_units,stable,in_catalog,category,in_library,shape,skeleton_blocks,structure_source,divalent_roles,props,attrs`）；JSON 为 `{spec, n_species, species[19 字段]}`（`alchemy/biome.py:537-575`） | 行数 = 各自 `n_species`（9/22/4/937/43/67/43/43/4/7/5/14） | ✔ 分子式集合与计数 **完全一致**（12/12 组，`out_lineage.txt:17-40`） |

`spec` 来源：`load_result(run)` 抽取 `config/load_summary/summary/final_composition` → `alchemy/biome.py:104-161`；`n_molecules = Σcount`，`n_atoms = summary.final_atoms`（`alchemy/biome.py:135,149-150`），实测与 `_catalogue.json` 的 `n_molecules/n_atoms/n_species/top1` **全部吻合**（`out_lineage.txt:43-54`）。

### 1.5 `candidates/*`（5 个候选群系 + 并集）

| 文件 | 行数 | 列数 | 说明 |
|---|--:|--:|---|
| `T55.csv` | 9 | 16 | 来自 `t55_kinetic_result.json` |
| `T57.csv` | 4 | 16 | 来自 `t57_area_result.json` |
| `T63S4.csv` | 14 | 16 | 来自 `t63_phase4_result.json`（第 4 阶段 = S4） |
| `T62B.csv` | 43 | 16 | 来自 `t62_phaseB_result.json` |
| `T59B.csv` | 67 | 16 | 来自 `t59_phaseB_result.json` |
| `_union.csv` | **121** | **34** | 五群系去重并集，扁平化视图 |
| `_union.json` | 121 species | 24 字段 | `{candidates, n_union:121, species}` |

- 每群系 CSV 列：`formula,label,natoms,count,abundance,atom_abundance,reserve_units,shape,category,skeleton_blocks,骨架,状态,能量,相型,in_catalog,stable`（`examples/build_biome_candidates.py:46-49`）。
- 群系选择：T58 被剔除（等效物种 20.6、单例率 74.9%，判为退火未完成噪声，`docs/BIOME_CANDIDATES.md:4`）；`_catalogue.json` 12 条中只有 5 条进入候选（T55/T57/T63S4/T62B/T59B，对应 `build_biome_candidates.py:35-41`），其余 7 条（t63_phase1~3、t56、t62_phaseA、t59_phaseA、t58）**未使用**（`out_lineage.txt:89-100`）。
- 并集：`n_biomes` 分布 `{1: 105, 2: 16}`，即 **16 种物质出现在 ≥2 个群系**，与 `docs/BIOME_CANDIDATES.md:16` 的「121 种 / 16 种」一致；`in_catalog = 46`；`dominant_in` 非空 12 种；`裁决轴数>0` 73 种；`第四相来源` 全为空（v4 无第四相，`alchemy/phase.py:134-140`）。

### 1.6 完整流水线

```
根目录实验输出  t*_result.json（当前共 50 个 t*_result.json；其中 12 个被目录收录）
   │  alchemy.biome.load_result()            alchemy/biome.py:104-161
   ▼
   ├─ abundance_table() → 每物种 17 字段行   alchemy/biome.py（含 label/shape/props/in_catalog）
   │     ├─ to_csv()/to_json()   → data/biomes/<name>.csv|json（12 组×2）
   │     └─ 汇总指标 → template_catalogue() → data/biomes/_catalogue.json（12 行）
   │
   └─ examples/build_biome_candidates.py
         ├─ CANDIDATES 5 个根结果           :35-41
         ├─ candidates/<TAG>.csv            :43,46-49
         ├─ candidates/_union.csv           :126-135
         ├─ candidates/_union.json          :（含 spec.file/spec.source）
         └─ docs/BIOME_CANDIDATES.md        :44,171-232
               │
               └─ examples/render_species_sheets.py（仅 in_catalog 46 种）
                     ├─ images/biome_candidates/species_01..04.png（12/页，4×3）
                     ├─ species_index.png（46 行索引）
                     └─ species_legend.png（元素/键型/读法图例）

另一条线（32 群系，不与本任务文件混用）：
t64_biome_B01..B12 / t65_biome_C01..C10 / t66_biome_E01..E10 的 *_result.json
   → t67_catalog.py → t67_catalog.json + docs/T67_BIOME_CATALOG.md（A10/B11/C7/D4）
```

### 1.7 谱系复现性实测（`intake/tmp/repro.py`，26.4 s）

```
[1] _catalogue.json 重算（template_catalogue，12 个根结果文件）
  重算 12 条，文件 12 条，耗时 14.1s
  顺序一致: True
  字段差异数: 0 （source 列因绝对路径跳过）

[2] candidates/* 重算（复用 build()/render_doc()，输出改到 intake/tmp，不写仓库）
  build+render_doc 完成，耗时 12.2s
  并集物质数: 121 | 跨群系>=2: 16
  仓库 _union.csv   vs 重算: 逐字节相同
  仓库 _union.json  vs 重算: 不同（4575 行中 5 行不同）
       repo:      "source": "D:\\Alchemistry DeepSeek工作区\\alchemy\\t55_kinetic_result.json",
       repro:     "source": "G:\\AI work\\deepseek\\work1\\alchemy\\t55_kinetic_result.json",
  仓库 T55.csv / T57.csv / T63S4.csv / T62B.csv / T59B.csv: 全部逐字节相同
  仓库 docs/BIOME_CANDIDATES.md vs 重算: 225 行 vs 225 行，不同行 0
```

---

## 2. `docs/THREE_AXES_FINAL.md` §8.2 / §8.3 复算核对

### 2.1 判定规则来源（内核）

| 机制 | 位置 |
|---|---|
| 三轴定义 `AXES = (("skeleton","骨架",("O","K","P")), ("state","状态",("X","A","W")), ("energy","能量",("C","F","L")))` | `alchemy/phase.py:82-86` |
| 概念族 `FRAME_NAMES = {O:刚体, K:胶体, P:软体}`（注释：秩 O→刚体、沌 K→胶体、势 P→软体） | `alchemy/phase.py:90-97` |
| 物态 `STATE_NAMES = {X:固, A:气, W:液}` | `alchemy/phase.py:100` |
| 能量 `ENERGY_NAMES = {C:冰, F:焰, L:电}` | `alchemy/phase.py:103` |
| 轴内相名 `PHASE_NAMES = {O:秩, K:沌, P:势, X:固, A:气, W:液, C:冰, F:焰, L:电}`（`_union` 的「骨架」列用这一套） | `alchemy/phase.py:116-120` |
| v4 裁决：严格多数；两两并列走循环压制（聚>散>动 → 秩>沌>势）；三者全等归聚；无第四相 | `alchemy/phase.py:142-166`，`docs/THREE_AXES_FINAL.md` §4/§9 |
| 物性名拼接 `物理名 = {刚体:刚性, 胶体:黏性, 软体:松散} + {冰:低温, 焰:高温, 电:带电} + {固:固体, 液:液体, 气:气体}` | `alchemy/phase.py` `physical_name` / `describe` |
| 复算入口：`alchemy.phase.phase_of(formula)` + `alchemy.phase.phase_names(...)` + `describe(...)` | 脚本 `intake/tmp/recompute_stats.py` |

> 注意：`_union.json` 里 `骨架` 字段值是**轴内相名**「秩/势/沌」，不是概念族名「刚体/软体/胶体」；概念族要按 `FRAME_NAMES` 再映射一次。

### 2.2 §8.2（`docs/THREE_AXES_FINAL.md:229-238`）逐项对比

46 种 `in_catalog == true` 的并集物种，用内核 `phase_of`/`describe` 重算（`out_stats.txt:11-28`）：

| 轴 | 文档 §8.2 | 复算 | 差异 |
|---|---|---|---|
| 概念族 | 刚体 31 · 软体 13 · 胶体 2 | 秩 O → **刚体 31**；势 P → **软体 13**；沌 K → **胶体 2** | **0** |
| 物态 | 固 35 · 液 6 · 气 5 | X 35 / W 6 / A 5 | **0** |
| 能量 | 冰 39 · 焰 5 · 电 2 | C 39 / F 5 / L 2 | **0** |

10 种物性名（文档 §8.2 第 237-238 行 vs `out_stats.txt:15-26`）：

| 物性名 | 文档 | 复算 | 物性名 | 文档 | 复算 |
|---|--:|--:|---|--:|--:|
| 刚性低温固体 | 19 | 19 | 黏性低温固体 | 2 | 2 |
| 松散低温固体 | 9 | 9 | 刚性带电固体 | 2 | 2 |
| 刚性低温气体 | 4 | 4 | 刚性低温液体 | 1 | 1 |
| 松散低温液体 | 4 | 4 | 刚性高温气体 | 1 | 1 |
| 刚性高温固体 | 3 | 3 | 刚性高温液体 | 1 | 1 |

- 合计 46，**无文档外的物性名**（`文档外物性名: 无`）。
- 另做交叉校验：把 `_union.json` 自带的 `骨架/状态/能量/物性名/相型/典型对应` 与内核重算逐条比对，**0 条不一致**（`out_stats.txt:27`）。
- 结论：**§8.2 完全可复现，未发现任何数字差异。**

### 2.3 §8.3（`docs/THREE_AXES_FINAL.md:240-250`）逐项对比

口径：对每个群系，把该群系所有物种按 `atom_abundance`（= `count×natoms / Σcount×natoms`）相加，再按物态归类。两种等价口径（候选 CSV 的 `atom_abundance` 字段；`_union.json` 的 `abundance × natoms`）结果完全一样（`out_stats.txt:42-77`）。

| 群系 | 文档 §8.3 固/气/液 | 复算（原子数占比） | 复算（`abundance×natoms`） | 差异 |
|---|---|---|---|---|
| T55 | 100% / — / — | **100.0 / 0.0 / 0.0** | 100.0 / 0.0 / 0.0 | 0 |
| T57 | 100% / — / — | **100.0 / 0.0 / 0.0** | 100.0 / 0.0 / 0.0 | 0 |
| T63S4 | 89.8 / 10.2 / — | **89.8 / 10.2 / 0.0** | 89.8 / 10.2 / 0.0 | 0 |
| T62B | 98.3 / 0.6 / 1.2 | **98.3 / 0.6 / 1.2** | 98.3 / 0.6 / 1.2 | 0 |
| T59B | 57.5 / 29.1 / 13.5 | **57.5 / 29.1 / 13.5** | 57.5 / 29.1 / 13.5 | 0 |

**口径说明（不构成数字差异，但需标注）**：
`docs/BIOME_SPEC.md:30` 把 `atom_abundance` 定义为「质量占比（地表覆盖率）」，即文档的"质量份额"= **原子数占比**，与逐元素质量无关。若改用内核逐元素质量（`alchemy/biome.py:89-97`：O3/X4/C1/P3/W2/L1/K3/A1/F2，`props.mass` = Σ元素质量）做真实质量加权，会得到略有不同的数字：

| 群系 | 原子数占比（文档口径） | `props.mass` 加权 |
|---|---|---|
| T63S4 | 89.8 / 10.2 / — | 91.5 / 8.5 / — |
| T62B | 98.3 / 0.6 / 1.2 | 98.2 / 0.4 / 1.4 |
| T59B | 57.5 / 29.1 / 13.5 | 54.5 / 30.8 / 14.7 |

两者定性结论一致（T55/T57 纯固、T63S4 近固、T62B 近固带微量液气、T59B 三相混合），但若以后要求"严格按质量"，需明确采用哪种口径。**复现文档现值必须用原子数占比。**

### 2.4 46 种目录内物质清单（复算对象，用于核对）

```
OXC OXCPWKA LF F2 CF OK OX2C O2XP2WK2A2
OXCPWK L2 XA O3XP4WK3A WA O2X2C4 O2X4 O2XP2K2A
O2X3C3K3A3 XA2F2 XC2A2 O2XCP3WK2 XCA2F PK OXPWKAF O2X2P2WK2A2
O2X2 O2XC2 O2XC4 O2X2P2WK2A O2X3 OXPWKF O2C4 O2XP2WK2A
O3X2P4WK3 O2XCP2WK O3X2P4WK3A O2XCP3WK2A O2X2P2K2A O3X2P4WK3A2 O2X2C2P3W2K O3X2P3WK2A2
O3X3CP4W2K2A O2X2P2W2K2A2 O2XCP2WKA CL O3X2P3WK2 O3X2CP4W2K2A
```

（46 个，按 `_union.json` 原顺序；`in_catalog == true`。）

---

## 3. `_union.json` 与 `_union.csv` 一致性

（脚本 `recompute_stats.py` [E] 段，`out_stats.txt:59-79`）

```
csv 行数=121  json species=121
csv 列数=34  json 字段数=24
json 有而 csv 无: ['abundance', 'count', 'dominant_in', 'props', 'stable']
csv 有而 json 无: ['attack','hp','mobility','resist','slots',
                  '个数_T55','个数_T57','个数_T59B','个数_T62B','个数_T63S4',
                  '丰度_T55','丰度_T57','丰度_T59B','丰度_T62B','丰度_T63S4']
行序 formula 完全一致: True
逐格比对（121 行 × 34 列）不一致列: 仅 hp 的浮点格式化（csv "168.0" vs json 168.0）
```

| 检查项 | 结果 |
|---|---|
| 行数 / 键集合 | 121 vs 121；行序 `formula` 完全一致 |
| 共有列逐格 | **全部相等**（`max_abundance` 为 6 位小数字符串，数值一致；`hp` 等 `props` 数值一致，仅格式不同） |
| 关系 | CSV = JSON 的**扁平化视图**：JSON 的 `props` 展开成 `hp/attack/resist/mobility/slots`，`abundance/count` 按 5 群系展开成 `丰度_*`/`个数_*`；`dominant_in/stable/abundance/count/props` 以嵌套形式只存在于 JSON |
| 抽样 | row0 OXC：n_biomes 2/2、max_abundance 0.995146/0.995146、in_catalog True/True、hp 100/100；row60 O4X3C4P14W3L3K3A3F2：0.000026 vs 2.6e-05；row120 O5X4C2P14W4K4A2F5：hp csv 为空 / json `null` |

**结论：同源一致，无内容冲突。** 二者由同一 `build()` 同时写出（`examples/build_biome_candidates.py:126-169`），可安全互推。

---

## 4. 脚本审读与可运行性

### 4.1 `examples/build_biome_candidates.py`（249 行）—— 可在当前数据上跑通

- **输入**：仓库根目录 5 个实验 JSON（硬编码 `CANDIDATES`，`:35-41`）：`t55_kinetic_result.json`、`t57_area_result.json`、`t63_phase4_result.json`、`t62_phaseB_result.json`、`t59_phaseB_result.json`（均已存在，5.98~27.60 MB）。
- **输出**（写在仓库内，硬编码）：`candidates/<TAG>.csv`（`:43,46-49`）、`candidates/_union.csv`（`:126-135`）、`candidates/_union.json`（`spec` 内含 `file`/`source`）、`docs/BIOME_CANDIDATES.md`（`:44,` `render_doc()` `:171`）。
- **依赖**：stdlib + 本仓库 `alchemy`（`biome`/`phase`/`catalog`），无第三方包。
- **运行方式**：无 CLI 参数（`main()` `:233` 不读 `sys.argv`）；`python examples/build_biome_candidates.py` 会**直接重写仓库文件**，因此本次没有按原样运行，而是 import 后把 `OUT_DIR`/`DOC` 重定向到 `intake/tmp/repro_candidates` 再调用 `build()`+`render_doc()`。
- **实测**：26.4 s；并集 121/跨群系 16 与仓库一致；5 个 CSV **逐字节相同**，`docs/BIOME_CANDIDATES.md` **225 行逐行相同**；`_union.json` 仅 5 行不同 = 5 个 `spec.source` 绝对路径（旧机器 `D:\Alchemistry DeepSeek工作区\alchemy\...`）。→ **生成逻辑与数据完全可复现**。
- 风险：路径全部硬编码（`REPO`/`OUT_DIR`/`DOC`），换目录/换机器必须改代码；`spec.source` 记录绝对路径，跨机器重跑必然产生 diff。

### 4.2 `examples/render_species_sheets.py`（422 行）—— 本环境不能跑，仅审读

- **输入**：`_union.json`（`:37`）→ 仅保留 `in_catalog`（46 种）；`alchemy.get_catalog()` 取 `atoms/edges/place`（需根目录 `t4_catalog_all_validated.json` 39 MB）；`alchemy.validate` 复核落位。
- **输出**：`images/biome_candidates/`（`:38`，写仓库）——`species_01..0N.png`、`species_index.png`、`species_legend.png`。
- **依赖**：**PIL/Pillow（第三方，已声明但本机未安装）**，`from PIL import Image, ImageDraw, ImageFont`（`:27`）；依赖声明见仓库根 `requirements.txt`（`Pillow>=9.0`）与 `pyproject.toml` 的 `optional-dependencies.plots = ["Pillow>=9.0"]`；Windows 字体 `C:/Windows/Fonts/msyhbd.ttc|msyh.ttc|simhei.ttf|segoeui.ttf`（`:67-77`，找不到回退 `load_default`）。
- **实测**：`python -c "import PIL"` → `ModuleNotFoundError: No module named 'PIL'`，**无法实跑**；因此只做源码审读 + 既有产物核对（尺寸/行数与代码公式完全吻合，见 §5）。
- **风险**：①本机未安装已声明的 Pillow，`pip install -r requirements.txt` 后应可运行；②字体路径硬编码 Windows；③直接写 `images/` 仓库目录，无 `--out` 参数。
- 视觉规格（与既有图核对无误）：页 1600×1240，4 列×3 行 = 12 面板/页（`:221-254`）；索引 1600 宽、行高 21、`H=170+21N+70`（`:258-305`）；图例 1600×900（`:309+`）；元素色 `O #46B95B / X #F5A623 / C #3FD0C9 / P #F07AC8 / W #3B6FD4 / L #F5E04B / K #8E5AA8 / A #B3B3B3 / F #E74C3C`（`:44-52`）；键型色 S 红/C 绿/L 紫、键级线宽 3/5/7 px（`:123-135`）；L 键中点紫虚线格必须为空（图例明示）。

---

## 5. 图像核对（`images/biome_candidates/`）

| 文件 | 尺寸 | 与数据的对应 |
|---|---|---|
| `species_index.png` | **1600×1206** | 标题「候选群系物质索引（**目录内 46 种**，按最高丰度排序）」，**46 行**；高度 1206 = 170 + 21×46 + 70，与 `sheet_index` 公式完全一致。列 = `#/分子式/标识（机械）/原子/形状/6级骨架块/物性名/T55/T57/T63S4/T62B/T59B`。首行 `OXC 99.515% / 80.853%`（= union `max_abundance` 0.995146 / T57 0.808528）；第 2~6 行 `OXCPWKA .4706 / LF .4693 / F2 .3785 / CF .3142 / OK .2458`，与 `_union.json` 按 `max_abundance` 降序完全一致（12 项逐一核对通过）。缺失群系用「—」。 |
| `species_legend.png` | **1600×900** | 四块：①9 元素六边形（O秩/X晶/C冰/P势/W流/L电/K沌/A气/F焰，`CN` 实测 = `{O:秩,X:晶,C:冰,P:势,W:流,L:电,K:沌,A:气,F:焰}`）；②6 种键样例（S 键级 1/2/3、C 键级 1、L 键级 1/2，L 中点虚线格标注"必须为空"）；③怎么读一个面板；④元素→键型倾向（聚素 O/X/C → S 短键·刚性贴边；动素 P/W/L → C 角键·铰接可转动；散素 K/A/F → L 长键·柔性长距离），并注明"倾向而非绝对"。与代码 `sheet_legend` 完全对应。 |
| `species_01.png` | **1600×1240** | 「候选群系的物质结构图（第 **1/4** 页）」，4×3 = 12 面板：#1 OXC 秩晶冰·链、#2 OXCPWKA 秩晶冰势流汽气环、#3 LF 电焰链、#4 F2 焰2链、#5 CF 冰焰链、#6 OK 秩沌链、#7 O2X3C3K3A3 秩2晶3冰3势3气3团、#8 OX2C 秩晶冰2环、#9 O2XP2WK2A2 秩2晶2势2流2气2环、#10 OXCPWK 秩晶冰势流汽环、#11 L2 电2链、#12 XA2F2 晶气焰2链 —— 与索引 #1~#12 完全对应。每个面板底部大字 = `describe()` 物性名（如「刚性低温固体」）+ 小字「id·典型对应」，与 §8.2 统计口径一致。46 种 ÷ 12 = **4 页（12+12+12+10）**，`species_02/03/04.png` 均存在。 |
| `species_02..04.png` | 1600×1240 | 对应索引 #13~#24、#25~#36、#37~#46。 |

- 图与数据对应关系结论：索引 = 46 种（`in_catalog`）按最高丰度排序的扁平表；面板页 = 同序 12/页的结构图，物性名来自内核 `describe()`；图例色标 = **元素色**（不是群系分类色，也不对应 27 型），「27 型」只体现在物性名/相型文字列，视觉上不按 27 型着色。索引中的 5 列群系丰度对应 T55/T57/T63S4/T62B/T59B 五个候选群系（非 32 群系目录）。

---

## 6. 不一致与风险清单（含位置）

| # | 问题 | 证据 | 影响/建议 |
|--:|---|---|---|
| 1 | `_catalogue.json` 不是 32 群系目录；A10/B11/C7/D4 在 `t67_catalog.json` | `_catalogue.json` 12 条 ×20 字段；`t67_catalog.json` `category_counts` = A10/B11/C7/D4、`biomes` 32 条 | 文档/汇报时说清"12 个实验模板目录"vs"32 个生态群系目录"，避免混用 |
| 2 | `docs/BIOME_SPEC.md:98` 的复现命令 `glob('t*_result.json')` 现在匹配 **50** 个结果文件 | 根目录实测 50 个 `t*_result.json`（含 t64/t65/t66 的 32 个、`_hf` 变体、t13、t57_uniform） | 照文档跑会生成 50 行目录，与仓库内 12 行文件不同；应改为显式 12 个文件或按 `_catalogue` 名单过滤 |
| 3 | `data/biomes/t*.csv|json` 与当前内核**标签漂移** | 旧导出：`OXC 秩晶冰·孤核`、`shape=孤核`；当前 `abundance_table` 输出 `OXC 秩晶冰·链`（规则 `alchemy/biome.py:176-208`，3 原子分子走「链」）。共 13 处：T55 7、T57 3、T63S4 1（OK）、T62B 2（OK/PK）、T59B 0 | 计数/丰度/其他字段一致；若引用 `data/biomes/t*.json` 的 label/shape 会与 `candidates/*` 和 `docs/BIOME_CANDIDATES.md` 冲突，应以重生成的 candidates 为准 |
| 4 | `_union.json` 的 `spec.source` 是旧机器绝对路径 | `D:\Alchemistry DeepSeek工作区\alchemy\t55_kinetic_result.json` 等 5 处 | 重跑必产生 diff；建议只存相对路径或文件名 |
| 5 | `render_species_sheets.py` 依赖 PIL + Windows 字体 + 写仓库 | `:27`、`:67-77`、`:38`；本机 `ModuleNotFoundError: No module named 'PIL'`（依赖已在根 `requirements.txt:2` 与 `pyproject.toml` 的 `plots` extra 中声明） | 声称"可重跑"有环境前提：需 `pip install -r requirements.txt`；建议加 `--out` 输出参数与字体回退配置 |
| 6 | 并集 121 种里 **54 种 `props=None`**（`natoms≥38`、不在 84,225 目录） | `out_stats.txt:9` | 这些物质无属性/无法进入图鉴（渲染只覆盖 46 种目录内物质）；属设计选择，但"121 种"与"46 种可命名"需在文档中区分 |
| 7 | 根目录 50 个 `t*_result.json` 中 `_hf` 变体、`t57_uniform`、`t63_phase1~3`、`t56`、`t62A/59A`、`t58` 未入候选 | `out_lineage.txt:89-100`（12 条目录中仅 5 条入候选） | 引用实验结果时确认用哪一份，避免用 `_hf` 变体或未入目录的 run |
| 8 | `docs/THREE_AXES_FINAL.md` §8.3 的"质量"实为原子数占比 | `docs/BIOME_SPEC.md:30`；按 `props.mass` 真质量加权会得 T63S4 91.5/8.5、T62B 98.2/0.4/1.4、T59B 54.5/30.8/14.7 | 复现文档数字须用 `atom_abundance`；若要严格质量口径需改文档表述 |
| 9 | `data/biomes/t55_kinetic.csv` 与 `candidates/T55.csv` 同名物种 label 不同（孤核 vs 链） | 同上 #3 | 跨目录引用时注意 |

**未发现**：§8.2、§8.3 的任何数字差异；`_union.csv`/`_union.json` 的内容冲突；`_catalogue.json` 与 `data/biomes/*.json` 的计数差异（12/12 全部吻合）。

---

## 附录 A：文件清单与规模（`data/biomes/`）

| 文件 | 字节 | 文件 | 字节 |
|---|--:|---|--:|
| `_catalogue.json` | 6,073 | `t58.json` | 491,637 |
| `t55_kinetic.csv` / `.json` | 3,158 / 7,942 | `t59_phaseA.csv` / `.json` | 11,494 / 32,116 |
| `t56_kinetic.csv` / `.json` | 7,550 / 18,764 | `t59_phaseB.csv` / `.json` | 13,518 / 43,662 |
| `t57_area.csv` / `.json` | 1,501 / 3,729 | `t62_phaseA.csv` / `.json` | 12,282 / 33,424 |
| `t58.csv` | 106,877 | `t62_phaseB.csv` / `.json` | 11,964 / 32,947 |
| `t63_phase1.csv` / `.json` | 1,499 / 3,726 | `t63_phase3.csv` / `.json` | 1,768 / 4,427 |
| `t63_phase2.csv` / `.json` | 2,461 / 6,180 | `t63_phase4.csv` / `.json` | 5,439 / 12,910 |
| `candidates/T55.csv` | 1,042 | `candidates/T62B.csv` | 4,939 |
| `candidates/T57.csv` | 556 | `candidates/T63S4.csv` | 1,824 |
| `candidates/T59B.csv` | 7,951 | `candidates/_union.csv` / `_union.json` | 21,823 / 98,707 |

相关文档：`docs/BIOME_SPEC.md`（字段语义 + 复现命令）、`docs/BIOME_CANDIDATES.md`（5 候选 + 并集表，225 行）、`docs/THREE_AXES_FINAL.md`（27 型与 §8 数据事实）、`docs/T67_BIOME_CATALOG.md`（32 群系）。

## 附录 B：复跑命令

```powershell
# 控制台 GBK，中文输出请重定向到 UTF-8 文件后阅读
cd 'G:\AI work\deepseek\work1\alchemy'
python 'G:\AI work\deepseek\work1\intake\tmp\inspect_biomes.py'    # 盘点 data/biomes + candidates
python 'G:\AI work\deepseek\work1\intake\tmp\recompute_stats.py'   # §8.2/§8.3 复算 + union.csv/json 比对
python 'G:\AI work\deepseek\work1\intake\tmp\lineage.py'           # 谱系：根结果 -> biomes -> candidates
python 'G:\AI work\deepseek\work1\intake\tmp\repro.py'             # 可复现性：_catalogue / candidates 重算（不写仓库，~27s）
# 输出：intake/tmp/out_{stats,lineage,repro,cat}.txt
```
