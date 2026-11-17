# T64 生态群系：独立验证报告

> 验证脚本：`t64_verify.py`；输出：`t64_verify.json`（76,894 B）；
> 验证时间：2026-11-17 15:29:29（耗时 3.0 秒）；验证者：独立 verifier（不跑模拟、只读文件）。

## 0. 总判定

**overall = PASS**

| 指标 | 数量 |
|---|---|
| PASS | 102 |
| FAIL | 0 |
| PENDING | 0 |
| SKIP | 0 |
| INFO | 2 |

输入文件 27 个，全部记录 SHA256（12 个 `t64_biome_B*.json` + 12 个 `t64_biome_B*_state.json`
+ `t64_biomes.json`、`t64_biome_index.json`、`t64_control_B01.json`）。

## 1. 检查分组与结果

| # | 检查 | 结果 | 通过/总数 |
|---|---|---|---|
| 1 | 设计与投料合规（`t64_biomes.json`） | PASS | 8/8 |
| 2 | 每群系投料（result config / load_spec / biome 元数据） | PASS | 12/12 |
| 3 | 质量与元素守恒（终态分子/原子/逐元素/state 汇总） | PASS | 12/12 |
| 4 | 温度日程（1000→25°C 退火 975 + 25°C 浮动 600） | PASS | 12/12 |
| 5 | 判定自洽（reaction_counts / events_total / 抽样事件 / cap） | PASS | 12/12 |
| 6 | 快照（snapshots 数量/时间点/每帧点数） | PASS | 12/12 |
| 7 | 终态表 sanity（final_composition / top structures） | PASS | 12/12 |
| 8 | state 与 result 一致性（总数/组成/逐元素/结构合法性） | PASS | 12/12 |
| 9 | 无化学对照（`t64_control_B01.json`） | PASS | 6/7（1 项 INFO） |
| 10 | index 与 result 一致性（`t64_biome_index.json`） | PASS | 2/2 |
| 11 | 输入文件 SHA256（27 个输入） | PASS | 2/3（1 项 INFO） |

## 2. 关键实测

### 2.1 设计合规（8 项）

- 12 群系 id 完整、顺序 B01~B12；
- 每群系 elements/atoms_per_element/L/name 与独立预期一致；
- 每群系元素数 3~9、均含至少一种三价元素（O/P/K）；
- 投料仅含本群系元素的双原子单质；
- 密度/空间/总原子与设计值一致。

### 2.2 投料（12 项）

每群系 `config.load_spec` 仅含本群系元素的双原子单质，分子数 = atoms_per_element/2，
初始分子/原子数 = 设计值（B01/B02/B03/B05/B06：6,000 分子/12,000 原子；B04/B07/B12：
7,000/14,000；B08/B09/B10：7,500/15,000；B11：9,000/18,000）。

### 2.3 质量与元素守恒（12 项）

- `final_atoms == 设计总原子`，12/12 通过（3,980 分子群系的原子数均为 12,000 等）；
- 逐元素终态 == 投料，delta=0；
- `Σcomp`（终态分子×原子数）== summary.final_atoms == state 汇总。
- final_N：3,980 / 3,979 / 3,979 / 5,213 / 5,872 / 5,952 / 5,226 / 1,542 / 7,288 / 7,296 / 4,185 / 5,202
  （合计 59,714 分子），逐群系与结果文件一致。

### 2.4 温度日程（12 项）

- `config.temp_schedule` 存在且字段正确（T0=1000、T_mid=25、anneal_minutes=975、hold_minutes=600、
  day_amp=8/240、year_amp=3/900、总 1575）；
- 1575 行时间序列 T 逐分钟复算 max|ΔT| < 1e-6；
- 恒温段 T 实测 15.56~35.71°C（波动 20.15°C ≥ 8°C，日/季节浮动生效）；
- `final_T = 22.25°C` 与日程末值（t=1574）一致。

### 2.5 判定自洽（12 项）

- `reaction_counts` 四类判定之和 == 判定总数；
- `events_total` 与时间序列末行一致；
- capped 占比全部 <5%（B09 0.181%、B11 0.159%、B10 0.053%、B05/B08≈0，其余 0）；
- 抽样事件（每群系 4 次抽样合计 130,106 条，含 30,000 蓄水池）原子/价数守恒 0 违规；
- 合并后最大原子数 ≤40（实际最大 39）；`decomp` 仅 B08=1、B10=2。

### 2.6 快照（12 项）

12 群系各 25 帧、时间点与设计一致、每帧点数 >0（B08 末帧 1,542 点为最少）。

### 2.7 终态表与 state（24 项）

- `final_composition` 原子数合计 == final_atoms、0 个 None；
- top 结构（每群系 4~17 个）全部合法（价数填满、无自环/重复边/越界）；
- state 的总分子/总原子/组成/逐元素 == result 终态；结构合法。

### 2.8 无化学对照（7 项，6 PASS + 1 INFO）

`t64_control_B01.json`：`chemical_reactions=False`；装载 6,000 分子/12,000 原子；
min=706.5、median=750.4、mean=750.2、fraction_ge_500=1.0、runtime 2.3 秒。
INFO：对照只用于验证"纯物理运移标定"，不与 B01 终态组成对比（与 T57/T59/T62/T63 同口径）。

### 2.9 index 与 SHA256（5 项，4 PASS + 1 INFO）

`t64_biome_index.json` 12 行全部 `status=done`，final_N/final_T/reaction_counts 与结果文件一致；
27 个输入文件的 SHA256/字节数全部记录；INFO：`t64_analysis.json` 与 `t64_verify.json` 自身不在输入集合
（分析文件生成于验证之后的部分字段不作为验证对象）。

## 3. 结论

T64 生态群系 12 群系全部通过独立验证：投料合规、质量/元素守恒、温度日程（含逐分钟复算）、
判定自洽、快照完整、终态表与 state 一致、无化学对照达标、index 与文件哈希完整。
无 FAIL、无异常；仅两条 INFO（对照用途、分析文件不列入输入集合），不影响结论。
