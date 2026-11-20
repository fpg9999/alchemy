# ALCHEMY（炼金术化学系统）

这是元素反应/骨架分类/自然环境的完整研究工作区。

**第一次接手请先读 [`HANDOFF.md`](HANDOFF.md)。**

> **T83 九元素环境三轴切片（2026-11-20，最新成果）**：质量/物态/温度三轴 + 三素力同时打开，6,998 个九元素分子投入 240×160 方格硬边界世界（1,000°C → 900 拍冷却到 73.4°C），骨架方块渲染 4 个 22×16 切片 + 13×9 原地放大；质量三档 y 均值 33.0/79.2/111.6 行、物态 气 46.0%/液 27.5%/固 26.5%、恒素场 ρ 0.549±0.043；1,034 团 / 最大团 1,322（21.7%）、顶部 10 行「浮膜」（22.0%）；成功反应 5,199 次、2,032 种分子式、734 种目录外新物质。报告 [`docs/T83_ENV_AXES.md`](docs/T83_ENV_AXES.md)、图 `images/t83_slices.png`。

> **T82 九元素环境切片（2026-11-20）**：150×110 环面 1,599 个九元素小分子 → 1,425 分子、1,005 次反应、701 种分子式、188 种目录外新物质、9 元素严格守恒；报告 [`docs/T82_ENV_SLICES.md`](docs/T82_ENV_SLICES.md)、图 `images/t82_slices.png`。

> **T81 三素相互作用公式（2026-11-20）**：把"聚/散/动"从能力标签落成**可计算点值 + 配对公式**——**聚素=吸引力**（O3/X2/C1 点）、
> **散素=覆盖半径**（K3/A2/F1 点）、**动素=排斥力**（P3/W2/L1 点）；对 84,225 条目录全目录校准（同种净吸 80,396 = 95.5%、强粘 69,046 = 82.0%、
> 无作用/自斥 3,829 = 4.5%），方阵环面 8 邻域动态验证（强吸引物种成团 max_comp 4~5，无聚素/自斥物种 0 键），夜间扩展网格 25 组 κ × 3 混合 × 3 seed
> 定性不变（选择性 0.772~0.829）。**诚实结论**：同种强吸引 + 异种双弱成立；**力是动力学加速器而非终态决定者**；"体生长"需不对称机制
> （食物不自粘 / 体更强 / 主动抓取，即 T80 模型）。代码 [`alchemy/three_su.py`](alchemy/three_su.py)，报告 [`docs/THREE_SU_AXES.md`](docs/THREE_SU_AXES.md)，
> 图 [`images/t81_su.png`](images/t81_su.png)。

> **T80 / T79 生命追问（2026-11-19）**：T80 按用户澄清把问题改成**组装体生长**（主体 A 的组装体吞小分子 → 合成新 A → 并入自身）：能长，但体是动态组装体
> （会解体再重组）、生长全靠外部食物、无边界/遗传/复制/稳态，且抓取与并入是脚本化主动步骤 → **不算生命**
> （[`docs/T80_ASSEMBLY_LIFE.md`](docs/T80_ASSEMBLY_LIFE.md)、[`images/t80_assembly.png`](images/t80_assembly.png)）；T79 在 84,225 目录中搜索
> "单分子自催化生长" → **无此类生命**，只找到端帽聚合物生长体（[`docs/T79_LIFE_SEARCH.md`](docs/T79_LIFE_SEARCH.md)）。

> **T78 九元素三轴环境实验（2026-11-19）**：在 4×2 km² 竖直「中·气·温」介质箱里投入 **1,793 个等量价数九元素分子**
> （120 分子式、18,222 原子、9 元素各约 2020）跑 240 分钟，三轴全部跑通：**质量→重力**（轻/中/重 y 均值 3936.5 / 2330.6 / 91.4，
> 重贴底、轻贴顶）、**物态→碰撞**（气-气穿过、液-液黏附、固-固阻挡，mode_counts 与实际反应率一致）、
> **温度→恒素富集**（终态局部 ρ 与局部平均温度 r=0.957）；恒素门控把 13,329 次成功反应中 **70.6% 压到顶部富集带**，
> 产出 **810 个目录外新物质**（全部不在 84,225 目录内）；三臂（main/nogate/nochem）元素守恒与漏斗全部闭合。
> **但 T78 不收敛**（607 种终态、双原子小分子主导），与 T62 的 `LF`+`OXCPWKA` 双组分不动点对照——收敛依赖退火+整理+全局混合，
> 不是九元素+等量价数本身的性质。详见 [`docs/T78_THREE_AXIS_ENV.md`](docs/T78_THREE_AXIS_ENV.md)、
> 独立分析 [`docs/T78_ANALYSIS.md`](docs/T78_ANALYSIS.md)（27 格缺轴碎片修正 / ρ0.6 桶 rate 三重解释 / 与 T62 高温爆裂相对照）、
> 独立验证 `t78_verify_report.json`（16/16 PASS）与 [`images/t78_overview.png`](images/t78_overview.png)；
> 终产物分层图 [`images/t78_products.png`](images/t78_products.png)（每层有哪些物质/多少/结构形态）+
> [`images/t78_products_matrix.png`](images/t78_products_matrix.png)（物种×层分布矩阵），脚本 `t78_three_axis_env.py`（自包含，不改内核）。

> **物质三轴定稿同步（2026-11-19，最新）**：远端 `c438fef`「rules: 三轴定为 质量/物态/温度（碰撞/重力/恒素富集），27 格行为表」
> 已拉到本地，与本地设计提交 rebase 干净，并已随 T78~T83 一起推送（HEAD 见 `TRANSFER.md` §0）：
> 物质分类的权威定义改为 [`docs/MATERIAL_AXES.md`](docs/MATERIAL_AXES.md)——**质量**（三价 O3/K2/P1，按层平均，阈值 1.67/2.30）→ 轻/中/重 → 重力 上升/悬浮/下沉；
> **物态**（二价 X3/W2/A1，1.70/2.22）→ 气/液/固 → 碰撞 穿过/游泳/阻挡；**温度**（一价 F3/L2/C1，1.50/2.00）→ 冷/温/热 → 恒素 稀薄/中性/富集；
> 三轴组合成 **27 格行为表**，浮力 `F=(介质质量−物体质量)×体积`（`alchemy.attrs.buoyancy`）。原「物性 = 密度/粘性/温度」作废，
> [`docs/TRAITS.md`](docs/TRAITS.md) 仅留历史记录。本轮同时补入本地设计定稿：[`docs/THERMAL_DIMENSION.md`](docs/THERMAL_DIMENSION.md)（温度维度 v2）、
> [`docs/ABILITY_CATALOG.md`](docs/ABILITY_CATALOG.md)（能力候选 11 域 110 项）、[`docs/ABILITY_PRIMITIVES.md`](docs/ABILITY_PRIMITIVES.md)（基础能力原子 6 类 36 个）。

> **内核入库（2026-11-18）**：规则 1~11 与大锅反应已从根目录脚本抽成**独立纯标准库内核包 [`alchemy/`](alchemy/README.md)**——
> 四入口 `simulate` / `embed`+`validate` / `get_catalog` / `classify`（另有 `trace`），`rules=8|9|11` 是单份参数化实现，
> 84,225 条目录**已 100% 切到规则 1~11 口径**（14,745 条 = 17.51% 结构被替换，分子式不变）；同时把新规则写成 9 份正式文档：
> 三轴判相（[`docs/THREE_AXES_FINAL.md`](docs/THREE_AXES_FINAL.md)：概念族 刚/粘/松 × 物态 固/液/气 × 能量 冰/焰/电，27 型全覆盖）、
> 物相规则（[`docs/PHASE_RULE.md`](docs/PHASE_RULE.md)）、口径分歧（[`docs/CALIBER_DIVERGENCE.md`](docs/CALIBER_DIVERGENCE.md)）、
> 能力（[`docs/ABILITY.md`](docs/ABILITY.md)：聚/散/动 三项数值 + 9 项次级能力三阶，旧 512 体系冻结作历史）、外观（[`docs/APPEARANCE.md`](docs/APPEARANCE.md)）、
> 物质三轴（现行 [`docs/MATERIAL_AXES.md`](docs/MATERIAL_AXES.md)：质量/物态/温度 → 27 格行为表；
> 原 [`docs/TRAITS.md`](docs/TRAITS.md) 的「密度/粘性/温度 → 3³ = 27 格」方案已废弃，仅历史）+
> 群系规格/候选（[`docs/BIOME_SPEC.md`](docs/BIOME_SPEC.md)、[`docs/BIOME_CANDIDATES.md`](docs/BIOME_CANDIDATES.md)）。
> **150 项测试全绿**（`python tests/run_all.py`，约 16~27s），另有 4 个示例脚本与群系物种图；整理分析见
> [`docs/KERNEL_INTAKE.md`](docs/KERNEL_INTAKE.md)。

> **第二轮同步（2026-11-19）**：远端 `facb162`（三价轴属性 硬度→**密度**、物性改成 **3³ = 27 格**、能力改成**类别辐条三项数值**
> 并加 **9 项次级能力三阶**）+ `cf9d01b`（`docs/SYNC.md` 记 post-commit 自动推送钩子）已拉到本地（网络受限，经 GitHub API/raw 逐文件取回，
> 内容与上游一致；本地提交 `7516ce0`，未 push）。另新增 [`docs/REPO_SLIM.md`](docs/REPO_SLIM.md)（694.3MB 仓库体积治理），
> 第二轮整理分析（属性/能力/表现层）见 [`docs/INTAKE_R2.md`](docs/INTAKE_R2.md)。

> **最新进展（2026-11-18）**：2D 粒子环境实验已完成 **T55~T67** 系列——T59 两阶段九元素
> （三价最多）、T62 两阶段九元素（三/二/一价等量，收敛到 `OXCPWKA`+`LF` 1:1 双组分）、
> T63 聚素熔体逐级价数滴定（纯聚素退火 → 加 F2 → 加 A2 → 加 K2，每次投放都整体换代）、
> **T64 生态群系**（12 个"元素社区"：3~9 种元素、1000→25°C 退火 + 25°C 恒温浮动，
> 纯族收敛为单一三元分子，B08 形成 `O2X2P2W2K2` 十原子簇，B11 复现 `LF`+`OXCPWKA` 双组分）、
> **T65 生态群系第二轮**（10 个群系、每群系 ≥4 种元素：产物更杂更大更多新物质，
> 但纯杂由价数互补与端帽决定——C03 98.4% 单一 `XPLA`、C06 93.6% 十原子簇 `O2X2P2K2A2`、
> C09 缺 F 时 26 种/488 新物质；C10 与 T64 B11 同种子逐项复现）、
> **T66 生态群系第三轮（化合物播种）**（10 群系与 T65 一一对应，约 37.5%~60% 原子以化合物/
> 骨架投入：**终态组成余弦 10/10 对 ≥0.9999、top1 8/10 相同**，但 capped 平均少 980 次、
> 净事件少 19.8%——初始化学形态记忆≈0（组成）、路径记忆显著（动力学））、
> **T67 生态群系总目录**（32 个群系按终态专一性分四类：**A 单主 10 / B 主辅 11 / C 双主 7 /
> D 多主 4**；类别由元素角色配比 + 温度日程决定、初始形态无关；特色 Top10 见报告）；
> T61/T62/T63/T64 另有全部大分子的严格六边形棋盘格摆放图。详见
> [`docs/T67_BIOME_CATALOG.md`](docs/T67_BIOME_CATALOG.md)、
> [`docs/T66_BIOMES.md`](docs/T66_BIOMES.md)、[`docs/T65_BIOMES.md`](docs/T65_BIOMES.md)、
> [`docs/T64_BIOMES.md`](docs/T64_BIOMES.md)、
> [`docs/T63_STAGED_TITRATION.md`](docs/T63_STAGED_TITRATION.md)
> 与 [`docs/T62_EQUAL_VALENCE.md`](docs/T62_EQUAL_VALENCE.md)、[`docs/T60_SERIES_SUMMARY.md`](docs/T60_SERIES_SUMMARY.md)。
>
> **图形阶段（2026-11-17~18，最新）**：T68 大分子骨架形状语言 + 36 个 ≥14 原子稳定大分子图册
> （[`docs/T68_GIANT_ATLAS.md`](docs/T68_GIANT_ATLAS.md)、[`docs/T68_GLYPH_SYSTEM.md`](docs/T68_GLYPH_SYSTEM.md)）、
> T69 连接件与端帽（元素隐去版，[`docs/T69_SKELETON_SHAPES.md`](docs/T69_SKELETON_SHAPES.md)）、
> T70 生成式形状语言（超公式骨架 + 编织腱/褶幕桥 + 冰锥/飘带/螺旋丝端帽，
> [`docs/T70_EMERGENT_GLYPHS.md`](docs/T70_EMERGENT_GLYPHS.md)）、
> T70b 整体形体画法（块/桥/端帽并入同一剪影，一个分子看起来像一件完整物质，
> [`docs/T70B_WHOLE_BODY.md`](docs/T70B_WHOLE_BODY.md)）。
>
> **能力与方块世界阶段（2026-11-18，历史口径）**：T71 每种骨架的能力与分化（30 能力/6 形态，结构门控生命度）、
> T72 能力扩到 72 项 ×9 类 + 28 种分化形态 + 小分子形态；T73 器官按位置/朝向选形态、形态**直接代替器官外形**
> （[`docs/T73_MORPH_GEOMETRY.md`](docs/T73_MORPH_GEOMETRY.md)）；T74 分类规则改为按价数元素判定；
> **T75 方块世界**：每个骨架 = 1 个单位方块，物质 = 若干方块拼成（外观仍以此为主规范）
> （[`docs/T75_BLOCK_WORLD.md`](docs/T75_BLOCK_WORLD.md)）；**T75b** 属性改为**逐骨架**计算、连接桥不计入；
> **T76 桥的功用标签**（刚性焊接/铰接/定距隔空/多点编织…，[`docs/T76_BRIDGE_FUNCTIONS.md`](docs/T76_BRIDGE_FUNCTIONS.md)）。
> 注意：T71/T72 的能力项、T75/T75b 的「硬度」与逐骨架口径、T74 的 27 型并列序均已被新成果取代——
> 现行能力见 [`docs/ABILITY.md`](docs/ABILITY.md)（v3 三项 + v4 九项三阶），现行物质三轴见
> [`docs/MATERIAL_AXES.md`](docs/MATERIAL_AXES.md)（质量/物态/温度 → 27 格行为表；`TRAITS.md` 的密度/粘性/温度方案已废弃），
> 能力→器官→生命的新设计见 [`docs/ABILITY_EMERGENCE.md`](docs/ABILITY_EMERGENCE.md)。

## 快速开始

1. 安装 Python 3.10+，并安装 Pillow（绘图脚本需要）：
   ```powershell
   pip install -r requirements.txt
   ```
2. 如果 `t4_catalog_all_validated.json` 等大文件不存在（clone 后通常只有 `_data_gz/`），先解压：
   ```powershell
   python unpack_data.py
   ```
3. 跑内核示例（推荐；在仓库根目录执行）：
   ```powershell
   $env:PYTHONIOENCODING="utf-8"      # Windows GBK 控制台需要，否则 demo 的 ✓/→ 会报 UnicodeEncodeError
   python examples/demo_kernel.py     # 四入口演示 + 骨架分类表
   python tests/run_all.py            # 150 项测试（约 16~27s）
   ```
4. 兼容旧根脚本的大锅反应示例：
   ```powershell
   python -c "import pot_v4; print(pot_v4.simulate(['O','K']))"
   ```
5. 群系候选示例（需 Pillow 才能出图）：
   ```powershell
   python examples/build_biome_candidates.py   # 复算 data/biomes/candidates/（约 26s）
   python examples/render_species_sheets.py    # 46 种物种 → 4 页图
   ```

## 目录

- `alchemy/`：**内核包（纯标准库）**——四入口大锅/摆放/目录/分类，另有 `phase`（三轴判相 v4）、`ability`（能力 v3 三项数值 + v4 九项次级三阶，512 冻结作历史）、`attrs`（物质三轴：质量/物态/温度 → 27 格行为表 + 浮力 `buoyancy`）、`biome`（群系物种表）、`ops`（9 操作能力）与 `emergence`（组装体→器官→生命原型）；见 [`alchemy/README.md`](alchemy/README.md)；
- `tests/`：内核测试（`test_*.py` + `run_all.py`，150 项用例）；`examples/`：内核/群系示例与出图；
- `pot_all.py` / `pot_v2.py` / `pot_v3.py` / `pot_v4.py`：历史大锅反应与几何校验脚本（规则 1~11 已迁入 `alchemy/`，`pot_v4.py` 保留为兼容实现）；
- `natural_engine.py` / `fast_pot.py` / `t55_kinetic_env.py`：自然环境引擎与 2D 粒子环境；
- `t4_*` ~ `t76_*`：各阶段研究脚本/数据（编号=任务阶段；T71~T76 为能力/形态/方块世界）；
- `docs/`：全部研究报告（`T*.md`）；新规则正式文档为 `THREE_AXES_FINAL.md` / `PHASE_RULE.md` / `CALIBER_DIVERGENCE.md` / `MATERIAL_AXES.md`（物质三轴现行口径）/ `ABILITY.md` / `APPEARANCE.md` / `BIOME_SPEC.md` / `BIOME_CANDIDATES.md`（`TRAITS.md` 已被 `MATERIAL_AXES.md` 取代，仅历史），另有本地设计文档 `THERMAL_DIMENSION.md` / `ABILITY_CATALOG.md` / `ABILITY_PRIMITIVES.md`，本次入库整理见 `KERNEL_INTAKE.md`；`docs/templates/` 放报告模板（如 `t60_report_template.md`）；
- `data/biomes/`：群系模板物种表（`t*.csv/json`，12 组）、候选群系（`candidates/`，5 个 + `_union` 121 种）与模板目录 `_catalogue.json`；
- `images/`：全部结果图（T68~T70b 的图册按 `t68_*`/`t69_*`/`t70_*`/`t70b_*` 命名；内核的群系物种图在 `images/biome_candidates/`）；
- `_data_gz/`：大数据的 gzip 版本 + `manifest.json`（GitHub 传输用）；
- `tools/`：跨电脑传输工具（`make_transfer_archive.py` 重新生成全量 zip、`pack_transfer_data.py` 打包 `_data_gz/`）；
- `archive/`：历史脚本与旧数据，已按阶段/主题分子文件夹（`archive/README.md` 有对照表）。

## 跨电脑交接

见 [`TRANSFER.md`](TRANSFER.md)：GitHub / 全量 ZIP / git bundle 三种方式。
2026-11-18 清理时已删除工作区里 2026-11-14 的旧 ZIP / bundle 快照（内容已被 GitHub 上的 T01~T70b / T71~T76 / kernel 提交覆盖）；
需要新的离线包时运行 `python tools\make_transfer_archive.py` 重新生成。
