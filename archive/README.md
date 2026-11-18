# archive —— 历史脚本与旧数据（已归档，不参与当前实验）

> 本目录存放被后续阶段取代的早期脚本/数据。**当前（T70b）的脚本与数据都在仓库根目录**，
> 不要从这里引用；这里的内容只用于追溯早期思路与复核历史结论。
> 2026-11-18 按"阶段/主题"重新分文件夹；文件本身未改动，历史文档（如 `docs/CLEANUP_LOG.md`）
> 中记录的是归档前的平铺路径。

## old_scripts/（136 个 .py）

| 子文件夹 | 数量 | 内容 |
|---|---:|---|
| `t3/` | 15 | T03 阶段脚本（`t3_analyze_existing.py`、`t3_anneal*.py`、`t3_probe*.py`、`t3_validate.py`…） |
| `t4p/` | 11 | T4' 阶段脚本（`t4p_analyze.py`、`t4p_scale*.py`、`t4p_lemma_check.py`、`t4p_mu.py`…） |
| `late/` | 3 | 较晚被归档的遗留脚本（`t9_rule9b_rand.py`、`t12b_compute.py`、`t13_bench.py`） |
| `early/` | 107 | T3 之前的探索脚本（`pot*.py` 早期版本、`scan*/probe*/render*/classify*/verify*` 等），文件名即用途 |

## old_data/（50 个 .json/.txt）

| 子文件夹 | 数量 | 内容 |
|---|---:|---|
| `t3/` | 9 | T03 的退火/精确枚举/搜索数据 |
| `scope/` | 12 | `scope3~6` 的 growth / big_examples / subset_growth 数据 |
| `catalog/` | 6 | `catalog2_*`、`catalog_feed_map.json`、`families*.json` |
| `finite/` | 8 | `extended_finite*`、`finite_verify.json`、`recheck_finite.json` |
| `minimal/` | 5 | `minimal_*`、`cores_growth.json` |
| `misc/` | 10 | 分类汇总（`all_classified_*`、`classification_revised.json`、`enum_summary.json`…）及 `t12c_run_log.txt` |

## 约定

- 新的归档文件放进对应阶段子文件夹；没有明确阶段时放 `early/`（脚本）或 `misc/`（数据），并在本文件补一行说明。
- 归档内容不保证能直接运行（路径、数据格式可能已随阶段变化）。
