# ALCHEMY 文件索引（2026-11-18 更新）

> **新对话/新接手：先读 HANDOFF.md、README.md、TRANSFER.md、NEW_CHAT_PROMPT.md。**
> 本文件是历史/主题索引；最新结论与交接以 HANDOFF.md 为准。
> **物质三轴口径以 [`docs/MATERIAL_AXES.md`](docs/MATERIAL_AXES.md) 为准**（2026-11-19 `c438fef` 定稿：质量/物态/温度 → 27 格行为表；旧 `docs/TRAITS.md` 密度/粘性/温度方案作废，仅历史）。

---

# alchemy 工作区索引（自动整理于 2026-11-13 10:58）

## 目录结构
- `docs/`：全部研究报告（T4~T77、HANDOFF 等）；`docs/templates/` 报告模板
- `images/`：全部图片（结构图、反应矩阵、循环图、统计图、T68~T70b 大分子图册等）
- `archive/old_scripts/`：历史探索脚本，已按阶段分子文件夹（`t3/` `t4p/` `late/` `early/`）
- `archive/old_data/`：历史数据，已按主题分子文件夹（`t3/` `scope/` `catalog/` `finite/` `minimal/` `misc/`）
- `tools/`：跨电脑传输工具（`make_transfer_archive.py`、`pack_transfer_data.py`）
- 根目录：核心模拟器 + 权威数据 + 各阶段脚本/数据 + `unpack_data.py` + 本索引

## 核心代码（根目录 + 内核包）

- **`alchemy/`（内核包，纯标准库，2026-11-18 入库）**：规则 1~11 大锅反应 / 摆放 / 目录 / 分类的正式实现，四入口
  `simulate` / `embed`+`validate` / `get_catalog` / `classify`；`core/` 为 elements/canon/geometry/reactor/catalog/classify，
  上层为 `phase`（三轴判相）/`ability`（能力 v3 三项数值 + v4 九项次级三阶；512 冻结作历史）/`attrs`（物质三轴：质量/物态/温度 → 27 格行为表 + 浮力 `buoyancy`）/
  `biome`（群系物种表）、`ops`（v5 9 操作能力：撑/锁/黏/分/捕/断/蓄/移/传）、`emergence`（L1 分子→L2 组装体→L3 器官→L4 生命系统原型）；`rules=8|9|11` 单份参数化；
  见 `alchemy/README.md`、`docs/KERNEL_INTAKE.md`、`docs/ABILITY_EMERGENCE.md`；测试 `tests/run_all.py`（**150 项**）
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

- **2026-11-20 T88 环境群系：3/4/5/6/9 种元素子集在 T87 规则下的终态对比**：`T88_BIOMES.md`
  （6 个群系 × 2,500 分子、240×160 硬边界；投料从目录"元素⊆子集、2~8 原子"池 IPF 配平；
  连续重力 + 非对称力 + 骨架占格 + resolve；物种池 28/28/110/258/533/3,931 → 终态种数 28/28/282/531/656/1,234；
  HHI 0.089→0.025、优势种 21%→6.6%、最大团占比 84%→63%；类型 B/B/B/B/D/D；
  脚本 `t88_biomes.py`/`t88_analyze.py`/`t88_render.py`，图 `images/t88_biomes.png`）
- **2026-11-20 T87 九元素环境：连续重力（取消质量阈值）+ 非对称分子间力 + 团簇自主移动观察**：`T87_ENV_ASYM.md`
  （320×220 硬边界方格、7,000 分子骨架占格；`gacc += 0.30·mass` 连续重力，A 对 B 与 B 对 A 的力分开算且无匹配度；
  1000→10°C @600 拍后恒温 800 拍；resolve → complete 31,925 / incomplete 30,995 / none 67；终态 N 14,290、19,822 格（28.2%）、
  1,718 种、1,703 新物质、9 元素守恒；质量 y 均值 101.3/197.0/198.7；最大团 6,046；3,101 track / 160 mover / 尺寸稳定仅 3 条；
  脚本 `t87_env_asym.py`/`t87_analyze.py`/`t87_render.py`，图 `images/t87_env.png`、`images/t87_mover.png`）
- **2026-11-20 T86 九元素环境：默认质量阈值 + 三价元素富集（O/X/F 各 18%）+ 2~4 分子同时反应（cap 36）**：`T86_ENV_TRI.md`
  （320×220 硬边界方格、7,000 分子骨架占格；三价份额 33%→54%；1000→10°C @650 拍后恒温 550 拍；resolve →
  complete 30,177 / incomplete 29,342 / none 45；终态 N 14,141、18,395 格（26.1%）、1,742 种、1,472 新物质、9 元素守恒；
  质量 y 均值 30.1/73.0/112.8；最大团 7,961（56.3%）；同物质同色大色块切片；脚本 `t86_env_tri.py`/`t86_render.py`，
  图 `images/t86_slices.png`）
- **2026-11-20 T85 九元素环境：更低质量阈值 + 10°C 恒温平台 + 完全/不完全反应**：`T85_ENV_RESOLVE.md`（320×220 硬边界方格、
  6,998 分子骨架占格；实验内质量阈值 (1.20,1.85)，同一投料重档 27.9%→56.3%；1000°C 冷却 650 拍到 **10°C** 后恒温 550 拍；
  反应改 `resolve` → complete 24,994 / incomplete 13,285 / none 11 / decomp 0；终态 N 14,436、18,879 格（26.8%）、2,620 种、
  896 新物质、9 元素守恒；质量 y 均值 36.6/90.1/131.6；最大团 6,416；切片改为**同物质同色填满整格 + 相邻同物质合并大色块**；
  脚本 `t85_env_resolve.py`/`t85_render.py`，图 `images/t85_slices.png`）
- **2026-11-20 T84 九元素环境：三轴 + 三素力、中间态骨架占格、自然冷却到 21°C**：`T84_ENV_SKEL.md`（320×220 硬边界方格、
  6,998 分子按 k=len(skeleton_units) 占 1~4 格（初始 11,519 格 = 16.4%）；初始 1000°C 按 T=10+990·exp(−4.5t/1199) 冷却到 21.0°C；
  终态 6,365 分子 / 624 种 / 945 次反应 / 362 种目录外新物质 / 9 元素守恒；质量 y 均值 轻 46.6 / 中 108.2 / 重 144.2；
  团簇 1,630 个（最大 1,205）；4 个 24×18 切片，每个骨架块占 1 格、多块分子用虚线框标出 footprint；
  脚本 `t84_env_skel.py`/`t84_render.py`，图 `images/t84_slices.png`）
- **2026-11-20 T83 九元素环境：三轴 + 三素力 + 单位方格骨架切片**：`T83_ENV_AXES.md`（240×160 硬边界方格、6,998 分子、900 拍 1000→73.4°C、规则 1~11 反应 + 三素力 + 质量/物态/温度三轴：
  质量分层 y 均值 33.0/79.2/111.6 行、含固反应占 58.3%、恒素场 ρ 0.549±0.043；1,034 团、最大 1,322（21.7%）、86.7% 在 ≥3 团、顶部浮膜 22.0% / 底部沉降 11.2%；
  5,199 次反应、2,032 种分子式、734 种目录外新物质、9 元素严格守恒；4 个 22×16 切片 + 14×10 原地放大，每个分子图标=1 单位方格；
  脚本 `t83_env_axes.py`/`t83_render.py`，图 `images/t83_slices.png`）
- **2026-11-20 T82 九元素环境切片（骨架方块 + 原地渲染）**：`T82_ENV_SLICES.md`（150×110 方格环面、三素力场 + 规则 1~11 反应、
  1,599→1,425 分子、1,005 次反应、120→701 种分子式、188 种目录外新物质、9 元素严格守恒；格层面均匀（占位率 8.6%、泊松）
  但接触层强聚集（587 团、最大 43、63.3% 分子在 ≥3 团）；4 个 40×30 切片 + 16×12 原地放大展示原子方块与骨架；
  脚本 `t82_env_sim.py`/`t82_render.py`，图 `images/t82_slices.png`）

- **2026-11-20 T81 三素相互作用（聚=吸引 / 散=覆盖半径 / 动=排斥）**：`THREE_SU_AXES.md`（用户重定义后的三素维度：点值表、配对公式、全目录 84,225 校准与方阵环面动态验证：
  同种净吸引 95.5% / 强粘 82.0%，异种双弱 58.7%（<1.0 时 94.6%）、强吸仅 5.4%，27 格 27/27；动态世界强吸引成团、混合世界同性键占比 0.63~1.00（期望 0.16）；
  诚实结论=同质吸引不足以让单个"种子体"选择性长大；代码 `alchemy/three_su.py`，图 `images/t81_su.png`）
- **2026-11-19 T80 组装体生长（生命追问）**：`T80_ASSEMBLY_LIFE.md`（用户澄清后的问题："主体 A 的组装体吞食小分子→合成新 A→并入自身"；
  A=C3K3F2、食物 C2K2+CKF2、7 个 A 圆盘种子、600 步 × 4 臂 × 3 seed：full 臂体 5→19 / 7→20 / 7→10，并入率 97%（31 合成/30 并入），
  对照 farspawn/nochem/bare 全部不生长；结论=**组装体代谢生长存在**，但无遗传/边界/复制/稳态，抓取与并入为脚本化主动步骤）
- **2026-11-19 T79 自催化生长生命搜索**：`T79_LIFE_SEARCH.md`（问题："主体 A + 辅件、吞小分子产生新 A 并加入自身"是否存在；
  当前规则 1~11 下 3,403 对营养物 / 16 条生长链 / 1,476 组本体+营养 / 40 条随机链：净增 174 对（`A2+W2→2WA`、`A3+A3→3A2`），
  生长可到 14~40 原子后饱和，但本体 A 催化再生 0 例、净放大 0 例 → 无此类生命；找到最接近实体=端帽聚合物体，与真实化学自催化/自复制系统对照）
- **2026-11-19 T78 九元素三轴环境实验**：`T78_THREE_AXIS_ENV.md`（质量→重力/物态→碰撞/温度→恒素富集三轴在 2D 介质箱中的实现与 240 min 三臂结果：
  轻/中/重分层 3936.5/2330.6/91.4、局部 ρ-温度 r=0.957、门控把 70.6% 反应压到顶带、810 新物质、不收敛对照 T62；含局限与下一步）；
  独立分析 `T78_ANALYSIS.md`（27 格缺轴碎片修正、ρ0.6 桶 rate 三重解释、T62 高温爆裂相对照），独立验证 `t78_verify_report.json`（16/16 PASS）
- **2026-11-19 物质三轴定稿（`c438fef`）**：`MATERIAL_AXES.md`（**权威定义**：质量/物态/温度按层平均、阈值 1.67/2.30 / 1.70/2.22 / 1.50/2.00、
  27 格行为表（碰撞/重力/恒素富集）、浮力 `F=(介质质量−物体质量)×体积`；§7 记被否方案）、`TRAITS.md`（**已被 `MATERIAL_AXES.md` 取代，仅历史**）、
  `THERMAL_DIMENSION.md`（温度维度 v2 设计定稿，未实施）、`ABILITY_CATALOG.md`（能力候选 11 域 110 项）、`ABILITY_PRIMITIVES.md`（基础能力原子 6 类 36 个）
- **2026-11-18 内核入库新文档**：`THREE_AXES_FINAL.md`（三轴判相 v4 定稿）、`PHASE_RULE.md`（物相规则 v1/v2）、
  `CALIBER_DIVERGENCE.md`（规则 1~8/1~9/1~11 口径分歧审计）、`ABILITY.md`（能力：v3 三项数值 + v4 九项次级三阶；512 作历史）、
  `APPEARANCE.md`（外观，仅记录）、`TRAITS.md`（密度/粘性/温度 → 27 格物性；**已被 `MATERIAL_AXES.md` 取代，仅历史**）、`BIOME_SPEC.md`（群系物种规格）、
  `BIOME_CANDIDATES.md`（候选群系清单）、`SYNC.md`（同步约定 + 自动推送钩子）、`REPO_SLIM.md`（仓库体积治理）、
  `KERNEL_INTAKE.md`（内核入库整理分析总报告）、`INTAKE_R2.md`（第二轮：属性/能力/表现层整理分析）、
  `ABILITY_EMERGENCE.md`（**能力→涌现生命总纲 v5/T77**：9 操作能力/9×9 矩阵/L1~L4/器官原型/生命判据/动力学/E-T 实验）
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
- **2026-11-19 三次整理（T77b 推送前，详见 `docs/CLEANUP_LOG.md` 末节）**：删除工作区根 `intake/` 暂存区
  （312.2MB，7 个 md 与 `alchemy/intake/` 逐一相同、`tmp/` 为入库过程中间产物）与仓库 5 处 `__pycache__/`；
  保留 `alchemy/intake/tmp/calib/`（标定中间产物，gitignore 排除）。

## 最新补充
- **T89 群系里的"类生命"候选：自主移动 / 生长 / 分裂 / 驻留团簇（2026-11-20，最新）**：在 T88 六群系上做 track 跟踪，
  判据 mover = 持续 ≥4 帧、4~64 分子、速度 ≥0.06 格/拍、直线度 ≥0.25；结果 **B4 起共 86 个 mover**（B4 7 / B5 15 / B6 25 / B9 39，
  占分子 1.2~7.9%），B3 两个三元素群系因整群并成巨团（76%/84%）而无 mover；最佳候选 = **B9 的 13 个 CF 团**（t=575~675，
  净移 7.4 格、v=0.110 格/拍、直线度 0.67、下沉）；另有 growth 48~178 次、division 8~17 次（皆并合/破碎，无可继承子团）；
  结论：非对称力确实能让团簇"自主漂移"，但没有边界/遗传/代谢/自我维持，**不是生命**；`docs/T89_LIFE.md`、`images/t89_life.png`。
  附：T87 方向口径修正（dx/dy 互换、dir 改按垂直判定；方向数改为 上浮 51/横向 48/下沉 61）。
- **T88 环境群系：3/4/5/6/9 种元素子集对比（2026-11-20）**：6 个群系（B3_OFL / B3_OXC / B4_OXKF /
  B5_OXKAF / B6_OXCKAF / B9_all9），每群系 2,500 分子、240×160 硬边界、800 拍（400 拍降到 10°C 后恒温 400 拍）；
  投料 = 目录中"元素⊆子集、2~8 原子"分子式池 + IPF 等份额配平（池 28/28/110/258/533/3,931 种）；
  终态：N 2,648~3,771、种数 **28→1,234**、新物质 0→288、HHI **0.089→0.025**、优势种 **21%→6.6%**、
  最大团占比 **84%→63%**；群系类型 B 主辅 4 个、D 多主 2 个；质量分层普遍成立（B3 轻档 y≈66~72、B9 110）；
  `docs/T88_BIOMES.md`、`images/t88_biomes.png`。
- **T87 九元素环境：连续重力 + 非对称分子间力 + 团簇自主移动观察（2026-11-20）**：320×220 硬边界方格、
  7,000 分子骨架占格；**取消质量阈值**，每拍 `gacc += 0.30·mass`（mass=3→0.9 格/拍、2→0.6、1→0.3、0→0）；
  **非对称力**（无匹配度）：`F_on_B = 2.5·A_A·F(d,ratt_A) − 0.5·R_B·F(d,rrep_B)`、`F_on_A = 2.5·A_B·F(d,ratt_B) − 0.5·R_A·F(d,rrep_A)`；
  1000→10°C（600 拍）后恒温 800 拍；resolve → complete 31,925 / incomplete 30,995 / none 67；
  终态 N **14,290**、19,822 格（28.2%）、**1,718 种 / 1,703 目录外**、9 元素守恒；质量 y **101.3/197.0/198.7**（中/重几乎全压到底部）；
  最大团 **6,046（78.6% 分子在 ≥3 团）**、ρ 0.5155±0.0422；每 25 拍跟踪 → **3,101 track、1,243 条 ≥6 帧、160 个 mover（25.7% 分子）、
  上浮 45/横向 59/下沉 56、尺寸稳定仅 3 条**；`docs/T87_ENV_ASYM.md`、`images/t87_env.png`、`images/t87_mover.png`。
- **T86 九元素环境：默认质量阈值 + 三价元素富集 + 多分子同时反应（2026-11-20）**：320×220 硬边界方格、7,000 分子
  骨架占格；IPF 重配平 batchA → **三价份额 33%→54%**（O/X/F 各 18%、其余各 7.67%，89 物种/67,317 原子）；质量阈值回到内核默认
  (1.67,2.30)；反应支持 **2~4 分子同组**、cap 26→36；1000→10°C（650 拍）后恒温 550 拍；
  resolve → complete 30,177 / incomplete 29,342 / none 45 / decomp 0（不完全 49.3%）；
  终态 N **14,141**、占用 18,395 格（26.1%）、**1,742 种 / 1,472 目录外**、9 元素守恒；质量 y **30.1/73.0/112.8**；
  最大团 **7,961（56.3%）**、ρ 0.481±0.055、T=10.0°C；切片同物质同色大色块；`docs/T86_ENV_TRI.md`、`images/t86_slices.png`。
- **T85 九元素环境：低质量阈值 + 10°C 恒温平台 + resolve 完全/不完全反应（2026-11-20，最新）**：320×220 硬边界方格、
  6,998 分子骨架占格（k 格/分子）；质量阈值实验内降为 **(1.20,1.85)**（默认 1.67/2.30），同一投料三档 轻19.3/中24.4/重56.3%；
  1000°C → **10°C（650 拍）+ 恒温 550 拍**；反应改用 `natural_engine.resolve`，同时出现 **complete 24,994 / incomplete 13,285 /
  none 11 / decomp 0**；终态 N **14,436**（完全反应可裂成 2~3 产物）、占用 18,879 格（26.8%）、**2,620 种**、896 目录外、
  9 元素守恒；质量档 y **36.6/90.1/131.6**；最大团 **6,416**；ρ 0.392±0.044、T=10.0°C。
  切片渲染改为**同物质同一种颜色填满整格、相邻同物质不画边界连成大色块**；图 `images/t85_slices.png`，报告 `docs/T85_ENV_RESOLVE.md`。
- **T84 九元素环境：骨架占格 + 自然冷却到 21°C（2026-11-20，最新）**：320×220 硬边界方格、6,998 分子按 **k=中间态骨架块数占 k 格**
  （k=1/2/3/4 → 6,796/6,511/1,320/125 个分子，平均 1.65），初始占 11,519 格（16.4%）；初始 1000°C 按 T=10+990·exp(−4.5t/1199)
  **自然冷却到 21.0°C**，1200 拍。结果：N 6,998→6,365、624 种分子式、945 次成功反应（失败 24,737）、362 种目录外新物质、
  9 元素严格守恒；质量分层 y 均值 **46.6/108.2/144.2 行**；团簇 1,630 个（最大 1,205、78.4% 在 ≥3 团）；恒素场 ρ 0.544±0.044。
  4 个 24×18 切片中每个骨架块占 1 格、多块分子用浅蓝虚线框标出 footprint，灰块=目录外产物。脚本 `t84_env_skel.py`/`t84_render.py`，
  报告 `docs/T84_ENV_SKEL.md`，图 `images/t84_slices.png`（+5 张单图）。
- **T83 九元素环境：三轴 + 三素力 + 单位方格骨架切片（2026-11-20）**：240×160 硬边界方格、6,998 分子（T62 batchA ×0.4745）、
  初始 1000°C 冷却到 73.4°C、900 拍；**质量/物态/温度三轴 + 三素力 + 规则 1~11 反应**同时生效。结果：N 6,998→6,105、2,032 种分子式、
  5,199 次反应（成功率 13.7%）、734 种目录外新物质、9 元素严格守恒；**质量分层 y 均值 33.0/79.2/111.6 行**、含固反应占 58.3%、
  恒素场 ρ 0.549±0.043；1,034 团、最大 1,322（21.7%）、86.7% 分子在 ≥3 团，**顶部 10 行浮膜 22.0% / 底部 10 行沉降 11.2%**；
  4 个 22×16 切片（A 密度 44.9%、B 12.5%、C 3.1%、D 11.9%）+ 14×10 原地放大，每个分子图标=1 单位方格。脚本 `t83_env_axes.py`/`t83_render.py`，
  报告 `docs/T83_ENV_AXES.md`，图 `images/t83_slices.png`（+5 张单图）。
- **T82 九元素环境切片（2026-11-20）**：150×110 方格环面里投 1,599 个小分子（T62 batchA 缩放、9 元素等量），
  三素力场驱动位移 + 相邻以 p=0.008 触发规则 1~11 反应、w≥1 粘附锁——1,200 拍后 1,425 分子 / 701 种 / 1,005 次成功反应 / 188 种目录外新物质，9 元素严格守恒。
  **格层面均匀（占位率 8.6%，逐格泊松）但接触层强聚集（587 团、最大 43、63.3% 分子在 ≥3 团）**；4 个 40×30 切片（10.6%、8.5%、7.2%、8.25% 占用）
  差异只在"团大小/密度"、不在成分（四块首位都是 `L2A2`）；16×12 原地放大图看清分子骨架方块。脚本 `t82_env_sim.py`/`t82_render.py`，
  报告 `docs/T82_ENV_SLICES.md`，图 `images/t82_slices.png`（+5 张单图）。
- **T81 三素相互作用公式与验证（2026-11-20）**：聚素=吸引力（O3/X2/C1 点）、散素=覆盖半径（K3/A2/F1 点）、动素=排斥力（P3/W2/L1 点）；
  `Att=κA·√(AiAj)/3·J_att·F(d,r_att)`、`Rep=κR·√(DiDj)/3·J_rep·F(d,r_rep)`、`w=Att−Rep`（κA=2.5 锚原 κ0、κR=0.5，J=元素组成 Jaccard，无其它变量；
  r_att=1+[Q≥10]+[Q≥20]，r_rep=1+[Q≥15]+[Q≥30]）。84,225 分子校准：同种净吸 **95.5%**、强粘 **82.0%**，异种双弱 **58.7%**（<1.0 时 94.6%）、强吸仅 5.4%，27 格 27/27；
  方阵环面动态世界：强吸引物种成团、混合世界同性键占比 0.63~1.00（期望 0.16），力显著加速初期装配；3 组诚实结论（同质吸引不足让单个体选择性长大 / 力是动力学加速器 / 排斥半径永远落后）。
  代码 `alchemy/three_su.py`、脚本 `t81_su_calibrate.py`/`t81_su_world.py`/`t81_overnight.py`/`t81_su_plot.py`，报告 `docs/THREE_SU_AXES.md`，图 `images/t81_su.png`。
- **T80 组装体生长（2026-11-19）**：回答"主体是 A 的组装体能否吞小分子合成新 A 并连到体上"——
  A=C3K3F2（8 原子、5 位点、自界面能 2.5），食物 C2K2+CKF2 单产物合成 A；7 个 A 圆盘种子在 emergence 物理里生长：
  full 臂三 seed 5→19 / 7→20 / 7→10（并入率 97%，31 合成/30 并入），farspawn（合成但远投）/nochem（不合成）/bare（无食物）全部不生长；
  体是动态组装体（会解体再重组），生长靠外部食物、无边界/遗传/复制/稳态，且抓取与并入为脚本化主动步骤。脚本 `t80_assembly_body.py`，
  作图 `t80_plot.py` → `images/t80_assembly.png`，报告 `docs/T80_ASSEMBLY_LIFE.md`。
- **T79 自催化生长生命搜索（2026-11-19）**：回答"主体 A + 辅件、吞小分子长出新 A"是否存在——
  小分子→A（单体）的净增合成存在（174 对，如 `A2+W2→2WA`、`A3+A3→3A2`），端帽聚合物体可逐级生长（`O2+WA`→`O2W6A6` 14 原子，
  `O2X3+O2CPA`→40 原子后分裂），但**本体 A 催化再生/净放大均为 0**（1,476 组），生长到 14~40 原子必然饱和/分裂；
  结论：本宇宙不存在该定义的生命，只存在其化学前身（自催化生长/晶体生长层）；真实化学对照（formose、自催化集合、自复制 RNA/囊肽、囊泡分裂）
  与"缺什么才能出现"见报告。脚本 `t79_life_scan.py`（--quick 约 35 s），数据 `t79_life_scan.json`。
- **T78 九元素三轴环境实验完成（2026-11-19，最新）**：新三轴在 2D 竖直介质箱（2000×4000，介质=中·气·温）中全部跑通——
  质量→重力分层（轻/中/重 y 均值 3936.5/2330.6/91.4）、温度→恒素富集（局部 ρ-温度 r=0.957）、物态→碰撞；
  main/nogate/nochem 三臂 240 min、1,793 分子/18,222 原子、守恒与漏斗全闭合；门控把 13,329 次反应中 70.6% 压到顶带、810 新物质（目录外）；
  不收敛（607 种终态、双原子小分子主导），与 T62 双组分不动点对照。脚本 `t78_three_axis_env.py`/`t78_analysis.py`/`t78_render.py`，
  报告 `docs/T78_THREE_AXIS_ENV.md`，图 `images/t78_overview.png`；**终产物分层图** `t78_products.py` → `images/t78_products.png`
  （每层有哪些物质/多少/结构形态）与 `images/t78_products_matrix.png`（16 种主要产物的物种×层分布矩阵），数字见 `t78_products.json`。
- **物质三轴定稿同步（2026-11-19）**：远端 `c438fef` 已同步——`alchemy/attrs.py` 重写为三轴按层平均 + **27 格行为表**
  （`molecule_attrs`/`attrs_of`/`property_of`/`behavior`/`grid`/`buoyancy`），权威定义 `docs/MATERIAL_AXES.md`；
  本地 5 个纯文档设计提交（温度维度 v1/v2 定稿、能力候选总目录 110 项、基础能力原子 36 个）rebase 干净
  （HEAD `4aea764`，`origin/main`=c438fef，**ahead 5，未 push**）；根文档 README/HANDOFF/TRANSFER/NEW_CHAT_PROMPT 已回填旧口径。
  下一步：**九元素三轴环境实验（T78）已完成**——结果与独立分析见上两条，后续优先级见 `docs/T78_THREE_AXIS_ENV.md` §5。
- **第三轮（2026-11-19）能力维度 v5 + 涌现原型**：`docs/ABILITY_EMERGENCE.md` 总纲（9 操作能力/9×9 矩阵/
  L1~L4/9 器官原型/B·M·R·I·H 判据/S1~S8 动力学/E·T 实验）；原型 `alchemy/ops.py` + `alchemy/emergence.py`（~2330 行，纯标准库，无 alive 标志）；
  测试 **151 项全绿**（`tests/test_ops.py` 11 + `tests/test_emergence.py` 16 新增）；`examples/emergence_demo.py`（`--sample/--steps/--seed/--out`）；
  需求文档 `intake/ability_spec.md`、`intake/emergence_spec.md`；参数标定见 `intake/calibration.md` 与 `alchemy/data/emergence_params.json`（`calibration` 段）：
  标定后 800×800 两 seed 组装率 68.5%、器官系统 1~4、首次出现「活性无机」档；B/H 判据仍为 0，拟生命/有机生命待后续（`HANDOFF.md` §14.4）
- **内核入库（2026-11-18）**：`alchemy/` 内核包（11 模块 + data，纯标准库）；`tests/`（106 项全绿）；
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

- **第二轮同步（2026-11-19）属性/能力改造**：远端 `facb162`（`alchemy/attrs.py` 三价轴 硬度→密度、物性 3³=27 格新增
  `cell_of`/`grid`/`N_CELLS`；`alchemy/ability.py` 新增 v3 三项数值 `scores`/`category_score` 与 v4 九项次级 `SUB_ABILITIES`/`profile`/`abilities_of`；
  `docs/ABILITY.md`、`docs/TRAITS.md` 改口径；新增 `docs/REPO_SLIM.md`；测试 +18 → 124）+ `cf9d01b`（`docs/SYNC.md`
  记 post-commit 自动推送钩子）。本地经 GitHub API/raw 取回并提交 `7516ce0`（网络受限未能 `git fetch`，未 push）。
  第二轮整理分析见 `docs/INTAKE_R2.md`（属性/能力/表现层）。
  **（注：2026-11-19 `c438fef` 已把三轴定稿为 质量/物态/温度，本节「密度/粘性」口径随之作废，以 `docs/MATERIAL_AXES.md` 为准。）**

- **第三轮（2026-11-19）能力维度 v5 + 涌现原型**：`docs/ABILITY_EMERGENCE.md`（总纲）；
  `alchemy/ops.py`（9 元素↔9 操作：撑/锁/黏/分/捕/断/蓄/移/传，p33/p67 阈值、9×9 `LINKAGE`）、
  `alchemy/emergence.py`（L1~L4 动力学，无 `alive` 标志，`M` 由 LINKAGE 派生）、`tests/test_ops.py`+`test_emergence.py`（+27 → **151 项全绿**）、
  `examples/emergence_demo.py`、`alchemy/data/emergence_params.json`（`calibration` 段：标定后组装率 68.5%、器官系统 1~10、活性无机档出现；
  B/H 仍 0）；stale-sweeper 覆盖 35 文件旧口径（含 `data/biomes` 120 处旧快照字段）；
  本地提交 `b15ae4a`/`e9b178c`，tag `kernel-0.2.0`，**未 push**。

- **2026-11-20 整理 + T78~T81 全量推送**：删除未跟踪生成物（21 个根 `*.log`、3 处 `__pycache__/`、16 个 0 字节 `t80_*.err`、
  5 份被 12 份 seed 版取代的 T80 首轮结果），删除后 `git status` 干净、tracked 1355 文件；先拉取远端世界物理/力模型 13 个提交（`c438fef`→`bdaaff1`），把本地
  **12 个提交**（T78 三轴环境实验、T79 生命搜索、T80 组装体生长、T81 三素相互作用公式、T82 九元素环境切片 + 本轮整理）rebase 无冲突，连同并发代理的 T83 结果提交全量推送（共 15 个提交）；
  测试 `python tests/run_all.py` → **150/150 PASS**（`c438fef` 重写 `test_attrs.py` 后由 151 变 150）。详见 `docs/CLEANUP_LOG.md` 末节与 `TRANSFER.md` §6.1。