# task-7 过时内容清扫报告

- 任务：把 alchemy 仓库中仍按旧口径书写的"当前状态"内容改为新成果口径；历史文档只加顶部横幅。
- 执行：stale-sweeper（teammate），2026-11-19。
- 仓库：`G:\AI work\deepseek\work1\alchemy`（Windows + PowerShell，`python` 3.11）。
- 基线：`python tests/run_all.py` → **ALL 124 TESTS PASSED (17.8s)**，git HEAD `2916777`，工作树干净。
- 收尾：**ALL 124 TESTS PASSED (16.7s)**，`exit=0`；未 commit / push。
- 改动量：`git diff --stat` → **35 files changed, 272 insertions(+), 178 deletions(-)**。
- 授权外文件（HANDOFF / 根 README / INDEX / TRANSFER / docs/KERNEL_INTAKE / docs/INTAKE_R2 /
  docs/APPEARANCE / intake 其他人的 md）**一律未改**（详见 §8）。

## 0. 结论

| 项 | 结果 |
|---|---|
| 全量测试 | 124 / 124 PASS（16.7s） |
| data/biomes 复算差异 | json=0、csv=0、多余物种=0、union 旧路径=[]（脚本 `--check` exit 0） |
| data/biomes 差异修复 | 30 个物种 × label+shape（json+csv 共 120 处）+ 5 处 `spec.source` |
| 代码 docstring | attrs.py、ability.py、phase.py、tests/test_phase.py 四处 |
| 现行文档 | docs/ABILITY.md（结构改造）、TRAITS.md、BIOME_SPEC.md |
| 历史横幅 | T71、T72、T74、T75、T76 五个文件，仅加顶部横幅，正文未动 |
| 入口文档 | NEW_CHAT_PROMPT.md、alchemy/alchemy/README.md（包内 README） |
| API 行为 | 无改动（只改 docstring / `__all__` / 文档 / 数据字段值） |

## 1. 判定口径（以什么为准）

- 权威新口径来源（Lead 已整理，本次只读参考）：根 `README.md` 顶部两段、`docs/INTAKE_R2.md`、
  `docs/ABILITY.md` §0、`docs/TRAITS.md`、`docs/BIOME_SPEC.md`。
- 现行内核事实（本次实测）：
  - 物性 = **密度 / 粘性 / 温度** 三数值，阈值分档 → **3³ = 27 格**（`alchemy/attrs.py`）；
  - 能力 = **v3 三项数值（聚/散/动）+ v4 九项次级能力 × 三阶**（`alchemy/ability.py`），旧 **512 冻结**；
  - 相分类 = **phase v4 `hybrid` 默认**（两两并列循环压制、三者全等归聚、无第四相），
    `cycle` / `hierarchy` 为历史兼容模式（`alchemy/phase.py`）；
  - 群系物种表 = 当前内核 `rules=11` 复算结果（`alchemy/biome.py`）。
- 历史口径（已被取代，保留背景）：T71 能力/生命度、T72 72 能力×28 形态、T74 旧 27 型、
  T75/T76 的"硬度"及"桥不计入"。

## 2. 代码 docstring（逐项）

### 2.1 `alchemy/attrs.py`

| 位置 | 原表述 | 新表述 | 验证 |
|---|---|---|---|
| 模块 docstring 用法示例（:24~35） | `A.property_of(A.attrs_of("OXC"))["cell"] -> '密-低\|粘-低\|温-中'` | `-> '密-低\|粘-低\|温-低'`，并补 `["index"] -> 0`，附注"档位一律以 `property_of` 实际输出为准（OXC 温度 1.0 落在 (3,6) 之下，是温-低不是温-中）" | `python -c` 实测 OXC：density 3.0 / stickiness 3.0 / temperature 1.0 → grades 全低，cell `密-低\|粘-低\|温-低`，index 0；另测 OXCPWKA→index 3、O2X3C3K3A3→index 16、F2→温-高，全部与 docstring 一致 |

### 2.2 `alchemy/ability.py`

| 位置 | 原表述 | 新表述 | 验证 |
|---|---|---|---|
| 模块 docstring（:2~30） | 标题"能力系统：三条轴 × 每轴 8 种情况 = 512 种复合能力"；正文把 512 当现行（"3 + 3 + 1 + 1 = 8 种/轴，三条轴复合 → 8³ = 512 种能力"） | 标题改"v3 三项数值能力（聚/散/动）+ v4 九项次级能力（三阶）"；正文列 v3 三主方向权重表（O/X/C=3/2/1 等）、v4 九项次级能力与阈值（结构支撑 6,12 / 刚性 2,6 …）、`SUB_TIERS` 三阶规则、`MAIN_TH`、并存不组合；旧 512 单列"## 历史口径（已冻结）"并注明全目录只出现 308/512 | 实测 `AB.scores("OXC")` → `(6.0, 0.0, 0.0)`；`AB.profile("OXC")["main"]["poly"]["tier"]` → `'低'` |
| 同一 docstring 用法示例 | `AB.ability_of("OXCWKAF")["label"]` → `'秩\|晶\|冰'`（错误） | `'秩沌\|三合\|冰焰'`（实测值），并注明"历史 512 接口，行为不变" | `python -c` 实测三者：OXC id `O\|X\|C`、OXCWKAF label `秩沌\|三合\|冰焰`、O2X2P2W2K2A2 id `ALL\|ALL\|NONE` |

未改 `ability_of()` / `distribution()` / `catalog_combos()` 的实现与 `__all__`；512 接口可继续调用。

### 2.3 `alchemy/phase.py`

| 位置 | 原表述 | 新表述 | 验证 |
|---|---|---|---|
| 模块 docstring（:2~33） | "## 规则 v2（2026-11-17 备选方案：循环压制 + 第四相）"；"``mode="cycle"``（默认，v2 方案）与 ``mode="hierarchy"``（v1 方案）只差两点" | "## 规则 v4（2026-11-18 定稿：两两并列循环压制、三者全等归聚）"；判据 3 条明确"默认 mode=hybrid、永不产生第四相"；"## 三种模式"表（hybrid 默认 / hierarchy=v1 / cycle=v2 遗留已弃用）；"## 第四相与'无该层'（仅遗留 cycle 模式）" | `F.DEFAULT_MODE` → `'hybrid'`；`F.phase_of("OXC")["label"]` → `'秩·固·冰'`；`F.phase_of("O2XP2WK2A2")["id"]` → `'O/A/C'`；`F.phase_of("OXC", mode="cycle")["n_fourth"]` → 0 |
| `__all__`（原 :61~70） | 缺 `FRAME_ADJ` / `ENERGY_ADJ` / `STATE_NOUN` / `TYPICAL` / `physical_name` / `describe` | 补齐上述 6 个公开名（不删不改原有名） | `python -c "import alchemy.phase as F; [print(n, hasattr(F,n)) for n in (...)]"` 全部 True；单测 test_phase 16 项仍绿 |
| `role_of()` docstring | 标题"刚体 / 胶体 / 软体 / 晶体"，表含"晶体 第四相 三种键各 1/3"行 | 标题"刚体 / 胶体 / 软体（v4 只有这三态）"，删晶体行，加注"晶体已并入刚体（v4）：hybrid/hierarchy 不产生第四相，只有遗留 cycle 才可能" | `F.role_of("OXC")` → `{'element':'O','role':'刚体','phase':'秩','kind':'strict','count':1,...,'fourth_source':None}`；`F.physical_name("OXC")` → `'刚性低温固体'` |
| `state_of()` / `energy_of()` docstring | "固 / 液 / 气 / 虚"；"冰(冷) / 焰(热) / 电(电磁与光) / 无属性。第四相（三种能量抵消）= 无属性" | 分别注明"`虚` 只在遗留 `cycle` 模式出现"、"`无属性` 只在遗留 `cycle` 出现" | 同上 phase 实测（hybrid 下不出现 `虚` / `无属性`） |
| `describe()` docstring | 只列返回键，未说明 `hardness` 等字段口径 | 补 `'id'` 键；注明 `hardness`/`density`/`cohesion` 是概念族相对展示档位 1~4、历史表现层字段、与 attrs 27 格口径不同不可混用 | `F.describe("OXC")` → hardness 3 / density 4 / cohesion 4 / gravity True / typical `'岩石、金属、水晶'` |

### 2.4 `tests/test_phase.py`

| 位置 | 原表述 | 新表述 | 验证 |
|---|---|---|---|
| :2 docstring | "相分类规则：三条轴 + 两两并列循环压制 + 三者全等第四相。"（旧 v2 口径，且与同文件 `test_hybrid_is_the_default_rule` 矛盾） | "相分类规则：三条轴 + hybrid 默认（两两并列循环压制、三者全等归聚、无第四相），cycle/hierarchy 为历史兼容模式。" | 该文件 16 项测试全绿；`test_hybrid_is_the_default_rule`、`test_no_fourth_phase_by_default`、`test_three_way_tie_is_fourth_phase`（cycle）通过 |

## 3. 现行文档

### 3.1 `docs/ABILITY.md`（结构改造）

| 位置 | 原表述 | 新表述 | 验证 |
|---|---|---|---|
| 标题 / 文件头 | 标题"能力系统：从 512 离散状态到三项数值"；测试"`tests/test_ability.py`（115 项全通过）"；"§1~§4 描述的 512 体系…保留作历史" | 标题"能力系统：v3 三项数值 + v4 九项次级三阶（附 512 历史口径）"；测试改"test_ability.py 26 项、全仓库 run_all.py 124 项全通过"；正文明确"当前口径 §0（v3+v4），512 整体冻结" | 测试计数与实际一致（test_ability 26 个、总 124）；`grep 115` 无残留 |
| §0 | "## 0. v3：能力 = 三项数值（当前口径）"；"### 0.1 三主方向 × 三次级能力 × 三阶"（v4 内容却挂在 v3 标题下） | 拆为 "## 0. v3 + v4：能力 = 三项数值 + 九项次级三阶（当前口径）" + "### 0.1 v3：三个主方向 = 三项数值" + "### 0.2 v4：九项次级能力 × 三阶（默认输出）" | 目录层级连续；v4 节内容未改 |
| §1~§4 | `## 1. 规则`、`## 2. 全目录实测`、`## 3. 收紧方案`、`## 4. 用法`（与 §0 并列，像现行章节） | 统一降级为 "## 附：v2 512 历史口径（已冻结，仅作对照）" 下的 `### A. 规则（v2 512）`、`### B. 全目录实测…`、`### C. 收紧方案（v2 讨论记录，已作废）`、`### D. 用法（512 历史接口，冻结但可调用）`；A~D 子标题同步降一级 | 标题扫描无并列的 §1~§4；`ability_of` 示例仍实测正确（OXC label `秩\|晶\|冰`、OXCPWKA id `ALL\|ALL\|C`） |
| §5 | "## 5. 当前三层职责"：物性=硬度/粘性/温度；能力=三轴各 8 种情况复合（512 已冻结） | "## 1. 当前三层职责（现行）"：物性=密度/粘性/温度 + 两级阈值 → 27 格（`attrs.py`，链接 TRAITS）；能力=v3 三项数值 + v4 九项次级三阶（`scores`/`profile`），v2 的 512 已冻结；外观不变 | 表内三层与 `alchemy/attrs.py`、`alchemy/ability.py` 实现对得上 |
| §6 | "512 还是收紧到 384/256：未定"；"与 phase.py 的关系：phase.py 的 27 型已被本模块取代" | "已定：不收紧——v3/v4 直接取代，512 冻结（全目录实测 308/512）"；"不取代——phase 27 型与 v3/v4 能力同层并列、互不换算，被取代的是 T74 旧 27 型" | 结论与根 README / INTAKE_R2 口径一致 |
| §0.2 其他约定 | "次级能力名取自 T71 材料层能力表" | 追加"（T71 整体已被取代并加历史横幅，但 9 项命名仍沿用该表）" | 与 T71 横幅一致 |

### 3.2 `docs/TRAITS.md`

| 位置 | 原表述 | 新表述 | 验证 |
|---|---|---|---|
| 文件头 | 测试"`tests/test_attrs.py`（113 项全通过）" | "tests/test_attrs.py 13 项、全仓库 run_all.py 124 项全通过" | test_attrs 13 项、总 124 |
| §2 阈值 | 只写"编号 0~26，格式 密-X\|粘-Y\|温-Z" | 补编号公式 `index = 密档 + 粘档×3 + 温档×9`（低=0/中=1/高=2）；补"档位与编号以 `property_of()` 实际输出为准"及严格不等号规则 | 实测 OXC=0、OXCPWKA=3、O2X3C3K3A3=16、F2=2，与公式一致 |
| §4 用法 | `p["index"]  # 0~26` | `# 16（密档1 + 粘档2×3 + 温档1×9）` | 同上 |
| §5 三层职责 | 能力="三轴加权和 + 元素占比（ability.scores）"；外观="T75 方块世界（docs/APPEARANCE.md）" | 能力="v3 三轴加权和 + 占比，v4 再切九项次级三阶（ability.profile）"；外观="沿用项目现有骨架外观规范（docs/APPEARANCE.md，T68~T75）" | 与实际模块/文件对应 |

### 3.3 `docs/BIOME_SPEC.md`

| 位置 | 原表述 | 新表述 | 验证 |
|---|---|---|---|
| §2 字段表 | `shape` = "团/环/链/星/孤核" | "团/星/环/链/孤核（`孤核` 仅当 `natoms <= 1`）" | 与 `alchemy/biome.shape_label` 实现一致 |
| §4 复现命令 | `B.template_catalogue(sorted(Path('.').glob('t*_result.json')), ...)`（仓库根有 50+ 个 `*_result.json`，会多取模板） | 显式 12 模板元组 `T=('t55_kinetic','t56_kinetic','t57_area','t58','t59_phaseA','t59_phaseB','t62_phaseA','t62_phaseB','t63_phase1','t63_phase2','t63_phase3','t63_phase4')` 再 `template_catalogue([Path(t+'_result.json') for t in T], ...)`；并加注"勿用 t*_result.json 通配" | 12 个模板名与 data/biomes 实际 12 组文件逐一核对 |
| §4 数据口径 | 无说明 | 加注：data/biomes 的 `label`/`shape` 已按当前内核（rules=11）复算刷新（旧快照曾把链/环误记为孤核）；`_union.json` 的 `spec.source` 已统一为相对文件名 | 见 §5 复算与 `--check` 结果 |

## 4. 历史文档顶部横幅（正文未重写）

统一格式：H1 标题后插入 `> **历史口径提示（2026-11-19）**` 引用块（按 task-7 第 8 条要求），说明旧口径、新口径与链接。

| 文件 | 原文开头（旧口径关键句） | 横幅要点 | 验证 |
|---|---|---|---|
| `docs/T75_BLOCK_WORLD.md` | "用户 (m02325) 的新规则：…三价元素决定**硬度**、二价元素决定**粘性**、一价元素决定**温度**" | 第三条"硬度"已被内核**密度/粘性/温度 → 3³=27 格**取代；文中硬度按旧口径读，不要当现行属性；外观权重 1.20/0.90/0.60 与内核 3/2/1 两套并存无换算表（INTAKE_R2 §4/§6） | `git diff` 仅 +5 行（横幅），正文 0 改动 |
| `docs/T76_BRIDGE_FUNCTIONS.md` | "桥…**不参与硬度/粘性/温度计算**，它是纯粹的功能件" | 本文硬/粘/温是 v2 口径；现行物性是密度/粘性/温度 27 格；**桥（X/W/A）照常参与粘性计算（权重 3/2/1）**，"不参与"只反映旧划分 | 同上（+5 行）；attrs 实测桥原子计入 `stickiness` |
| `docs/T71_ABILITIES.md` | "# T71 骨架能力与涌现生命" + 两层能力模型/生命度打分 | 能力清单与"生命度"已被 ABILITY.md 的 **v3+v4** 取代；仅"材料层能力"9 项命名仍被 `ability.py` 沿用，生命度等不再作现行判据 | 同上（+5 行） |
| `docs/T72_ABILITIES_MORPHS.md` | "能力扩到 **72 项 / 9 大类**…7 家族 × 4 种具体形态 = **28 种**" | 72 项能力/28 形态口径已被 v3/v4 取代；外观与形态层沿用 APPEARANCE，不再按 28 种分化实现 | 同上（+5 行） |
| `docs/T74_CLASSIFICATION.md` | "## 1. 固/液/气…并列时优先 X>W>A…"（旧 27 型分类规则） | 旧 **27 型分类**已被 phase v4（hybrid 默认、无第四相）+ 能力 v3/v4 + 物性 27 格共同取代 | 同上（+5 行） |

注：上述五个文件正文一字未动，`git diff` 均为 5 insertions / 0 deletions。

## 5. `data/biomes/` 旧快照复算与覆盖

### 5.1 复算方法

- 用当前内核复算：`alchemy.biome.load_result(<tag>_result.json)` + `abundance_table(run)`（默认 `rules=11`），
  逐物种取 `label`（`systematic_name`）与 `shape`（`shape_label`）。
- 与 `data/biomes/*.json` / `*.csv` 快照逐字段比对：**只有 `label`、`shape` 两字段有差异，其他字段 0 差异**。
- 备份：`intake/tmp/stale/backup/data_biomes/`（改动前完整副本）。
- 脚本：`intake/tmp/stale/fix_biomes.py`（复算 → 只替换差异字段 → 保留原 JSON/CSV 字节格式 → 自检；
  `--check` 只检不写）。修改日志：`intake/tmp/stale/biome_fix_log.json`（125 条 = 120 字段 + 5 路径）。
- 格式保持：JSON `ensure_ascii=False, indent=1` + CRLF + 无末尾换行；CSV `utf-8-sig` + CRLF + `QUOTE_MINIMAL`。
  改动前已验证未改动文件可被同一序列化器字节级复现；改后 diff 只涉及目标行。

### 5.2 差异清单（13 处指定 + 17 处同类 = 30 个物种，60 字段/格式）

指定 13 处：`t55_kinetic` 7、`t57_area` 3、`t63_phase4` 1、`t62_phaseB` 2。
同类自查追加 17 处：`t56_kinetic` 1、`t58` 3、`t62_phaseA` 2、`t63_phase1` 3、`t63_phase2` 6、`t63_phase3` 2。
全部 30 处都是同一类错误：**旧快照把 `链` 误记为 `孤核`**（本轮复算没有出现新的 `环`/`团`/`星` 差异）。

| 模板 | 物种数 | 旧 label → 新 label（代表） | 旧 shape → 新 shape |
|---|--:|---|---|
| t55_kinetic | 7 | `秩晶冰·孤核` → `秩晶冰·链`（OXC、O2X2、O2X2C4、O2XC4、O2X4、O2X3、O2C4） | 孤核 → 链 |
| t57_area | 3 | OXC / O2X2C4 / O2X4 同上 | 孤核 → 链 |
| t63_phase4 | 1 | `秩沌·孤核` → `秩沌·链`（OK） | 孤核 → 链 |
| t62_phaseB | 2 | OK / PK（`秩沌·孤核`→`秩沌·链`、`势沌·孤核`→`势沌·链`） | 孤核 → 链 |
| t56_kinetic | 1 | OK | 孤核 → 链 |
| t58 | 3 | OK / OP / PK | 孤核 → 链 |
| t62_phaseA | 2 | OK / PK | 孤核 → 链 |
| t63_phase1 | 3 | OXC / O2X2C4 / O2X4 | 孤核 → 链 |
| t63_phase2 | 6 | O2X2C2F2、OCF2、OC2F、O2X3C2F2、O2X2CF3、O2X3CF3 | 孤核 → 链 |
| t63_phase3 | 2 | OAF、O2A3 | 孤核 → 链 |

### 5.3 `candidates/_union.json` 的 `spec.source` 旧绝对路径（5 处）

| 候选 | 旧值 | 新值 |
|---|---|---|
| T55 | `D:\Alchemistry DeepSeek工作区\alchemy\t55_kinetic_result.json` | `t55_kinetic_result.json` |
| T57 | `D:\Alchemistry DeepSeek工作区\alchemy\t57_area_result.json` | `t57_area_result.json` |
| T63S4 | `D:\Alchemistry DeepSeek工作区\alchemy\t63_phase4_result.json` | `t63_phase4_result.json` |
| T62B | `D:\Alchemistry DeepSeek工作区\alchemy\t62_phaseB_result.json` | `t62_phaseB_result.json` |
| T59B | `D:\Alchemistry DeepSeek工作区\alchemy\t59_phaseB_result.json` | `t59_phaseB_result.json` |

`spec.source` 改为与同对象 `file` 字段一致的相对文件名，符合 `load_result` 的相对路径用法。

### 5.4 验证

- 修改后重跑 `python intake/tmp/stale/fix_biomes.py --check`：
  `check: json_diff=0 csv_diff=0 extra_json=0 extra_csv=0 union_bad=[]`，`exit=0`。
- `git diff --stat -- data/biomes`：21 files changed，95 insertions(+)/95 deletions(-)；
  抽查 `t55_kinetic.json` / `.csv`、`_union.json`：行序、缩进、BOM、CRLF 均不变，仅目标字段变化。
- `data/biomes/candidates/*.csv` 与 `_union.csv` 复算后 0 差异（已是当前口径），本轮未改。

## 6. `NEW_CHAT_PROMPT.md`

| 位置 | 原表述 | 新表述 | 验证 |
|---|---|---|---|
| 必读文件清单第 5 条 | "按需读 docs/ 下对应主题的 T*.md" | 补"现行口径优先：根 README 顶部、ABILITY.md、TRAITS.md、BIOME_SPEC.md、INTAKE_R2.md；T71~T76 已加历史横幅只作背景" | 文案与本次横幅一致 |
| 状态摘要"大锅反应规则" | "规则 1~11 以 **pot_v4.py** 为准…pot_v3.py 是规则 1~9 的历史实现" | "以 **alchemy/ 内核**为准（alchemy.core.reactor，rules=8\|9\|11 单份参数化）；pot_v4.py 保留为兼容实现，pot_v3.py 是历史实现" | 与 `alchemy/core/reactor.py`、包 README 规则表一致 |
| 状态摘要"迁移" | "但 84,225 目录结构仍是规则 1~9 口径…迁移待做" | "84,225 条目录**已 100% 切到规则 1~11 口径**（14,745 条 = 17.51% 结构被替换，分子式不变），迁移已完成" | 与根 README 顶部"已 100% 切到规则 1~11"一致 |

其余 T55~T66 历史实验摘要未动（属历史记录，不是现行状态）。

## 7. `alchemy/alchemy/README.md`（包内 README）

| 位置 | 原表述 | 新表述 | 验证 |
|---|---|---|---|
| "规则版本"表 | 权威实现列 `pot_all.simulate` / `pot_v3.simulate` / `pot_v4.simulate`，rules=11 "当前正式" | 权威实现改为内核 `alchemy.core.reactor`（单份参数化），`pot_*` 降为"兼容/历史实现"；rules=11 仍为当前正式 | 与 `tests/test_equivalence.py` 差分测试及 reactor 实现一致 |
| "目录结构" | 只有 `core/` 与 `data/`，缺 phase/ability/attrs/biome | 增 `phase.py` / `ability.py` / `attrs.py` / `biome.py` 及各自口径说明；`__init__` 注"四个入口，另有 trace"；`tests/` 注 124 项 | `ls alchemy/*.py` 与实现核对；无 106/512 旧数残留（grep 空） |
| 新增段落 | — | 指向 `docs/ABILITY.md`（能力）、`docs/TRAITS.md`（27 格）、`docs/BIOME_SPEC.md`（群系）；说明 T71~T76 已加历史横幅 | 链接文件均存在 |

## 8. 越权发现（未改 / 已按授权回退）

清扫过程中发现以下"当前状态"内容仍过时，但文件**不在 task-7 授权范围**，仅记录交 Lead：

| 文件 | 位置 | 旧表述 | 建议 |
|---|---|---|---|
| 根 `README.md` | 快速开始第 3 步 | `python tests/run_all.py  # 106 项测试（约 21~27s）` | 改 124 项（约 17~27s）；同文件顶部已写 124，前后矛盾 |
| 根 `README.md` | "## 目录" | "`ability`（512 能力）"、"tests … 106 用例" | 改 v3/v4 能力、124 用例 |
| 根 `README.md` | 第三段 | T71…T75/T76 段落仍把硬度/生命度当现存设计 | 可加"历史"标注（本报告 §4 已备好措辞） |
| `docs/THREE_AXES_FINAL.md` | 全文 | 旧三轴判相文档，未提 v4 hybrid 默认/无第四相 | 待 Lead 决定是否加横幅或改现行 |
| `docs/PHASE_RULE.md` / `docs/CALIBER_DIVERGENCE.md` | 全文 | 可能仍是 v2/v3 口径 | 建议同轮清扫 |

说明：根 `README.md` 本次曾误改 4 处（三轴判相句、T71~T76 段、106→124、目录两行），发现越权后**已全部回退**；
`git diff -- README.md` 为**空**（与 HEAD 一致），未留痕迹。HANDOFF.md、INDEX.md、TRANSFER.md、
docs/KERNEL_INTAKE.md、docs/INTAKE_R2.md、docs/APPEARANCE.md 及 intake/ 下他人文件全程未改。

## 9. 验证命令与结果汇总

```powershell
$env:PYTHONIOENCODING="utf-8"
Set-Location "G:\AI work\deepseek\work1\alchemy"

# 1) 基线 / 收尾全量测试
python tests/run_all.py
#   → ALL 124 TESTS PASSED (16.7s)   exit=0

# 2) data/biomes 复算差异（只检不写）
python ..\intake\tmp\stale\fix_biomes.py --check
#   → check: json_diff=0 csv_diff=0 extra_json=0 extra_csv=0 union_bad=[]   exit=0

# 3) docstring 示例值核对（attrs / ability / phase）
python -c "import alchemy.attrs as A; print(A.property_of(A.attrs_of('OXC')))"
#   → cell '密-低|粘-低|温-低', index 0
python -c "import alchemy.ability as AB; print(AB.scores('OXC'), AB.ability_of('OXCWKAF')['label'])"
#   → (6.0, 0.0, 0.0) / '秩沌|三合|冰焰'
python -c "import alchemy.phase as F; print(F.DEFAULT_MODE, F.phase_of('OXC')['label'], F.role_of('OXC')['role'])"
#   → hybrid / '秩·固·冰' / '刚体'

# 4) 改动范围核对
git status --porcelain
git diff --stat
#   → 35 files changed, 272 insertions(+), 178 deletions(-)；README.md / HANDOFF.md 等不在列表
```

## 10. 遗留项

1. 根 `README.md` 的 106 项/512 能力/T75 硬度段落（§8）——需 Lead 或后续任务处理，本任务未授权。
2. `docs/THREE_AXES_FINAL.md`、`docs/PHASE_RULE.md`、`docs/CALIBER_DIVERGENCE.md` 未在本任务写作用域；
   其中"27 型全覆盖"等表述需按 phase v4 再核。
3. `data/biomes/candidates/_union.json` 的 `catalog`/`desc` 等文本未逐条复核（非 shape/label 差异，复算 0 差异）。
4. `data/biomes` 的 12 组 CSV/JSON 与 `examples/build_biome_candidates.py` 的导出脚本保持双份来源；
   本轮只覆盖已生成快照，未改生成脚本（脚本输出即当前口径）。
5. 本报告未列出的其他 T*.md（T55~T70 等）属历史实验记录，未做"现行状态"断言，原则上无需横幅；
   若 Lead 希望统一加"历史记录"标注，可另开小任务。
