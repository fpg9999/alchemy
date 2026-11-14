# -*- coding: utf-8 -*-
"""t28d_stats.py：v2 规则最终统计（价数分级、几何、能量网格、收敛）"""
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
pairs = [tuple(rng.sample(small, 2)) for _ in range(400)]

out = {}
# 1) 无几何，价数分级开/关
for uv in (True, False):
    st = Counter()
    newf = set()
    for a, b in pairs:
        r = react_v2([to_system(a), to_system(b)], use_valence=uv, check_geometry=False)
        if not r["changed"]:
            st["不反应"] += 1
            continue
        forms = sorted(p["formula"] for p in r["products"])
        if forms == sorted([a["formula"], b["formula"]]):
            st["复原"] += 1
        else:
            st["变化"] += 1
            for f in forms:
                if f not in catf:
                    newf.add(f)
    st["新分子式数"] = len(newf)
    out["no_geo_valence_" + str(uv)] = dict(st)

# 2) 几何校验（200 对）
st = Counter()
newf = set()
geo_examples = []
for a, b in pairs[:200]:
    r = react_v2([to_system(a), to_system(b)], use_valence=True, check_geometry=True)
    if not r["changed"]:
        st["不反应_" + r.get("reason", "?")] += 1
        continue
    forms = sorted(p["formula"] for p in r["products"])
    if forms == sorted([a["formula"], b["formula"]]):
        st["复原"] += 1
    else:
        st["变化"] += 1
        for f in forms:
            if f not in catf:
                newf.add(f)
        if len(geo_examples) < 8:
            geo_examples.append({"A": a["formula"], "B": b["formula"],
                                 "out": forms, "class": r["class"]})
st["新分子式数"] = len(newf)
out["geometry"] = dict(st)
out["geometry_examples"] = geo_examples

# 3) 收敛：对有变化的对（无几何）迭代 5 轮
st = Counter()
changed_systems = 0
for a, b in pairs:
    system = [to_system(a), to_system(b)]
    prev = sorted([a["formula"], b["formula"]])
    changed_rounds = 0
    final = prev[:]
    for step in range(5):
        r = react_v2(system, use_valence=True, check_geometry=False)
        if not r["changed"]:
            break
        cur = sorted(p["formula"] for p in r["products"])
        if cur == prev:
            break
        changed_rounds += 1
        prev = cur
        final = cur
        system = [(list(p["atoms"]), [tuple(e) for e in p["edges"]]) for p in r["products"]]
        if len(cur) == 1:
            break
    if changed_rounds:
        changed_systems += 1
        if len(final) == 1:
            st["最终单分子"] += 1
        else:
            st["最终多分子"] += 1
        if changed_rounds == 1:
            st["1轮稳定"] += 1
        else:
            st["多轮稳定"] += 1
out["iteration"] = {"changed_systems": changed_systems, **dict(st)}

# 4) 能量网格（无几何）
grid = []
for unit in (3.0, 4.0, 5.0, 6.0, 8.0):
    for storage in (1.0, 2.0):
        st = Counter()
        changes = 0
        for a, b in pairs:
            r = react_v2([to_system(a), to_system(b)], use_valence=True,
                         check_geometry=False, energy=True,
                         unit_atoms=unit, storage_per_unit=storage)
            if not r["changed"] and r.get("reason") == "能量不足":
                st["能量不足"] += 1
            elif not r["changed"]:
                st["其它不反应"] += 1
            else:
                forms = sorted(p["formula"] for p in r["products"])
                if forms != sorted([a["formula"], b["formula"]]):
                    changes += 1
                    st["变化"] += 1
                else:
                    st["复原"] += 1
        grid.append({"unit_atoms": unit, "storage": storage, **dict(st)})
out["energy_grid"] = grid
print(json.dumps(out, ensure_ascii=False, indent=1))
json.dump(out, open(BASE + r"\t28d_stats.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved t28d_stats.json")
