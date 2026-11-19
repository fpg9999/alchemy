# -*- coding: utf-8 -*-
"""T81 参数敏感性（动态）：κA/κR 对选择性 + 自组装初速的影响"""
import io
import json
import os
import time

import t81_su_world as W
from alchemy import three_su as TS

BASE = os.path.dirname(os.path.abspath(__file__))
out = {"meta": {"time": time.strftime("%Y-%m-%dT%H:%M:%S")}, "rows": []}

for ka, kr in ((2.0, 0.4), (2.5, 0.5), (3.0, 0.6)):
    TS.K_A, TS.K_R = ka, kr
    for sd in (21, 22, 23):
        e2 = W.run_e2(["O2", "X2", "C2", "K2", "A2", "F2"], 20, 40, 800, sd, sample=400)
        same = e2["final"]["same_bond"]
        e1 = W.run_e1("O2K2A2", 40, 40, 800, sd, sample=100)
        bonds100 = [s["bonds"] for s in e1["series"] if s["t"] == 100][0]
        out["rows"].append({
            "k_a": ka, "k_r": kr, "seed": sd,
            "same_frac": round(same["frac"], 4), "expected": round(same["expected"], 4),
            "bonds": same["total"],
            "max_comp": e1["final"]["max_comp"], "bonds_t100": bonds100,
            "bonds_final": e1["final"]["bonds"],
        })
        print(ka, kr, sd, out["rows"][-1])

with io.open(os.path.join(BASE, "t81_sweep.json"), "w", encoding="utf-8") as fp:
    json.dump(out, fp, ensure_ascii=False, indent=1)
print("saved t81_sweep.json")
