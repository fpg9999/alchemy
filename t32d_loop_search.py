# -*- coding: utf-8 -*-
"""t32d_loop_search.py：搜索更长的完整循环（A+B → 不稳定 → 稳定 → ... → A+B）"""
import json
import random
import sys
from itertools import combinations
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v3
from t28_rule_v2 import react_v2, formula

BASE = r"G:\AI work\deepseek\work1\alchemy"
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
pool = [r for r in cat if 2 <= len(r["atoms"]) <= 4 and r.get("place")]
rng = random.Random(8181)
_fc = {}


def F(mol):
    key = tuple(sorted(mol["atoms"]))
    if key in _fc:
        return _fc[key]
    mols = pot_v3.simulate(list(mol["atoms"]))
    if mols is None:
        _fc[key] = []
    else:
        _fc[key] = [{"atoms": list(m["atoms"]), "edges": [tuple(e) for e in m["edges"]],
                     "formula": formula(m["atoms"])} for m in mols]
    return _fc[key]


def stable(mol):
    p = F(mol)
    return len(p) == 1 and p[0]["formula"] == mol["formula"]


def decay_all(ms):
    out = []
    for m in ms:
        if stable(m):
            out.append(dict(m))
        else:
            out += [dict(p) for p in F(m)]
    return out


def to_mol(p):
    return {"atoms": list(p["atoms"]), "edges": [tuple(e) for e in p["edges"]],
            "formula": p["formula"]}


def key(ms):
    return tuple(sorted(m["formula"] for m in ms))


loops = []
chains = []
tried = 0
# 随机抽 6000 对
pairs = []
while len(pairs) < 6000:
    a, b = rng.sample(pool, 2)
    if (a["formula"], b["formula"]) not in pairs:
        pairs.append((a["formula"], b["formula"]))
byf = {r["formula"]: r for r in cat}

for fa, fb in pairs:
    tried += 1
    A = byf[fa]; B = byf[fb]
    a = {"atoms": list(A["atoms"]), "edges": [tuple(e) for e in A["edges"]], "formula": fa}
    b = {"atoms": list(B["atoms"]), "edges": [tuple(e) for e in B["edges"]], "formula": fb}
    inp = key([a, b])
    r = react_v2([(a["atoms"], a["edges"]), (b["atoms"], b["edges"])],
                 use_valence=True, check_geometry=False)
    if not r["changed"]:
        continue
    prods = [to_mol(p) for p in r["products"]]
    if key(prods) == inp:
        continue
    S1 = decay_all(prods)
    if key(S1) == inp:
        loops.append({"depth": 1, "init": [fa, fb], "steps": [key(prods), key(S1)],
                      "class": r["class"], "products": [p["formula"] for p in prods]})
        continue
    # 深度 2：从 S1 中尝试所有 2/3 子集反应
    n = len(S1)
    found = False
    for k in (2, 3):
        for idx in combinations(range(n), k):
            sub = [S1[i] for i in idx]
            rr = react_v2([(m["atoms"], m["edges"]) for m in sub],
                          use_valence=True, check_geometry=False)
            if not rr["changed"]:
                continue
            pp = [to_mol(p) for p in rr["products"]]
            if key(pp) == key(sub):
                continue
            S2 = [m for j, m in enumerate(S1) if j not in idx] + decay_all(pp)
            if key(S2) == inp:
                loops.append({"depth": 2, "init": [fa, fb],
                              "steps": [key(prods), key(S1), key(S2)],
                              "class": r["class"], "products": [p["formula"] for p in prods],
                              "class2": rr["class"]})
                found = True
                break
        if found:
            break
    if not found and len(chains) < 30:
        # 记录链式：S1 还能继续反应
        for k in (2, 3):
            if len(S1) < k:
                continue
            for idx in combinations(range(len(S1)), k):
                sub = [S1[i] for i in idx]
                rr = react_v2([(m["atoms"], m["edges"]) for m in sub],
                              use_valence=True, check_geometry=False)
                if rr["changed"] and key([to_mol(p) for p in rr["products"]]) != key(sub):
                    chains.append({"init": [fa, fb],
                                   "products1": [p["formula"] for p in prods],
                                   "decay1": list(key(S1)),
                                   "reaction2_in": [m["formula"] for m in sub],
                                   "reaction2_out": [p["formula"] for p in rr["products"]],
                                   "class1": r["class"], "class2": rr["class"]})
                    break
            if chains:
                break

print("试试对数:", tried)
print("闭环数:", len(loops), "链式数:", len(chains))
for l in loops[:20]:
    print(" LOOP", l)
for c in chains[:10]:
    print(" CHAIN", c)
json.dump({"loops": loops, "chains": chains},
          open(BASE + r"\t32d_loops.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved t32d_loops.json")
