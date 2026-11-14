# -*- coding: utf-8 -*-
"""t29d_split_old.py：寻找"裂解但不产生新分子式"的几何合法示例"""
import json
import random
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from t28_rule_v2 import react_v2, to_system

BASE = r"G:\AI work\deepseek\work1\alchemy"
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
catf = {r["formula"] for r in cat}
small = [r for r in cat if 2 <= len(r["atoms"]) <= 8 and r.get("place")]
rng = random.Random(777)
tried = 0
best = None
while tried < 8000:
    tried += 1
    a, b = rng.sample(small, 2)
    if len(a["atoms"]) + len(b["atoms"]) > 9:
        continue
    r = react_v2([to_system(a), to_system(b)], use_valence=True, check_geometry=False)
    if not r["changed"]:
        continue
    forms = sorted(p["formula"] for p in r["products"])
    if len(forms) < 3:
        continue
    if any(f not in catf for f in forms):
        continue
    rr = react_v2([to_system(a), to_system(b)], use_valence=True, check_geometry=True)
    if not rr["changed"]:
        continue
    best = {"A": {"formula": a["formula"], "atoms": a["atoms"],
                  "edges": [list(e) for e in a["edges"]], "place": a["place"]},
            "B": {"formula": b["formula"], "atoms": b["atoms"],
                  "edges": [list(e) for e in b["edges"]], "place": b["place"]},
            "class": rr["class"], "products": rr["products"],
            "new": [], "nprod": len(rr["products"]),
            "total_atoms": len(a["atoms"]) + len(b["atoms"])}
    break
print("tried", tried, "found", best["A"]["formula"], "+", best["B"]["formula"],
      "→", [p["formula"] for p in best["products"]]) if best else print("none")
if best:
    d = json.load(open(BASE + r"\t29_examples_geo.json", encoding="utf-8"))
    d["split_old"] = best
    json.dump(d, open(BASE + r"\t29_examples_geo.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("updated t29_examples_geo.json")
