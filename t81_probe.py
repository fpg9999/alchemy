# -*- coding: utf-8 -*-
"""挑动态实验用的高半径强吸引分子"""
import io
import json
import os

from alchemy import three_su as TS

BASE = r"G:\AI work\deepseek\work1\alchemy"
records = json.load(io.open(os.path.join(BASE, "t4_catalog_all_validated.json"), encoding="utf-8"))
cands = []
for r in records:
    c = TS.parse_formula(r["formula"])
    s = TS.scores(c)
    if not (4 <= s["natoms"] <= 10):
        continue
    if s["A"] < 2.5 or s["Q"] < 10 or s["D"] > 0:
        continue
    pf = TS.pair_force(c, c, 1)
    if pf["w"] < 2.0:
        continue
    cands.append((s["Q"], s["r_att"], r["formula"], round(s["A"], 2), round(pf["w"], 2)))
cands.sort(key=lambda t: (-t[0], t[2]))
print("count", len(cands))
for t in cands[:25]:
    print(t)
# 也看几个固定候选
for f in ["O2K2A2", "O2K3A2", "O3K3", "O2K3A2F2", "O3A2K2", "O2A2K2", "O2K2", "O2", "C2", "WA"]:
    try:
        c = TS.parse_formula(f)
        s = TS.scores(c)
        pf = TS.pair_force(c, c, 1)
        print("%-10s n=%d P=%d Q=%d S=%d A=%.2f B=%.2f D=%.2f rA=%d rR=%d att=%.2f rep=%.2f w=%.2f" % (
            f, s["natoms"], s["P"], s["Q"], s["S"], s["A"], s["B"], s["D"], s["r_att"], s["r_rep"],
            pf["att"], pf["rep"], pf["w"]))
    except Exception as e:
        print(f, "ERR", e)
