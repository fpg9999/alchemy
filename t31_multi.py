# -*- coding: utf-8 -*-
"""t31_multi.py：自然环境不完全反应——多分子体系（k=2..5）统计（修正版）"""
import json
import random
import sys
from collections import Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from t28_rule_v2 import react_v2, to_system

BASE = r"G:\AI work\deepseek\work1\alchemy"
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
catf = {r["formula"] for r in cat}
pool = [r for r in cat if 2 <= len(r["atoms"]) <= 4 and r.get("place")]
print("pool:", len(pool))
rng = random.Random(9090)

stats = {}
examples = {}
for k in (2, 3, 4, 5):
    st = Counter()
    exs = []
    tried = 0
    while st["体系"] < 500 and tried < 50000:
        tried += 1
        recs = rng.sample(pool, k)
        if sum(len(r["atoms"]) for r in recs) > 4 * k + 2:
            continue
        system = [to_system(r) for r in recs]
        r = react_v2(system, use_valence=True, check_geometry=False)
        st["体系"] += 1
        if not r["changed"]:
            st["不反应"] += 1
            continue
        forms = sorted(p["formula"] for p in r["products"])
        inh = sorted(rec["formula"] for rec in recs)
        if forms == inh:
            st["复原"] += 1
            continue
        st["真正改变"] += 1
        n = len(forms)
        new = [f for f in forms if f not in catf]
        if new:
            st["产新物质"] += 1
        st[f"产物数{n}"] += 1
        partial = any(f in forms for f in inh)
        if partial:
            st["部分反应(有分子未参与)"] += 1
        else:
            st["全体参与"] += 1
        if n < k:
            st["合并(n<k)"] += 1
        elif n == k:
            st["交换(n=k)"] += 1
        else:
            st["裂解(n>k)"] += 1
        if len(exs) < 30:
            exs.append({"inputs": inh, "class": r["class"], "products": forms,
                        "new": new, "n": n, "partial": partial,
                        "atoms": sum(len(rec["atoms"]) for rec in recs)})
    stats[k] = dict(st)
    examples[k] = exs
    print(f"k={k}:", dict(st), flush=True)
    longest = max((len(e["products"]) for e in exs), default=0)
    print("  example counts:", Counter(e["n"] for e in exs))

json.dump({"stats": {str(k): v for k, v in stats.items()},
           "examples": {str(k): v for k, v in examples.items()}},
          open(BASE + r"\t31_multi.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved t31_multi.json")
