# -*- coding: utf-8 -*-
"""t56_sensitivity.py —— T56 低温窗口敏感性实验

主实验按 1000°C 起步（绝大部分时间远高于 T35 阈值 Σc≈1~24），净化学在 T=16 就结束。
本脚本把初温放到阈值量级（T0=12/20°C，各自在 T0 分钟内降到 0°C），观察 6 元素体系
的不完全反应、自分解与新物质窗口。

运行：python t56_sensitivity.py
产出：t56_sens_T12.json、t56_sens_T20.json、t56_sensitivity.json
"""
import json
import sys

BASE = r"G:\AI work\deepseek\work1\alchemy"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import t56_ratio_6elem as T
from t55_kinetic_env import KineticEnvironment

CONFIGS = [12, 20]

if __name__ == "__main__":
    known = T.load_catalog_formulas()
    rows = []
    for t0 in CONFIGS:
        env = KineticEnvironment(minutes=t0, seed=T.SEED, t0=t0,
                                 load_spec=T.LOAD_SPEC, known_formulas=known,
                                 event_limit=5000, snap_minutes=[0, t0],
                                 color_mode="bitmask")
        res = env.run()
        out = BASE + r"\t56_sens_T%d.json" % t0
        json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        comp = res["final_composition"]
        new = res["new_substances"]
        rows.append({
            "T0": t0,
            "final_N": res["summary"]["final_N"],
            "events": res["summary"]["events_total"],
            "reactions": res["summary"]["reaction_counts"],
            "decomp": res["summary"]["decomp_events"],
            "n_final": len(comp),
            "n_new_total": len(new),
            "n_new_final": sum(1 for f in comp if f in new),
            "max_atoms": max((v["atoms"] for v in comp.values()), default=0),
            "top": sorted([(f, v["count"]) for f, v in comp.items()],
                          key=lambda x: -x[1])[:6],
            "new_examples": list(new)[:8],
            "file": out,
        })
        print("== T0=%d ==" % t0, json.dumps(rows[-1], ensure_ascii=False)[:500])
    json.dump({"seed": T.SEED, "runs": rows},
              open(BASE + r"\t56_sensitivity.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t56_sensitivity.json")
