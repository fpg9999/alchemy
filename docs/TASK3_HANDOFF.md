# 交接入口（最新）

> **新会话请先读 `PROJECT_HANDOFF.md`**（项目总交接：规则摘要、代码/数据/文档清单、
> 当前权威结论、重大修正记录、有限性证明状态与待办、复现命令）。
> 本文件保留为历史过程记录。

# TASK3_HANDOFF —— "511 个元素组合类别"最终任务交接

> 目标：9 元素全部 511 个非空子集类别：① 有限/无限；② 有限类完整物质清单；
> ③ 无限类的无限增长规律；④ 表格/图/JSON（CATALOG.md）。
> 上下文若不够，本文件 + 已落盘 JSON 足够续做。

## 环境
- Python：`C:\Users\123\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`
- 目录：`G:\AI work\deepseek\work1\alchemy`
- 模拟器 `pot_all.py`（规则 1~8 + typed embedding，`embed_mol(..., max_nodes=)`）；`scan_league.py` 多进程扫描。

## 口径（重要）
- 物质按分子式；“类别 S” = 允许元素池 S，物质 = 组成元素 ⊆ S 的可产出物质。
- 已验证：任何物质可用自身组成元素直接投料复现（800/800 抽样）。
- **早期“有限封顶 16 原子”的假设是错的**：T=32~44 大投料实测发现大量类别能产出 21~32 原子分子。
  最终分类改为大投料实测口径（整锅成功 = 所有产物可摆）。

## 已完成的关键数据
- `catalog_raw_compact.json`：全 9 元素 ≤16 原子全扫描的轻量目录，**82239 条物质**。
- 无限 3 元组实测结论：
  - 强证据（T≤32，最大分子 24~32）：O/X/P, O/X/K, O/P/W, O/P/K, O/P/A, O/W/K, O/K/A,
    X/P/K, P/W/K, P/K/A
  - 中证据→T=40/44 继续增长（最大 29~30，判无限）：O/X/A, X/P/W, X/K/A, P/W/A, W/K/A, O/X/W
  - 平台型（T=36/40/44 都卡在 21~22，疑似有限但未证明）：O/W/A, X/P/A, X/W/K
  - 其余 3 元组大投料 ≤16（疑似有限）
- 脚本：`classify_rest.py` 正在测 4~9 元子集（只测不含上述无限 3 元组的），结果写
  `all_classified_final.json` / `all_classified_stats.json`；中间结果 `classify_rest_raw.json`。
- 旧的 `minimal_infinite.json`/`families_full.json`/`cores_growth.json` 基于旧（不完整）分类，
  需按最终 minimal 重跑：`find_families2.py <minimal 文件>`（它读 {"minimal": [...]}）。

## 剩余步骤（按顺序）
1. 等 `classify_rest.py` → `all_classified_final.json`（511 类别：infinite / cores / max）。
2. 由 stats 的 minimal 列表写 `minimal_empirical.json`（格式 {"minimal": ["A/B/C", ...]}），
   跑 `find_families2.py minimal_empirical.json` → `families_full.json`（按最小类别找参数族）。
   注意 5 元最小集合的 Nmax 可能过大，可改小。
3. 跑 `build_catalog2.py`（它读 all511_classified.json——**需改读 all_classified_final.json**，
   且 minimal 从 all_classified_stats.json 取；families 用 families_full.json）→ catalog2_*.json。
4. 跑 `render_catalog2.py`（总览图 + 增长曲线）、`render_core_families2.py` + 
   `render_cross.py reps_core_families2.json core_families2.png 标题` 出图。
5. 跑 `write_catalog2.py` → `CATALOG.md`（511 行表 + 精确组成清单 + 无限规律）。
6. 更新 `RESULTS.md` 顶部加“任务3：511 类别目录”小节；最终汇报给用户。

## 注意
- 有限类最终判定 = 大投料实测未超过封顶（非形式化证明），CATALOG 里要注明。
- 无限类的“规律”：参数族方向（families）例如 X_m K_2、O_m K_{m+2}、O_m X_m K_{m+2}，
  以及 3 价网络型；4/5 元最小集合的族里可能出现 X13/W13/A13 长链。
- 若 classify_rest 报错：它按层处理、结果增量写 `classify_rest_raw.json`，可修正后从断点续。


## 最终结果（已完成）
- 511 类别：**无限 304，有限 207**；16 个最小无限三元素类别：
  O/X/P O/X/W O/X/K O/X/A O/P/W O/P/K O/P/A O/W/K O/K/A X/P/W X/P/K X/K/A P/W/K P/W/A P/K/A W/K/A
- 数据：`catalog_raw_compact.json`（82239 条 ≤16 原子物质）；分类 `all_classified_final.json`；
  目录 `catalog2_*.json`；说明 `CATALOG.md`（3.4MB，511 类总表 + 精确组成物质清单）；
  图 `catalog2_overview.png` / `catalog2_growth_curves.png` / `core_families2.png`；
  参数族 `families_full.json`。
- 后续若继续：可对 3 个平台型三元素（O/W/A、X/P/A、X/W/K）与"有限类"在更大 T 下复核；
  可把参数族推广到一般证明（目前是实测族）。


## 第二轮收尾（已完成）
- 有限类别扩展枚举：20 个有限类别含 >16 原子物质（封顶最高 23），完整清单在
  `CATALOG_FINITE_LISTS.md`（含真实投料例）；其余有限类别 ≤16 原子完整。
- `CATALOG.md` 已更新（★ 标记 + 真实投料例指引）；`catalog_feed_map.json` 存每个物质的真实投料例。
- 验证：`verify_selfprod_all.py` 82335 个物质，94 个“自组成重放摆不出”的已用真实投料例替代。
- 6 元有限类（X/C/P/L/A/F、X/C/W/L/K/F）封顶已探到 23 原子；若后续想更严可再扫总原子 24 档
  （`extend6.py` 可改 T0/T1 复用）。


## 第三轮最终确认
- 20 个扩展有限类别全部补到封顶：最大 23 原子（3/4/5/6 元类别一致）。
- `CATALOG_FINITE_LISTS.md` = 207 个有限类别的完整清单（含真实投料例），★ 标记 >16 原子的 20 类。
- 全量投料例：`catalog_feed_map.json`；自身组成复现验证 82335 个中 94 个例外（已用真实投料例）。
- 任务 3 目标（511 类别分类 + 有限清单 + 无限规律 + 表格/图/JSON）已完成。


## 接手会话复核（2026-11-12 05:20）—— 对上面"最终结果"的更正
- ⚠ 上面的「无限 304 / 有限 207」「16 个最小无限三元素」「参数族」**不可靠**，详见 `TASK3_VERIFY.md`。
- 精确全枚举：9 个"2 个不同大类 3 价 + 1 个 2 价"三元组在 T=64、T=96 都封顶 **42**；其余三元组 18~31；
  4 元 a=1 类（X/C/K/A）封顶 33；7 元 a=1 类 ~46。旧"参数族"（X_mK_2 / O_mK_{m+2} / O_mX_mK_{m+2}）经直接投料检验是假的。
- 已校验可摆放的最大分子：全 9 元素池 **97 原子**（一锅一分子）。110~160 原子候选图在 embedding 预算内未通过校验。
- 结论：现有证据不支持任何类别无限；更可能「全部 511 类有限，封顶随元素池增大（~9 到 ~100+）」。
- 因此 `CATALOG.md` 只保留物质清单（≤16 原子 82239 条）与 ≤23 原子的有限类清单（同样不是真封顶）；
  分类与"无限规律"章节作废，以 `TASK3_VERIFY.md` 为准。


---

## 最终修正（T4，2026-11-12）——「真正的」511 类别分类表与有限性论证

1. **模拟器 bug**：`pot_all.embed_mol` 的 L 中间格 set 回溯 bug + `scan_league` 的规范形缓存碰撞 bug，
   导致旧目录约 5.3% 摆放非法、10 个伪物质；旧「无限族」全部是假象。
   修复版 `pot_v2.py`（embed_mol2 + validate_place）。
2. **重做数据**：
   - 全 9 元素 ≤16 原子完备目录：**82961 条**（全部严格可摆 + 全部自组成一锅复现）；
   - 84 个三元组 T≤48 **完备枚举**：4837 条（999 条 >16 原子，最大分子 42）；
   - 4~9 元类别搜索最大合法分子：4 元 57、5 元 69、6 元 82、8 元 87、全 9 元 97。
   - 合并全部已知物质：**84225 条**。
3. **511 类分类**：**全部有限**（无限 0）。完整表：`T4_CLASSIFICATION.md` / `t4_classification.json`。
4. **有限性**：条件性证明（严格归约到「单分子原子数上界」猜想）+ 6 条严格结构引理
   + 全 511 类数值证据；唯一缺口一条组合引理。详见 `T4_FINAL_REPORT.md` §4、`T4_PROOF_ATTEMPT.md`。
5. **口径**：规则 1~8 仍有并列（约 0.5% 随机投料产物不同）；物质清单是「确定并列裁决」口径。
6. 结论以 `T4_FINAL_REPORT.md` 为准；本文件此前各节的分类/无限规律均作废。
