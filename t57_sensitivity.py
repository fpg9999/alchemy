# -*- coding: utf-8 -*-
"""t57_sensitivity.py —— T57 面积模型的低温窗口敏感性（补充实验）

主实验 1000°C 下完全反应主导，终态由元素配比决定（OXC+OX2C）；本脚本把初温放到
T35 阈值量级（T0=12/20°C，各自在 T0 分钟内降到 0°C，面积模型不变），观察
"低温下大分子能否保留"。

运行：python t57_sensitivity.py
产出：t57_sens_T12.json、t57_sens_T20.json、t57_sensitivity.json
"""
import json
import sys

BASE = r"G:\AI work\deepseek\work1\alchemy"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import pot_all as P
import t57_all29_area as T
from t55_kinetic_env import KineticEnvironment

CONFIGS = [12, 20]

if __name__ == "__main__":
    spec, rows, meta = T.build_load_spec()
    known = {r["formula"] for r in T.load_29()}
    out_rows = []
    for t0 in CONFIGS:
        env = KineticEnvironment(minutes=t0, seed=T.SEED, t0=t0,
                                 load_spec=spec, known_formulas=known,
                                 area_model="count", weighted_partner=True,
                                 event_limit=5000, snap_minutes=[0, t0])
        res = env.run()
        fn = BASE + r"\t57_sens_T%d.json" % t0
        json.dump(res, open(fn, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        comp = res["final_composition"]
        sizes = {}
        for f, v in comp.items():
            n = sum(P.parse_formula(f))
            sizes[n] = sizes.get(n, 0) + v["count"]
        N = res["summary"]["final_N"]
        row = {
            "T0": t0, "final_N": N, "atoms": res["summary"]["final_atoms"],
            "events": res["summary"]["events_total"],
            "reactions": res["summary"]["reaction_counts"],
            "decomp": res["summary"]["decomp_events"],
            "mean_size": round(sum(n * c for n, c in sizes.items()) / N, 3),
            "max_atoms": max(sizes),
            "big5": sum(c for n, c in sizes.items() if n >= 5),
            "n_formulas": len(comp),
            "new": len(res["new_substances"]),
            "size_dist": {str(n): c for n, c in sorted(sizes.items())},
            "file": fn,
        }
        out_rows.append(row)
        print("== T0=%d ==" % t0, json.dumps(row, ensure_ascii=False))
    json.dump({"seed": T.SEED, "area_model": "count", "runs": out_rows},
              open(BASE + r"\t57_sensitivity.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t57_sensitivity.json")
