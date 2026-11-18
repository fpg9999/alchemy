# 涌现原型参数标定（task-10，第二轮迭代）

> 对象：`alchemy/emergence.py`（L1~L4 涌现原型，纯标准库）。
> 目标：让器官系统 / 生命档位**真实出现**，向 `intake/emergence_spec.md` §8.3 的预注册分布靠近；
> 达不到的项如实报告并给出机制解释。**不**把预注册数字硬凑成常量。
> 约束：只改 `alchemy/emergence.py`、`alchemy/data/emergence_params.json`、`examples/emergence_demo.py`、
> `tests/test_emergence.py`、`intake/calibration.md`、`intake/tmp/calib/*`；不改 ops/attrs/ability/phase/core
> 公式；保持 A0（无 alive 标志、life_report 纯读）、M≡0 消融零组装、同 seed 逐位可复现。

---

## 0. 结论摘要

| 指标 | task-8 起点 | task-10 终选 | spec 预注册 |
|---|---|---|---|
| 组装率 | 38.5%（6000×1200） | **68.5~72.2%** | 55~70% |
| 尺寸中位 | 10 | **8~11** | 3 |
| 尺寸 p90 | 29 | 49~131 | 9 |
| 器官数 / 组装体 | 0.22 | **1.38~1.58** | 1.8±0.9 |
| 器官系统 | **0** | **1~10** | 1~3% |
| 四档「活性无机」 | 0 | **10~29 份** | 60~75% |
| 四档「拟生命」 | 0 | 0 | 4~8% |
| 四档「有机生命」 | 0 | 0 | 0.2~1.5% |
| B 判据通过率 | 0 | **0（结构性）** | 40~55% |
| M 判据通过率 | 0 | **10~23%** | 15~28% |
| R / I 判据通过率 | 0 | 48~80% / 0~10% | 5~10% / 3~8% |
| H 判据通过率 | 0 | 0 | 0.4~1.8% |

**一句话**：器官系统与「活性无机」档已真实出现；组装率进入预注册区间；但 **B 判据仍结构性不可达**
（组装体是稀疏树状团，1 格 footprint 下不存在「闭合壳子图」），因此「拟生命/有机生命」仍为 0。

---

## 1. 起点与瓶颈判读（为什么要先修 bug 再调参）

task-8 实测（6000×1200，seed 20261119）：组装率 38.5%、尺寸 10/29/1227（1 个贯通巨团）、器官 15、
器官/组装体 0.22、系统 0、四档全 0。读完关键路径后判断瓶颈在**几何与记账**，不在参数：

- `_hex_dist` 直接比较世界格坐标 → 环面接缝两侧相邻分子被算成相距 `L-1`，`_rupture` 误断、
  `classify_shape` 的 bbox 被算成 `L×L`；
- S3 的 `pairs` 在 tick 开头算，`_push_apart` 推开后仍按旧 pairs 成键 → 假远键；
- 界面键不约束相对运动 → 组装体被分子随机行走拉成松散随机链（R/n 随 tick 增长），
  形态全落 `团`，壳/膜/膜子图不可能出现；
- 观察窗口 `window()` 把 `shape` 字符串也求和 → `TypeError`；
- 事件计数落到 `mol_asm`（每 10 tick 重排）的旧 aid → 新组装体通量恒 0、器官全灭；
- M 的 harvest 只算 sto 位点、dissip 却每 tick 记 `0.3×mov` → M 恒为大负数；
- 每对分子可含同一位点两次接触（2×2 候选组合的重复 si/sj）→ 位点被两条键重复占用。

**这些不修，任何参数扫描都只是在错误模型上调数字。**

---

## 2. 本轮的代码修改（全部在 `alchemy/emergence.py`；ops/attrs/ability/phase/core 未动公式）

### 2.1 环面几何（真 bug，已修）
- 新增 `_cells_touch(ca, cb, L)`：用 `_NEIGH12` 偏移 + `_wrap` 判断两分子骨牌格是否接触（边/顶点相邻）。
- 新增 `_unwrap_cells(cells, L)`：以首格为原点把环面格展开到连续坐标，供 bbox / 壳子图用。
- `_rupture` 改用 `_cells_touch`；`_push_apart` 用 wrap 后的 `dq/dr` 算分离方向。
- `classify_shape(mols, bonds, cells, L=None)` 增加 `L` 参数；`rebuild_assemblies` 传 `L=world.env.L`。

### 2.2 S3 假远键（真 bug，已修）
S3 循环内成键前重新 `_cells_touch` 验证：`pairs` 是 tick 开头快照，排斥可能已改变几何。

### 2.3 组装体空间连贯性（结构性，已修）
- 移动候选必须与所有已键合邻居保持 `_cells_touch`；
- 已键合分子只接受使「到键合邻居六角距离之和」**严格下降**的候选（内聚约束，链会卷成紧凑团）。

### 2.4 B 判据的壳子图（实现缺口，已补）
- 新增 `shell_subgraph(cells, L)`：外层格（有边邻空格）成闭合环（连通且 min degree≥2）且内部格≥1
  即存在壳/膜子图。§6.2 的 B 判据要求的是**子图**，不是 §4.4 的整组装体形态。
- B 的 `has_shell` 与 `organ_flux` 的 bnd 闭合率都改用它。

### 2.5 通量记账与 M（口径错误，已修）
- `ObsBuffer` 新增 `mol_counters` / `bump_mol(uid, key, value)`；`_bump_uid` 改按 uid 归集（不再挂旧 aid）。
- 能量：`_exchange` 每分子每 tick `energy += eta·ρ_E·i_e_scale` 并记 `nrg_in`；ads 吸能也记 `nrg_in`；
  `_move_molecule` 记 `nrg_out=move_cost`；`_add_bond` 两侧各记 `nrg_out=bond_cost×接触数`。
- `_criteria_from_counts` 的 M 改为 `(harvest-dissip)/(maint_rate·n_mols·T_obs+ε)`，
  新增可标定参数 `maint_rate`（见 §2.6）。R 的修复计数改用 `repair`（不再与复制 `rep` 混用）。

### 2.6 标定开关（JSON `calibration` 段可覆盖）
`contacts_per_pair`、`contact_base`、`contact_div`、`theta_scale`、`max_organs_per_mol`、`maint_rate`。
默认值等于 task-8 行为；`load_params` 顶层参数先应用、`calibration` 段覆盖同名标量键，矩阵仍由
`ops.LINKAGE` 派生（不写进 JSON）。`InterfaceBond` 新增 `contacts: [(site_a, site_b, w_i), ...]`，
一个界面对可含多个位点接触；S3 内位点去重，保证「每位点最多 1 条键」。

### 2.7 无系统组装体的四档
`tier_from_criteria`：只有器官**系统**才可能判「拟生命/有机生命」；含 ≥1 活跃器官但未成系统的组装体
最多「活性无机」。这是 spec §6.3 的原意（无机晶体/活性无机按有无器官区分，不要求系统），
此前只统计系统 → 系统 0 时四档全 0 属实现偏差。`life_report_all` 现在 = 系统报告 + 组装体级报告。

---

## 3. 扫描

扫描脚本（临时，产物在 `intake/tmp/calib/`）：
- `sweep.py`：多配置批量扫描，写 `intake/tmp/calib/<name>.json`；
- `probe.py`：单/多配置探针，输出组装率/尺寸/形态/器官/系统/四档/判据率/壳子图命中数；
- `diag_shape.py`：最大组装体的 n/shape/beta0/度数/直径/R-over-n/hole/器官，以及 report 的判据明细。

### 3.1 第一轮（b17 记录，几何修复前，仅作方向性参考）
| 配置 | 键/分子 | 组装率 | 尺寸 中位/p90/max | 形态 | 器官 | 系统 | 活性无机 |
|---|---|---|---|---|---|---|---|
| base | 0.575 | 40.5% | 10/219/219 | 全团 | 1 | 0 | 1 |
| A_contacts2 | 0.651 | 50.9% | 8/16/203 | 团14/链6/簇2 | 23 | 0 | 16 |
| B_contacts3 | 0.601 | 45.5% | 6/34/102 | 团17/链6/簇4 | 29 | **1** | 19 |
| C_fastbind | — | 46.1% | 6/20/198 | — | 22 | 1 | 15 |
| D_loose | 0.489 | 33.9% | 6/16/30 | — | 38 | **2** | 25 |
| E_energy | — | 49.2% | 11/59/116 | — | 24 | 1 | 13 |

结论：多接触 + 放宽 k_on/k_off/Q_min 已能把 systems 从 0 提到 1~2、四档出现「活性无机」；
但 B 恒 False、M 巨负、I 偏低 → 指向 §2.4/§2.5 的记账与子图缺口。

### 3.2 第二轮（几何+记账修复后，800×800，L=58，791 分子，seed 20261119，每组 ~25~30s）
| 配置 | 键/分子 | 组装率 | 中位 | 器官 | 器官/组装体 | 系统 | 活性无机 | B/M/R/I |
|---|---|---|---|---|---|---|---|---|
| r2_base（默认） | 0.676 | 51.5% | 8 | 4 | 0.44 | 0 | 3 | B0 M100 R33 I0 |
| B3（contacts 3） | 0.766 | 59.0% | 6 | 53 | 1.26 | **9** | 27 | B0 M100 R67 I0 |
| DENSE | 0.837 | 66.0% | 9 | 58 | 1.61 | 6 | 30 | B0 M100 R73 I6.7 |

DENSE = `contacts_per_pair=3, contact_base=6, k_on0=0.30, k_off0=0.008, rupture_p=0.30,
W0=0.25, Q_min=0.30, theta_scale=0.8, max_organs_per_mol=3, bond_cost=0.5`。

### 3.3 M 的 `maint_rate` 标定（DENSE，seed 20261119）
| maint_rate | M 通过率 |
|---|---|
| 1.00 | 76.7% |
| 1.05 | 63.3% |
| 1.10 | 33.3% |
| 1.15 | **16.7%** |
| 1.20 | 13.3% |
| 1.50 | 0% |

取 1.15（预注册 15~28%）。M 只是把 `harvest-dissip` 除以「维持消耗」，不改变动力学，
因此它只校准「代谢」判据的严格程度，不伪造能量事件。

### 3.4 终选配置两 seed 复验（800×800，L=58，791 分子；k_on0=0.25, k_off0=0.010, rupture_p=0.35，其余同 DENSE）
| seed | 组装率 | 尺寸 中位/top | 器官 | 系统 | 活性无机 | M | R | I |
|---|---|---|---|---|---|---|---|---|
| 20261119 | 68.5% | 8 / [342,66,48,42,10,8] | 18 | 1 | 10 | 10.0% | 80.0% | 10.0% |
| 20261120 | 68.5% | 9 / [150,107,42,32,31,28] | 37 | 4 | 20 | 20.0% | 50.0% | 0% |

两 seed 组装率一致（68.5%），但**头部尺寸方差很大**（342 vs 150），是接触图渗透的典型表现。

### 3.5 终选配置的 demo 与全量
- `python examples/emergence_demo.py --sample 600 --steps 600`（L=51）：内部 **13.48s**、墙钟 14.76s（<90s），
  组装率 57.1%，组装体 16，尺寸 17/55/65，器官 22，器官/组装体 1.375，系统 **3**，
  四档 活性无机 14（系统 3 + 组装体 11），I 7.1%，digest `8ac5099c…`。
- `python -m alchemy.emergence --sample 2000 --steps 800`（L=92）：**67.56s**，1982 分子，
  组装率 72.2%，组装体 38，尺寸 11/49/441，器官 60，器官/组装体 1.579，系统 **10**（各 cycle_rank=1），
  四档 活性无机 29，M 13.79%，R 48.28%，I 10.34%，H 0，digest `af3fc38d…`。

---

## 4. 推荐配置（`alchemy/data/emergence_params.json` 的 `calibration` 段）

```json
"calibration": {
  "contacts_per_pair": 3, "contact_base": 6,
  "k_on0": 0.25, "k_off0": 0.01, "rupture_p": 0.35, "W0": 0.25,
  "Q_min": 0.3, "theta_scale": 0.8, "max_organs_per_mol": 3,
  "bond_cost": 0.5, "maint_rate": 1.15
}
```

证据：§3.4 两 seed 复验、§3.5 demo/全量；临时产物 `intake/tmp/calib/{configs_a,configs_b,configs_c,
configs_final,configs_alt,sweep_round1,r2_base,demo_600_final,big_2000x800_final}.json`。
选择理由：组装率稳定落在预注册区间；器官/组装体 1.38~1.58（预注册 1.8±0.9）；系统从 0 提升到 1~10；
四档出现「活性无机」；同时 M 通过率 ~10~20%（预注册 15~28%）。
`k_on0` 从 0.30 降到 0.25、`rupture_p` 从 0.30 提到 0.35 是为了压低贯通巨团的占比
（但两 seed 仍各有一个 300~440 的头部团，见 §5）。

---

## 5. 与预注册对照（终选，800×800 与 2000×800）

| 指标 | 预注册 | 实测 | 判定 |
|---|---|---|---|
| 组装率 | 55~70% | 68.5 / 72.2% | 达标（全量略超上限） |
| 尺寸中位 | 3 | 8~11 | 偏高（footprint 压缩导致大分子更占优） |
| 尺寸 p90 | 9 | 49~131 | 明显偏高 |
| 尺寸 max | ≥25 | 150~441 | 达标但来自贯通巨团 |
| 器官/组装体 | 1.8±0.9 | 1.38~1.58 | 接近 |
| ≥3 类器官占比 | 10~18% | 系统报告均 3 类；组装体级 1~3 类 | 部分达标 |
| 器官系统 | 1~3% | 1~10 个/约 23~38 组装体 | 量级偏高 |
| 四档 无机晶体 | 5~15% | 0 | 偏低（有器官的组装体太多） |
| 四档 活性无机 | 60~75% | 系统+组装体全部 | 偏高（缺「无机晶体」对照） |
| 四档 拟生命 | 4~8% | 0 | **未达**（B 卡死） |
| 四档 有机生命 | 0.2~1.5% | 0 | **未达**（B/H 卡死） |
| B 判据 | 40~55% | 0 | **未达**（结构性） |
| M 判据 | 15~28% | 10~23% | 接近（`maint_rate` 标定） |
| R 判据 | 5~10% | 48~80% | **偏高**（见 §6） |
| I 判据 | 3~8% | 0~10% | 接近 |
| H 判据 | 0.4~1.8% | 0 | **未达** |

---

## 6. 未达项与机制（如实报告）

### 6.1 B 恒 False：壳子图结构性不出现（最重要）
- 实测：全部组装体的 `shell_subgraph` 命中 **0**；`classify_shape` 的 `hole` 虽常为 True，
  但那是 bbox 内有空格，不等于「外层格成闭合环」。
- 原因链条：① 1 格 footprint（§4.1 骨牌压缩）使每个分子只占 1 格；② 界面键只在对接触时形成，
  所得接触图是**稀疏树状/低环秩**（`deg_min=1`，`beta0` 多在 3~13）；③ 内聚约束只保证
  「键不松脱」，不产生致密化/相分离 → 组装体内部格（6 邻域全占）几乎为 0；
  ④ 无内部格 ⇒ 不存在「隔开内外的闭合外层」⇒ shell_subgraph 恒 False ⇒ bnd 器官 F 恒 0
  ⇒ has_shell False ⇒ B 恒 0 ⇒ 拟生命/有机生命判档的第一项被卡死。
- 这不是阈值问题：把 B_TH 降到 0 也只会让「漏率」通过，而 has_shell 仍 False。
- 结论：在「每分子 1 格 + 对接触才成键」的简化下，**壳/膜子图是结构性不可达的**，
  需要新的致密化机制（见 §7）。

### 6.2 H = 0：复制回路未闭合
- H 需要 `rep` 器官活跃（复制原型 θ=0.25 且需 fid≥0.85）+ 子代可育（B∧M）+ h≥0.8。
- 本轮扫描中 `rep` 器官从未进入活跃集合（器官类型只出现 sup/trn/nrg/cat/int/def）；
  且 B=0 → 子代不可育。H 是 B 的下游，B 不解决 H 必为 0。

### 6.3 R 偏高（48~80% vs 5~10%）
- `R = repair/(dmg+ε)`，`repair` 由 {sup,dif,adh} 分子以 3%/tick 概率修复事件累计，
  而 `dmg` 只统计 `_damage_repair` 造成的断键。损伤-修复回合数被低估，修复代理过松。
- 这是实现口径问题而非动力学问题；更严格的做法是给修复加「损伤位点必须相邻」与
  「每原子 e_rep 成本」的约束，并把 R 分母改为 §5.1 的 J_dmg 真值。本轮未改（预算与风险）。

### 6.4 M：`maint_rate` 是标定量，不是物理量
- 明确记录：M 的通过率由 `maint_rate`（维持消耗率）标定到 10~23%，与预注册 15~28% 接近。
  它只决定「能量收支归一化的尺度」，不改变任何动力学事件；因此 M 通过率不能当作
  独立预测的证据，报告中作为「口径已标定」而非「预测命中」。

### 6.5 贯通巨团与两态问题（task-8 遗留，仍未根除）
- 接触图在「键/分子 ≈ 0.8~1.0」时接近渗透阈值：要么亚临界小团（组装率 30~50%），
  要么出现几百个分子的贯通团（组装率 65~72% 但 max=150~441）。两 seed 头部方差大。
- 本轮用 k_on0/rupture_p 把「组装率」推入预注册区间，但没有改变两态本质；
  若要「55~70% 且 max≈25」，需要**有限尺寸的键饱和机制**（见 §7）。

### 6.6 其他已知简化
- ρ_E 场实测恒为 1.0（扩散后均匀），趋化/能量场结构未真正生效；能量输入是均匀项。
- 每分子每 tick 至多 1 次移动、信号用脉冲计数近似、复制单代、通量用分子事件代理。
- 这些简化都写进了 `emergence.py` 顶部 docstring，报告里不当作真实动力学解释。

---

## 7. 下一步建议（按预期收益排序）

1. **致密化机制（解决 B/H）**：给已键合分子加「朝键合邻居质心」的主动位移（不止是「不劣化」，
   而是每 tick 以 p_cohesion 向质心靠近一格），或在 `interface_energy` 之外加短程吸引势
   （w_extra = -k·(d-1) for d≤2），让组装体从树状卷成密实团 → 出现内部格 → 壳子图。
   这是唯一能让 B 判据有意义的路径。
2. **键饱和/有限团机制（解决贯通巨团）**：按组装体尺寸或 `sum(w)` 施加负反馈
   （如对每个分子已有键数做软上限、或对 E 超过 E_sat 的组装体提高 k_off），
   使尺寸分布有 p90 9 的截断，而不是靠 rupture 在「小团/巨团」之间跳。
3. **R 口径收紧**：把 J_dmg 改成全事件计数（含 cut/break），修复加位点相邻与 e_rep 约束。
4. **复制回路**：让 rep 器官的最小能力组合（分+支+粘）与 M_dir≥0.4 的接触更容易满足；
   子代可育检测需要 B 先成立，故依赖第 1 条。
5. **对照实验**：至少跑一次 M≡0 消融（应零组装）与 B 阈值扫描，确认新机制不是靠阈值硬凑。

---

## 8. 复现

```powershell
cd "G:\AI work\deepseek\work1\alchemy"
$env:PYTHONIOENCODING='utf-8'

# 测试（151 项）
python tests\run_all.py

# demo（终选参数；<90s）
python examples\emergence_demo.py --sample 600 --steps 600 --seed 20261119

# 全量（2000×800，约 68s）
python -m alchemy.emergence --sample 2000 --steps 800 --seed 20261119 --out intake\tmp\calib\big.json

# 扫描探针（临时工具）
python intake\tmp\calib\probe.py --configs-file intake\tmp\calib\configs_final.json --seed 20261119
```

产物：`intake/tmp/calib/demo_600_final.json`、`intake/tmp/calib/big_2000x800_final.json`、
`intake/tmp/calib/configs_*.json`、`intake/tmp/calib/r2_base.json`、`intake/tmp/calib/sweep_round1.json`。

**A0 复核**：`life_report` / `life_report_all` 前后 `_world_digest` 不变；`M≡0` 消融零组装；
同 seed 逐位可复现（`test_emergence` 覆盖）。本轮只改 emergence.py 与参数 JSON，内核模块公式未动。
