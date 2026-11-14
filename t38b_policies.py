# -*- coding: utf-8 -*-
"""t38b_policies.py：不同并列策略下，中间态骨架块是否落在 38 + 7×3 库内"""
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
multi_keys = {wl_key(f["atoms"], [tuple(e) for e in f["edges"]]): f["formula"]
              for f in t8 if len(set(f["atoms"]) & TRI) >= 2}
single_templates = [
    ("单原子", ["A"], []),
    ("单键二聚", ["A", "A"], [(0, 1, 1)]),
    ("双键二聚", ["A", "A"], [(0, 1, 2)]),
    ("三键二聚", ["A", "A"], [(0, 1, 3)]),
    ("三元链", ["A", "A", "A"], [(0, 1, 1), (1, 2, 1)]),
    ("三元环(全单)", ["A", "A", "A"], [(0, 1, 1), (1, 2, 1), (0, 2, 1)]),
    ("三元环(一单双)", ["A", "A", "A"], [(0, 1, 2), (1, 2, 1), (0, 2, 1)]),
]
single_keys = {wl_key(a, [tuple(e) for e in es]) for _, a, es in single_templates}


def ok_block(b):
    ats = b["atoms"]
    types = set(ats) & TRI
    k = wl_key(ats, [tuple(e) for e in b["edges"]])
    if len(types) >= 2:
        return k in multi_keys
    if len(types) == 1:
        return k in single_keys
    return False


def status(atoms, policy, seed):
    r = T.run(atoms, policy=policy, rng=random.Random(seed))
    if not r or not r["block_structs"]:
        return None
    return all(ok_block(b) for b in r["block_structs"])


rng = random.Random(2024)
pool = [r for r in cat if 2 <= len(r["atoms"]) <= 10]
sample = rng.sample(pool, 200)
stats = Counter()
outs = {}
for rec in sample:
    atoms = list(rec["atoms"])
    d = status(atoms, "first", 0)
    rand = [status(atoms, "random", i) for i in range(15)]
    intra = [status(atoms, "intra_random", i) for i in range(10)]
    if d is None:
        continue
    stats["有结果物质"] += 1
    if d:
        stats["默认库内"] += 1
    else:
        stats["默认库外"] += 1
    if any(rand) and not all(rand):
        stats["随机并列有库内/库外变化"] += 1
    elif not any(rand):
        stats["随机全库外"] += 1
    else:
        stats["随机全库内"] += 1
    if any(intra) and not all(intra):
        stats["新规则后仍库内/库外变化"] += 1
    elif not any(intra):
        stats["新规则全库外"] += 1
    else:
        stats["新规则全库内"] += 1
    if len(outs) < 12 and (not all(rand)):
        outs[rec["formula"]] = {"default": d, "random": rand, "intra": intra}
print(dict(stats))
for f, v in outs.items():
    print(" ", f, v)
json.dump({"stats": dict(stats), "examples": outs},
          open(BASE + r"\t38b_policies.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved t38b_policies.json")
