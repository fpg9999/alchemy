# T91 三元组搜索：主体 A + 锁住的 B + 只在热区生成 A 的 C

> 2026-11-21。规则 = 规则 1~11（`natural_engine`）+ 三素非对称力（`alchemy/three_su.py`）。
> 目的：为「A 主体团簇在热区被喂食、并入而生长」的假说找**化学上自洽的三元组**——
> A 与 B 强吸引锁定但不反应；B 与 C 只在 A 所在的高温区反应生成 A；环境温度下 B+C 惰性。
> 工具：`t91_search.py`（搜索）、结果 `t91_candidates.json`。

## 0. 摘要

- 从 84,225 条目录中取 **2~5 原子小分子池 551 种**，穷举无序对 **151,525 对**；其中「B+C 恰好完全反应生成单一产物 A，且 A 在目录内」的三元组 **38,312 组**（32.8 s 扫完）。
- 依次施加温度窗口/吸引锁/自粘/resolve 行为四类条件后，**仅 4 组候选**（score 0.95），全部是 **7 原子富 F 主体**：
  **O2AF4+OAF+OF3**、**O2WF4+OWF+OF3**、**XK2F4+XKF+KF3**、**XP2F4+XPF+PF3**。
- 机制条件高度一致：`T_hot = 8`（A 的温度轴 `L+2F`）、`T_env = 2.0`、`csum(B+C) = 5`（2 < 5 ≤ 8 进热区反应）、`csum(A+B) = 8`（≤ 8 使 A+B 在热区也不反应）；B+C 在热区 `resolve` 为 **complete 且产物恰为 A**。
- 结论：**满足「锁住食物 B、热区 B+C→A」的化学三元组存在但极稀少**（4/151,525 ≈ 0.0026%），说明该「热区投喂生长」路径依赖精确的温度窗口与富 F 小分子；ChemLab 预设即取 `XK2F4 + XKF/KF3`。

## 1. 方法

### 1.1 候选池与三元组生成

- 小分子池：目录中 `natoms ∈ [2,5]` 的分子式 → **551 种**（`t4_catalog_all_validated.json`，需先 `python unpack_data.py`）。
- 对 `(B, C)` 无序对（`B` 取字典序在前者）：
  - `sum(vec(B)+vec(C)) > MAX_A = 12` 跳过（主体过大）；
  - `E.complete_products(B+C)` 必须**恰好 1 个产物**，记为 A，且 A 在目录内、`natoms ≤ 12`；
  - 记录三元组 `(A, B, C)` 并去重。→ 151,525 对产出 **38,312 组**。

### 1.2 筛选条件（`t91_search.py:127-200`）

记 `TA = L(A) + 2·F(A)`（A 的温度轴），`cval = max(1, 原子数-1)`，`csum(XY) = cval(X)+cval(Y)`，
`wAB = K_A·A_att(A) − K_R·A_rep(B)`（`three_su.scores` 的非对称力）。

| 条件 | 含义 | 被筛掉 |
|---|---|---|
| `TA ≥ csum_AB` 且 `csum_BC ≤ TA` | 热区温度足以进入 complete 分支（窗口成立） | 38,210（`hot too low`） |
| `wAB ≥ LOCK_W = 1.0` | A→B 强吸引锁（单向即可，实际 wBA 同值） | 48（`no_lock`） |
| `wA_self ≥ SELF_A = 1.2` | A 自身有粘性（能成团） | 2（`A not sticky`） |
| `resolve([A,B], TA)` 为 complete 且产物 = `{A,B}` | A+B 在热区**不反应**（并列不合并） | 37（`A+B reacts (hot)`） |
| `resolve([B,C], TA)` 为 complete 且产物 = `[A]` | B+C 在热区**干净合成 A** | 0 |
| `resolve([A,B], T_ENV=2.0)` 为 none（或 complete 且产物 = `{A,B}`） | A+B 在环境温度惰性 | 11（`A+B reacts (ambient)`） |

- 打分：`0.40·min(1, min(wAB,wBA)/3) + 0.25·min(1, wA_self/2.5) + 0.20·min(1,(TA−T_ENV)/8) + 0.15·[A ∈ 热区产物]`。
- 注：这里的 `complete` 表示 resolve 走到"完整反应"分支；产物等于输入即等价于**未发生净反应**。

## 2. 结果：4 组候选

| A（主体） | A 原子 | B（食物） | C（热区补料） | wAB | A 自粘 | T_hot | csum_BC | csum_AB | B+C 热区产物 | score |
|---|---|---|---|---|---|---|---|---|---|---|
| `O2AF4` | 7 | `OAF` | `OF3` | 7.5 | 7.5 | 8 | 5 | 8 | `O2AF4` | 0.95 |
| `O2WF4` | 7 | `OWF` | `OF3` | 6.5 | 6.5 | 8 | 5 | 8 | `O2WF4` | 0.95 |
| `XK2F4` | 7 | `XKF` | `KF3` | 5.0 | 5.0 | 8 | 5 | 8 | `XK2F4` | 0.95 |
| `XP2F4` | 7 | `XPF` | `PF3` | 3.5 | 3.5 | 8 | 5 | 8 | `XP2F4` | 0.95 |

共同点：主体都是 7 原子、F 富集（2 个 F3 单元或 4 F）、`TA = 8`；B 为 `OAF/OWF/XKF/XPF`（3~4 原子），C 为对应 `F3` 端基（`OF3`/`KF3`/`PF3`）；`B+C` 恰好补成 A。

## 3. 解释与用法

- 把 A 做成主体团簇（自粘 + 富 F），B 被 A 的吸引力锁在表面；环境温度 2 时 B/C 惰性，A 表面附近（热区，T≈8）`B+C→A`，新生成的 A 与主体同种、可并入主体 → 实现"**投喂-并入-生长**"的化学闭环。
- 这是**静态化学条件筛选**（resolve + 力参数），没有跑动态世界；动态验证由 ChemLab 预设与后续 T92 群系网格承担。
- ChemLab（`godot/chem_lab/`）预设 4 组主体+食物即来自本表，见 `godot/chem_lab/README.md`。

## 4. 复现

```powershell
$env:PYTHONIOENCODING="utf-8"
python unpack_data.py        # 若 t4_catalog_all_validated.json 不存在（clone 后通常只有 _data_gz/）
python t91_search.py         # 约 33 s → t91_candidates.json（并打印 top 30 表）
```

## 5. 文件

- `t91_search.py`（搜索，8.0KB）
- `t91_candidates.json`（2.3KB：`meta` 含各阶段计数，`candidates` 4 组）
- 相关：`alchemy/three_su.py`（三素非对称力）、`natural_engine.py`（规则 1~11 与 resolve）、`docs/THREE_SU_AXES.md`（三素口径）、`docs/T92_BIOME_GRID.md`（后续群系全扫）、`godot/chem_lab/`（交互验证）
