# -*- coding: utf-8 -*-
"""t65_biomes.py —— T65：生态群系构建实验（第二轮：每群系 ≥4 种元素）

用户 2026-11-17 要求（第二轮）：
  "再次进行十组生态群系实验，这次至少要用四种元素。不需要再严格摆放大分子了。"
  即沿用 T64 的群系定义与温度日程，但每个群系元素数 ≥4（仍 3 种三价元素之一，≤9 种），
  重做 10 个群系并分析特色；本轮不做大分子六边形严格摆放。

设计（用户未指定、自行调节）：
* 10 个群系（C01~C10），元素数覆盖 4/5/6/7/8/9，全部含 O/P/K 至少一种三价元素：
  4 元素×4（双骨架/散素配位/动素配位/散素晶原）、5 元素×2、6 元素×1、7 元素×1、
  8 元素×1（九元素缺 F）、9 元素×1（与 T64 B11 同条件复现，检验可重复性）；
* 每个群系只投入该元素集合的**双原子单质**（O2/X2/C2/P2/W2/L2/K2/A2/F2），
  各元素原子数相等（2000~3500 个原子/元素）——保证"只有这些元素"且配方中性；
* 空间边长 L 按"原子密度 ≈4.2e-5 原子/面积"反推（18000~20000）；
* 温度日程与 T64 完全一致（便于跨轮对比）：
    0 ~ 975 分钟：1000 → 25°C 线性退火（1°C/分钟）；
    975 ~ 1575 分钟：恒温 25°C + 上下浮动（±8°C 日周期/240 分钟、±3°C 季节周期/900 分钟，
                              相位固定），真实范围约 14~36°C；
* 面积模型 A∝原子数、cap=40、事件蓄水池 30000（同 T57/T63/T64）；
* 每个群系一种子（20261128 + 序号）；C01 另跑 500 分钟无化学对照。

输出：
  t65_biomes.json                全部群系设计（元素/投料/L/温度日程/种子）
  t65_biome_{id}_result.json     每个群系的完整结果（时间序列/组成/快照/事件）
  t65_biome_{id}_state.json      每个群系终态归档（按结构聚合，供后续分析）
  t65_biome_index.json           结果文件索引 + 每个群系一行摘要
  t65_control_C01.json           C01 无化学对照

用法：
  python t65_biomes.py --list
  python t65_biomes.py --biome C01
  python t65_biomes.py --all
  python t65_biomes.py --control
"""
import argparse
import json
import math
import sys
import time

BASE = r"G:\AI work\deepseek\work1\alchemy"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import natural_engine as E  # noqa: E402
import t55_kinetic_env as K  # noqa: E402
from t55_kinetic_env import KineticEnvironment, run_control  # noqa: E402

SEED = 20261128
CAP = 40
EVENT_LIMIT = 30000

# ---------------------------------------------------------------- 温度日程
T0 = 1000.0
T_MID = 25.0
ANNEAL_MINUTES = 975          # 1000 -> 25°C，1°C/分钟
HOLD_MINUTES = 600            # 恒温 25°C 上下浮动
MINUTES = ANNEAL_MINUTES + HOLD_MINUTES
AMP_DAY, PERIOD_DAY = 8.0, 240.0        # 日周期浮动
AMP_YEAR, PERIOD_YEAR = 3.0, 900.0      # 季节周期浮动
PHASE_YEAR = 0.7

SNAP_MINUTES = [0, 25, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900,
                950, 975, 1000, 1050, 1100, 1150, 1200, 1300, 1400, 1500,
                1560, 1570, 1574]

# ---------------------------------------------------------------- 群系定义
# atoms_per_element：每个元素投入的原子数（双原子单质 => 分子数 = 该值/2）
# L：空间边长；按密度 ≈4.2e-5 原子/面积 选定（与 T63 阶段 1 同量级）
BIOMES = [
    dict(id="C01", name="双骨架平原", elements=["O", "P", "X", "W"],
         atoms_per_element=3500, L=18000,
         tag="两种三价（O/P）+ 两种二价（X/W），无低价端帽"),
    dict(id="C02", name="散素配位谷", elements=["O", "K", "C", "L"],
         atoms_per_element=3500, L=18000,
         tag="两种三价（O/K）+ 两种一价（C/L），无二价"),
    dict(id="C03", name="动素配位台地", elements=["P", "X", "A", "L"],
         atoms_per_element=3500, L=18000,
         tag="三价 P + 二价 X/A + 一价 L（无 O，P 主导）"),
    dict(id="C04", name="散素晶原", elements=["K", "A", "F", "X"],
         atoms_per_element=3500, L=18000,
         tag="K 三价 + 二价 A/X + 一价 F（KAF 与 X 竞争）"),
    dict(id="C05", name="聚动五元林", elements=["O", "X", "C", "P", "W"],
         atoms_per_element=3000, L=19000,
         tag="聚素全 + 动素 P/W（无 L/A；B09 缺端帽）"),
    dict(id="C06", name="三骨架麓", elements=["O", "P", "K", "X", "A"],
         atoms_per_element=3000, L=19000,
         tag="三种三价齐全 + 两种二价（无低价端帽，检验大簇）"),
    dict(id="C07", name="聚动散混合坡", elements=["O", "X", "C", "P", "K", "A"],
         atoms_per_element=2500, L=19000,
         tag="B10 的 F→P 替换（一价端帽换成第三骨架）"),
    dict(id="C08", name="七元雨林带", elements=["O", "X", "C", "P", "W", "L", "K"],
         atoms_per_element=2400, L=20000,
         tag="B09 六元雨林 + K（多骨架、无散素 A/F）"),
    dict(id="C09", name="缺焰八元生态", elements=["O", "X", "C", "P", "W", "L", "K", "A"],
         atoms_per_element=2100, L=20000,
         tag="九元素缺 F（检验一价端帽 F 的作用）"),
    dict(id="C10", name="九元大生态复现", elements=["O", "X", "C", "P", "W", "L", "K", "A", "F"],
         atoms_per_element=2000, L=20000,
         tag="与 T64 B11 同条件复现（检验可重复性）"),
]

BIOME_BY_ID = {b["id"]: b for b in BIOMES}


def biome_atoms(b):
    return len(b["elements"]) * b["atoms_per_element"]


def temp_profile(t):
    """温度日程：ANNEAL 段线性 1000->T_MID，HOLD 段在 T_MID 附近上下浮动。"""
    if t < ANNEAL_MINUTES:
        return T0 + (T_MID - T0) * (t / float(ANNEAL_MINUTES))
    tt = t - ANNEAL_MINUTES
    return (T_MID
            + AMP_DAY * math.sin(2.0 * math.pi * tt / PERIOD_DAY)
            + AMP_YEAR * math.sin(2.0 * math.pi * tt / PERIOD_YEAR + PHASE_YEAR))


def schedule_info():
    return {
        "model": "t65_biome",
        "T0": T0, "T_mid": T_MID,
        "anneal_minutes": ANNEAL_MINUTES, "hold_minutes": HOLD_MINUTES,
        "anneal_rate_c_per_min": round((T0 - T_MID) / ANNEAL_MINUTES, 4),
        "minutes": MINUTES,
        "day_amp": AMP_DAY, "day_period": PERIOD_DAY,
        "year_amp": AMP_YEAR, "year_period": PERIOD_YEAR, "year_phase": PHASE_YEAR,
        "hold_T_min": round(T_MID - AMP_DAY - AMP_YEAR, 2),
        "hold_T_max": round(T_MID + AMP_DAY + AMP_YEAR, 2),
    }


def build_schedule():
    def sched(t):
        return temp_profile(t)
    sched.info = schedule_info()
    return sched


def load_spec(b):
    """每元素只投双原子单质；原子数 = atoms_per_element。"""
    spec = []
    for e in b["elements"]:
        molecules = b["atoms_per_element"] // 2
        spec.append(("群系底物", "%s单质" % e, e + "2", int(molecules)))
    return spec


def load_known():
    known = {r["formula"] for r in
             json.load(open(BASE + r"\t4_catalog_index.json", encoding="utf-8"))}
    known |= {r["formula"] for r in
              json.load(open(BASE + r"\substances.json", encoding="utf-8"))}
    known |= {e + "2" for e in "OXCPWLKAF"}
    return known


def build_design():
    rows = []
    for b in BIOMES:
        spec = load_spec(b)
        rows.append({
            "id": b["id"], "name": b["name"], "tag": b["tag"],
            "elements": list(b["elements"]), "n_elements": len(b["elements"]),
            "trivalent": [e for e in b["elements"] if e in ("O", "P", "K")],
            "L": b["L"], "atoms_per_element": b["atoms_per_element"],
            "total_atoms": biome_atoms(b),
            "total_molecules": sum(int(s[3]) for s in spec),
            "load_spec": [{"desc": d, "formula": f, "count": int(c)} for _t, d, f, c in spec],
            "density_atoms_per_area": round(biome_atoms(b) / (b["L"] ** 2), 8),
        })
    return {
        "experiment": "T65 生态群系（10 群系 × 退火 + 恒温浮动，每群系 ≥4 元素）",
        "seed_base": SEED,
        "schedule": schedule_info(),
        "cap": CAP, "event_limit": EVENT_LIMIT,
        "area_model": "count（A∝原子数，同 T57/T63）",
        "snap_minutes": SNAP_MINUTES,
        "biomes": rows,
    }


def run_biome(b, design_minutes=MINUTES):
    idx = BIOMES.index(b)
    seed = SEED + idx
    spec = load_spec(b)
    known = load_known()
    E.set_fast(True)
    K.set_geometry(b["L"])
    sched = build_schedule()
    t_start = time.time()
    env = KineticEnvironment(
        minutes=design_minutes, seed=seed, load_spec=spec,
        known_formulas=known, area_model="count", weighted_partner=True,
        max_reaction_atoms=CAP, color_mode="bitmask",
        event_limit=EVENT_LIMIT, snap_minutes=SNAP_MINUTES,
        t0=T0, temp_schedule=sched)
    res = env.run()
    res["biome"] = {"id": b["id"], "name": b["name"], "tag": b["tag"],
                    "elements": list(b["elements"]),
                    "L": b["L"], "atoms_per_element": b["atoms_per_element"],
                    "total_atoms": biome_atoms(b),
                    "schedule": schedule_info()}
    res["config"]["experiment"] = (
        "T65 %s %s：元素 %s，L=%d，每元素 %d 原子；1000→25°C 退火 %d 分钟 + "
        "25°C 浮动 %d 分钟（±8°C 日周期 + ±3°C 季节周期）"
        % (b["id"], b["name"], "+".join(b["elements"]), b["L"],
           b["atoms_per_element"], ANNEAL_MINUTES, HOLD_MINUTES))
    res["biome"]["seed"] = seed
    res["summary"]["runtime_s"] = round(time.time() - t_start, 1)
    res["summary"]["biome_id"] = b["id"]
    res["summary"]["biome_name"] = b["name"]
    json.dump(res, open(BASE + r"\t65_biome_%s_result.json" % b["id"], "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)
    state = env.export_state()
    state["biome_id"] = b["id"]
    json.dump(state, open(BASE + r"\t65_biome_%s_state.json" % b["id"], "w",
                          encoding="utf-8"), ensure_ascii=False, indent=1)
    print("[%s] %s  saved t65_biome_%s_result.json / _state.json  runtime %ss"
          % (b["id"], b["name"], b["id"], res["summary"]["runtime_s"]), flush=True)
    print(json.dumps(res["summary"], ensure_ascii=False, indent=1)[:1200], flush=True)
    return res


def run_control_c01(minutes=500):
    b = BIOME_BY_ID["C01"]
    spec = load_spec(b)
    K.set_geometry(b["L"])
    res = run_control(minutes=minutes, seed=SEED, load_spec=spec,
                      area_model="count")
    res["biome"] = {"id": b["id"], "name": b["name"], "L": b["L"],
                    "elements": list(b["elements"])}
    res["config"]["experiment"] = ("T65 C01 无化学对照：O/P/X/W 双原子单质、"
                                   "L=%d、%d 分钟" % (b["L"], minutes))
    json.dump(res, open(BASE + r"\t65_control_C01.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t65_control_C01.json", flush=True)
    print(json.dumps(res["stats"], ensure_ascii=False, indent=1)[:800], flush=True)
    return res


def update_index():
    rows = []
    for b in BIOMES:
        p = BASE + r"\t65_biome_%s_result.json" % b["id"]
        try:
            r = json.load(open(p, encoding="utf-8"))
        except FileNotFoundError:
            rows.append({"id": b["id"], "status": "pending"})
            continue
        rows.append({
            "id": b["id"], "name": b["name"], "status": "done",
            "file": "t65_biome_%s_result.json" % b["id"],
            "elements": r["biome"]["elements"], "L": r["biome"]["L"],
            "total_atoms": r["biome"]["total_atoms"],
            "runtime_s": r["summary"]["runtime_s"],
            "final_N": r["summary"]["final_N"],
            "final_atoms": r["summary"]["final_atoms"],
            "final_T": r["summary"]["final_T"],
            "reaction_counts": r["summary"]["reaction_counts"],
        })
    idx = {"experiment": "T65 生态群系", "schedule": schedule_info(),
           "biomes": rows}
    json.dump(idx, open(BASE + r"\t65_biome_index.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t65_biome_index.json", flush=True)
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--biome", default=None, help="群系 id，如 C01")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--control", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--minutes", type=int, default=MINUTES)
    args = ap.parse_args()
    if args.list:
        for b in BIOMES:
            print("%s  %-8s  %-2d 元素 %-30s L=%-6d 原子=%45d  %s" % (
                b["id"], b["name"], len(b["elements"]), "+".join(b["elements"]),
                b["L"], biome_atoms(b), b["tag"]))
        return
    if args.control:
        run_control_c01()
        return
    if args.biome:
        run_biome(BIOME_BY_ID[args.biome], args.minutes)
        update_index()
        return
    design = build_design()
    json.dump(design, open(BASE + r"\t65_biomes.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t65_biomes.json：%d 群系" % len(BIOMES), flush=True)
    t0 = time.time()
    for b in BIOMES:
        run_biome(b, args.minutes)
        update_index()
    print("all done", round(time.time() - t0, 1), "s", flush=True)


if __name__ == "__main__":
    main()
