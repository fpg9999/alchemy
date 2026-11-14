# -*- coding: utf-8 -*-
"""render_core_families：把每个"最小无限类别"的代表分子序列渲染成图。

从 cores_growth.json 取 reps（N=不同档的最大分子），每个类别选 3~4 个代表性分子
（最小 / 中等 / 最大），重新模拟投料得到结构，输出 reps_core_families.json 供 render_cross 使用。
"""
import json
import sys

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def find_mol(mols, formula):
    for m in mols:
        if P.formula_of(m["atoms"]) == formula:
            return m
    return None


def main():
    cores = json.load(open(BASE + r"\cores_growth.json", encoding="utf-8"))
    reps = []
    for key, data in cores.items():
        rs = data["reps"]
        if not rs:
            continue
        # 选择：最小非平凡 + 中间 + 最大
        picks = []
        nz = [r for r in rs if r["natoms"] >= 4]
        if nz:
            picks.append(nz[0])
        if len(rs) > 2:
            picks.append(rs[len(rs) // 2])
        picks.append(rs[-1])
        seen = set()
        for r in picks:
            if r["formula"] in seen:
                continue
            seen.add(r["formula"])
            atoms = P.vec_to_atoms(tuple(r["feed"]), P.ORDER)
            mols = P.simulate(atoms)
            if not mols:
                continue
            m = find_mol(mols, r["formula"])
            if m is None:
                continue
            place = P.embed_mol(m["atoms"], m["edges"], max_nodes=400000)
            if place is None:
                continue
            cats = sorted({P.CAT[e] for e in m["atoms"]}, key=lambda c: "聚动散".index(c))
            reps.append({
                "label": f"{key} · N={r['N']}",
                "formula": r["formula"],
                "zh": P.zh_of(m["atoms"]),
                "natoms": len(m["atoms"]),
                "cats": "-".join(cats),
                "feed": r["feed"],
                "atoms": list(m["atoms"]),
                "edges": [list(e) for e in m["edges"]],
                "place": {str(k): list(v) for k, v in place.items()},
            })
    json.dump(reps, open(BASE + r"\reps_core_families.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved reps_core_families.json:", len(reps), "个代表分子")


if __name__ == "__main__":
    main()
