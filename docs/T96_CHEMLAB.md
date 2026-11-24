# T96：把推挤/团簇动量移植进 ChemLab（Godot）

## 摘要

用户 m01396 指出 ChemLab 里「大分子簇悬浮不动」，根因是 `sim.gd` 的 `try_move` 只有
「单格重压轻挤一步」：多格分子/锁团的目标格被自己或邻居占用时整团不动；重力对多格
锁团也只是整团检查后原地不动。T95 在 Python 侧验证的链式推挤（P1）与团簇动量（P2）
从未进入 Godot。

本任务在 `godot/chem_lab/scripts/sim.gd` 内实现：

1. **P1 链式推挤**：沿移动方向构造最多 `Kmax=6` 个分子（含锁连通分量作刚体单元）的
   候选链，整链先做边界/占格/锁检查，再逐对用 `J_A/J_B`（质量+受力+动量+粘附+地面摩擦）
   判定，全部通过才统一提交；失败记 `n_push_fail`。
2. **P2 团簇动量**：每分子维护 `vx/vy` 与累积位移 `px/py`，受力按 `F/M·F2V` 加速、
   `γ=0.15` 阻尼、`|v|≤Vmax=2`，按整格推进；冲量用恢复系数 `e=0.2`。
3. **团簇整体受力平移**：每拍对锁连通分量求 `ΣF/M`，超过阈值时取主方向
   `try_move_group` 整团平移 1 格，统计 `n_group_push/n_group_push_fail`。
4. 参数全部进入 `sim.p`，并在 UI「碰撞/推挤」区提供滑条/开关；HUD 追加 push/group/
   mean_speed；`--selftest` 追加统计行。

验证：Godot 4.7.2 headless（`--headless --path . --quit-after 400 --selftest`）在真实
内核（127.0.0.1:8765）下跑通 240 拍，无解析/运行错误；推挤链与整团平移均产生非零计数。
`--no-push` 对照组退回旧规则，行为与改动前基线一致（12.13 vs 11.82 ms/拍，moves
14,798 vs 14,323，属随机波动）。

## 1. 背景与问题

- 旧 `try_move(id, step)`：footprint 目标格全部为空才移动；被占时只允许 **单格、重压轻**
  挤一步。多格分子（`k>1`）与锁团成员几乎无法前进。
- 旧 `try_move_group(ids, step)`：整团做一次占用检查，冲突则整团不动；没有“推别人”的概念。
- 旧重力分支：`lock_rigid_fall=true` 时整团检查后下落，被占即停 → 团簇悬在别人头上。
- 旧三素力分支：`facc` 累积位移，与碰撞解耦；被占时 `facc` 卡在 <1，表现为“黏住”。

结果：世界底部堆一层，上方锁团一旦形成就静止；用户看到的“悬浮”即此。

## 2. 实现落点

### 2.1 `godot/chem_lab/scripts/sim.gd`（869 → 1193 行）

| 位置 | 内容 |
|---|---|
| 顶部常量 | `const F2V := 0.02`（力→速度标定，与 `alchemy/t95_collision.F2V` 一致） |
| `p` 字典 | 9 个 T96 参数（见 §4） |
| `reset()` stats | `n_push/n_push_fail/chain_hist/n_group_push/n_group_push_fail/mean_speed` |
| `place()` 分子 | 增加 `vx/vy/px/py/fx/fy` |
| `_push_fail()` L576 | `n_push_fail += 1` |
| `_clamp_vel()` L579 | Vmax 限幅 |
| `_unit_for()` L586 | 锁连通分量（≥2）作为推挤单元 |
| `_unit_mass/_unit_vel/_unit_force_n` L597–614 | 单元 M、质心速度、ΣF·n |
| `_stick_j()` L616 | 链外锁邻居 `max(0,w)` 之和（w 用 T87 非对称力公式） |
| `_floor_j()` L631 | 下方越界/被非链分子支撑 → `μ·M·g` |
| `_locks_ok_after()` L646 | 整链移动 1 格后与链外锁伙伴仍 ≤`lock_r` |
| `_add_impulse()` L659 | 沿 n 加 Δv 并限幅 |
| `_commit_shift()` L668 | 清旧格→统一写新格，更新 anchor/cells/px/py，`moves += n` |
| `_unit_stats()` L687 | 返回 {M, u=v·n, fn=ΣF·n} |
| `_try_push_chain()` L694 | 见 §3.1 |
| `try_move(id, step, gravity_ctx=false)` L793 | 空则直接移动；被占时 push_enable→`_try_push_chain`，否则旧重压轻 |
| `step()` L885 | 重力 else 分支 `try_move(..., true)`；三素力阶段改 P2 速度积分；新增 2b 整团平移；`mean_speed` 统计 |

### 2.2 `godot/chem_lab/scripts/main.gd`（1026 → 1096 行）

- L291–326：「碰撞/推挤（T96…）」区：1 个 push 开关、6 个参数滑条、1 个 group 开关、1 个阈值滑条。
- `_update_hud()` L810–824：HUD 第二行显示 `push/fail/整团/chain/v̄/开-关`。
- `--selftest` L735–738：打印 `push: n_push=…`；新增 `--no-push` / `--no-group` 开关（L695–700）。
- 参数同步：`_slider()` 把每个普通参数键注册到 `param_controls`（L531）；`_refresh_param_ui()` L534–544 在 `_load_state()`（L1057，调用点 L1068）读档后把 `sim.p` 的值回填滑条/数字框。`sim.save_json()` 已包含 `p.duplicate()`，因此 9 个 push 参数自动随存档保存/恢复。

未改动：`main.tscn`、内核 Python（`alchemy/alchemy/*`、`t9x_*.py`）、`kernel_server.py`。

## 3. 算法

### 3.1 P1 链式推挤（`_try_push_chain`）

1. 起点 `cur=[A]`；若 `cur.size()>Kmax` → `n_push_fail`。
2. 循环：
   - 对 `cur` 的每个格做边界检查；越界 → fail。
   - 把 `cur` 加入 `chain`；计算目标格上的 blocker。
   - 无 blocker → 结束构链；多个 unit → fail；`own.size()+next.size()>Kmax` → fail。
3. 整链占用/锁校验：目标格不被链外分子占用；`_locks_ok_after`。
4. 逐对 A→B 判定：
   - `J_A = M_A·max(0,u_A) + max(0,fn_A)`（重力通道 `+M_A·g`）
   - `J_B = M_B·max(0,−u_B) + stick + floor`
   - `M_A ≥ ratio·M_B` 且 `J_A > J_B`，否则 fail（整链不动）。
5. 冲量更新每个单元速度（§2.6 公式，冲量后 Vmax 限幅）。
6. `_commit_shift(own_ids, step)`；`n_push+=1`；`chain_hist[own.size()]+=1`。

### 3.2 P2 团簇动量

- 每拍 `v ← (1−γ)·v + (F/M)·F2V`，再 Vmax 限幅。
- `px += vx; py += vy`；按符号逐格 `try_move`，失败则清零该分量（防“鬼畜”）。
- 冲量直接写入 `vx/vy`，与力加速共用同一速度场。

### 3.3 团簇整体受力平移

- 对每个锁连通分量（≥2 分子）：`F̄ = ΣF/M`，若 `|F̄| ≥ group_push_thresh`：
  取 8 方向中与 `F̄` 最接近者，`try_move_group(comp, dir)` 整团 1 格；
  成功 `n_group_push+=1`，失败 `n_group_push_fail+=1`。
- 该步在逐分子速度积分之后、反应之前；每团每拍最多一次。

### 3.4 与 Python T95 的差异（口径说明）

| 项 | Python T95 | Godot T96 |
|---|---|---|
| 逐分子驱动力 | `force_on` → 8 方向随机尝试（v1/v2 与 v0 同口径） | 受力→速度积分（P2），保留 `force_scale` 旧路径仅在 push 关时 |
| 时间步 | 1 拍 = 1 tick | 同 |
| 世界 | 160×110，内核 resolve 异步 | 200×140 渲染/世界（selftest 用 T91 预设），内核异步 |
| 反应 | resolve 温度门槛 | 同（既有 ChemLab 逻辑） |
| 初始配置 | E4 环境 300 分子 | T91 预设约 350 分子，`--selftest` 限流 p_react≤0.01 |

因此**T95 的绝对计数不能直接与 T96 的 selftest 数字比较**；这里只做“同一 Godot 场景
下 push 开/关”的对照。

## 4. 参数默认值与 UI

| 参数 | 默认 | UI |
|---|---|---|
| push_enable | true | CheckButton |
| push_e | 0.2 | 滑条 0~1 |
| push_mu | 0.25 | 滑条 0~1 |
| push_kmax | 6 | 滑条 1~24 |
| push_vmax | 2.0 | 滑条 0.1~8 |
| push_gamma | 0.15 | 滑条 0~0.9 |
| push_m_min_ratio | 0.5 | 滑条 0.01~1 |
| group_push_enable | true | CheckButton |
| group_push_thresh | 0.5 | 滑条 0.05~4 |

全部默认值与 `alchemy/t95_config.PUSH` 一致。

## 5. 验证（Godot 4.7.2 headless，真实内核 127.0.0.1:8765）

命令（工作目录 `alchemy/godot/chem_lab`）：

```
Godot_v4.7.2-stable_win64.exe --headless --path . --check-only --script res://scripts/sim.gd
Godot_v4.7.2-stable_win64.exe --headless --path . --check-only --script res://scripts/main.gd
Godot_v4.7.2-stable_win64.exe --headless --path . --quit-after 400 --selftest
Godot_v4.7.2-stable_win64.exe --headless --path . --quit-after 400 --selftest --no-push
Godot_v4.7.2-stable_win64.exe --headless --path . --quit-after 400 --selftest --no-group
```

### 5.1 解析/加载

- `sim.gd`、`main.gd` 的 `--check-only` 均 `EXIT=0`，无 GDScript 解析错误。
- `--headless --quit-after 120` 正常启动退出，无脚本错误。

### 5.2 240 拍自检结果（同一 T91 预设，随机种子未固定，故 N/反应数为随机波动）

| 运行 | tick | N | complete | joins | moves | n_push / fail | 整团 push / fail | mean_speed | rows mean | high/low | 耗时 ms/拍 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `--no-push`（旧规则） | 240 | 345 | 245 | 422 | 14,798 | 0 / 0 | 0 / 0 | 0.000 | 91.7 | 189 / 92 | 12.13 |
| 默认（push+group） | 240 | 341 | 228 | 384 | 28,494 | 78 / 30,944 | 1,999 / 3,283 | 0.744 | 75.8 | 242 / 38 | 15.71 |
| push 开、`--no-group` | 240 | 357 | 199 | 342 | 20,516 | 107 / 23,133 | 0 / 0 | 0.615 | 82.9 | 238 / 60 | 13.57 |

- 三次运行均 `hard_walls=true`、`oob_cells=0`、`max_row=139 (=H-1)`；无脚本错误、无崩溃。
- `--no-push` 与改动前基线（N=344, moves=14,323, rows=91.0, 11.82 ms/拍）差异属随机波动，
  说明 push 关闭时行为未被破坏。
- push 打开后 `rows mean` 从 91.7 降到 75.8：团簇被净力抬离底部，直接回应用户观察。
- 成功/失败比约 1:400（78 vs 30,944）：质量比、地面摩擦与边界判定是主拒绝原因；
  这也符合 T95 A/B 中 v1 的 `n_push_fail` 量级。
- 性能：15.71 vs 12.13 ms/拍 = **1.30×**（<2× 目标）；`--no-group` 为 13.57 ms/拍。

## 6. 关键 stats 与解读

- `n_push`：成功链式推挤次数。默认 240 拍 78 次；关 group 后 107 次（少了整团预移动，
  更多单链机会）。
- `n_push_fail`：质量比 / J_B / 边界 / 质量比 / 锁距任一不满足即计数；量级 2~3 万，
  说明大多数接触仍推不动（底部堆叠、被更重团压住）。
- `n_group_push`：锁团整团平移成功 1,999 次（240 拍），是“悬浮团”被移动的主通道；
  关掉后 rows mean 从 75.8 回到 82.9。
- `mean_speed=0.744`：P2 速度场使分子持续带速度（旧规则纯位移、无速度），HUD 可观测。
- `chain_hist={2:67, 3:11}`：绝大多数推挤只牵动 1~2 个被推分子，未出现长链雪崩；
  `Kmax=6` 未被触顶（符合设计）。

## 7. 失败模式与局限

1. **推挤失败率极高**：质量比 0.5 + 地面摩擦 `μ·M·g` 使轻分子推不动重团；这是设计
   取舍（避免“一推全动”），但观感上仍可能显得“黏”。可把 `push_mu` 降到 0.1、
   `push_m_min_ratio` 降到 0.2 观察。
2. **整团平移只走 1 格/团/拍**，且用净力主方向；净力接近 0 的对称团不动（合理）。
3. **未做旋转/破碎**：团簇按刚体平移，内部不旋转，也不因剪切断锁（T95 §8 后续）。
4. **速度场无热噪声**：布朗已删，静止团在净力为 0 时完全静止；`mean_speed` 可低至 0。
5. **headless 自检随机性**：未固定 seed，不同次运行的 N/complete/moves 有波动；
   A/B 结论基于同一预设的定性方向与量级，不做逐位对比。
6. **内核异步**：反应数与内核队列有关（`pend` 1~3），不影响碰撞统计。
7. **selftest 随机波动**：同配置多次运行 `n_push` 78~128、`n_group_push` 1,779~1,999、`rows mean` 75.8~77.9 属正常（未固定 seed）；表格取日志 [3] 那一次的代表值，结论方向不变。

## 8. 复现

```
cd alchemy/godot/chem_lab
Godot_v4.7.2-stable_win64.exe --headless --path . --check-only --script res://scripts/sim.gd
Godot_v4.7.2-stable_win64.exe --headless --path . --quit-after 400 --selftest
Godot_v4.7.2-stable_win64.exe --headless --path . --quit-after 400 --selftest --no-push
Godot_v4.7.2-stable_win64.exe --headless --path . --quit-after 400 --selftest --no-group
```

（需先启动 `kernel_server.py` 于 127.0.0.1:8765；UI 手动复现：打开 ChemLab，物理区下方
「碰撞/推挤」开关，观察底部锁团是否开始移动、HUD push 计数是否增长。）

## 9. 产物清单

- 修改：`alchemy/godot/chem_lab/scripts/sim.gd`（869→1193 行）
- 修改：`alchemy/godot/chem_lab/scripts/main.gd`（1026→1080 行）
- 修改：`alchemy/godot/chem_lab/docs/CHEMLAB_PARAMS.md`（追加 T96 段）
- 新增：`alchemy/docs/T96_CHEMLAB.md`（本文件）
- 新增：`alchemy/t96_chemlab.log`（命令与输出；含参数同步补丁后的复验记录）
- 未改：`main.tscn`、Python 内核与 `t9x_*.py`、`kernel_server.py`
