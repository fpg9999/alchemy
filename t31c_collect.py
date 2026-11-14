# -*- coding: utf-8 -*-
"""t31c_collect.py：收集多分子不完全反应的几何合法示例"""
import json
import random
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from t28_rule_v2 import react_v2, to_system

BASE = r"G:\AI work\deepseek\work1\alchemy"
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
catf = {r["formula"] for r in cat}
small = [r for r in cat if 2 <= len(r["atoms"]) <= 5 and r.get("place")]
rng = random.Random(6060)

want = {
    "pair_new": None,          # k=2，合并/交换，产生新物质
    "triple_partial_new": None, # k=3，部分参与，有新物质
    "triple_all_to_one": None,  # k=3，全部合并成一个
    "triple_all_participate": None,  # k=3，全体参与（无输入分子残留）
    "quad_partial_new": None,   # k=4，部分参与，有新物质
    "quint_partial_new": None,  # k=5，部分参与，有新物质
}
tried = 0
while any(v is None for v in want.values()) and tried < 40000:
    tried += 1
    k = rng.choice([2, 3, 4, 5])
    if any(v is None for kk, v in want.items() if kk.startswith({2: "pair", 3: "triple", 4: "quad", 5: "quint"}[k])):
        pass
    recs = rng.sample(small, k)
    if sum(len(r["atoms"]) for r in recs) > 4 * k + 2:
        continue
    system = [to_system(r) for r in recs]
    # 先无几何筛选
    r0 = react_v2(system, use_valence=True, check_geometry=False)
    if not r0["changed"]:
        continue
    forms0 = sorted(p["formula"] for p in r0["products"])
    inh = sorted(rec["formula"] for rec in recs)
    if forms0 == inh:
        continue
    new0 = [f for f in forms0 if f not in catf]
    partial = any(f in forms0 for f in inh)
    # 目标判定
    keys = []
    if k == 2 and new0:
        keys.append("pair_new")
    if k == 3 and new0 and partial and len(forms0) < 3:
        keys.append("triple_partial_new")
    if k == 3 and len(forms0) == 1:
        keys.append("triple_all_to_one")
    if k == 3 and not partial:
        keys.append("triple_all_participate")
    if k == 4 and new0 and partial:
        keys.append("quad_partial_new")
    if k == 5 and new0 and partial:
        keys.append("quint_partial_new")
    keys = [x for x in keys if want.get(x) is None]
    if not keys:
        continue
    # 几何校验
    rr = react_v2(system, use_valence=True, check_geometry=True)
    if not rr["changed"]:
        continue
    data = {"k": k, "inputs": [{"formula": rec["formula"], "atoms": rec["atoms"],
                                "edges": [list(e) for e in rec["edges"]],
                                "place": rec["place"]} for rec in recs],
            "class": rr["class"], "products": rr["products"], "new": new0,
            "partial": partial, "n": len(forms0),
            "atoms": sum(len(rec["atoms"]) for rec in recs)}
    for key in keys:
        if want[key] is None:
            want[key] = data
            print("found", key, "k=", k, "inputs", inh, "→", forms0, "new", new0, flush=True)
print("tried", tried, "found", {k: (v is not None) for k, v in want.items()})
json.dump(want, open(BASE + r"\t31_examples_geo.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved t31_examples_geo.json")
