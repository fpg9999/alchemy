# -*- coding: utf-8 -*-
"""T81 生长实验 A 选取：两种小营养物 → 单产物 A，且 A 自粘强（w≥1）。"""
import io
import itertools
import json
import os

from alchemy import three_su as TS
from alchemy.core.elements import ORDER as ELEM_ORDER
from natural_engine import complete_products

BASE = r"G:\AI work\deepseek\work1\alchemy"
records = json.load(io.open(os.path.join(BASE, "t4_catalog_index.json"), encoding="utf-8"))
small = [r["formula"] for r in records if r.get("natoms") in (2, 3)]
print("small pool", len(small))
comps = {f: TS.parse_formula(f) for f in small}
sc = {f: TS.scores(c) for f, c in comps.items()}

res = []
for a, b in itertools.combinations(sorted(small), 2):
    ca, cb = comps[a], comps[b]
    pf = TS.pair_force(ca, cb, 1)
    if pf["w"] <= 0.2:
        continue
    vec = [ca.get(e, 0) + cb.get(e, 0) for e in ELEM_ORDER]
    prods = complete_products(vec)
    if not prods or len(prods) != 1:
        continue
    f = prods[0].get("formula")
    if not f:
        continue
    c = TS.parse_formula(f)
    s = TS.scores(c)
    if s["natoms"] < 5 or s["natoms"] > 8:
        continue
    selfw = TS.pair_force(c, c, 1)["w"]
    if selfw < 1.0:
        continue
    res.append((round(selfw, 2), f, a, b, s["A"], s["B"], s["D"], pf["w"],
                round(TS.pair_force(c, ca, 1)["w"], 2), round(TS.pair_force(c, cb, 1)["w"], 2)))

res.sort(key=lambda t: (-t[0], t[1]))
print("%4s %-10s %-8s %-8s %5s %5s %5s %6s %6s %6s" % (
    "self", "A", "food1", "food2", "Aavg", "Bavg", "Davg", "f_pair", "A-f1", "A-f2"))
for r in res[:40]:
    print("%4.2f %-10s %-8s %-8s %5.2f %5.2f %5.2f %6.2f %6.2f %6.2f" % r)
with io.open(os.path.join(BASE, "t81_growth_candidates.json"), "w", encoding="utf-8") as fp:
    json.dump([{"self_w": r[0], "A": r[1], "f1": r[2], "f2": r[3],
                "Aavg": r[4], "Bavg": r[5], "Davg": r[6], "f_pair_w": r[7],
                "A_f1_w": r[8], "A_f2_w": r[9]} for r in res], fp, ensure_ascii=False, indent=1)
print("candidates", len(res))
