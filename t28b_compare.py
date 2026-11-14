# -*- coding: utf-8 -*-
"""t28b_compare.py：规则 v2 对比（价数分级是否加入、几何校验、能量参数）"""
import json
import random
import sys
from collections import Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from t28_rule_v2 import react_v2, to_system

BASE = r"G:\AI work\deepseek\work1\alchemy"
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
small = [r for r in cat if 2 <= len(r["atoms"]) <= 8 and r.get("place")]
rng = random.Random(99)
pairs = [tuple(rng.sample(small, 2)) for _ in range(400)]

out = {}
# A) 有/无价数分级（无几何）
for uv in (True, False):
    st = Counter()
    for a, b in pairs:
        r = react_v2([to_system(a), to_system(b)], use_valence=uv, check_geometry=False)
        if not r["changed"]:
            st["不反应"] += 1
        else:
            forms = sorted(p["formula"] for p in r["products"])
            if forms == sorted([a["formula"], b["formula"]]):
                st["复原"] += 1
            else:
                st["变化"] += 1
    out[f"valence_{uv}"] = dict(st)

# B) 几何校验（子集 200）
st = Counter()
for a, b in pairs[:200]:
    r = react_v2([to_system(a), to_system(b)], use_valence=True, check_geometry=True)
    if not r["changed"]:
        st["不反应_" + r.get("reason", "?")] += 1
    else:
        forms = sorted(p["formula"] for p in r["products"])
        if forms == sorted([a["formula"], b["formula"]]):
            st["复原"] += 1
        else:
            st["变化"] += 1
out["geometry"] = dict(st)

# C) 能量参数矩阵（无几何，400 对）
energy_table = []
for unit_atoms in (3.0, 4.0, 5.0):
    for storage in (0.25, 0.5, 1.0, 2.0):
        st = Counter()
        for a, b in pairs:
            r = react_v2([to_system(a), to_system(b)], use_valence=True,
                         check_geometry=False, energy=True,
                         unit_atoms=unit_atoms, storage_per_unit=storage)
            if not r["changed"] and r.get("reason") == "能量不足":
                st["能量不足"] += 1
            elif not r["changed"]:
                st["其它不反应"] += 1
            else:
                forms = sorted(p["formula"] for p in r["products"])
                if forms == sorted([a["formula"], b["formula"]]):
                    st["复原"] += 1
                else:
                    st["变化"] += 1
        energy_table.append({"unit_atoms": unit_atoms, "storage": storage, **dict(st)})
out["energy"] = energy_table
print(json.dumps(out, ensure_ascii=False, indent=1))
json.dump(out, open(BASE + r"\t28b_compare.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved t28b_compare.json")
