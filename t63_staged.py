# -*- coding: utf-8 -*-
"""t63_staged.py —— T63：聚素退火 + 三次单质投放（焰 F2 → 气 A2 → 沌 K2）

用户 2026-11-17 要求：
1. **先只用聚素物质**（O/X/C 三类，全部 29 种纯聚素，沿用 T57 投料/面积/数量模型）；
2. **第一次退火之后加入大量的焰单质（焰-焰，F2）**，做第二次反应实验；
3. **退火后加入大量的气单质（气-气，A2）**，做第三次反应实验；
4. **退火后加入大量的沌单质（沌-沌，K2）**，做第四次反应实验。

即：连续四次"升温→1000→0°C 退火"，每次退火到 0°C 后投放下一种价数的单质：
一价 F（端帽）→ 二价 A（桥）→ 三价 K（骨架），观察聚素熔体被逐级"价数滴定"的过程。

设计选择（用户未指定、自行调节）：
* 环境 L=30000（T57 是 10000、T59 是 60000；取中间值，使 4 阶段原子密度/碰撞率
  与 T59 同一量级，既保证退火充分又控制计算量）；
* 第一批：全部 29 种纯聚素，9002 分子 / 38,532 原子（T57 同款）；
* 每次投放：8000 个双原子单质 = 16,000 个原子（F2 / A2 / K2），约占初始原子数的 42%、
  与初始单元素原子量（O/X/C 各约 1.2~1.4 万）同量级，属于"大量"；
* 每阶段 1000 分钟、1000→0°C；阶段间在新环境中重新均匀分布 + 复热（等价 T59 的"整理"）；
* cap=40（同 T59/T62）；面积模型（A∝原子数）与 0.2%/碰撞衰减沿用 T57；
* 无化学对照：第一批 500 分钟（t63_control_s1.json）。

输出：
  t63_loads.json           投料/投放设计
  t63_phase{1..4}_result.json  四阶段完整结果
  t63_state{1..4}.json     各阶段 0°C 终态归档（供下一阶段/分析）
  t63_control_s1.json      第一批无化学对照

用法：
  python t63_staged.py --phase 1        # 只跑第一阶段
  python t63_staged.py --phase all      # 四阶段连续（默认）
  python t63_staged.py --control        # 第一批无化学对照
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
import t57_all29_area as T57
from t55_kinetic_env import KineticEnvironment, run_control

SEED = 20261126
ENV_L = 30000.0
MINUTES = 1000
MAX_REACTION_ATOMS = 40
EVENT_LIMIT = 30000
SNAP_MINUTES = [0, 2, 5, 10, 25, 50, 100, 200, 300, 400,
                500, 600, 700, 800, 900, 950, 980, 995, 1000]
# 三次投放：(中文名, 分子式, 分子数)；每个双原子单质 = 2 个原子
ADDITIONS = [
    {"stage": 2, "element": "F", "name": "焰单质", "formula": "F2",
     "molecules": 8000, "atoms": 16000},
    {"stage": 3, "element": "A", "name": "气单质", "formula": "A2",
     "molecules": 8000, "atoms": 16000},
    {"stage": 4, "element": "K", "name": "沌单质", "formula": "K2",
     "molecules": 8000, "atoms": 16000},
]


def load_known():
    """已知分子式 = 84,225 目录 + 29 聚素 + F2/A2/K2（用于统计目录外新物质）。"""
    known = {r["formula"] for r in
             json.load(open(BASE + r"\t4_catalog_index.json", encoding="utf-8"))}
    known |= {r["formula"] for r in
              json.load(open(BASE + r"\substances.json", encoding="utf-8"))}
    known |= {"F2", "A2", "K2"}
    return known


def build_design():
    load_spec, rows, meta = T57.build_load_spec()
    design = {
        "experiment": "T63 聚素退火 + F2/A2/K2 三次单质投放",
        "seed": SEED, "L": ENV_L, "minutes": MINUTES,
        "max_reaction_atoms": MAX_REACTION_ATOMS,
        "area_model": "A = π·R0²·(n/2)，R0=0.2（同 T57）",
        "stage1": {"name": "全部 29 种纯聚素（O/X/C）", "load_spec": load_spec,
                   "species": rows, "meta": meta},
        "additions": ADDITIONS,
        "stage_design": [
            {"stage": 1, "add": None, "initial_molecules": meta["total_molecules"],
             "initial_atoms": meta["total_atoms"]},
            {"stage": 2, "add": ADDITIONS[0]},
            {"stage": 3, "add": ADDITIONS[1]},
            {"stage": 4, "add": ADDITIONS[2]},
        ],
    }
    return design


def spec_from_rows(rows):
    return [("29聚素", "%s(%d原子)" % (r["formula"], r["atoms"]),
             r["formula"], int(r["count"])) for r in rows]


def add_spec(add):
    """把双原子单质转成 load_spec（tag/desc/formula/count）。"""
    return [("添加%s" % add["name"], add["name"], add["formula"],
             int(add["molecules"]))]


def run_phase(stage, design=None, minutes=MINUTES, cap=MAX_REACTION_ATOMS):
    design = design or build_design()
    known = load_known()
    E.set_fast(True)
    K.set_geometry(ENV_L)
    t_start = time.time()
    if stage == 1:
        load_spec = spec_from_rows(design["stage1"]["species"])
        seed_particles = None
        description = "T63 stage1：全部 29 种纯聚素（9002 分子/38532 原子）、L=30000、cap=%d" % cap
    else:
        add = ADDITIONS[stage - 2]
        prev_state = json.load(open(BASE + r"\t63_state%d.json" % (stage - 1),
                                    encoding="utf-8"))
        seed_particles = prev_state["molecules"]
        load_spec = add_spec(add)
        description = ("T63 stage%d：stage%d 整理底物 + %s %s（%d 分子/%d 原子）、"
                       "重置 1000°C、L=30000、cap=%d"
                       % (stage, stage - 1, add["name"], add["formula"],
                          add["molecules"], add["atoms"], cap))
        print("整理后底物：分子 %d 原子 %d 结构 %d" %
              (prev_state["total_molecules"], prev_state["total_atoms"],
               prev_state["distinct_structures"]), flush=True)
    env = KineticEnvironment(minutes=minutes, seed=SEED + stage, load_spec=load_spec,
                             seed_particles=seed_particles,
                             known_formulas=known,
                             area_model="count", weighted_partner=True,
                             max_reaction_atoms=cap,
                             color_mode="bitmask",
                             event_limit=EVENT_LIMIT, snap_minutes=SNAP_MINUTES)
    res = env.run()
    res["stage"] = stage
    if stage == 1:
        res["load_summary"] = design["stage1"]["meta"]
    else:
        res["load_summary"] = {k: v for k, v in ADDITIONS[stage - 2].items()}
    res["config"]["experiment"] = description
    res["config"]["L"] = ENV_L
    res["summary"]["runtime_s"] = round(time.time() - t_start, 1)
    json.dump(res, open(BASE + r"\t63_phase%d_result.json" % stage, "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)
    state = env.export_state()
    json.dump(state, open(BASE + r"\t63_state%d.json" % stage, "w",
                          encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved t63_phase%d_result.json / t63_state%d.json, runtime %s s"
          % (stage, stage, res["summary"]["runtime_s"]), flush=True)
    print(json.dumps(res["summary"], ensure_ascii=False, indent=1)[:1500], flush=True)
    return res


def run_control_s1(minutes=500):
    design = build_design()
    K.set_geometry(ENV_L)
    load_spec = spec_from_rows(design["stage1"]["species"])
    res = run_control(minutes=minutes, seed=SEED, load_spec=load_spec,
                      area_model="count")
    res["config"]["experiment"] = ("T63 stage1 无化学对照：29 种纯聚素、L=30000、"
                                   "面积模型、%d 分钟" % minutes)
    res["config"]["L"] = ENV_L
    json.dump(res, open(BASE + r"\t63_control_s1.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t63_control_s1.json")
    print(json.dumps(res["stats"], ensure_ascii=False, indent=1), flush=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="all",
                    choices=["1", "2", "3", "4", "all"])
    ap.add_argument("--minutes", type=int, default=MINUTES)
    ap.add_argument("--cap", type=int, default=MAX_REACTION_ATOMS)
    ap.add_argument("--control", action="store_true")
    ap.add_argument("--control-minutes", type=int, default=500)
    args = ap.parse_args()
    if args.control:
        run_control_s1(args.control_minutes)
        return
    design = build_design()
    json.dump(design, open(BASE + r"\t63_loads.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t63_loads.json：stage1 %d 种 / %d 分子 / %d 原子；每次投放 %d 分子/%d 原子"
          % (design["stage1"]["meta"]["n_species"],
             design["stage1"]["meta"]["total_molecules"],
             design["stage1"]["meta"]["total_atoms"],
             ADDITIONS[0]["molecules"], ADDITIONS[0]["atoms"]), flush=True)
    t0 = time.time()
    stages = [1, 2, 3, 4] if args.phase == "all" else [int(args.phase)]
    for stage in stages:
        run_phase(stage, design=design, minutes=args.minutes, cap=args.cap)
    print("all done", round(time.time() - t0, 1), "s", flush=True)


if __name__ == "__main__":
    main()
