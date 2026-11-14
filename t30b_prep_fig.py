# -*- coding: utf-8 -*-
"""t30b_prep_fig.py：准备自分解图的数据（XCP2WLK2A -> 产物）"""
import json
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v3
import pot_v2
from t28_rule_v2 import formula

BASE = r"G:\AI work\deepseek\work1\alchemy"
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
by = {r["formula"]: r for r in cat}

M = "XCP2WLK2A"
atoms = P.vec_to_atoms(P.parse_formula(M), P.ORDER)
mols = pot_v3.simulate(atoms)
prods = []
for m in mols:
    f = formula(m["atoms"])
    rec = {"formula": f, "atoms": m["atoms"], "edges": [list(e) for e in m["edges"]]}
    if f in by:
        rec["place"] = by[f]["place"]
    else:
        place = pot_v2.embed_mol2(m["atoms"], [tuple(e) for e in m["edges"]], max_nodes=300000)
        if place:
            rec["place"] = {str(k): list(v) for k, v in place.items()}
    prods.append(rec)
# 不稳定分子本身的 place 来自 t29 的合并产物
ex = json.load(open(BASE + r"\t29_examples_geo.json", encoding="utf-8"))
mrec = None
for key, v in ex.items():
    for p in v.get("products", []):
        if p["formula"] == M:
            mrec = p
print("M place found:", mrec is not None)
data = {"M": {"formula": M, "atoms": atoms,
              "edges": [list(e) for e in mrec["edges"]] if mrec else [],
              "place": mrec["place"] if mrec else None},
        "products": prods}
json.dump(data, open(BASE + r"\t30_fig_data.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("products:", [p["formula"] for p in prods],
      "places:", [("place" in p) for p in prods])
