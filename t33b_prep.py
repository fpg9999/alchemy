# -*- coding: utf-8 -*-
"""t33b_prep.py：温度阈值示例（W2A + WA3F2）的结构/坐标"""
import json
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v3
import pot_v2
from t28_rule_v2 import react_v2, formula

BASE = r"G:\AI work\deepseek\work1\alchemy"
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
by = {r["formula"]: r for r in cat}
A = "W2A"; B = "WA3F2"


def rec(f):
    r = by[f]
    return {"formula": f, "atoms": list(r["atoms"]),
            "edges": [list(e) for e in r["edges"]], "place": r["place"]}


def attach(mol):
    if mol["formula"] in by and by[mol["formula"]].get("place"):
        mol["place"] = by[mol["formula"]]["place"]
    else:
        place = pot_v2.embed_mol2(mol["atoms"], [tuple(e) for e in mol["edges"]], max_nodes=300000)
        mol["place"] = {str(k): list(v) for k, v in place.items()} if place else None
    return mol


ra, rb = by[A], by[B]
r = react_v2([(list(ra["atoms"]), [tuple(e) for e in ra["edges"]]),
              (list(rb["atoms"]), [tuple(e) for e in rb["edges"]])],
             use_valence=True, check_geometry=True)
print("incomplete changed", r["changed"], "products", [p["formula"] for p in r["products"]])
prods = []
for p in r["products"]:
    prods.append(attach({"formula": p["formula"], "atoms": list(p["atoms"]),
                         "edges": [list(e) for e in p["edges"]]}))
# 完全反应
atoms = list(ra["atoms"]) + list(rb["atoms"])
mols = pot_v3.simulate(atoms)
comp = []
for m in mols:
    comp.append(attach({"formula": formula(m["atoms"]), "atoms": list(m["atoms"]),
                        "edges": [list(e) for e in m["edges"]]}))
data = {"A": rec(A), "B": rec(B), "incomplete": prods, "complete": comp,
        "cA": sum(e[2] for e in ra["edges"]), "cB": sum(e[2] for e in rb["edges"]),
        "class": r["class"]}
print("cA", data["cA"], "cB", data["cB"])
print("incomplete", [(p["formula"], p["place"] is not None) for p in prods])
print("complete", [(p["formula"], p["place"] is not None) for p in comp])
json.dump(data, open(BASE + r"\t33_fig_data.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved t33_fig_data.json")
