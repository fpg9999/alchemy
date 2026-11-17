# -*- coding: utf-8 -*-
"""t62_two_phase.py —— T62：九元素两阶段连续实验（三价/二价/一价数量相当）

实验流程（与 T59 相同，仅把"价数配比"从 3>2>1 改为 ≈1:1:1）：
1. **第一阶段**：投入 120 种物质（batchA，14,752 分子 / 150,019 原子，
   三价:二价:一价 = 33.41%:33.30%:33.29%，9 元素各 ≈11.1%）；
   环境 L=60000，面积模型（A∝原子数），初速按 500 次穿越设计；
   温度 1000→0°C，运行 1000 分钟（完全反应 + 不完全反应 + 自分解，T35 规则）。
2. **整理**：到达 0°C 后清点归档全部物质（不丢弃），作为第二阶段底物重新装入环境。
3. **第二阶段**：再投入一批物质（batchB，120 种 / 8,124 分子 / 80,027 原子，同样三/二/一价等量），
   温度重置 1000°C，再连续运行 1000 分钟到 0°C。
4. 保存两阶段完整结果，供对比分析；另跑 cap=60 高保真对照与无化学对照。

算法：`natural_engine.set_fast(True)`（fast_pot，与 pot_v4 规则 1~11 等价）；
`max_reaction_atoms=40`（主实验）/ 60（高保真对照）。

用法：
  python t62_two_phase.py --phase A
  python t62_two_phase.py --phase B
  python t62_two_phase.py --phase both
  python t62_two_phase.py --control          # 无化学对照（500 分钟）
"""
import argparse
import json
import sys
import time

BASE = r"G:\AI work\deepseek\work1\alchemy"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import natural_engine as E
import t55_kinetic_env as K
from t55_kinetic_env import KineticEnvironment, run_control

SEED_A = 20261124
SEED_B = 20261125
ENV_L = 60000.0
MAX_REACTION_ATOMS = 40
MINUTES = 1000
SNAP_MINUTES = [0, 2, 5, 10, 25, 50, 100, 200, 300, 400,
                500, 600, 700, 800, 900, 950, 980, 995, 1000]
EVENT_LIMIT = 50000


def load_design():
    return json.load(open(BASE + r"\t62_loads.json", encoding="utf-8"))


def spec_from_rows(rows, tag="T62"):
    return [(tag, r["formula"], r["formula"], int(r["count"])) for r in rows]


def load_known():
    return {r["formula"] for r in json.load(open(BASE + r"\t4_catalog_index.json",
                                                  encoding="utf-8"))}


def run_phase(phase, minutes, cap=MAX_REACTION_ATOMS, tag="", seeds=None):
    d = load_design()
    known = load_known()
    E.set_fast(True)
    K.set_geometry(ENV_L)
    t_start = time.time()
    seed = seeds or {"A": SEED_A, "B": SEED_B}
    if phase == "A":
        rows = d["batchA"]["rows"]
        env = KineticEnvironment(minutes=minutes, seed=seed["A"],
                                 load_spec=spec_from_rows(rows),
                                 known_formulas=known,
                                 area_model="count", weighted_partner=True,
                                 max_reaction_atoms=cap,
                                 color_mode="bitmask",
                                 event_limit=EVENT_LIMIT, snap_minutes=SNAP_MINUTES)
        res = env.run()
        res["phase"] = "A"
        res["load_summary"] = d["batchA"]["summary"]
        res["config"]["experiment"] = ("T62 phaseA：120 种物质、三/二/一价等量"
                                       "（33.3/33.3/33.3）、L=60000、cap=%d" % cap)
        res["summary"]["runtime_s"] = round(time.time() - t_start, 1)
        json.dump(res, open(BASE + r"\t62_phaseA%s_result.json" % tag, "w",
                            encoding="utf-8"), ensure_ascii=False, indent=1)
        state = env.export_state()
        json.dump(state, open(BASE + r"\t62_stateA%s.json" % tag, "w",
                              encoding="utf-8"), ensure_ascii=False, indent=1)
        print("saved t62_phaseA%s_result.json / t62_stateA%s.json, runtime" % (tag, tag),
              res["summary"]["runtime_s"], "s", flush=True)
        print(json.dumps(res["summary"], ensure_ascii=False, indent=1)[:2000], flush=True)
        return res
    if phase == "B":
        state = json.load(open(BASE + r"\t62_stateA%s.json" % tag, encoding="utf-8"))
        rows = d["batchB"]["rows"]
        print("整理后底物：分子", state["total_molecules"], "原子", state["total_atoms"],
              "结构种数", state["distinct_structures"], flush=True)
        env = KineticEnvironment(minutes=minutes, seed=seed["B"],
                                 seed_particles=state["molecules"],
                                 load_spec=spec_from_rows(rows),
                                 known_formulas=known,
                                 area_model="count", weighted_partner=True,
                                 max_reaction_atoms=cap,
                                 color_mode="bitmask",
                                 event_limit=EVENT_LIMIT, snap_minutes=SNAP_MINUTES)
        res = env.run()
        res["phase"] = "B"
        res["load_summary"] = d["batchB"]["summary"]
        res["seed_state_summary"] = {k: state[k] for k in
                                     ("total_molecules", "total_atoms",
                                      "distinct_formulas", "distinct_structures",
                                      "t", "T")}
        res["config"]["experiment"] = ("T62 phaseB：phaseA 整理后底物 + 120 种等量价数物质、"
                                       "T 重置 1000°C、L=60000、cap=%d" % cap)
        res["summary"]["runtime_s"] = round(time.time() - t_start, 1)
        json.dump(res, open(BASE + r"\t62_phaseB%s_result.json" % tag, "w",
                            encoding="utf-8"), ensure_ascii=False, indent=1)
        stateB = env.export_state()
        json.dump(stateB, open(BASE + r"\t62_stateB%s.json" % tag, "w",
                               encoding="utf-8"), ensure_ascii=False, indent=1)
        print("saved t62_phaseB%s_result.json / t62_stateB%s.json, runtime" % (tag, tag),
              res["summary"]["runtime_s"], "s", flush=True)
        print(json.dumps(res["summary"], ensure_ascii=False, indent=1)[:2000], flush=True)
        return res
    raise ValueError(phase)


def run_control_A(minutes=500):
    d = load_design()
    rows = d["batchA"]["rows"]
    K.set_geometry(ENV_L)
    res = run_control(minutes=minutes, seed=SEED_A,
                      load_spec=spec_from_rows(rows),
                      area_model="count")
    res["config"]["experiment"] = ("T62 batchA 无化学对照：120 种物质、L=60000、"
                                   "面积模型、500 分钟")
    res["config"]["L"] = ENV_L
    json.dump(res, open(BASE + r"\t62_control_A.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t62_control_A.json")
    print(json.dumps(res["stats"], ensure_ascii=False, indent=1), flush=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="both", choices=["A", "B", "both"])
    ap.add_argument("--minutes", type=int, default=MINUTES)
    ap.add_argument("--cap", type=int, default=MAX_REACTION_ATOMS)
    ap.add_argument("--tag", default="")
    ap.add_argument("--control", action="store_true")
    ap.add_argument("--control-minutes", type=int, default=500)
    args = ap.parse_args()
    t0 = time.time()
    if args.control:
        run_control_A(args.control_minutes)
        return
    if args.phase in ("A", "both"):
        run_phase("A", args.minutes, cap=args.cap, tag=args.tag)
    if args.phase in ("B", "both"):
        run_phase("B", args.minutes, cap=args.cap, tag=args.tag)
    print("all done", round(time.time() - t0, 1), "s", flush=True)


if __name__ == "__main__":
    main()
