# -*- coding: utf-8 -*-
"""t27b_pairs.py：测试分解规则在"两个/多个分子"体系中的表现（含迭代）"""
import json
import random
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from t27_break_rule import react

BASE = r"G:\AI work\deepseek\work1\alchemy"
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
small = [r for r in cat if 2 <= len(r["atoms"]) <= 8 and r.get("place")]
mid = [r for r in cat if 9 <= len(r["atoms"]) <= 16 and r.get("place")]
rng = random.Random(11)


def to_system(rec):
    return (list(rec["atoms"]), [tuple(e) for e in rec["edges"]])


def run_pair(a, b):
    out = react([to_system(a), to_system(b)])
    return out


stats = {"pairs": 0, "无变化": 0, "有变化": 0, "重结合失败": 0, "含新分子式": 0}
examples = []
for _ in range(500):
    a, b = rng.sample(small, 2)
    out = run_pair(a, b)
    stats["pairs"] += 1
    if not out["ok"]:
        stats["重结合失败"] += 1
        continue
    inh = sorted([a["formula"], b["formula"]])
    prods = sorted(p["formula"] for p in out["products"])
    if prods == inh:
        stats["无变化"] += 1
    else:
        stats["有变化"] += 1
        for f in prods:
            if f not in {r["formula"] for r in cat}:
                stats["含新分子式"] += 1
                break
        if len(examples) < 20:
            examples.append({"A": a["formula"], "B": b["formula"],
                             "class": out["class"], "broken": out["broken"],
                             "out": [p["formula"] for p in out["products"]]})
print("小分子对:", stats)
for e in examples[:10]:
    print(" ", e)

# 迭代测试：选 100 个小分子，单独反复施加规则，看是否固定点
iter_stats = {"tested": 0, "fixed": 0, "changed": 0, "fail": 0}
for rec in rng.sample(small, min(100, len(small))):
    cur = to_system(rec)
    orig = rec["formula"]
    changed = False
    for step in range(5):
        out = react([cur])
        if not out["ok"]:
            iter_stats["fail"] += 1
            break
        if len(out["products"]) != 1:
            changed = True
            break
        p = out["products"][0]
        cur = (p["atoms"], [tuple(e) for e in p["edges"]])
    iter_stats["tested"] += 1
    if changed:
        iter_stats["changed"] += 1
    else:
        iter_stats["fixed"] += 1
print("迭代(5 轮)测试:", iter_stats)
json.dump({"pair_stats": stats, "examples": examples,
           "iter_stats": iter_stats},
          open(BASE + r"\t27b_pairs.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved t27b_pairs.json")
