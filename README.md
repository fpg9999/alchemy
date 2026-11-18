# ALCHEMY（炼金术化学系统）

这是元素反应/骨架分类/自然环境的完整研究工作区。

**第一次接手请先读 [`HANDOFF.md`](HANDOFF.md)。**

> **内核入库（2026-11-18，最新）**：规则 1~11 与大锅反应已从根目录脚本抽成**独立纯标准库内核包 [`alchemy/`](alchemy/README.md)**——
> 四入口 `simulate` / `embed`+`validate` / `get_catalog` / `classify`（另有 `trace`），`rules=8|9|11` 是单份参数化实现，
> 84,225 条目录**已 100% 切到规则 1~11 口径**（14,745 条 = 17.51% 结构被替换，分子式不变）；同时把新规则写成 9 份正式文档：
> 三轴判相（[`docs/THREE_AXES_FINAL.md`](docs/THREE_AXES_FINAL.md)：概念族 刚/粘/松 × 物态 固/液/气 × 能量 冰/焰/电，27 型全覆盖）、
> 物相规则（[`docs/PHASE_RULE.md`](docs/PHASE_RULE.md)）、口径分歧（[`docs/CALIBER_DIVERGENCE.md`](docs/CALIBER_DIVERGENCE.md)）、
> 能力（[`docs/ABILITY.md`](docs/ABILITY.md)：聚/散/动 三项数值 + 9 项次级能力三阶，旧 512 体系冻结作历史）、外观（[`docs/APPEARANCE.md`](docs/APPEARANCE.md)）、
> 物性（[`docs/TRAITS.md`](docs/TRAITS.md)：密度/粘性/温度 → 3³ = 27 格）+
> 群系规格/候选（[`docs/BIOME_SPEC.md`](docs/BIOME_SPEC.md)、[`docs/BIOME_CANDIDATES.md`](docs/BIOME_CANDIDATES.md)）。
> **124 项测试全绿**（`python tests/run_all.py`，约 17~27s），另有 3 个示例脚本与群系物种图；整理分析见
> [`docs/KERNEL_INTAKE.md`](docs/KERNEL_INTAKE.md)。

> **第二轮同步（2026-11-19，最新）**：远端 `facb162`（三价轴属性 硬度→**密度**、物性改成 **3³ = 27 格**、能力改成**类别辐条三项数值**
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
> **能力与方块世界阶段（2026-11-18，最新）**：T71 每种骨架的能力与分化（30 能力/6 形态，结构门控生命度）、
> T72 能力扩到 72 项 ×9 类 + 28 种分化形态 + 小分子形态；T73 器官按位置/朝向选形态、形态**直接代替器官外形**
> （[`docs/T73_MORPH_GEOMETRY.md`](docs/T73_MORPH_GEOMETRY.md)）；T74 分类规则改为按价数元素判定；
> **T75 方块世界**：每个骨架 = 1 个单位方块，物质 = 若干方块拼成，属性改为硬度/粘性/温度
> （[`docs/T75_BLOCK_WORLD.md`](docs/T75_BLOCK_WORLD.md)）；**T75b** 属性改为**逐骨架**计算、连接桥不计入；
> **T76 桥的功用标签**（刚性焊接/铰接/定距隔空/多点编织…，[`docs/T76_BRIDGE_FUNCTIONS.md`](docs/T76_BRIDGE_FUNCTIONS.md)）。

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
   python tests/run_all.py            # 106 项测试（约 21~27s）
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

- `alchemy/`：**内核包（纯标准库）**——四入口大锅/摆放/目录/分类，另有 `phase`（三轴判相）、`ability`（512 能力）、`attrs`（三数值性状）、`biome`（群系物种表）；见 [`alchemy/README.md`](alchemy/README.md)；
- `tests/`：内核测试（11 个 `test_*.py` + `run_all.py`，106 用例）；`examples/`：内核/群系示例与出图；
- `pot_all.py` / `pot_v2.py` / `pot_v3.py` / `pot_v4.py`：历史大锅反应与几何校验脚本（规则 1~11 已迁入 `alchemy/`，`pot_v4.py` 保留为兼容实现）；
- `natural_engine.py` / `fast_pot.py` / `t55_kinetic_env.py`：自然环境引擎与 2D 粒子环境；
- `t4_*` ~ `t76_*`：各阶段研究脚本/数据（编号=任务阶段；T71~T76 为能力/形态/方块世界）；
- `docs/`：全部研究报告（`T*.md`）；新规则正式文档为 `THREE_AXES_FINAL.md` / `PHASE_RULE.md` / `CALIBER_DIVERGENCE.md` / `ABILITY.md` / `APPEARANCE.md` / `TRAITS.md` / `BIOME_SPEC.md` / `BIOME_CANDIDATES.md`，本次入库整理见 `KERNEL_INTAKE.md`；`docs/templates/` 放报告模板（如 `t60_report_template.md`）；
- `data/biomes/`：群系模板物种表（`t*.csv/json`，12 组）、候选群系（`candidates/`，5 个 + `_union` 121 种）与模板目录 `_catalogue.json`；
- `images/`：全部结果图（T68~T70b 的图册按 `t68_*`/`t69_*`/`t70_*`/`t70b_*` 命名；内核的群系物种图在 `images/biome_candidates/`）；
- `_data_gz/`：大数据的 gzip 版本 + `manifest.json`（GitHub 传输用）；
- `tools/`：跨电脑传输工具（`make_transfer_archive.py` 重新生成全量 zip、`pack_transfer_data.py` 打包 `_data_gz/`）；
- `archive/`：历史脚本与旧数据，已按阶段/主题分子文件夹（`archive/README.md` 有对照表）。

## 跨电脑交接

见 [`TRANSFER.md`](TRANSFER.md)：GitHub / 全量 ZIP / git bundle 三种方式。
2026-11-18 清理时已删除工作区里 2026-11-14 的旧 ZIP / bundle 快照（内容已被 GitHub 上的 T01~T70b / T71~T76 / kernel 提交覆盖）；
需要新的离线包时运行 `python tools\make_transfer_archive.py` 重新生成。
