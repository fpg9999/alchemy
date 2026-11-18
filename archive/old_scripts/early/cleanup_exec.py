# -*- coding: utf-8 -*-
"""cleanup_exec.py：执行整理（删除无用、文档/图/旧脚本分类归档），并生成 INDEX.md"""
import fnmatch
import os
import shutil
import time

BASE = r"G:\AI work\deepseek\work1\alchemy"
DOCS = os.path.join(BASE, "docs")
IMAGES = os.path.join(BASE, "images")
ARCH_S = os.path.join(BASE, "archive", "old_scripts")
ARCH_D = os.path.join(BASE, "archive", "old_data")
for d in (DOCS, IMAGES, ARCH_S, ARCH_D):
    os.makedirs(d, exist_ok=True)

DELETE_PATTERNS = ["_patch*.py", "*_scratch.py", "*.log", "*console*.txt", "_peek*.py",
                   "_pats.py", "_append*.py", "_dump.py", "_analyze.py", "_final_docs*.py",
                   "_mk_triples.py", "_summary.py", "cleanup_plan.py", "_patch*.py"]
DELETE_FILES = {
    "substances_league_s6.json", "substances_all.json",
    "t4_catalog_le16.json", "t4_catalog_le16_rule9.json", "t4_catalog_all.json",
    "catalog2_subsets.json", "catalog_raw_compact.json", "substances_index.json",
    "t12b_vec_data2.json", "substances_dong.json", "substances_san.json",
    "substances_league_s3.json", "substances_league_s4.json", "substances_league_s5.json",
    "reps_cross_345.json", "reps_scope6.json", "reps_core_families2.json",
}
DELETE_DIRS = {"t12b_shards", "t12b_v3parts", "t12b_vecparts", "__pycache__"}

KEEP = {
    # core simulators
    "pot_all.py", "pot_v2.py", "pot_v3.py",
    # T4
    "t4_scan_le16.py", "t4_batch_triples.py", "t4_enum.py", "t4_caps_all.py", "t4_cap_probe.py",
    "t4_assemble.py", "t4_build_catalog.py", "t4_analyze_le16.py", "t4_embed2.py",
    "t4_lattice_csp.py", "t4_mark_old.py", "t4_validate_catalog.py", "t4_validate_embed.py",
    "t4_validate_search.py",
    # T5-T7
    "t5_level6.py", "t5_level6_struct.py", "t5_levelbounds.py", "t5_pure.py", "t5_mark.py",
    "t6_active.py", "t6_active_exhaustive.py", "t6_excess.py", "t6_excess_exhaustive.py",
    "t6_highrem.py", "t6_maxh.py", "t6_priority_only.py", "t6_randtie.py", "t6_searchD.py",
    "t6_fix_notes.py", "t6_fix_notes2.py",
    "t7_tie_examples.py", "t7_tie_trace.py", "t7_pointers.py", "t7_update_handover.py",
    # T8-T10
    "t8_level6_forms.py", "t8_analyze.py", "t8_canon.py", "t8_check_big.py",
    "t8_complete_check.py", "t8_render_forms.py", "t8_render_rem1.py",
    "t8_rule9_scan.py", "t8_rule9_sample.py", "t8_rule9_sample2.py",
    "t9_single_trivalent.py", "t9_report.py", "t9_none_report.py", "t9_none_probe.py",
    "t9_none_probe2.py", "t9_rule9b.py", "t9_rule9b_randscan.py", "t9_trace.py", "t9_variants.py",
    "t10_skeleton.py", "t10_module_check.py", "t10_render.py", "t10_rule9c.py", "t10_trace.py",
    # T11
    "t11_reactions.py", "t11_analyze.py", "t11_chains.py", "t11_binary_more.py",
    "t11_cycles.py", "t11_cycles2.py", "t11_cycles3.py", "t11_cycles4.py",
    "t11_cycles_report.py", "t11_report.py", "t11_trace.py", "t11_exact.py", "t11_rule9d.py",
    # T12/T13
    "t12_theory.py", "t12_verify_big.py", "t12_exact.py", "t12_struct.py", "t12_rule9e.py",
    "t12a_chains.py", "t12b_prep.py", "t12b_compute2.py", "t12b_compute_v3.py",
    "t12b_merge.py", "t12b_failreason.py", "t12b_embed.py", "t12b_analyze.py",
    "t12b_report.py", "t12b_figs.py", "t12b_shards.py", "t12b_timeout_fix.py",
    "t12b_timeout_fix_v3.py", "t12b_verify_catalog.py", "t12b_diag.py", "t12b_diag2.py",
    "t12c_run.py", "t12c_law.py", "t12c_pure.py", "t12c_retry.py", "t12c_analyze.py",
    "t12c_inspect.py",
    "t13_onepot_rule9.py", "t13_scan_le16_v3.py", "t13_validate_v3.py", "t13_docs_final.py",
    "t13_docs_final2.py", "t13_edit_handoff.py", "t13_patch_t13doc.py",
    "t13_update_project_handoff.py",
    # data: authoritative
    "t4_catalog_all_validated.json", "t4_catalog_index.json", "t4_classification.json",
    "t4_caps_all.json", "t4_cap_probe.json", "t4_triples_complete.json", "t4_le16_stats.json",
    "t4p_all511_scale.json", "t4_enum_O_X_K.json", "t4_enum_O_X_K_T1_64.json",
    "t5_level6.json", "t5_level6_struct.json", "t5_levelbounds.json", "t5_pure_聚.json",
    "t6_active.json", "t6_active_exhaustive.json", "t6_excess.json", "t6_excess_exhaustive.json",
    "t6_excess_exhaustive_3.json", "t6_highrem.json", "t6_maxh.json", "t6_searchD.json",
    "t7_tie_examples.json",
    "t8_forms.json", "t8_complete_check.json", "t8_rule9_scan.json", "t8_rule9_sample.json",
    "t9_single_trivalent.json", "t9_rule9b_randscan.json", "t9_variants.json",
    "t10_skeletons.json", "t10_rule9c_scan.json",
    "t11_binary_ju.json", "t11_binary_none.json", "t11_binary_cross.json", "t11_cycles.json",
    "t11_rule9d_exact.json", "t11_rule9d_scan.json", "t11_rule9d_t9_rand.json",
    "t12a_chains.json", "t12_rule9e_exact.json", "t12_rule9e_scan.json",
    "t12_rule9e_struct.json", "t12_rule9e_t9_rand.json",
    "t12b_S.json", "t12b_results.json", "t12b_pairs.jsonl", "t12b_vec_v3.json",
    "t12b_summary.json", "t12b_failreason.json", "t12b_catalog_gap.json",
    "t12b_prep_stats.json", "t12b_timeout_fix.json", "t12b_shards_meta.json",
    "t12c_summary.json", "t12c_sample_pairs.json", "t12c_vectors.json", "t12c_law.json",
    "t12c_pure.json", "t12c_retry.json", "t12c_big108.json", "t12c_big140.json",
    "t13_onepot_rule9.json", "t13_validate_v3.json",
    "substances.json",
}


def main():
    files = [f for f in os.listdir(BASE) if os.path.isfile(os.path.join(BASE, f))]
    ops = {"deleted": [], "docs": [], "images": [], "old_scripts": [], "old_data": [], "kept": []}
    for f in files:
        if f == "cancel":  # 防呆
            continue
        fp = os.path.join(BASE, f)
        if any(fnmatch.fnmatch(f, p) for p in DELETE_PATTERNS) or f in DELETE_FILES:
            try:
                os.remove(fp)
                ops["deleted"].append(f)
            except Exception as e:
                print("del fail", f, e)
            continue
        if f in KEEP or f == "cleanup_exec.py" or fnmatch.fnmatch(f, "t13_big_search*") or fnmatch.fnmatch(f, "T13_BIG_SEARCH*"):
            ops["kept"].append(f)
            continue
        try:
            if f.endswith(".md"):
                shutil.move(fp, os.path.join(DOCS, f)); ops["docs"].append(f)
            elif f.endswith(".png"):
                shutil.move(fp, os.path.join(IMAGES, f)); ops["images"].append(f)
            elif f.endswith((".py",)):
                shutil.move(fp, os.path.join(ARCH_S, f)); ops["old_scripts"].append(f)
            elif f.endswith((".json", ".jsonl", ".txt")):
                shutil.move(fp, os.path.join(ARCH_D, f)); ops["old_data"].append(f)
            else:
                ops["kept"].append(f)
        except Exception as e:
            ops.setdefault("failed", []).append(f + " :: " + str(e))
    for d in os.listdir(BASE):
        if d in DELETE_DIRS and os.path.isdir(os.path.join(BASE, d)):
            shutil.rmtree(os.path.join(BASE, d), ignore_errors=True)
            print("deleted dir", d)

    # INDEX
    idx = f"""# alchemy 工作区索引（自动整理于 {time.strftime('%Y-%m-%d %H:%M')}）

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
- 删除：{len(ops['deleted'])} 个（_patch/_scratch/日志/重复大文件等）
- 移入 docs：{len(ops['docs'])} 个；images：{len(ops['images'])} 个
- 移入 archive/old_scripts：{len(ops['old_scripts'])} 个；archive/old_data：{len(ops['old_data'])} 个
- 保留根目录：{len(ops['kept'])} 个
"""
    open(os.path.join(BASE, "INDEX.md"), "w", encoding="utf-8").write(idx)
    # cleanup log
    lines = ["# 整理记录\n"]
    for k, v in ops.items():
        lines.append(f"\n## {k} ({len(v)})\n")
        lines.append(", ".join(sorted(v)))
    open(os.path.join(DOCS, "CLEANUP_LOG.md"), "w", encoding="utf-8").write("\n".join(lines))
    print({k: len(v) for k, v in ops.items()})


if __name__ == "__main__":
    main()
