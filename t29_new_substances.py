# -*- coding: utf-8 -*-
"""t29_new_substances.py：规则 v2（含价数分级，不含能量）下产生新物质的反应分类
统计：
- 断裂类 (d, m, v) 分布
- 产物个数变化（2→1 合并 / 2→2 交换 / 2→≥3 裂解）
- 是否出现目录外新分子式
- 收集每类示例（含结构/坐标，供绘图）
"""
import json
import random
import sys
from collections import Counter, defaultdict
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_v2
from t28_rule_v2 import react_v2, to_system, formula

BASE = r"G:\AI work\deepseek\work1\alchemy"
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
catf = {r["formula"] for r in cat}
small = [r for r in cat if 2 <= len(r["atoms"]) <= 8 and r.get("place")]
rng = random.Random(4242)

N = 1500
stats = Counter()
by_class = Counter()
tag_count = Counter()
by_prodcount = Counter()
examples = defaultdict(list)   # category -> list

for _ in range(N):
    a, b = rng.sample(small, 2)
    r = react_v2([to_system(a), to_system(b)], use_valence=True, check_geometry=False)
    if not r["changed"]:
        stats["不反应"] += 1
        continue
    forms = sorted(p["formula"] for p in r["products"])
    in_forms = sorted([a["formula"], b["formula"]])
    if forms == in_forms:
        stats["复原"] += 1
        continue
    stats["变化"] += 1
    cls = tuple(r["class"])
    by_class[cls] += 1
    nprod = len(forms)
    by_prodcount[nprod] += 1
    new = [f for f in forms if f not in catf]
    if new:
        stats["含新分子式"] += 1
    catg = {1: "合并", 2: "交换", 3: "裂解"}.get(nprod, "裂解")
    tag_count[catg + ("_新" if new else "_旧")] += 1
    # 判断是否合并了新物质
    if new:
        key = catg + ("_新" if True else "")
    else:
        key = catg + "_旧"
    # 收集示例
    if len(examples[key]) < 6:
        examples[key].append({"A": a["formula"], "B": b["formula"],
                              "class": r["class"], "products": forms,
                              "new": new, "nprod": nprod})
print("总样本:", N)
print("统计:", dict(stats))
print("按断裂类:", dict(by_class.most_common()))
print("按产物个数:", dict(by_prodcount))
print("按分类:", dict(tag_count))
print("\n分类示例:")
for k, v in examples.items():
    print(k)
    for e in v[:3]:
        print("  ", e)

json.dump({"stats": dict(stats), "by_class": {str(k): v for k, v in by_class.items()},
           "by_prodcount": dict(by_prodcount),
           "tag_count": dict(tag_count),
           "examples": {k: v for k, v in examples.items()}},
          open(BASE + r"\t29_new_substances.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved t29_new_substances.json")
