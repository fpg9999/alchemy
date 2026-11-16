# -*- coding: utf-8 -*-
"""t55_sensitivity.py —— T55 温度标度敏感性实验

主实验按用户设定 1000°C 起步、-1°C/分钟；但项目 T35 的温度阈值（Σc）对聚素
小分子只有 1~20，1000°C 在整个前 980 分钟都远超阈值 => 完全反应主导、系统迅速
退火到 F 不动点。为了看清"温度阈值窗口"里的自然化学反应，补充一组把初温放到
阈值量级的对照实验：T0 = 6/8/12/20°C，各自在 T0 分钟内降到 0°C。

运行：python t55_sensitivity.py
产出：t55_sens_T{t0}.json（每次实验）、t55_sensitivity.json（汇总表）
"""
import json
import sys

BASE = r"G:\AI work\deepseek\work1\alchemy"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from t55_kinetic_env import KineticEnvironment, N_BATCH

CONFIGS = [6, 8, 12, 20]
SEED = 20261116

if __name__ == "__main__":
    rows = []
    for t0 in CONFIGS:
        env = KineticEnvironment(minutes=t0, n_batch=N_BATCH, seed=SEED,
                                 t0=t0, snap_minutes=[0, t0])
        res = env.run()
        out = BASE + r"\t55_sens_T%d.json" % t0
        json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        comp = res["final_composition"]
        n29 = sum(1 for f, v in comp.items() if v["known29"])
        nnew = sum(1 for f, v in comp.items() if not v["known29"])
        top = sorted(comp.items(), key=lambda kv: -kv[1]["count"])[:6]
        row = {
            "T0": t0,
            "minutes": t0,
            "final_N": res["summary"]["final_N"],
            "events_total": res["summary"]["events_total"],
            "reaction_counts": res["summary"]["reaction_counts"],
            "decomp_events": res["summary"]["decomp_events"],
            "new_substances": list(res["new_substances"]),
            "n_distinct_final": len(comp),
            "n_known29_final": n29,
            "n_new_final": nnew,
            "top_final": [(f, v["count"]) for f, v in top],
            "file": out,
        }
        rows.append(row)
        print("== T0=%d ==" % t0, json.dumps(row, ensure_ascii=False)[:600])
    json.dump({"seed": SEED, "runs": rows},
              open(BASE + r"\t55_sensitivity.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t55_sensitivity.json")
