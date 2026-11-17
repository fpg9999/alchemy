# -*- coding: utf-8 -*-
"""t60_top20_extract.py —— 汇总 T55~T59 各次实验的 top20 物质、结构、重要物质并集

输出：
  t60_top20_data.json  每次实验 top20（结构/数量/原子数/元素/价数/目录归属/中文名）
  t60_summary.json     各实验规模/结果对比数据 + 重要物质并集
"""
import json
import sys

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import natural_engine as E
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
V3 = {"O", "P", "K"}
V2 = {"X", "W", "A"}
V1 = {"C", "L", "F"}

EXPERIMENTS = [
    ("T55", "T55：等比例聚素单质（O/X/C）", "t55_kinetic_result.json"),
    ("T56", "T56：价数比 3<2<1 + 散素 K/A/F", "t56_kinetic_result.json"),
    ("T57", "T57：全部 29 种聚素 + 面积∝元素数", "t57_area_result.json"),
    ("T58", "T58：九元素 + 物质库随机 44 种大投料", "t58_result.json"),
    ("T59A", "T59 第一阶段：120 种、三价最多/一价最少", "t59_phaseA_result.json"),
    ("T59B", "T59 第二阶段：整理底物 + batchB、T 重置", "t59_phaseB_result.json"),
    ("T59A_hf", "T59 第一阶段 cap=60 高保真", "t59_phaseA_hf_result.json"),
    ("T59B_hf", "T59 第二阶段 cap=60 高保真", "t59_phaseB_hf_result.json"),
]

INDEX = json.load(open(BASE + r"\t4_catalog_index.json", encoding="utf-8"))
CAT = {r["formula"] for r in INDEX}
SUBS = json.load(open(BASE + r"\substances.json", encoding="utf-8"))
SET29 = {r["formula"] for r in SUBS}


def zh_of(f):
    vec = P.parse_formula(f)
    return "".join(P.CN[P.ORDER[i]] + (str(c) if c > 1 else "")
                   for i, c in enumerate(vec) if c)


def val_atoms(vec):
    a3 = sum(vec[P.ORDER.index(e)] for e in V3)
    a2 = sum(vec[P.ORDER.index(e)] for e in V2)
    a1 = sum(vec[P.ORDER.index(e)] for e in V1)
    return a3, a2, a1


def structure_for(f, comp_rec, tops, label_to_struct):
    """优先 final_top_structures，缺的用 fast F 重建（取同 formula 的单产物）。"""
    if f in tops:
        t = tops[f]
        return {"atoms": t["atoms"], "edges": t["edges"], "label": t.get("label"),
                "rebuilt": False}
    mols = E.complete_products(tuple(P.parse_formula(f)))
    if mols:
        for m in mols:
            if m["formula"] == f:
                return {"atoms": list(m["atoms"]),
                        "edges": [list(e) for e in m["edges"]],
                        "label": m["label"], "rebuilt": True}
    # 最后兜底：从现有同 formula 结构
    for m in label_to_struct.get(f, []):
        return m
    return None


def main():
    E.set_fast(True)
    out = {"experiments": [], "important": []}
    seen = {}
    for name, desc, fn in EXPERIMENTS:
        d = json.load(open(BASE + "\\" + fn, encoding="utf-8"))
        comp = d["final_composition"]
        s = d["summary"]
        tops = d.get("final_top_structures", {}) or {}
        label_to_struct = {}
        for f2, t in tops.items():
            label_to_struct.setdefault(f2, []).append(
                {"atoms": t["atoms"], "edges": t["edges"],
                 "label": t.get("label"), "rebuilt": False})
        rows = []
        ranked = sorted(comp.items(), key=lambda kv: (-kv[1]["count"], kv[0]))
        for rank, (f, v) in enumerate(ranked[:20], 1):
            vec = P.parse_formula(f)
            a3, a2, a1 = val_atoms(vec)
            st = structure_for(f, v, tops, label_to_struct)
            row = {
                "rank": rank, "formula": f, "zh": zh_of(f),
                "count": v["count"], "atoms": v["atoms"],
                "element_counts": {P.ORDER[i]: c for i, c in enumerate(vec) if c},
                "valence_atoms": {"v3": a3, "v2": a2, "v1": a1},
                "in_catalog": f in CAT, "in_29": f in SET29,
                "structure": st,
            }
            rows.append(row)
            key = (f, st.get("label") if st else None)
            occ = seen.setdefault(key, {"formula": f, "zh": row["zh"],
                                        "atoms": row["atoms"],
                                        "structure": st,
                                        "occurrences": []})
            occ["occurrences"].append({"experiment": name,
                                       "rank": rank, "count": v["count"]})
        # 实验规模/结果指标
        sizes = {}
        for f, v in comp.items():
            n = sum(P.parse_formula(f))
            sizes[n] = sizes.get(n, 0) + v["count"]
        n_mol = s["final_N"]
        out["experiments"].append({
            "name": name, "desc": desc, "file": fn,
            "initial_particles": d["config"].get("initial_particles"),
            "initial_atoms": d["config"].get("initial_atoms"),
            "final_N": n_mol,
            "final_atoms": s["final_atoms"],
            "distinct_formulas": len(comp),
            "mean_atoms": round(sum(n * c for n, c in sizes.items()) / n_mol, 3),
            "max_atoms": max(sizes),
            "size_distribution": {str(n): c for n, c in sorted(sizes.items())},
            "reaction_counts": s.get("reaction_counts", {}),
            "events_total": s.get("events_total"),
            "decomp_events": s.get("decomp_events"),
            "environment_L": d["config"].get("L"),
            "max_reaction_atoms": d["config"].get("max_reaction_atoms"),
            "runtime_s": s.get("runtime_s"),
            "top20": rows,
        })
    # 重要物质并集：按出现次数、跨实验最大排名/数量排序
    important = []
    for key, occ in seen.items():
        exp_names = [o["experiment"] for o in occ["occurrences"]]
        important.append({
            "formula": occ["formula"], "zh": occ["zh"], "atoms": occ["atoms"],
            "structure": occ["structure"],
            "occurrences": occ["occurrences"],
            "n_experiments": len(set(exp_names)),
            "best_rank": min(o["rank"] for o in occ["occurrences"]),
            "max_count": max(o["count"] for o in occ["occurrences"]),
            "total_count": sum(o["count"] for o in occ["occurrences"]),
        })
    important.sort(key=lambda r: (-r["n_experiments"], r["best_rank"], -r["max_count"]))
    out["important"] = important
    out["meta"] = {"n_experiments": len(EXPERIMENTS),
                   "n_important": len(important),
                   "experiments": [e[0] for e in EXPERIMENTS]}
    json.dump(out, open(BASE + r"\t60_top20_data.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    # 简短 summary
    print(json.dumps({
        "n_important": len(important),
        "experiments": [
            {"name": e["name"], "final_N": e["final_N"], "distinct": e["distinct_formulas"],
             "max_atoms": e["max_atoms"], "mean_atoms": e["mean_atoms"]}
            for e in out["experiments"]
        ],
        "top_important": [(r["formula"], r["n_experiments"], r["best_rank"])
                          for r in important[:20]],
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
