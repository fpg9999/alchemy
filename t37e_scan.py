# -*- coding: utf-8 -*-
"""t37e_scan.py：抽样目录物质，统计并列歧义与新规则后的残留歧义"""
import json
import random
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all
import t37_tie_analysis as T
from t15_forms_examples import wl_key

BASE = r"G:\AI work\deepseek\work1\alchemy"
ORDER = pot_all.ORDER
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
pool = [r for r in cat if 2 <= len(r["atoms"]) <= 10]
rng = random.Random(9876)
sample = rng.sample(pool, min(400, len(pool)))


def canon(r):
    return tuple(sorted([wl_key(m["atoms"], [tuple(e) for e in m["edges"]]) for m in r["molecules"]], key=str))


def formulas(mols):
    out = []
    for m in mols:
        c = {}
        for a in m["atoms"]:
            c[a] = c.get(a, 0) + 1
        out.append(tuple(sorted(c.items())))
    return tuple(sorted(out, key=str))


stats = {"tested": 0, "with_ties": 0, "formula_ambiguity": 0,
         "skeleton_ambiguity": 0, "residual_after_intra": 0}
res_examples = []
for rec in sample:
    atoms = list(rec["atoms"])
    rd = T.run(atoms, policy="first", collect_ties=True)
    stats["tested"] += 1
    if not rd or not rd["ties"]:
        continue
    stats["with_ties"] += 1
    outs = set()
    fset = set()
    for i in range(20):
        r = T.run(atoms, policy="random", rng=random.Random(i))
        if r:
            outs.add(canon(r))
            fset.add(formulas(r["molecules"]))
    intra_outs = set()
    for i in range(20):
        r = T.run(atoms, policy="intra_random", rng=random.Random(i))
        if r:
            intra_outs.add(canon(r))
    if len(fset) > 1:
        stats["formula_ambiguity"] += 1
    elif len(outs) > 1:
        stats["skeleton_ambiguity"] += 1
    if len(intra_outs) > 1:
        stats["residual_after_intra"] += 1
        if len(res_examples) < 10:
            res_examples.append({"formula": rec["formula"], "natoms": len(atoms),
                                 "ties": len(rd["ties"]), "outcomes": len(outs),
                                 "intra_outcomes": len(intra_outs)})
print(json.dumps(stats, ensure_ascii=False, indent=1))
for e in res_examples:
    print(e)
json.dump({"stats": stats, "residual_examples": res_examples},
          open(BASE + r"\t37_scan.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved t37_scan.json")
