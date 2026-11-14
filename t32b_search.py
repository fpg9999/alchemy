# -*- coding: utf-8 -*-
"""t32b_search.py：搜索自然环境完整循环的简单实例
1) 两分子 A+B → ... → A+B（反应后不稳定物质衰变回原物质）——2步闭环
2) 三分子催化：Cat 不变，另两分子反应→不稳定→衰变成新稳定产物
"""
import json
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v3
from t28_rule_v2 import react_v2, formula

BASE = r"G:\AI work\deepseek\work1\alchemy"
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
catf = {r["formula"] for r in cat}
pool = [r for r in cat if 2 <= len(r["atoms"]) <= 4 and r.get("place")]

_fc = {}


def F(atoms):
    key = tuple(sorted(atoms))
    if key in _fc:
        return _fc[key]
    mols = pot_v3.simulate(list(atoms))
    if mols is None:
        _fc[key] = []
    else:
        _fc[key] = [{"atoms": list(m["atoms"]), "edges": [tuple(e) for e in m["edges"]],
                     "formula": formula(m["atoms"])} for m in mols]
    return _fc[key]


def is_stable(m):
    prods = F(m["atoms"])
    return len(prods) == 1 and prods[0]["formula"] == m["formula"]


def decay_all(mols):
    out = []
    for m in mols:
        if is_stable(m):
            out.append(m)
        else:
            out += F(m["atoms"])
    return out


cycles = []
for i in range(len(pool)):
    A = pool[i]
    for j in range(i + 1, len(pool)):
        B = pool[j]
        a = {"atoms": list(A["atoms"]), "edges": [tuple(e) for e in A["edges"]], "formula": A["formula"]}
        b = {"atoms": list(B["atoms"]), "edges": [tuple(e) for e in B["edges"]], "formula": B["formula"]}
        r = react_v2([(a["atoms"], a["edges"]), (b["atoms"], b["edges"])],
                     use_valence=True, check_geometry=False)
        if not r["changed"]:
            continue
        prods = [{"atoms": list(p["atoms"]), "edges": [tuple(e) for e in p["edges"]],
                  "formula": p["formula"]} for p in r["products"]]
        if sorted(x["formula"] for x in prods) == sorted([A["formula"], B["formula"]]):
            continue
        final = decay_all(prods)
        f_forms = sorted(m["formula"] for m in final)
        if f_forms == sorted([A["formula"], B["formula"]]):
            cycles.append({"A": A["formula"], "B": B["formula"],
                           "class": r["class"], "products": [p["formula"] for p in prods],
                           "decay": [m["formula"] for m in final]})
print("2步闭环数:", len(cycles))
for c in cycles[:20]:
    print(" ", c["A"], "+", c["B"], "→", c["products"], "→", c["decay"], "class", c["class"])
json.dump({"cycles": cycles}, open(BASE + r"\t32b_cycles.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved t32b_cycles.json")
