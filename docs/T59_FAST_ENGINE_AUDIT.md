# T59 · fast_pot.py / natural_engine fast 路径 独立审计报告

> 审计对象：`G:\AI work\deepseek\work1\alchemy\fast_pot.py`、
> `natural_engine.py` 的 `set_fast(True)` 快速路径
> 审计方式：**只读**（未修改被审文件），由独立审计脚本自动对照 `pot_v4` / `natural_engine.greedy_bond`
> 审计脚本：`t59_fast_engine_audit.py`；明细数据：`t59_fast_engine_audit.json`
> 随机种子：20261117；运行环境：Python（DSH primary runtime），alchemy 目录
> 运行耗时：**34.9 s**（脚本整体，含 84,225 条目录读取）
> 背景：T58 暴露 >16 原子完全反应 F 过慢；本审计为今晚 T59 大实验（9 元素、100+ 物质、两阶段）前置验证。

---

## 0. 摘要结论

**4 项审计全部通过（PASS），未发现 `fast_pot.py` 与 `natural_engine` fast 路径的功能性 bug。**

| # | 审计项 | 结果 | 关键数字 |
|---|---|---|---|
| 1 | 完全反应等价（vs `pot_v4.simulate`） | ✅ 通过 | **27,315 个向量 0 不一致**（公式/label/None/level6 全一致） |
| 2 | 固定键 / 不完全反应等价 | ✅ 通过 | 450 对真实分子 + 200 组合成 base_edges **0 不一致**；level6 0 不一致；set_fast 端到端 890 次对比 0 不一致 |
| 3 | 速度（F 单次） | ✅ 通过 | ≤24 原子 **0.3~1.2 ms**（慢版 1.1~6.2 ms，**3.6~5.0×**）；30~60 原子 **5.6~6.3×** |
| 4 | 缺陷排查 | ✅ 通过 | ring_flags 300 图 0 误判；结构化 32 例、大 n 80 例、高对称并列 5 例 0 不一致；dt 全为 int |

**结论：fast_pot 可以放心用于 T59**（`natural_engine.set_fast(True)`）。
两条操作注意（不影响正确性，见 §5）：
- `set_fast()` **不会清缓存**：若先跑过慢版 F，再切 fast，旧缓存会直接命中（结果正确但不会重算）。建议 `set_fast(True)` 后调用 `clear_caches()`。
- `fast_pot` 模块 docstring 里列的 `simulate_with_base` / `simulate_level6` **并未实现**；`natural_engine` 用的是 `simulate(..., base_edges=...)`，不受影响，但外部若按 docstring 调用会 `AttributeError`。

---

## 1. 审计方法

- **只读**：只调用 `fast_pot.simulate`、`natural_engine` 公开函数与 `pot_v4.simulate` 作对照；未修改任何被审文件。
- **对照组**：
  - 完全反应：`pot_v4.simulate(atom_list, return_level6=True)`（规则 1~11 的正式实现）；
  - 不完全反应/固定键：`natural_engine.greedy_bond(atom_list, base_edges)`（规则 1~11 + 固定键原实现）；
  - **level6（固定键）独立参考**：审计脚本用 `inspect.getsource(NE.greedy_bond)` 复制 slow 源码，
    末端改为返回 `(mols, level6, bond)`，得到与 slow 逐字相同的 level6；对"结束前未捕获 level6"的
    post-loop 情形，再用最终 `bond` 矩阵独立重算组件块。这样固定键下的 level6 / 规则 10 有独立真值。
- **比较口径**：
  - 产物：`(formula, mol_label)` 多重集（`pot_all.mol_label` 规范形，与原子顺序无关）；
  - 失败：`None` / 非 None 状态完全一致；
  - level6：块列表按 **(原子索引集合, mol_label)** 且**保持块顺序**逐项相等；
  - fast / slow 切换：每次 `set_fast(...)` 后都 `clear_caches()`，避免缓存掩盖。
- 数据：`t4_catalog_all_validated.json`（84,225 条，其中 2~8 原子小分子 3,931 条）、
  `substances.json`（29 种聚素物质）、随机小分子池。

---

## 2. 通过 / 差异总表

| 审计项 | 检查量 | 不一致 | 判定 |
|---|---|---|---|
| 1. 完全反应等价 | 27,315 向量（穷举 ≤7 原子 11,440 + =8 原子 12,870 + 随机 8~24 3,000 + 边界 5） | **0**（含 level6 0） | PASS |
| 2. 固定键/不完全反应 | 450 真实对（base_edges 共 4,732 条，58 对发生重排）+ 200 合成 base + 890 次 set_fast 端到端 | **0**（含 level6 0） | PASS |
| 3. 速度 | n=12/16/20/24/30/40/60 + 小 n=2~10 + 端到端 n=20/24 | 每档正确性均通过 | PASS |
| 4. 缺陷排查 | 300 随机图 ring + 32 结构化 + 80 大 n + 5 高对称 + 5 边界 | **0** | PASS |

---

## 3. 分项结果

### 3.1 完全反应等价（PASS，0/27,315）

`fast_pot.simulate(atoms, return_level6=True)` vs `pot_v4.simulate(atoms, return_level6=True)`：

| 子集 | 数量 | 公式多重集 | mol_label 结构多重集 | level6 块 |
|---|---:|---:|---:|---:|
| 穷举：9 元素、总原子 0~7 全组合 | 11,440 | 0 差异 | 0 差异 | 0 差异 |
| 穷举：总原子 = 8 全组合 | 12,870 | 0 差异 | 0 差异 | 0 差异 |
| 随机：总原子 8~24（85% 偶数价和 / 15% 任意，含 None） | 3,000 | 0 差异 | 0 差异 | 0 差异 |
| 边界：空向量、单原子、单 F 等 | 5 | 0 差异 | 0 差异 | 0 差异 |

- 其中 **12,804 例双方同为 None**（奇数价和 / 无法成键），失败/成功状态 0 不一致；
- `return_level6=True` 的层级块（全局原子索引集合 + 块内 `mol_label`）**27,315 例全部逐块一致**，
  包括 Lead 提到的 **post-loop level6** 情形（见 §3.2 的专门覆盖）。
- 结论：**fast_pot 是 pot_v4 规则的逐条等价实现**，包括产物结构、失败语义与中间态块。

### 3.2 固定键 / 不完全反应等价（PASS）

#### 3.2a 真实分子对（450 对，0 不一致）

- 样本：29 聚素物质 + 3,931 个 ≤8 原子目录小分子随机配对（两分子总原子 ≤14）；
- 对每对用 **t28 断键逻辑**（`select_class` → 每条该键类元素对断 1 根）得到 `base_edges`，
  共 **4,732 条保留固定键**；
- `fast_pot.simulate(atom_list, base_edges=kept)` vs `natural_engine.greedy_bond(atom_list, kept)`：
  - 产物 `(formula, mol_label)` 多重集 **0 不一致**；
  - 其中 **58 对（12.9%）产物不同于原两分子**（发生了断键后重排/跨分子合并），说明固定键场景被真实覆盖；
  - **level6 0 不一致**（真实对的 level6 全部逐块比对；in-loop / post-loop 细分见 3.2b）。
- 重排示例（slow 产物）：
  - `CLK3F + OP3W → OCP3WLK3F`（合并）
  - `O2X2W3A + X3CAF → OX2WAF + OX3CW2A`（交换）
  - `C4P3F + XP3LA → C3P2F + XCP4LA`（交换）

#### 3.2b 合成 base_edges（200 例，0 不一致）

随机原子列表（n=4~14）+ 随机固定键（含多重键，45% 概率成边、受价数约束）：
- 产物结构多重集 **0 不一致**；
- **55 例**在循环内捕获 level6（规则 10 实际参与），**18 例**结束时 level6 为 None（触发 post-loop
  fallback），两类的 level6 块与独立 slow 参考/最终 bond 矩阵重算结果 **0 不一致**。
  → Lead 修复的 post-loop level6 逻辑复核通过。

#### 3.2c `natural_engine.set_fast(False/True)` 端到端（0 不一致）

| 接口 | 对比次数 | 结果 |
|---|---:|---|
| `complete_products` | 350 | 0 不一致 |
| `incomplete_products` | 200 | 0 不一致 |
| `resolve`（含 T=0/1/2/Σc/Σc-1/Σc/Σc+3 等） | 280 | 0 不一致（type/产物 label/stages/class/csum/isum） |
| `is_stable` | 60 | 0 不一致 |

#### 3.2d 固定键边界（5 例，0 不一致）

过价（rem<0 → 双方 None）、重复边、零键级、无键、**反向索引 `(1,0,3)`** 等边界场景，
`fast_pot` 与 `greedy_bond` 行为一致。

### 3.3 速度（PASS）

**F 单次耗时（raw `simulate`，不含 `mol_label`；reps 次中位数，Python `perf_counter`）**

| n | 代表投料 | fast (ms) | pot_v4 (ms) | 加速比 |
|---:|---|---:|---:|---:|
| 12 | C4WLK3AF2 | **0.30** | 1.07 | **3.6×** |
| 16 | O2X4C2P2A2F4 | **0.63** | 2.75 | **4.4×** |
| 20 | X2PL4K3A10 | **1.17** | 4.81 | **4.1×** |
| 24 | C4P2W2L4KA2F9 | **1.24** | 6.16 | **5.0×** |
| 30 | OX3CP2W13LK7A2 | **3.82** | 21.56 | **5.6×** |
| 40 | OX5CP10L3K5A13F2 | **8.02** | 50.13 | **6.3×** |
| 60 | O3C29P2W4K18A4 | **21.84** | 125.90 | **5.8×** |

- **典型大小 ≤24 原子：fast 0.30~1.24 ms，慢版 1.07~6.16 ms，加速 3.6~5.0×**；
- n=60 时单次 F 约 **22 ms**（慢版 126 ms），T59 若需对上千组合调用 F 也可承受；
- 小 n 无退化（fast 反而更快）：

| n | 2 | 4 | 6 | 8 | 10 |
|---|---:|---:|---:|---:|---:|
| fast (ms) | 0.010 | 0.062 | 0.069 | 0.241 | 0.251 |
| slow (ms) | 0.027 | 0.127 | 0.239 | 0.636 | 0.755 |
| 加速比 | 2.9× | 2.1× | 3.5× | 2.6× | 3.0× |

- **自然引擎端到端**（含 `make_mol`/`mol_label` 与清缓存，`complete_products`）：
  n=20 **1.81 ms vs 6.65 ms（3.7×）**；n=24 **2.38 ms vs 9.33 ms（3.9×）**。
- 说明：不同随机投料耗时会有波动（含元素分布影响），但加速比量级稳定；所有基准样本都先验证了
  `fast` 与 `pot_v4` 结果一致。

### 3.4 缺陷排查（PASS）

| 检查 | 结果 |
|---|---|
| **环标记** `fast_pot._ring_flags` vs `pot_v4.ring_flags`（300 随机多重图 + 链/三角/四元环+尾定点） | 0 不一致 |
| **dt 类型**：`ptable_dist` / `family_rank` 全部元素对 | 全部为 `int`（无浮点精度风险；`dt` 取 |价差| 或 价数和） |
| **并查集增量统计**（crem/csize/ctypes/cmask） | 通过 27,315 向量 + 450 真实固定键 + 200 合成固定键 + 32 组结构化用例（价数和为偶数的有效项全部比对）间接逐条验证（0 不一致）；结构化含全同元素大组件、链、混合长投料（n≤30） |
| **base_edges 下 level6 / 规则 10** | 55 in-loop + 18 post-loop 例与 slow 参考逐块一致；真实 450 对 level6 0 不一致 |
| **并列取序** | 24k 穷举 + 3k 随机 + 高对称样本（O12/X12/O8P8/K6A6/O16X8）全部与 pot_v4 结构一致 |
| **大 n** | 随机 25~60 原子 80 例 0 不一致 |
| `set_fast` 缓存行为 | 切换不清缓存（结果仍正确，但可能不会走 fast 重算）→ 操作注意，见 §5 |
| 文档 API | docstring 所述 `simulate_with_base` / `simulate_level6` 未实现 → 文档/API 不一致，见 §5 |

---

## 4. 与 T59 使用相关的结论

1. **正确性**：`fast_pot.simulate` 与 `pot_v4.simulate`（规则 1~11，空 base）**逐条等价**；
   带固定键时与 `natural_engine.greedy_bond` **逐条等价**；`natural_engine.set_fast(True)` 后
   `complete_products` / `incomplete_products` / `resolve` / `is_stable` 与慢路径完全一致。
2. **level6**：空 base 时与 `pot_v4` 的 level6 完全一致（含 post-loop 逻辑）；
   固定键时与 slow 参考（greedy_bond 源码副本）完全一致。
3. **速度**：≤24 原子 0.3~1.2 ms / 次 F；30~60 原子加速 5.6~6.3×。相比 T58 的瓶颈，fast 路径
   适合 T59 的多物质、两阶段批量 F 调用。
4. **使用方式**：
   ```python
   import natural_engine as NE
   NE.set_fast(True)
   NE.clear_caches()          # 建议：确保 fast 路径生效、缓存口径一致
   # 之后照常调用 complete_products / incomplete_products / resolve
   ```

---

## 5. 疑点 / 注意事项（均非功能性 bug）

1. **`set_fast()` 不清缓存（操作注意，建议 T59 前置处理）**。
   `natural_engine` 的 `_F_CACHE` / `_INC_CACHE` 按结构缓存，`set_fast` 只改全局开关。
   若先跑过慢版再切 fast，旧缓存会命中（结果正确，但该向量不会再走 fast 计算，测速会失真）。
   **建议 T59 在 `set_fast(True)` 后调用 `clear_caches()`**；审计脚本即按此执行（890 次端到端对比全部一致）。
2. **文档 API 不一致（低风险）**。`fast_pot` 模块 docstring 列出
   `simulate_with_base` / `simulate_level6`，但模块只实现
   `simulate(atom_list, base_edges=(), return_level6=False)`。
   `natural_engine` 走的是 `simulate(..., base_edges=...)`，故不影响 T59；
   但若 T59 其他代码按 docstring 调用会 `AttributeError`。建议补两个兼容函数或删除 docstring 条目。
3. **缓存无上限（长实验注意）**。`_MOL_CACHE` / `_F_CACHE` / `_INC_CACHE` / `_STABLE_CACHE` 单调增长，
   无 LRU。T59 大实验若遍历大量计数向量/分子组合，可定期 `clear_caches()` 控制内存
   （不影响正确性）。
4. **产物原子顺序差异（不影响下游）**：`pot_v4`/`greedy_bond` 的产物 `atoms` 按 DFS 发现序，
   `fast_pot` 按排序序；两者 `mol_label` 规范形一致，`natural_engine.make_mol` 也做了规范化，
   因此对 T59 使用（按结构/分子式判断）无影响。
5. **level6 的权威口径**：空 base 与 `pot_v4` 一致；固定键情形 `pot_v4` 本身不支持，
   本报告以 `greedy_bond`（slow 原实现）为权威，并额外独立重算 post-loop 块。该口径与
   `natural_engine` 的既有行为一致。
6. 基准为单线程 CPython、同机测量；绝对耗时会随机器/投料元素分布变化，但加速比量级稳定
   （n≥30 时 5.6~6.3×）。

---

## 6. 结论

- `fast_pot.py` 的"增量并查集 + 分层字典序筛选"实现与 `pot_v4`（规则 1~11）**完全等价**：
  27,315 个向量（含 24,310 个穷举组合）的产物公式、结构、失败状态、level6 块 0 差异；
- 固定键/不完全反应路径与 `natural_engine.greedy_bond` **完全等价**（450 对真实 + 200 组合成，含
  58 例真实重排、55 例规则 10 生效、18 例 post-loop level6）；
- `natural_engine.set_fast(True)` 端到端 890 次对比 0 不一致，**可放心用于 T59**；
- 速度：≤24 原子 0.3~1.2 ms/F，30~60 原子快 5.6~6.3×（n=60：22 ms vs 126 ms）；
- 唯一需要 T59 侧执行的操作是 `set_fast(True)` 后 `clear_caches()`；另建议顺手修
  `fast_pot` docstring 的未实现函数条目。

---

## 7. 复现

```powershell
$env:PYTHONIOENCODING="utf-8"
C:\Users\123\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe t59_fast_engine_audit.py
```

- 脚本：`t59_fast_engine_audit.py`（只读被审文件；约 35 s）
- 明细：`t59_fast_engine_audit.json`（每个任务的计数、示例、速度表）
- 被审文件：`fast_pot.py`、`natural_engine.py`（本次未修改）
- 对照实现：`pot_v4.py`、`natural_engine.greedy_bond`、`pot_all.py`
