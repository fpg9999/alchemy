# -*- coding: utf-8 -*-
"""t28e_combined.py：能量(4原子/单位,1能量)+几何 联合测试"""
import json
import random
import sys
from collections import Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from t28_rule_v2 import react_v2, to_system

BASE = r"G:\AI work\deepseek\work1\alchemy"
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
small = [r for r in cat if 2 <= len(r["atoms"]) <= 8 and r.get("place")]
catf = {r["formula"] for r in cat}
rng = random.Random(2029)
pairs = [tuple(rng.sample(small, 2)) for _ in range(200)]
st = Counter()
newf = set()
for a, b in pairs:
    r = react_v2([to_system(a), to_system(b)], use_valence=True, check_geometry=True,
                 energy=True, unit_atoms=4.0, storage_per_unit=1.0)
    if not r["changed"]:
        st["不反应_" + r.get("reason", "?")] += 1
    else:
        forms = sorted(p["formula"] for p in r["products"])
        if forms == sorted([a["formula"], b["formula"]]):
            st["复原"] += 1
        else:
            st["变化"] += 1
            for f in forms:
                if f not in catf:
                    newf.add(f)
st["新分子式数"] = len(newf)
print(dict(st))
json.dump(dict(st), open(BASE + r"\t28e_combined.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
