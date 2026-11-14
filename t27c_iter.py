# -*- coding: utf-8 -*-
"""t27c_iter.py：分解规则在分子对上的迭代行为（简化正确版）"""
import json
import random
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from t27_break_rule import react

BASE = r"G:\AI work\deepseek\work1\alchemy"
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
small = [r for r in cat if 2 <= len(r["atoms"]) <= 8 and r.get("place")]
rng = random.Random(23)
stats = {"pairs": 0, "无变化": 0, "有变化": 0, "一轮后稳定": 0,
         "多轮后稳定": 0, "5轮仍在变": 0, "失败": 0,
         "最终单分子": 0, "最终多分子": 0}
new_examples = []
for _ in range(300):
    a, b = rng.sample(small, 2)
    system = [(list(a["atoms"]), [tuple(e) for e in a["edges"]]),
              (list(b["atoms"]), [tuple(e) for e in b["edges"]])]
    prev = sorted([a["formula"], b["formula"]])
    initial = prev[:]
    changed_rounds = 0
    final = prev[:]
    n_final = 2
    fail = False
    for step in range(5):
        out = react(system)
        if not out["ok"]:
            fail = True
            break
        cur = sorted(p["formula"] for p in out["products"])
        if cur != prev:
            changed_rounds += 1
            prev = cur
            final = cur
            n_final = len(cur)
            system = [(list(p["atoms"]), [tuple(e) for e in p["edges"]]) for p in out["products"]]
            if len(cur) == 1:
                break
        else:
            prev = cur
            final = cur
            n_final = len(cur)
            break
    stats["pairs"] += 1
    if fail:
        stats["失败"] += 1
        continue
    if changed_rounds == 0:
        stats["无变化"] += 1
    else:
        stats["有变化"] += 1
        if changed_rounds == 1:
            stats["一轮后稳定"] += 1
        else:
            stats["多轮后稳定"] += 1
    if len(final) == 1:
        stats["最终单分子"] += 1
    else:
        stats["最终多分子"] += 1
print(stats)
json.dump(stats, open(BASE + r"\t27c_iter.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
