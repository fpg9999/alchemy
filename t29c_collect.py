# -*- coding: utf-8 -*-
"""t29c_collect.py：收集 6 类反应的示例（含结构/坐标），供图示"""
import json
import random
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_v2
from t28_rule_v2 import react_v2, to_system

BASE = r"G:\AI work\deepseek\work1\alchemy"
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
catf = {r["formula"] for r in cat}
small = [r for r in cat if 2 <= len(r["atoms"]) <= 7 and r.get("place")]
rng = random.Random(31415)

categories = {"merge_new": None, "exchange_new": None, "split_new": None,
              "merge_old": None, "exchange_old": None, "split_old": None,
              "class012_new": None}
found = {}
used = set()
tried = 0
while len(found) < 7 and tried < 20000:
    tried += 1
    a, b = rng.sample(small, 2)
    key = tuple(sorted([a["formula"], b["formula"]]))
    if key in used:
        continue
    if len(a["atoms"]) + len(b["atoms"]) > 9:
        continue
    r = react_v2([to_system(a), to_system(b)], use_valence=True, check_geometry=False)
    if not r["changed"]:
        continue
    forms = sorted(p["formula"] for p in r["products"])
    in_forms = sorted([a["formula"], b["formula"]])
    if forms == in_forms:
        continue
    new = [f for f in forms if f not in catf]
    n = len(forms)
    catg = "merge" if n == 1 else ("exchange" if n == 2 else "split")
    tag = catg + ("_new" if new else "_old")
    if tag in categories and tag not in found:
        # 几何校验
        rr = react_v2([to_system(a), to_system(b)], use_valence=True, check_geometry=True)
        if not rr["changed"]:
            continue
        found[tag] = {"A": {"formula": a["formula"], "atoms": a["atoms"],
                            "edges": [list(e) for e in a["edges"]], "place": a["place"]},
                      "B": {"formula": b["formula"], "atoms": b["atoms"],
                            "edges": [list(e) for e in b["edges"]], "place": b["place"]},
                      "class": rr["class"], "broken": rr["broken"],
                      "products": rr["products"], "new": new,
                      "nprod": len(rr["products"]), "total_atoms": len(a["atoms"]) + len(b["atoms"])}
        used.add(key)
        print("found", tag, a["formula"], "+", b["formula"], "→", forms, "new", new)
    cls = tuple(r["class"])
    if "class012_new" not in found and cls in ((0, -1, 2),) and new:
        rr = react_v2([to_system(a), to_system(b)], use_valence=True, check_geometry=True)
        if rr["changed"]:
            found["class012_new"] = {"A": {"formula": a["formula"], "atoms": a["atoms"],
                                           "edges": [list(e) for e in a["edges"]], "place": a["place"]},
                                     "B": {"formula": b["formula"], "atoms": b["atoms"],
                                           "edges": [list(e) for e in b["edges"]], "place": b["place"]},
                                     "class": rr["class"], "products": rr["products"],
                                     "new": new, "nprod": len(rr["products"]),
                                     "total_atoms": len(a["atoms"]) + len(b["atoms"])}
            print("found class012_new", a["formula"], "+", b["formula"], "→", forms)
print("tried", tried, "found", list(found.keys()))
json.dump(found, open(BASE + r"\t29_examples_geo.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved t29_examples_geo.json")
