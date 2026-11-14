# -*- coding: utf-8 -*-
"""t28c_examples.py：寻找适合图示的分解反应实例（小分子、几何合法、产物简单）"""
import json
import random
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from t28_rule_v2 import react_v2, to_system

BASE = r"G:\AI work\deepseek\work1\alchemy"
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
small = [r for r in cat if 2 <= len(r["atoms"]) <= 6 and r.get("place")]
rng = random.Random(2029)
found = []
tried = 0
while len(found) < 8 and tried < 3000:
    tried += 1
    a, b = rng.sample(small, 2)
    if len(a["atoms"]) + len(b["atoms"]) > 9:
        continue
    out = react_v2([to_system(a), to_system(b)], use_valence=True, check_geometry=True)
    if not out["changed"]:
        continue
    forms = sorted(p["formula"] for p in out["products"])
    if forms == sorted([a["formula"], b["formula"]]):
        continue
    found.append({"A": {"formula": a["formula"], "atoms": a["atoms"],
                        "edges": [list(e) for e in a["edges"]], "place": a["place"]},
                  "B": {"formula": b["formula"], "atoms": b["atoms"],
                        "edges": [list(e) for e in b["edges"]], "place": b["place"]},
                  "class": list(out["class"]), "broken": out["broken"],
                  "products": out["products"], "total_atoms": len(a["atoms"]) + len(b["atoms"])})
print("tried", tried, "found", len(found))
found.sort(key=lambda x: (x["total_atoms"], sum(len(p["atoms"]) for p in x["products"])))
for f in found:
    print(f["A"]["formula"], "+", f["B"]["formula"], "class", f["class"],
          "→", [p["formula"] for p in f["products"]])
json.dump(found, open(BASE + r"\t28_examples.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved t28_examples.json")
