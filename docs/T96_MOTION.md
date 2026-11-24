# T96：让分子动起来 —— 连续半径统一 + ChemLab 推挤/动量/整团平移

> 触发：用户 m01233「为什么现在分子又都不动了，尤其零重力下，小分子基本都悬浮不动而不是相互吸引排斥」、
> m01308「散素不是改成连续的了吗？每一点值就是一格作用范围」、m01380「为什么很多大分子簇悬浮在空中不动」、
> m01396「改 1、3 条，顺便把之前的两条也修了，全部同步到 chemlab：统一半径规则：Python 内核和脚本同步为
> R_att=clamp(Q,1,R_MAX)，删掉 10 点档位；断弱键已记入 TODO，本轮未实现」。

## 摘要

T96 修了三件事，全部同步到 ChemLab：

1. **半径规则统一（T96-A）**：`alchemy/three_su.py` 从「10 点一档」（`r_att=1+[Q≥10]+[Q≥20]`、
   `r_rep=1+[Q≥15]+[Q≥30]`）改为与 ChemLab 一致的连续规则
   `r_att=clamp(Q,1,R_MAX)`、`r_rep=clamp(round(0.7Q),1,R_MAX)`，`R_MAX` 默认 12；
   各 Python 世界以自身 `force_r`（力扫描窗口）为封顶，做到「半径封顶 == 扫描窗口」。
   取整用 half-away-from-zero，与 GDScript `round()` 一致（Q=15 时旧 Python 内置 round 会得 10、ChemLab 得 11）。
2. **ChemLab 推挤链（T96-B P1）**：`try_move` 被占时构造整条推挤链（锁连通分量当刚体单元，链长 ≤ `Kmax=6`），
   先做整链边界/占格/锁校验，再逐对用 `J_A`（质量·动量+受力，重力通道加 `M·g`）对 `J_B`
   （质量·动量+粘附+地面摩擦 `μ·M·g`）判定，过质量比门槛后按一维冲量（`e=0.2`）交换速度，全部通过才统一提交。
3. **团簇动量 + 整团受力平移（T96-B P2/2b）**：每分子维护 `vx/vy/px/py`，力→速度 `v=(1-γ)v+(F/M)·F2V`、
   `γ=0.15`、`|v|≤Vmax=2`；每拍对锁连通分量求 `ΣF/M`，超阈值（0.5）时取主方向整团平移 1 格。

结果（Godot 4.7.2 headless，真实内核，240 拍 selftest，T91 预设）：旧规则 `moves=14,798`、rows mean **91.7**、
无推挤统计；新规则 `moves≈26k`、`n_push≈78~94`、`n_push_fail≈3.1 万`、`n_group_push≈1,922~1,999`、
rows mean **75.8~76.5**（锁团被净力从底部抬回中部）、`mean_speed≈0.74~0.78`、性能 **1.3×**（<2× 目标）。
Python 侧 `tests/run_all.py` **150/150 PASS**。

## 1. 问题：为什么“都不动”

用户看到两种“不动”，根因不同：

### 1.1 零重力下小分子孤立不动

- 运动源只剩三素力与重力；布朗已在 T95 删除（按用户要求）。
- 旧 Python 半径档位下，Q<10 的小分子 `r_att=1`：只有**紧邻一格**有作用，`d=2` 处衰减为 0。
  E4 类世界 400 分子/160×110、占格率 2.27%，8 邻域期望邻居 0.18 → **83.4% 分子初始无邻居**；
  Q=0 体系（B3_OXC、T93 OXC 冰壳）半径钳到 1 → 84% 分子永久零力。
- 实测（`diag_static.py`，T95 世界 v2/nomem_G00/G=0，400 拍）：230 个非主体活分子中
  t=0 零力 **181 (78.7%)**、t=400 **184 (80.0%)**，`r_att` 全为 1，移动 6.93 次/拍（≈3%/拍）。

### 1.2 大分子簇“悬浮”不动

`godot/chem_lab/scripts/sim.gd` 旧 `try_move` 只有「单格重压轻挤一步」：
多格分子（k>1）与锁团的目标格被成员/邻居占用时直接 `return false`；重力对锁团只做整团检查后原地不动。
按旧规则模拟紧凑 7×7 单格分子团（49 个）：**25 个一步都动不了**，其余边界分子净力朝内、目标格被占。
“悬浮”= 零重力或 C2 等 `mass=0` 分子不受重力 + 锁把边界钉死 + 无布朗/热运动 + 反应产物原地生成。

## 2. T96-A：半径规则连续化

### 2.1 公式

| 项 | 旧（T81~T95） | 新（T96 起） |
|---|---|---|
| 吸引半径 | `1+[Q≥10]+[Q≥20]` ∈ {1,2,3} | `clamp(Q, 1, R_MAX)` |
| 排斥半径 | `1+[Q≥15]+[Q≥30]` ∈ {1,2,3} | `clamp(round(0.7·Q), 1, R_MAX)` |
| 封顶 | 固定 3 档 | `R_MAX` 默认 **12**（= ChemLab `r_cap` 默认）；Python 世界用 `force_r` |

`Q = 3n_K+2n_A+1n_F`（散素点数）——Q 点即半径格数，与用户说的「每一点值就是一格作用范围」一致。
取整用 half-away-from-zero（Q=15 → 11），与 GDScript `round()` 对齐。

### 2.2 Q → r 新旧对照（节选）

| Q | 旧(att,rep) | 新(R_MAX=12) | 新(force_r=2 的世界) |
|---|---|---|---|
| 0 | 1,1 | 1,1 | 1,1 |
| 2 | 1,1 | 2,1 | 2,1 |
| 6 | 1,1 | 6,4 | 2,2 |
| 10 | 2,1 | 10,7 | 2,2 |
| 11（C3K3F2） | 2,1 | 11,8 | 2,2 |
| 15 | 2,2 | 12,11 | 2,2 |
| ≥20 | 3,2 | 12,12 | 2,2 |

（完整 Q=0..24 表见 `docs/THREE_SU_AXES.md` §10 与 `alchemy/three_su.py` 自检输出。）

### 2.3 Python 侧封顶与调用点

`TS.scores/pair_force/radii` 新增 `r_max=None`（缺省 `R_MAX=12`）。
各世界把自身 `force_r` 作为 `r_max` 传入，保证「半径封顶 == 力扫描窗口」：

| 世界 | force_r / 封顶 |
|---|---|
| t82_env_sim | 3 |
| t83_env_axes（基类，覆盖 t84/t85/t86/t93/t94/t95） | 2 |
| t87_env_asym（覆盖 t87/t93/t94/t95 的 ensure_type） | 2 |
| t90_body_growth | GATE_R=3 |
| kernel_server / 静态分析脚本 | 12（默认 R_MAX） |
| ChemLab sim.gd | `r_cap` 默认 12（UI 2~24） |

> **注意**：Python 世界多数 `force_r=2`（性能考虑），半径被封顶在 2 格；ChemLab 默认 12 格。
> 因此 ChemLab 的“长程吸引”比 Python 世界更明显；若要 Python 世界也长程，需调大 `force_r` 并重跑（见 §5）。

### 2.4 影响（smoke，临时 outdir，未覆盖历史 JSON）

- `t94_life.py --quick`：29.8s（基线 28.5s，+4.6%）；contacts_env_body 多数上升
  （no_membrane_dyn 0→291、membrane_PK_FO 25→392、oxc_shell_FO 3→566），n_react_total 普遍升，conservation 全 True。
- `t95_run.py --quick`：40.55s（基线 39.91s）；`n_push_fail` 显著升（v1 nomem_G00 340→976、
  v2 PK_G00 2,545→4,306），`mean|v|` 升，coverage 多升。
- 机制：小 Q 分子半径变大（1→2），作用邻域从 8 格扩到 24 格（force_r=2 时），接触/反应/推挤自然增加。

## 3. T96-B：ChemLab 移植

### 3.1 实现

`sim.gd`（869→1193 行）+ `main.gd`（1026→1096 行）：

- **P1 链式推挤** `_try_push_chain`：候选链 ≤ Kmax=6；整链边界/占格/锁（`_locks_ok_after`）先校验；
  逐对 `J_A = M_A·max(0,v_A·n) + max(0,F_A·n)·dt`（重力通道再加 `M_A·g`）vs
  `J_B = M_B·max(0,-v_B·n) + J_stick(B) + J_floor(B)`，需 `M_A ≥ min_ratio·M_B` 且 `J_A > J_B`；
  通过后一维冲量 `v_A'=(M_A v_A+M_B v_B−M_B e(v_A−v_B))/(M_A+M_B)`、`v_B'` 对称，`Vmax` 限幅；
  最后 `_commit_shift` 统一写格（元素守恒、footprint 完整）。
- **P2 速度场**：每分子 `vx/vy/px/py`，`v=(1-γ)v+(F/M)·F2V`（F2V=0.02），按累积位移整格推进。
- **2b 整团平移**：每拍对锁连通分量求 `ΣF/M`，`|ΣF|/M ≥ group_thresh` 时取主方向 `try_move_group` 整团 1 格。
- 参数 9 个进 `sim.p` + UI「碰撞/推挤」区滑条/开关：`push_enable`、`push_e=0.2`、`push_mu=0.25`、
  `push_kmax=6`、`push_vmax=2.0`、`push_gamma=0.15`、`push_m_min_ratio=0.5`、`group_push_enable`、
  `group_push_thresh=0.5`；HUD 第二行显示 push/fail/整团/chain/v̄；`--no-push`、`--no-group` 对照开关。
- 新增 stats：`n_push`、`n_push_fail`、`chain_hist`、`n_group_push`、`n_group_push_fail`、`mean_speed`。

### 3.2 验证（Lead 独立复跑）

`--headless --path . --quit-after 400 --selftest`（Godot 4.7.2，kernel_server 127.0.0.1:8765）：

| 运行 | moves | n_push / fail | 整团 push / fail | mean_speed | rows mean | ms/拍 |
|---|---|---|---|---|---|---|
| `--no-push`（旧规则） | 14,798 | 0 / 0 | 0 / 0 | 0.000 | 91.7 | 12.13 |
| 默认（push+group） | 28,494 | 78 / 30,944 | 1,999 / 3,283 | 0.744 | 75.8 | 15.71 |
| Lead 复跑（默认） | 26,132 | 94 / 31,864 | 1,922 / 3,227 | 0.784 | 76.5 | 16.23 |
| push 开、`--no-group` | 20,516 | 107 / 23,133 | 0 / 0 | 0.615 | 82.9 | 13.57 |

均 `oob_cells=0`、`max_row=139 (=H−1)`，无脚本错误；`--check-only` 两脚本 EXIT=0。
selftest 未固定 seed，n_push 78~128 属随机波动；rows mean 的下降（91.7→75.8~76.5）是整团平移贡献的直接证据。

### 3.3 参数文档

`godot/chem_lab/docs/CHEMLAB_PARAMS.md` 已加 T96 段（参数表/规则/headless 自检），
并把第 71 行旧的「10 点一档」半径句改为连续公式。

## 4. 局限

1. **仍无热运动/布朗噪声**（用户要求全局删除）：净力为 0 的对称团完全静止；这属于物理上合理但观感上像“死”。
   若要让静止世界也有扩散，需要单独设计“温度驱动速度`（下一步，未实现）。
2. **推挤失败率极高**（成功率约 1:400）：质量比 0.5 + 地面摩擦 μ·M·g 使轻分子推不动重团。可调 `push_mu`/`push_m_min_ratio`。
3. **只平移不旋转/不破碎**：团簇按刚体单元处理；断弱键（可断键/熔化）按用户要求记 TODO、本轮未实现。
4. **Python 世界 force_r 封顶小（2~3）**：长程效果只在 ChemLab（r_cap=12）完整；旧 T81~T95 的半径/长程力数字不可与新规则直接比较。
5. **kernel_server `ratt/rrep` 变为 1..12 连续值**：`sim.gd` 自行用 `_radius_of_q` 重算并覆盖，未见破坏；外部消费者若断言 ≤3 需注意。
6. **T94/T95 正式报告未按新口径重跑**：其结论方向仍成立，但具体接触/推挤/膜留存数字已变（见 §2.4），引用时须注意。

## 5. 复现

```
cd alchemy/godot/chem_lab
Godot_v4.7.2-stable_win64.exe --headless --path . --check-only --script res://scripts/sim.gd
Godot_v4.7.2-stable_win64.exe --headless --path . --quit-after 400 --selftest
Godot_v4.7.2-stable_win64.exe --headless --path . --quit-after 400 --selftest --no-push
Godot_v4.7.2-stable_win64.exe --headless --path . --quit-after 400 --selftest --no-group
python alchemy/three_su.py          # 半径规则自检 + Q=0..24 表
python tests/run_all.py             # 150/150
```

UI 观感：在 Godot 编辑器按 F5 重跑（旧场景需重新加载），物理区下方「碰撞/推挤」开关；
观察底部锁团是否开始移动、HUD push/整团计数是否增长、rows mean 是否下降。

## 6. 产物清单

- 修改：`alchemy/alchemy/three_su.py`（R_MAX + 连续 radii/scores/pair_force + 自检）
- 修改：`t82_env_sim.py`、`t83_env_axes.py`、`t87_env_asym.py`、`t90_body_growth.py`（force_r 封顶透传）
- 修改：`alchemy/godot/chem_lab/scripts/sim.gd`（869→1193 行）、`main.gd`（1026→1096 行）
- 文档：`docs/THREE_SU_AXES.md` §10、`docs/T96_CHEMLAB.md`、`docs/T96_MOTION.md`（本文件）、
  `godot/chem_lab/docs/CHEMLAB_PARAMS.md`（T96 段 + 第 71 行修正）
- 注记：`INDEX.md`、`HANDOFF.md`、`docs/T83_ENV_AXES.md`、`docs/T87_ENV_ASYM.md`、`docs/T93_STATIC.md`（旧档位句加 T96 说明）
- 验证：`t96_chemlab.log`（headless 命令与输出；包含 Lead 复跑）
