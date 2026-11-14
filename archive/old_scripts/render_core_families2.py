# -*- coding: utf-8 -*-
"""render_core_families2：把各最小无限核心的"参数族最大成员"渲染成代表图。"""
import json
import sys

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def main():
    mins = json.load(open(BASE + r"\catalog2_minimal.json", encoding="utf-8"))
    reps = []
    for m in mins:
        fams = m.get("families") or []
        if not fams:
            continue
        fam = max(fams, key=lambda f: len(f["members"]))
        mem = fam["members"][-1]
        vec = mem["vec"]
        atoms = []
        for e, c in zip(m["elems"], vec):
            pass
        # vec 顺序 = m["elems"] 顺序（families 里 elems 顺序沿用 minimal 顺序）
        elems = fam.get("elems") or m["elems"]
        atoms = []
        for e, c in zip(elems, vec):
            atoms += [e] * c
        mols = P.simulate(atoms)
        if not mols:
            continue
        target = None
        for mm in mols:
            if P.formula_of(mm["atoms"]) == mem["formula"]:
                target = mm
                break
        if target is None:
            continue
        place = P.embed_mol(target["atoms"], target["edges"], max_nodes=400000)
        if place is None:
            continue
        cats = sorted({P.CAT[e] for e in target["atoms"]}, key=lambda c: "聚动散".index(c))
        reps.append({
            "label": "/".join(m["elems"]) + " 族最大成员",
            "formula": mem["formula"], "zh": P.zh_of(target["atoms"]),
            "natoms": len(target["atoms"]), "cats": "-".join(cats),
            "feed": [0] * 9, "atoms": list(target["atoms"]),
            "edges": [list(e) for e in target["edges"]],
            "place": {str(k): list(v) for k, v in place.items()},
        })
    # 补 feed（组成即投料）
    for r in reps:
        f = r["formula"]
        cnt = P.parse_formula(f)
        r["feed"] = list(cnt)
    json.dump(reps, open(BASE + r"\reps_core_families2.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved reps_core_families2.json:", len(reps))


if __name__ == "__main__":
    main()
