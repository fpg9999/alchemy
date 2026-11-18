# 内核入库整理与成果分析（KERNEL INTAKE，2026-11-18）

> 上游提交：`4a2e4d6`（2026-11-18 22:48）「kernel: 抽出 alchemy 内核（四入口 + 106 项测试）」，88 个新增文件。
> 本文件是对该提交的**整理结果**：拉取核对、内核包结构、新规则体系、数据与示例产物、质量核对、风险与待办。
> 三份明细分析（内核代码 / 规则文档 / 群系数据，共约 1,300 行）存在工作区 `..\intake\`（不在仓库内，含本机路径，故不入库）。

---

## 0. 一句话结论

远端把**「规则 → 代码 → 测试 → 数据 → 文档」收拢成了一个可独立安装的纯标准库内核包 `alchemy/`**（106 项测试全绿），
并把此前只存在于讨论与旧脚本里的**三轴（概念族/物态/能量）、物相判定、口径分歧、能力、外观、性状**写成 6 份正式规则文档 + 数据 + 示例；
经逐项复核，**文档里的关键数字与代码/数据 100% 自洽**（仅少数文档过期文字与 3 处实现接口风险），仓库根交接文档此前未同步，本次已补齐。

---

## 1. 拉取与验证

| 项 | 结果 |
|---|---|
| 拉取前状态 | 本地 `main` 落后 `origin/main` 1 个提交；工作树干净 |
| 拉取方式 | `git fetch --all --prune` → `git pull --ff-only`，fast-forward 到 `4a2e4d6` |
| 提交内容 | 88 个新增文件（纯新增，无删除/改名）：内核包、9 份文档、data/biomes、examples、images、tests、pyproject |
| 测试 | `python tests/run_all.py` → **106/106 PASS**（21.4s / 24.4s / 27.0s，三个环境复跑一致）；`tests/run_all.py reactor` → 10 PASS 0.2s |
| 示例 | `python examples/demo_kernel.py` 正常（Windows GBK 控制台需 `PYTHONIOENCODING=utf-8`，否则 UnicodeEncodeError ✓ 崩溃） |
| 数据 | catalog 84,225 条（`stats`: le16 82,961 / over16 1,264 / max_natoms 97 / place=null 245）；39MB 目录 sha256 与 `_data_gz/manifest.json` 的 `orig_sha256` 一致 |
| 仓库体积 | 内核包 + 文档 + 新数据约 3.2MB（不含 39MB 目录与 `_data_gz`） |

> 注：本地历史提交顺序为 `4c79217`（T68~T70b）→ `8877e8d`（T71~T76）→ `4a2e4d6`（kernel），T71~T76 与 kenel 均已在远端，本次整理同步更新 TRANSFER §6 的推送记录。

---

## 2. 内核包 `alchemy/`（纯标准库）

### 2.1 模块地图

| 文件 | 规模 | 职责 |
|---|---|---|
| `alchemy/__init__.py` | 90 行 | 公开 API 汇总、四入口再导出（急切导入 `phase`/`biome`） |
| `alchemy/core/elements.py` | 199 行 | 9 元素表、价数、周期表距离、六边形偏移、分子式解析 |
| `alchemy/core/canon.py` | 125 行 | 分子同构规范形（1-WL + 分支定界），替代不稳健的 `wl_key` |
| `alchemy/core/geometry.py` | 184 行 | 摆放搜索 `embed`、严格校验 `validate` |
| `alchemy/core/reactor.py` | 295 行 | 大锅反应引擎，规则 1~8 / 1~9 / 1~11 参数化可切 |
| `alchemy/core/catalog.py` | 185 行 | 84,225 条目录加载/查询/缓存；缺文件时提示 `python unpack_data.py` |
| `alchemy/core/classify.py` | 443 行 | 骨架分类：38 库、6 级块、三层拆解、结构定理 |
| `alchemy/phase.py` | 457 行 | 三轴相分类（概念族/物态/能量）：`phase_of`/`describe`/`physical_name` |
| `alchemy/ability.py` | 155 行 | 8 情形 × 3 轴 = 512 能力编号 |
| `alchemy/attrs.py` | 252 行 | 硬度/黏性/温度三数值属性与档位 |
| `alchemy/biome.py` | 604 行 | 生物群系：物种表、物性、分层、CSV/JSON/MD 导出 |
| `alchemy/data/forms38.json` | 103,930B | 38 形态库；与根目录 `t8_forms.json` **同 sha256**（字节级相同） |
| `alchemy/data/biome_names.json` | 754B | 物种中文名映射 |

依赖方向：`elements`（叶子）← `canon` / `geometry` / `reactor` / `catalog` ← `classify`；`phase`、`ability`、`attrs`、`biome` 在上层。
**内核不 import 任何历史脚本**（`pot_all/pot_v2/pot_v3/pot_v4`），rules=8/9/11 是同一份代码按参数追加 key 分量（`reactor.py:202-215`）。

### 2.2 四入口 API

| 入口 | 签名 | 返回 |
|---|---|---|
| `simulate` | `simulate(atom_list, rules=11, return_level6=False)` | `[{atoms, edges}]`；失败 `None`；`rules∉{8,9,11}` → `ValueError` |
| `trace` | `trace(atom_list, rules=11)` | `{mols, level6, bonds, atoms, steps}` |
| `embed` | `embed(atoms, edges, max_nodes=None, final_check=True)` | `{int: (q,r)}`；不连通/超预算 → `None`（"未判定"语义，区别于 pot_v2 的 `False`） |
| `validate` | `validate(place, atoms, edges)` | `(bool, 原因)`；只校验几何/键型，不校验每原子键级和==价数 |
| `get_catalog` | `get_catalog(path=None)` | `Catalog`（84,225 条只读索引） |
| `classify` | `classify(atoms, edges, rules=11, library=None, place=None, check_stable=True)` | 6 级块/38 库/三层/结构定理结果；`place` 需 **int 键** |

另导出 `Catalog`、`embed_all`、`to_place_dict`、`classify_record`、`classify_feed`、`classify_block`、`load_library`、`block_label`、
元素工具（`formula_of/parse_formula/vec_to_atoms/atoms_to_vec/ptable_dist/classify_offset`）与 `SUPPORTED_RULES`、`RULE9_PRIORITY`。

> 用法示例（`examples/demo_kernel.py` 同款）：
> ```python
> import alchemy
> alchemy.simulate(["O","X","C"])          # 大锅完全反应
> alchemy.embed(["O","X","C"], [(0,1,1),(0,2,2)])   # 六边形摆放
> cat = alchemy.get_catalog()              # 84,225 条
> alchemy.classify(["O","X","C"], [(0,1,1),(0,2,2)])["level6"]["blocks"][0]["kind"]  # 'single'
> ```

### 2.3 测试套件（11 个 `test_*.py`，106 用例）

| 文件 | 覆盖点 |
|---|---|
| `test_elements` / `test_geometry` / `test_canon` | 元素表/价数/周期表距离；摆放与校验（含 L 键中点、多重键）；同构规范形 |
| `test_reactor` / `test_equivalence` | 规则 1~11 引擎；与历史 `pot_all/pot_v3/pot_v4` 固定种子差分（120~200 feed） |
| `test_catalog` / `test_classify` | 84,225 条目录一致性；38 库、6 级块、结构定理（671 个融合形态、670/670 宿主定理） |
| `test_phase` / `test_ability` / `test_attrs` / `test_biome` | 三轴判相三模式；512 能力；三数值属性；群系物种表/导出往返 |
| `_util.py` / `run_all.py` | 断言工具；串行跑全套、打印耗时；支持按名称过滤 |

复跑命令：`python tests/run_all.py`（全套 ≈21~27s）、`python tests/run_all.py reactor`（单模块 0.2s）。

---

## 3. 新规则体系（9 份文档）

### 3.1 三轴最终规则（`docs/THREE_AXES_FINAL.md`，实现 `alchemy/phase.py`）

| 轴 | 价数 | 元素 → 相 | 相名 |
|---|---|---|---|
| 概念族（骨架/家族） | 3 价 | O 秩→**刚体** / K 沌→**胶体** / P 势→**软体** | 刚性/黏性/松散（物性名前缀） |
| 物态（状态） | 2 价 | X 晶→**固** / A 气→**气** / W 流→**液** | 固体/液体/气体（后缀） |
| 能量（现象） | 1 价 | C 冰→**冰** / F 焰→**焰** / L 电→**电** | 低温/高温/带电（中缀） |

**判定（v4 hybrid，默认）**：逐轴独立三步 —— ① 严格多数直接胜；② 恰好两两并列 → 循环压制 **聚>散>动>聚**；
③ 三者全等（含全零）→ 按 `RULE9_PRIORITY` 归「聚」。**永不第四相**，3×3×3=27 型全覆盖。

三模式并存：`hybrid`（v4 正式）、`hierarchy`（= PHASE_RULE 正文 v1，并列永远聚侧胜）、`cycle`（v2 遗留，产生第四相）。
**PHASE_RULE 正文的 41.41/30.60/27.99 是 hierarchy 口径，THREE_AXES 的 35.86/33.54/30.60 是 hybrid 口径**——差异全部来自模式，已全量复算验证。

全目录 v4 分布（84,225 条，复核一致）：概念族 软体 36.44% / 刚体 31.82% / 胶体 31.74%；
物态 固 35.86% / 液 33.54% / 气 30.60%；能量 冰 42.70% / 焰 28.66% / 电 28.64%。
并列裁决是承重规则：46.29% 的物质至少一条轴靠它定值；**动素（P/W/L）永不赢得并列**，势/液/电只能由严格多数产生。

物性名合成：`{概念族形容词}{能量形容词}{物态名词}`，如 OXC → 刚性低温固体、O2XP2WK2A2 → 刚性低温气体。
27 型完整短名尚未定（未定项）。

**恒素（E）**：0 价、周期表中心、不参与成键，只作「借出—归还」媒介（净消耗 0）；价数填满定理 总键级 = Σ价数/2，全目录 84,225/84,225 成立 → 端点是恒素中性不动点。
**物态与温度彻底解耦**：物态只由 X/A/W 组成决定；旧实验 `T0=1000→0` 实为「恒素密度稀释」，不是 1000°C。

### 3.2 物相规则（`docs/PHASE_RULE.md`）

- 正文 = v1 层级法（并列全按 `RULE9_PRIORITY`），附录 A = v2 循环+第四相，附录 B/C = 二维表定稿，D = 能量轴定稿，E = 恒素；
- 全目录实测：27 型全非空（2.0%~7.0%）、并列承重 46.29%、动素并列胜出 0 次；
- 对 T55/T57/T63S4/T62B/T59B 五群系的后果：46 种候选里 **固 42 / 气 4 / 液 0**，121 并集里 W 主导仅 2 种 → 要做液体/气体地形必须单独设计投料（提高 W 占比），不能靠改裁决顺序；
- 约定：该层三元素全 0（如 LF/CF/OK/F2）按「全零→聚」给固，可用 `phase_of()` 的 `tie=True && counts 全 0` 识别为约定值；
- **旧 T33/T34/T35 温度规则未进内核**（`reactor.py` grep 温度零命中）——属移出而非等价实现。

### 3.3 口径分歧（`docs/CALIBER_DIVERGENCE.md`，审计 2026-11-17）

| 口径 | 实现 | 状态 |
|---|---|---|
| 规则 1~8 | `pot_all.simulate` | 历史 |
| 规则 1~9 | `pot_v3.simulate` | 历史 |
| 规则 1~11 | `pot_v4.simulate` / `alchemy.core.reactor` | **正式** |

- v3→v4 结构差异 **14,615/84,225 = 17.35%**；目录实际替换 **14,745 = 17.51%**（=14,615 + 130 条仅规则 9 差异）；**分子式差异 0**；
- 规则 10/11 只在 T=n(O)+n(P)+n(K)≥4 时可能改变结果，T≤3 的 9,070 条差异 0；差异集中在 13~16 原子、T=7/8（27.95%/35.28%）；
- **目录 100% 已是 v4 口径**（84,225/84,225 与引擎逐条相同）；规则 1~8 只能复现 69,480 条（82.49%）；
- `place=null` 245 条（0.29%）= 替换产生 28 条（其中 24 条 ≤16 原子，6 条已证几何不可实现、18 条仅预算未判定）+ 历史遗留 217 条（216 条现在能直接摆出）；
- 6 级骨架库（38）不受规则 9/10/11 影响，v4 下 84,225/84,225 的 6 级块仍在库。

### 3.4 能力（`docs/ABILITY.md`，实现 `alchemy/ability.py`）

每轴 8 种情况（3 单主导 + 3 双主导 + 三合 + 无）= 512 种能力编号，**取代 T74 的「并列裁断 27 型」旧分类**。
全目录实际出现 308/512；46 种候选物质出现 34/512。文档 §3 给了「收紧方案」但 §6 又写「待确认」，属自相矛盾（本次整理未改上游文档，仅记录）。
旧 T71 30 项 / T72 72 项能力体系与 28 形态在文档中**未接续**（T72 为悬空历史）。

### 3.5 外观（`docs/APPEARANCE.md`）

采用 `T75_BLOCK_WORLD.md` 为唯一主规范（T68/T69/T70/T70b 为前身）；接口唯一依赖 `alchemy.attrs.skeleton_units(members/bridge_members/size)`。
当前**仅记录不实现**（方块渲染仍在根目录 `t75_tiles.py`/`t75b_render.py`），属未完成项。

### 3.6 性状（`docs/TRAITS.md`，实现 `alchemy/attrs.py`）

**整分子三数值累加**（取代 T75b「逐骨架各算」口径）：

| 属性 | 权重 | 分档（6000 样本 33%/67% 分位） |
|---|---|---|
| 硬度 | O 3 / K 2 / P 1 | 阈值 10 / 16 |
| 黏性 | X 3 / W 2 / A 1 | 阈值 6 / 11 |
| 温度 | F 3 / L 2 / C 1 | 阈值 3 / 6 |

示例表 3 行与阈值不符（OXC、OXCPWKA、XA），属文档笔误（实现与阈值一致）。

### 3.7 数据与示例（`docs/BIOME_SPEC.md`、`docs/BIOME_CANDIDATES.md`、`data/biomes/`、`examples/`）

- `data/biomes/_catalogue.json` = **12 条实验模板 × 20 字段**描述性目录（不是 32 群系目录；32 群系 A10/B11/C7/D4 的载体仍是根 `t67_catalog.json`）
- `data/biomes/t*.{csv,json}` = 12 组模板的物种表（17 列 / `{spec, n_species, species}`），由根 `*_result.json` 经 `load_result → abundance_table` 生成
- `candidates/*` = 5 个候选群系（T55/T57/T63S4/T62B/T59B）+ `_union`（121 种 × 34 字段）；`docs/BIOME_CANDIDATES.md` 为其清单
- `examples/build_biome_candidates.py`（249 行）：26.4s 可跑通，5 个候选 CSV 与文档逐字节相同；`_union.json` 仅 5 行旧机器绝对路径差异
- `examples/render_species_sheets.py`（422 行，需 Pillow）：46 种物种 → 4 页（12+12+12+10）PNG；索引图 1600×1206 = 170 + 21×46 + 70，数值与 `_union.json` 完全对应
- §8.2/§8.3 复算：46 种目录内物质 → 刚体 31/软体 13/胶体 2、固 35/液 6/气 5、冰 39/焰 5/电 2、10 种物性名计数逐项一致；T55/T57 固 100%、T63S4 89.8/10.2/0、T62B 98.3/0.6/1.2、T59B 57.5/29.1/13.5，**0 差异**（口径为原子数占比；真质量加权会略偏，定性不变）

---

## 4. 与旧阶段（T71~T76）的承接关系

| 旧成果 | 新内核对它的处理 |
|---|---|
| T74 分类（固/液/气、刚/粘/松、高温/低温/导电 三套并列序） | 被 `phase.py` 三轴 + `ability.py` 512 + `attrs.py` 三数值**取代**；T74 的并列序（X>W>A、O>P>K、C>L>F）与 RULE9 推出的序（X>A>W、O>K>P、C>F>L）冲突，新文档以前者为准但未明说 |
| T71 生命度 / 30 能力、T72 72 能力+28 形态 | 未接续（T72 悬空）；T71 实际 27 项却写作 30 项，ABILITY 又把 T71 写成「72 种」 |
| T75 方块世界权重（O1.2/P0.9/K0.6 等） | 被 `attrs.py` 的 O3/K2/P1 取代，旧权重未并入 |
| T75b 逐骨架属性 | 被整分子三数值取代 |
| T76 桥的 13 种功用标签 | 仍是唯一规范，新文档未引用 |
| T68~T70b 图形语言 | 降为外观层前身，`APPEARANCE.md` 只记录不实现 |

---

## 5. 质量核对（本次实测）

- 文档声明「catalog 84,225 / 14,745 替换 / forms38==t8_forms / 四入口」**全部成立**；14,745 三方自洽（t52 JSON + 脚本 + CALIBER 文档），随机 800 条抽样与 rules=11 引擎 100% 自洽；
- 文档测试数「85 / 96 / 106 项」实为整套 suite 的三个时点数（85+attrs11=96，96+ability10=106），被误写成模块数；SYNC 的「60 项」更旧；
- 全目录三轴分布、27 型完整计数、§8.2/§8.3 统计均由独立脚本复算，与文档**逐项一致**；
- 唯一运行期异常：`tests/test_biome.py::test_export_roundtrip` 在受限沙箱（禁止写系统临时目录）下 PermissionError；普通环境 106/106。

---

## 6. 风险与待办

### P1（建议尽快修）

1. **`get_catalog` 缓存无锁**：4 线程并发 12.24s、得到 4 个不同对象、重复加载 4×39MB；返回可变共享 dict。
2. **`place` 键类型双轨**：目录/JSON 是 **str 键**，`classify(place=...)` 要求 **int 键** → 直接传入会 `KeyError: 1`；`classify_record` 内部转，但公开接口未统一。
3. **`examples/demo_kernel.py` 在 Windows GBK 控制台崩溃**（✓/→ 字符），README 未提示；建议 `PYTHONIOENCODING=utf-8` 或改 ASCII 输出。

### P2

- `phase.py` 模块 docstring 仍写「v2 / cycle 默认 / 第四相」，`__all__` 漏 `describe`/`physical_name` 等 6 个符号；
- 测试硬依赖仓库根 `t57/t58/t62/t63_*` 与 39MB 目录（无 skip 守卫），干净 clone 未 unpack 时测试不可跑；
- `unpack_data.py` 校验失败时退出码仍 0（CI 假绿）；
- `test_catalog` 引擎一致性阈值仅 ≥70%，差分测试抽样有限；
- `pytest` 未安装验证；`run_all.py` 裸 `assert`（`python -O` 假绿）；
- `data/biomes/t*` 是旧内核快照：13 处 `shape/label` 为旧「孤核」而当前内核为「链」（计数/丰度一致）；
- `docs/BIOME_SPEC.md:98` 的复现命令会 glob 到 50 个结果文件（文档过期），应显式列 12 个；
- `_union.json` 的 `source` 存旧机器绝对路径；`BIOME_CANDIDATES.md` 复现依赖 `D:\...` 路径。

### 待办建议

1. 冻结并打 tag：`kernel-0.2.0`（SYNC.md 建议）；
2. 数据层加 `rules` 字段（避免历史脚本「v4 输入 + 1~9 反应」混合口径）；
3. 修 P1 三项 + `phase.py` 文档/`__all__` + 测试数据守卫；
4. 统一 `place` 键类型（入口处 `str→int` 归一化）；
5. T74/T75/T75b 旧页面切到新内核（`phase`/`ability`/`attrs`），或明确标注「历史参考」。

---

## 7. 文件索引（本次提交）

| 类别 | 路径 |
|---|---|
| 内核包 | `alchemy/`（含 `core/`、`data/`、`README.md`） |
| 规则文档 | `docs/THREE_AXES_FINAL.md`、`docs/PHASE_RULE.md`、`docs/CALIBER_DIVERGENCE.md`、`docs/ABILITY.md`、`docs/APPEARANCE.md`、`docs/TRAITS.md` |
| 群系文档/数据 | `docs/BIOME_SPEC.md`、`docs/BIOME_CANDIDATES.md`、`docs/SYNC.md`、`data/biomes/`（`_catalogue.json`、`t*.csv/json`、`candidates/`） |
| 示例 | `examples/build_biome_candidates.py`、`examples/demo_kernel.py`、`examples/render_species_sheets.py` |
| 图 | `images/biome_candidates/species_01~04.png`、`species_index.png`、`species_legend.png` |
| 测试 | `tests/`（11 个 `test_*.py` + `run_all.py` + `_util.py`，106 用例） |
| 打包 | `pyproject.toml`（package-data 含 `alchemy/data/*.json`；catalog 39MB 按设计不入包） |

---

## 8. 第二轮增量（2026-11-19，上游 facb162 + cf9d01b）

本文写成后，上游又推了两个提交，本节的增量以 `docs/INTAKE_R2.md` 为准（详细展开见该文）：

- **物性改口径**：`alchemy/attrs.py` 由「硬度/粘性/温度」改为 **密度/粘性/温度**，
  权重 O3/K2/P1、X3/W2/A1、F3/L2/C1，阈值 (10,16)/(6,11)/(3,6)，3³ = **27 格**；
  硬度与固态重合会产生「刚性液体」，故弃用。
- **能力改口径**：`alchemy/ability.py` 新增 v3 三项数值（聚 O/X/C、散 K/A/F、动 P/W/L，权重=价数）
  与 v4 九项次级能力三阶（结构支撑/刚性/粘合/分化/吸附/切割/储能/移动/信号）；
  512 种复合分类冻结为历史接口（实际 308/512）。
- **外观层**：仍不新设计，主规范 = `docs/T75_BLOCK_WORLD.md` 方块世界；内核侧只提供
  `attrs.skeleton_units` 作为唯一接口，渲染仍在上游 `t68~t76` 脚本。
- **测试**：106 → **124**（新增 `tests/test_attrs.py`、`tests/test_ability.py`）。
- **仓库体积**：新增 `docs/REPO_SLIM.md`（1199 文件 694.3MB，先 Tier1+Tier2）。
- **同步方式**：本机已装 `.git/hooks/post-commit` 自动推送钩子（见 `docs/SYNC.md`）。
- 本轮同时修正 `docs/APPEARANCE.md` 中 512/硬度旧口径与重复 §4 编号。
