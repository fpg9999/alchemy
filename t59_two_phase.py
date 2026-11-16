# -*- coding: utf-8 -*-
"""t59_two_phase.py —— T59：九元素两阶段连续实验（100+ 种物质，三价最多/一价最少）

实验流程（用户指定）：
1. **第一阶段**：投入 ≥100 种物质（batchA，120 种），三价元素含量最多、一价最少；
   环境 L=60000（比 T58 的 400000 缩小 44 倍面积），初速按 500 次穿越设计；
   温度 1000→0°C，运行 1000 分钟（完全反应 + 不完全反应 + 自分解，T35 规则）。
2. **整理**：第一阶段到达 0°C 后，清点归档全部物质（不丢弃任何物质），
   记录组成/结构；随后把全部物质作为第二阶段"底物"重新装入环境（随机位置、重置速度）。
3. **第二阶段**：再投入一次随机大量物质（batchB，120 种），温度重新设为 1000°C，
   再连续运行 1000 分钟到 0°C。
4. 保存两阶段完整结果，供对比分析。

算法：`natural_engine.set_fast(True)` —— 完全/不完全反应的贪心重结合使用 `fast_pot`
（与 pot_v4 规则 1~11 等价，已全量自检）。`max_reaction_atoms=40`：允许 ≤40 原子大分子反应
（比 T56 最大 36 原子还大；仅作为 F 成本上限，超出部分弹性碰撞）。

用法：
  python t59_two_phase.py --phase A      # 只跑第一阶段
  python t59_two_phase.py --phase B      # 从 t59_stateA.json 跑第二阶段
  python t59_two_phase.py --phase both   # 两阶段连续跑
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
from t55_kinetic_env import KineticEnvironment

SEED_A = 20261122
SEED_B = 20261123
ENV_L = 60000.0
MAX_REACTION_ATOMS = 40
MINUTES = 1000
SNAP_MINUTES = [0, 2, 5, 10, 25, 50, 100, 200, 300, 400,
                500, 600, 700, 800, 900, 950, 980, 995, 1000]
EVENT_LIMIT = 50000


def load_design():
    d = json.load(open(BASE + r"\t59_loads.json", encoding="utf-8"))
    return d


def spec_from_rows(rows):
    return [("T59", r["formula"], r["formula"], int(r["count"])) for r in rows]


def run_phase(phase, minutes, cap=MAX_REACTION_ATOMS, tag=""):
    d = load_design()
    known = {r["formula"] for r in json.load(open(BASE + r"\t4_catalog_index.json",
                                                  encoding="utf-8"))}
    E.set_fast(True)
    K.set_geometry(ENV_L)
    t_start = time.time()
    if phase == "A":
        rows = d["batchA"]["rows"]
        env = KineticEnvironment(minutes=minutes, seed=SEED_A,
                                 load_spec=spec_from_rows(rows),
                                 known_formulas=known,
                                 area_model="count", weighted_partner=True,
                                 max_reaction_atoms=cap,
                                 color_mode="bitmask",
                                 event_limit=EVENT_LIMIT, snap_minutes=SNAP_MINUTES)
        res = env.run()
        res["phase"] = "A"
        res["load_summary"] = d["batchA"]["summary"]
        res["config"]["experiment"] = "T59 phaseA：120 种物质、三价最多/一价最少、L=60000、cap=%d" % cap
        res["summary"]["runtime_s"] = round(time.time() - t_start, 1)
        json.dump(res, open(BASE + r"\t59_phaseA%s_result.json" % tag, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        state = env.export_state()
        json.dump(state, open(BASE + r"\t59_stateA%s.json" % tag, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("saved t59_phaseA%s_result.json / t59_stateA%s.json, runtime" % (tag, tag),
              res["summary"]["runtime_s"], "s")
        print(json.dumps(res["summary"], ensure_ascii=False, indent=1)[:2000])
        return res
    if phase == "B":
        state = json.load(open(BASE + r"\t59_stateA%s.json" % tag, encoding="utf-8"))
        rows = d["batchB"]["rows"]
        print("整理后底物：分子", state["total_molecules"], "原子", state["total_atoms"],
              "结构种数", state["distinct_structures"])
        env = KineticEnvironment(minutes=minutes, seed=SEED_B,
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
                                      "distinct_formulas", "distinct_structures", "t", "T")}
        res["config"]["experiment"] = ("T59 phaseB：phaseA 整理后底物 + 120 种随机物质、"
                                       "T 重置 1000°C、L=60000、cap=%d" % cap)
        res["summary"]["runtime_s"] = round(time.time() - t_start, 1)
        json.dump(res, open(BASE + r"\t59_phaseB%s_result.json" % tag, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        stateB = env.export_state()
        json.dump(stateB, open(BASE + r"\t59_stateB%s.json" % tag, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("saved t59_phaseB%s_result.json / t59_stateB%s.json, runtime" % (tag, tag),
              res["summary"]["runtime_s"], "s")
        print(json.dumps(res["summary"], ensure_ascii=False, indent=1)[:2000])
        return res
    raise ValueError(phase)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="both", choices=["A", "B", "both"])
    ap.add_argument("--minutes", type=int, default=MINUTES)
    ap.add_argument("--cap", type=int, default=MAX_REACTION_ATOMS)
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    t0 = time.time()
    if args.phase in ("A", "both"):
        run_phase("A", args.minutes, cap=args.cap, tag=args.tag)
    if args.phase in ("B", "both"):
        run_phase("B", args.minutes, cap=args.cap, tag=args.tag)
    print("all done", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
