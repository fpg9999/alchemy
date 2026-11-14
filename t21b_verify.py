# -*- coding: utf-8 -*-
"""t21b_verify.py（修正）：严格验证端帽交换产物"""
import json
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_v2
from t21_natural_caps import analyse, try_attach

BASE = r"G:\AI work\deepseek\work1\alchemy"
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
byname = {r["formula"]: r for r in cat}
res = json.load(open(BASE + r"\t21_natural_caps.json", encoding="utf-8"))
out = []
for e in res["new"][:8]:
    ia = analyse(byname[e["A"]])
    ib = analyse(byname[e["B"]])
    capsA = [ia["atoms"][i] for i in ia["caps"]]
    capsB = [ib["atoms"][i] for i in ib["caps"]]
    for who, info, newcaps, prod in (("A'", ia, capsB, e["prodA"]), ("B'", ib, capsA, e["prodB"])):
        att = try_attach(info, newcaps)
        if att is None:
            out.append({"product": prod, "attach": False})
            continue
        # 只保留骨架原子
        skel = list(info["skel"])
        remap = {old: k for k, old in enumerate(skel)}
        atoms = [info["atoms"][i] for i in skel]
        place = {remap[i]: info["place"][i] for i in skel}
        edges = [[remap[i], remap[j], m] for (i, j, m) in info["bonds"]]
        for t, (cell, si, tp) in att["caps_pos"].items():
            idx = len(atoms)
            atoms.append(newcaps[t])
            place[idx] = cell
            edges.append([remap[si], idx, 1])
        ok, msg = pot_v2.validate_place({i: place[i] for i in range(len(atoms))}, atoms, edges)
        out.append({"parent": e["A"] if who == "A'" else e["B"], "product": prod,
                    "validate": ok, "msg": msg, "in_catalog": prod in byname,
                    "natoms": len(atoms), "atoms": atoms, "edges": edges,
                    "place": {str(i): list(place[i]) for i in place}})
        print(who, "parent", e["A"] if who == "A'" else e["B"], "→", prod,
              "validate", ok, msg, "in_catalog", prod in byname, flush=True)
json.dump(out, open(BASE + r"\t21_verified.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved t21_verified.json")
