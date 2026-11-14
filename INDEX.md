# ALCHEMY 文件索引（2026-11-14 更新）

> **新对话/新接手：先读 HANDOFF.md、README.md、TRANSFER.md、NEW_CHAT_PROMPT.md。**
> 本文件是历史/主题索引；最新结论与交接以 HANDOFF.md 为准。

---

# alchemy 工作区索引（自动整理于 2026-11-13 10:58）

## 目录结构
- `docs/`：全部研究报告（T4~T13、HANDOFF、PROJECT_HANDOFF 等）
- `images/`：全部图片（结构图、反应矩阵、循环图、统计图等）
- `archive/old_scripts/`：历史探索脚本（可复现性保留）
- `archive/old_data/`：历史数据（旧扫描/旧分类结果）
- 根目录：核心模拟器 + 权威数据 + 本索引

## 核心代码（根目录）
- `pot_all.py`：规则 1~8 通用模拟器
- `pot_v2.py`：严格摆放校验（embed_mol2 / validate_place）
- `pot_v3.py`：正式口径（规则 1~9）
- `t4_*`~`t13_*`：各阶段扫描/分析脚本（文件名前缀=任务编号）

## 权威数据（根目录）
- `t4_catalog_all_validated.json`：84,225 条物质目录；`t4_catalog_index.json` 索引
- `substances.json`（29 聚素）、`t9_single_trivalent.json`（单三价）、`t8_forms.json`（38 三价骨架）
- `t10_skeletons.json`（7 骨架模块）、`t11_*.json`（二元反应/循环）、
  `t12a_chains.json`（反应链）、`t12b_*.json` + `t12b_pairs.jsonl`（7.73M 对）、
  `t12c_*.json`（全目录采样、140/108 原子纪录）、`t12b_catalog_gap.json`（212 补充产物）

## 主要报告（docs/）
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

## 最新补充
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
  - 真·库外 6 级块仅 `O3P5K2` 一族（三价 ≤10 穷举）；终态库外形态 671 个（全目录重扫）。
