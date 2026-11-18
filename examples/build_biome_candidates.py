# -*- coding: utf-8 -*-
"""生成五个候选群系的物质清单 + 命名工作表（并集视图）。

候选（已按用户决定剔除 T58）：
    T55    纯聚素单质碰撞（死世界 / 沙漠底材）
    T57    29 种聚素 + 面积模型（死世界 / 更"宽"的沙漠）
    T63S4  T63 第四阶段（K 滴定后的极端世界）
    T62B   九元素等量价数（标准世界）
    T59B   九元素三价最多（富尾部的世界）

产出：
    data/biomes/candidates/<TAG>.csv        每个群系的完整物质清单（含丰度）
    data/biomes/candidates/_union.csv       并集工作表（每个物质只出现一次，带"草稿名"空列）
    data/biomes/candidates/_union.json
    docs/BIOME_CANDIDATES.md                可读报告

运行（仓库根）：
    python examples/build_biome_candidates.py
"""

import csv
import json
import sys
from collections import OrderedDict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import alchemy.biome as B  # noqa: E402
import alchemy.phase as PH  # noqa: E402

# (标签, 结果文件, 一句话定位)
CANDIDATES = [
    ("T55", "t55_kinetic_result.json", "纯聚素单质碰撞，退火到单一物质"),
    ("T57", "t57_area_result.json", "29 种聚素 + 面积模型，同样收敛到 OXC"),
    ("T63S4", "t63_phase4_result.json", "逐级价数滴定的最后一阶段（K 骨架世界）"),
    ("T62B", "t62_phaseB_result.json", "九元素等量价数，收敛到等摩尔双组分"),
    ("T59B", "t59_phaseB_result.json", "九元素三价最多，尾部最丰富的可用世界"),
]

OUT_DIR = REPO / "data" / "biomes" / "candidates"
DOC = REPO / "docs" / "BIOME_CANDIDATES.md"

PER_BIOME_FIELDS = ["formula", "label", "natoms", "count", "abundance",
                    "atom_abundance", "reserve_units", "shape", "category",
                    "skeleton_blocks", "骨架", "状态", "能量", "相型",
                    "in_catalog", "stable"]


def build():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    per_biome = OrderedDict()
    specs = {}
    for tag, fname, desc in CANDIDATES:
        run = B.load_result(REPO / fname)
        rows = B.abundance_table(run)
        per_biome[tag] = rows
        specs[tag] = {"desc": desc, "file": fname, "spec": run["spec"],
                      "n_species": len(rows)}

    # ---- 并集工作表
    union = OrderedDict()
    for tag, rows in per_biome.items():
        for r in rows:
            key = r["formula"]
            if key not in union:
                ph = PH.phase_of(key)
                ph_strict = PH.phase_of(key, absent_mode="none")
                de = PH.describe(key)
                reasons = []
                for ax_key, ax_label, _ in PH.AXES:
                    a = ph["axes"][ax_key]
                    if a["element"] == PH.FOURTH:
                        reasons.append("全零" if a["count"] == 0 else "等量")
                union[key] = {
                    "formula": key,
                    "label": r["label"],
                    "natoms": r["natoms"],
                    "shape": r["shape"],
                    "category": r["category"],
                    "skeleton_blocks": "+".join(r["skeleton_blocks"]) or "—",
                    "in_catalog": r["in_catalog"],
                    "stable": r["stable"],
                    "props": r["props"],
                    "abundance": {},
                    "count": {},
                    "骨架": ph["names"][0],
                    "状态": ph["names"][1],
                    "能量": ph["names"][2],
                    "物性名": de["name"],
                    "典型对应": de["typical"],
                    "相型": ph["id"],
                    "相型_无层单列": ph_strict["id"],
                    "第四相来源": "+".join(reasons),
                    "裁决轴数": ph["n_tied_axes"],
                    "草稿名": "",
                }
            union[key]["abundance"][tag] = r["abundance"]
            union[key]["count"][tag] = r["count"]

    tags = [t for t, _, _ in CANDIDATES]
    for u in union.values():
        u["n_biomes"] = sum(1 for t in tags if t in u["abundance"])
        u["max_abundance"] = max(u["abundance"].values())
        u["dominant_in"] = [t for t in tags if u["abundance"].get(t, 0) >= 0.10]

    union_rows = sorted(union.values(), key=lambda u: (-u["n_biomes"], -u["max_abundance"]))

    # ---- 每群系 CSV
    for tag, rows in per_biome.items():
        p = OUT_DIR / f"{tag}.csv"
        with open(p, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=PER_BIOME_FIELDS, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                out = dict(r)
                out["skeleton_blocks"] = "+".join(r["skeleton_blocks"]) or "—"
                ph = PH.phase_of(r["formula"])
                out["骨架"], out["状态"], out["能量"] = ph["names"]
                out["相型"] = ph["id"]
                w.writerow(out)

    # ---- 并集 CSV（命名工作表）
    ufields = (["formula", "label", "natoms", "shape", "category", "skeleton_blocks",
                "骨架", "状态", "能量", "物性名", "典型对应",
                "相型", "相型_无层单列", "第四相来源", "裁决轴数",
                "n_biomes", "max_abundance"]
               + [f"丰度_{t}" for t in tags]
               + [f"个数_{t}" for t in tags]
               + ["hp", "attack", "resist", "mobility", "slots", "in_catalog", "草稿名"])
    up = OUT_DIR / "_union.csv"
    with open(up, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=ufields, extrasaction="ignore", restval="")
        w.writeheader()
        for u in union_rows:
            props = u["props"] or {}
            row = {
                "formula": u["formula"], "label": u["label"], "natoms": u["natoms"],
                "shape": u["shape"], "category": u["category"],
                "skeleton_blocks": u["skeleton_blocks"],
                "骨架": u["骨架"], "状态": u["状态"], "能量": u["能量"],
                "物性名": u["物性名"], "典型对应": u["典型对应"],
                "相型": u["相型"], "相型_无层单列": u["相型_无层单列"],
                "第四相来源": u["第四相来源"], "裁决轴数": u["裁决轴数"],
                "n_biomes": u["n_biomes"],
                "max_abundance": f"{u['max_abundance']:.6f}",
                "hp": props.get("hp"), "attack": props.get("attack"),
                "resist": props.get("resist"), "mobility": props.get("mobility"),
                "slots": props.get("slots"),
                "in_catalog": u["in_catalog"], "草稿名": "",
            }
            for t in tags:
                row[f"丰度_{t}"] = (f"{u['abundance'][t]:.6f}" if t in u["abundance"] else "")
                row[f"个数_{t}"] = u["count"].get(t, "")
            w.writerow(row)

    payload = {"candidates": {t: {"desc": specs[t]["desc"], "file": specs[t]["file"],
                                  "n_species": specs[t]["n_species"],
                                  "spec": specs[t]["spec"]} for t in tags},
               "n_union": len(union_rows),
               "species": [{k: v for k, v in u.items() if k != "props"} | {"props": u["props"]}
                           for u in union_rows]}
    with open(OUT_DIR / "_union.json", "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)

    return tags, per_biome, union_rows, specs


def render_doc(tags, per_biome, union_rows, specs):
    L = []
    L.append("# 五个候选群系的物质清单（BIOME CANDIDATES）\n")
    L.append("> 由 `examples/build_biome_candidates.py` 从真实实验结果生成，可重跑。")
    L.append("> T58 已按项目决定剔除（等效物种数 20.6、单例率 74.9%，判为退火未完成的噪声）。\n")

    L.append("## 0. 五个候选一览\n")
    L.append("| 标签 | 定位 | 元素配比 | 物种数 | 分子数 | 等效物种 | top1 质量 | top2 | 最大原子 |")
    L.append("|---|---|---|--:|--:|--:|--:|--:|--:|")
    for tag, _, desc in CANDIDATES:
        s = specs[tag]
        summ = B.biome_summary(B.load_result(REPO / s["file"]))
        shares = s["spec"].get("element_shares") or {}
        nz = [f"{k}{v:.0%}" for k, v in shares.items() if v >= 0.02]
        L.append(f"| **{tag}** | {desc} | {' '.join(nz)} | {s['n_species']} | "
                 f"{s['spec']['n_molecules']:,} | {summ['effective_species']} | "
                 f"{summ['dominance']:.1%} | {summ['top2_mass_share']:.1%} | "
                 f"{summ['max_natoms']} |")

    L.append(f"\n并集共 **{len(union_rows)} 种物质**（去重后）。"
             f"其中出现在 ≥2 个群系的有 "
             f"**{sum(1 for u in union_rows if u['n_biomes'] >= 2)} 种**。\n")

    L.append("## 1. 每个群系的物质清单（按丰度降序）\n")
    for tag, _, desc in CANDIDATES:
        rows = per_biome[tag]
        L.append(f"### {tag} —— {desc}\n")
        L.append(f"物种 **{len(rows)}**，分子 **{sum(r['count'] for r in rows):,}**，"
                 f"原子 **{sum(r['reserve_units'] for r in rows):,}**\n")
        L.append("| # | 分子式 | 标识 | 原子 | 个体数 | 丰度 | 质量份额 | 形状 | 骨架块 | 耐久/攻击 | 目录内 |")
        L.append("|--:|---|---|--:|--:|--:|--:|---|---|---|:--:|")
        for i, r in enumerate(rows, 1):
            p = r["props"] or {}
            L.append(f"| {i} | `{r['formula']}` | {r['label']} | {r['natoms']} | "
                     f"{r['count']:,} | {r['abundance']:.4%} | {r['atom_abundance']:.4%} | "
                     f"{r['shape']} | {('+'.join(r['skeleton_blocks']) or '—')} | "
                     f"{p.get('hp', '—')}/{p.get('attack', '—')} | "
                     f"{'✓' if r['in_catalog'] else '✗'} |")
        L.append("")

    L.append("## 2. 命名工作表：跨群系核心物质\n")
    L.append("出现在 ≥2 个群系的物质（建议优先定义，因为会同时影响多个群系）：\n")
    multi = [u for u in union_rows if u["n_biomes"] >= 2]
    L.append("| 分子式 | 标识 | 原子 | 出现群系数 | 最高丰度 | 主导于 | 骨架块 | 形状 |")
    L.append("|---|---|--:|--:|--:|---|---|---|")
    for u in multi:
        L.append(f"| `{u['formula']}` | {u['label']} | {u['natoms']} | {u['n_biomes']} | "
                 f"{u['max_abundance']:.3%} | {'/'.join(u['dominant_in']) or '—'} | "
                 f"{u['skeleton_blocks']} | {u['shape']} |")

    L.append("\n## 3. 文件\n")
    L.append("| 文件 | 内容 |")
    L.append("|---|---|")
    for tag, _, _ in CANDIDATES:
        L.append(f"| `data/biomes/candidates/{tag}.csv` | {tag} 完整清单 |")
    L.append("| `data/biomes/candidates/_union.csv` | **命名工作表**（并集，带空列 `草稿名`） |")
    L.append("| `data/biomes/candidates/_union.json` | 同上，JSON（含完整 props） |")

    DOC.write_text("\n".join(L) + "\n", encoding="utf-8")
    return DOC


def main():
    tags, per_biome, union_rows, specs = build()
    doc = render_doc(tags, per_biome, union_rows, specs)

    print("五个候选群系：")
    for tag, fname, desc in CANDIDATES:
        rows = per_biome[tag]
        print(f"  {tag:6} 物种 {len(rows):3}  分子 {sum(r['count'] for r in rows):7,}  "
              f"并集贡献 {len(rows)}")
    print(f"\n并集物质数: {len(union_rows)}")
    print(f"跨群系物质(≥2): {sum(1 for u in union_rows if u['n_biomes'] >= 2)}")
    print(f"\n输出: {OUT_DIR}")
    print(f"报告: {doc}")


if __name__ == "__main__":
    main()
