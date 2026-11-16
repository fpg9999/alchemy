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
  - 真·库外 6 级块仅 `O3P5K2` 一族（三价 ≤10 穷举）；671 个终态形态 = 库内块融合（670/670 宿主结构定理通过，不算库外）。
- **T55（2026-11-16）2D 粒子环境实验**：`natural_engine.py`（T35 判定 + pot_v4 规则 1~11 完全反应 +
  t28 不完全反应 + 自分解）；`t55_kinetic_env.py`（10000×10000 反射边界、9000 个聚素单质、
  初速 38197/分钟、每次碰撞 -0.2%、1000→0°C）、`t55_control_no_chem.json`（500 次穿越验证：
  9000/9000 达标，min 696.7）、`t55_sensitivity.py`（T0=6/8/12/20°C 敏感性）、`t55_analysis.py`/`t55_render.py`、
  `docs/T55_KINETIC_ENV.md`、`docs/T55_ENGINE_AUDIT.md`、`images/t55_*.png`（8 张）；
  结论：主实验快速退火到 99.5% `OXC`；温度标度敏感性下出现不完全反应/自分解/新物质。
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
