# -*- coding: utf-8 -*-
"""t38_library_check.py：检查在并列歧义下，中间态骨架块是否始终落在 38 + 7×3 库内"""
import json
import random
import sys
from collections import Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all
import t37_tie_analysis as T
from t15_forms_examples import wl_key

BASE = r"G:\AI work\deepseek\work1\alchemy"
TRI = {"O", "P", "K"}
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
t8 = json.load(open(BASE + r"\t8_forms.json", encoding="utf-8"))
multi_keys = {}
for f in t8:
    ats = f["atoms"]
    if len(set(ats) & TRI) >= 2:
        multi_keys[wl_key(ats, [tuple(e) for e in f["edges"]])] = f["formula"]
single_templates = [
    ("单原子", ["A"], []),
    ("单键二聚", ["A", "A"], [(0, 1, 1)]),
    ("双键二聚", ["A", "A"], [(0, 1, 2)]),
    ("三键二聚", ["A", "A"], [(0, 1, 3)]),
    ("三元链", ["A", "A", "A"], [(0, 1, 1), (1, 2, 1)]),
    ("三元环(全单)", ["A", "A", "A"], [(0, 1, 1), (1, 2, 1), (0, 2, 1)]),
    ("三元环(一单双)", ["A", "A", "A"], [(0, 1, 2), (1, 2, 1), (0, 2, 1)]),
]
single_keys = {wl_key(a, [tuple(e) for e in es]): n for n, a, es in single_templates}


def block_ok(b):
    ats = b["atoms"]
    types = set(ats) & TRI
    k = wl_key(ats, [tuple(e) for e in b["edges"]])
    if len(types) >= 2:
        return "multi" if k in multi_keys else "BAD"
    if len(types) == 1:
        return "single" if k in single_keys else "BAD"
    return "BAD"


def check(atoms, n=30, policy="random"):
    bad = []
    kinds = Counter()
    for i in range(n):
        r = T.run(atoms, policy=policy, rng=random.Random(i * 13 + 5))
        if not r:
            continue
        for b in r["block_structs"] or []:
            k = block_ok(b)
            kinds[k] += 1
            if k == "BAD":
                bad.append(("".join(sorted(b["atoms"])), b["edges"]))
    return kinds, bad


# 1) 10 原子示例
for f in ["O5X3KA", "O5X3PA", "OCP7W2KA2"]:
    atoms = pot_all.vec_to_atoms(pot_all.parse_formula(f), pot_all.ORDER)
    kinds, bad = check(atoms, 50)
    print(f, dict(kinds), "BAD", len(bad), bad[:3])

# 2) 随机 100 个物质，随机并列 20 次
rng = random.Random(777)
pool = [r for r in cat if 2 <= len(r["atoms"]) <= 10]
sample = rng.sample(pool, 100)
tot_kinds = Counter()
tot_bad = 0
bad_examples = []
for rec in sample:
    kinds, bad = check(list(rec["atoms"]), 20, policy="random")
    tot_kinds.update(kinds)
    tot_bad += len(bad)
    if bad and len(bad_examples) < 8:
        bad_examples.append((rec["formula"], bad[:2]))
print("随机100物质合计:", dict(tot_kinds), "BAD", tot_bad)
for e in bad_examples:
    print("  BAD example", e)
json.dump({"random_kinds": dict(tot_kinds), "bad": tot_bad, "bad_examples": bad_examples},
          open(BASE + r"\t38_library_check.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved t38_library_check.json")
