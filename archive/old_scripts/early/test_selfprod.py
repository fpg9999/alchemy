# -*- coding: utf-8 -*-
"""test_selfprod：验证"物质可由自身元素组成直接投料得到"（用于类别归组）。

若成立：类别 S 的物质 = 组成元素 ⊆ S 的物质集合，可按组成分组。
"""
import json
import random
import sys

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
data = []
for f in ("substances_league_s3.json", "substances_league_s4.json",
          "substances_league_s5.json", "substances_league_s6.json"):
    try:
        data += json.load(open(BASE + "\\" + f, encoding="utf-8"))
    except Exception as e:
        print("skip", f, e)
print("样本池", len(data))
rng = random.Random(2026)
sample = rng.sample(data, min(800, len(data)))
ok = fail = err = 0
fails = []
for x in sample:
    atoms = list(x["atoms"])
    mols = P.simulate(atoms)
    if not mols:
        fail += 1
        fails.append((x["formula"], "剩键"))
        continue
    if not P.embed_all(mols):
        fail += 1
        fails.append((x["formula"], "摆不出"))
        continue
    fs = [P.formula_of(m["atoms"]) for m in mols]
    if x["formula"] in fs:
        ok += 1
    else:
        fail += 1
        fails.append((x["formula"], fs[:4]))
print(f"自组成重放: OK={ok} FAIL={fail} / {len(sample)}")
for f in fails[:15]:
    print("  fail:", f)
