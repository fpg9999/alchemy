# -*- coding: utf-8 -*-
"""t30_self_decomp.py：不稳定物质的自分解规则分析
不稳定定义：完整大锅反应 F(v_M) 的产物集合 != {M}。
自分解：M -> F(v_M)（完全反应）。检查产物是否都是大锅可产物质、是否含 M、是否收敛。
"""
import json
import random
import sys
from collections import Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v3
from t28_rule_v2 import react_v2, to_system, formula

BASE = r"G:\AI work\deepseek\work1\alchemy"
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
catf = {r["formula"] for r in cat}
small = [r for r in cat if 2 <= len(r["atoms"]) <= 8 and r.get("place")]
rng = random.Random(555)


def atoms_of(f):
    v = P.parse_formula(f)
    return P.vec_to_atoms(v, P.ORDER)


def pot_products(atoms):
    mols = pot_v3.simulate(atoms)
    out = []
    for m in mols:
        out.append(formula(m["atoms"]))
    return out


# 1) 收集自然反应产生的新物质
newf = set()
examples = []
for _ in range(1200):
    a, b = rng.sample(small, 2)
    r = react_v2([to_system(a), to_system(b)], use_valence=True, check_geometry=False)
    if not r["changed"]:
        continue
    forms = sorted(p["formula"] for p in r["products"])
    for f in forms:
        if f not in catf:
            newf.add(f)
    if len(examples) < 10:
        for f in forms:
            if f not in catf:
                examples.append({"A": a["formula"], "B": b["formula"], "new": f})
                break
print("新物质种类:", len(newf))

stats = Counter()
rows = []
for f in sorted(newf):
    atoms = atoms_of(f)
    prods = pot_products(atoms)
    stats["总数"] += 1
    if prods == [f]:
        stats["F后仍为自己"] += 1
    elif f in prods:
        stats["F产物含自己"] += 1
    else:
        stats["完全转化为别的物质"] += 1
    if all(p in catf for p in prods):
        stats["产物全在目录"] += 1
    else:
        stats["产物含目录外"] += 1
    stats[f"产物数{len(prods)}"] += 1
    rows.append({"formula": f, "products": prods})
    if len(examples) < 20:
        examples.append({"new": f, "products": prods})

print("统计:", dict(stats))
print("\n示例:")
for r in rows[:10]:
    print(" ", r["formula"], "→", r["products"])
json.dump({"stats": dict(stats), "rows": rows, "examples": examples},
          open(BASE + r"\t30_self_decomp.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved t30_self_decomp.json")

# 2) 目录物质是否为 F 的不动点（抽样 80）
fixed = 0
tot = 0
for rec in rng.sample(cat, 80):
    prods = pot_products(list(rec["atoms"]))
    tot += 1
    if prods == [rec["formula"]]:
        fixed += 1
print(f"目录物质 F 不动点: {fixed}/{tot}")

# 3) 自分解产物是否稳定（抽样 30 个新物质，检查产物单独再 F）
conv = 0
for r in rows[:30]:
    ok = True
    for p in r["products"]:
        pp = pot_products(atoms_of(p))
        if pp != [p]:
            ok = False
            break
    if ok:
        conv += 1
print(f"自分解产物为 F 不动点: {conv}/30")
