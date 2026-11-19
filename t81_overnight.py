# -*- coding: utf-8 -*-
"""T81 扩展验证（多 seed / 长拍 / κ 网格）——夜间跑，输出 t81_overnight.json

E2grid: κA×κR 网格下三元混合的同性键占比（选择性）
E1ext : 多物种 × 多 seed 长时间自组装（键数、最大团）
E3ext : 体生长（吸积）多 seed 长拍
"""
import io
import json
import os
import time

import t81_su_world as W
from alchemy import three_su as TS

BASE = os.path.dirname(os.path.abspath(__file__))
KA = (2.0, 2.25, 2.5, 2.75, 3.0)
KR = (0.3, 0.4, 0.5, 0.6, 0.8)
MIXES = {
    "mix0": ["O2", "X2", "C2", "K2", "A2", "F2"],
    "mix1": ["OXC", "WCK", "LAF", "XA", "WK", "CL"],
    "mix2": ["O2", "X3", "C2", "O3X2", "X2C3", "OC3"],
}
E1S = ["O2K2A2", "O2K6A2", "O2K3A2F2", "O2", "X2", "C2", "XA", "K2", "WA", "LF"]
E3S = ["O2K2A2", "O2K3A2F2", "O2", "C2", "WA"]

t0 = time.time()
out = {"meta": {"time": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "grid_ka": list(KA), "grid_kr": list(KR),
                "mixes": MIXES, "e1_species": E1S, "e3_species": E3S},
       "e2_grid": [], "e1": [], "e3": []}

# ---- E2 网格：κ 敏感性 ----
n = 0
for ka in KA:
    for kr in KR:
        TS.K_A, TS.K_R = ka, kr
        for mname, mix in MIXES.items():
            for sd in (31, 32, 33):
                r = W.run_e2(mix, 20, 40, 1200, sd, sample=200)
                sb = r["final"]["same_bond"]
                out["e2_grid"].append({
                    "k_a": ka, "k_r": kr, "mix": mname, "seed": sd,
                    "same_frac": round(sb["frac"], 4),
                    "expected": round(sb["expected"], 4),
                    "bonds": sb["total"],
                    "max_comp": r["final"]["max_comp"],
                })
                n += 1
        print("E2grid ka=%.2f kr=%.2f done (%d runs, %.0fs)" % (ka, kr, n, time.time() - t0), flush=True)

# ---- E1 扩展：多 seed 长拍 ----
TS.K_A, TS.K_R = 2.5, 0.5
for f in E1S:
    for sd in (41, 42, 43, 44):
        r = W.run_e1(f, 50, 50, 2500, sd, sample=250)
        out["e1"].append({
            "formula": f, "seed": sd,
            "self_w": round(r["self"]["w"], 3),
            "final": {k: r["final"][k] for k in
                      ("bonds", "bonds_strong", "max_comp", "max_comp_strong", "n_comp", "bond_ratio")},
            "bonds_t250": [s["bonds"] for s in r["series"] if s["t"] >= 250][0],
            "bonds_t1000": [s["bonds"] for s in r["series"] if s["t"] == 1000][0],
        })
    print("E1ext %-6s done (%.0fs)" % (f, time.time() - t0), flush=True)

# ---- E3 扩展 ----
for f in E3S:
    for uf in (True, False):
        for sd in (51, 52, 53):
            r = W.run_e3(f, 25, 60, 4000, sd, use_force=uf, sample=200)
            out["e3"].append({
                "A": f, "use_force": uf, "seed": sd,
                "self_w": round(r["self_w"], 3),
                "body_n": r["final"]["body_n"],
                "body_n_max": max(s["body_n"] for s in r["series"]),
                "tails": [s["body_n"] for s in r["series"][-5:]],
                "bonds_final": r["final"]["bonds"],
            })
    print("E3ext %-6s done (%.0fs)" % (f, time.time() - t0), flush=True)

out["meta"]["elapsed_s"] = round(time.time() - t0, 2)
with io.open(os.path.join(BASE, "t81_overnight.json"), "w", encoding="utf-8") as fp:
    json.dump(out, fp, ensure_ascii=False, indent=1)
print("saved t81_overnight.json", out["meta"]["elapsed_s"], "s")
