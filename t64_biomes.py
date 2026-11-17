# -*- coding: utf-8 -*-
"""t64_biomes.py —— T64：生态群系（biomes）构建实验

用户 2026-11-17 要求：
  在特定的空间里，只让"特定几个元素"组成的物质存在（≥3 种元素、至少含一种三价元素、
  ≤9 种元素），先 1000°C 高温退火到一个恒定的中间温度，然后温度在该中间值附近上下浮动
  （像现实世界一样），形成较稳定的物质群落（生态群系）。至少构建 10 个群系并找出有特色的
  详细分析。

设计（用户未指定、自行调节）：
* 12 个群系，元素集合覆盖 9 元素的不同子集（全部含 O/P/K 至少一种三价元素）：
  3 元素纯族（聚/动/散 各一族）、4~6 元素混合、9 元素全生态、无氧双骨架等；
* 每个群系只投入该元素集合的**双原子单质**（O2/X2/C2/P2/W2/L2/K2/A2/F2），
  各元素原子数相等（3000~4000 个原子/元素）——保证"只有这些元素"且配方中性；
* 空间边长 L 按"原子密度 ≈ 4.2e-5 原子/面积"反推（15000~20000），对应不同大小的
  生态空间，但碰撞充分性一致；
* 温度日程（所有群系相同参数）：
    0 ~ 975 分钟：1000 → 25°C 线性退火（1°C/分钟，与 T55/T57/T59/T63 一致）；
    975 ~ 1575 分钟：恒温 25°C + 上下浮动（+8°C 日周期/240 分钟 + 3°C 季节周期/900 分钟，
                                  相位固定），真实范围约 14~36°C；
* 面积模型 A∝原子数、cap=40、事件蓄水池 30000（同 T57/T63）；
* 每个群系一种子（20261127 + 序号）；B01 另跑 500 分钟无化学对照。

输出：
  t64_biomes.json                全部群系设计（元素/投料/L/温度日程/种子）
  t64_biome_{id}_result.json     每个群系的完整结果（时间序列/组成/快照/事件）
  t64_biome_{id}_state.json      每个群系终态归档（按结构聚合，供后续分析/摆放）
  t64_biome_index.json           结果文件索引 + 每个群系一行摘要
  t64_control_B01.json           B01 无化学对照

用法：
  python t64_biomes.py --list
  python t64_biomes.py --biome B01
  python t64_biomes.py --all
  python t64_biomes.py --control
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

SEED = 20261127
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
    dict(id="B01", name="聚素平原", elements=["O", "X", "C"],
         atoms_per_element=4000, L=17000,
         tag="对照组 / 经典聚素三元素"),
    dict(id="B02", name="动素沼泽", elements=["P", "W", "L"],
         atoms_per_element=4000, L=17000,
         tag="纯动素三元素（P 三价 + W 二价 + L 一价）"),
    dict(id="B03", name="散素荒原", elements=["K", "A", "F"],
         atoms_per_element=4000, L=17000,
         tag="纯散素三元素（K 三价 + A 二价 + F 一价）"),
    dict(id="B04", name="氧晶气焰溪谷", elements=["O", "X", "A", "F"],
         atoms_per_element=3500, L=18000,
         tag="混乱四元素（含 F 端帽）"),
    dict(id="B05", name="双骨架丘陵", elements=["O", "P", "X"],
         atoms_per_element=4000, L=17000,
         tag="双三价（O+P）+ 二价 X"),
    dict(id="B06", name="秩沌冰火山", elements=["O", "K", "C"],
         atoms_per_element=4000, L=17000,
         tag="双三价（O+K）+ 一价 C"),
    dict(id="B07", name="聚动混合林", elements=["O", "X", "C", "P"],
         atoms_per_element=3500, L=18000,
         tag="聚素三元素 + 动素 P"),
    dict(id="B08", name="三骨架湖", elements=["O", "P", "K", "X", "W"],
         atoms_per_element=3000, L=19000,
         tag="三种三价元素齐全 + 二价 X/W"),
    dict(id="B09", name="六元雨林", elements=["O", "X", "C", "P", "W", "L"],
         atoms_per_element=2500, L=19000,
         tag="聚素全 + 动素全，无散素"),
    dict(id="B10", name="双族海岸", elements=["O", "X", "C", "K", "A", "F"],
         atoms_per_element=2500, L=19000,
         tag="聚素全 + 散素全，无动素"),
    dict(id="B11", name="九元素大生态", elements=["O", "X", "C", "P", "W", "L", "K", "A", "F"],
         atoms_per_element=2000, L=20000,
         tag="九元素全（完整生态）"),
    dict(id="B12", name="无氧双骨架地热泉", elements=["P", "K", "A", "L"],
         atoms_per_element=3500, L=18000,
         tag="无氧（P+K 三价 + A 二价 + L 一价）"),
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
        "model": "t64_biome",
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
        "experiment": "T64 生态群系（12 群系 × 退火 + 恒温浮动）",
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
        "T64 %s %s：元素 %s，L=%d，每元素 %d 原子；1000→25°C 退火 %d 分钟 + "
        "25°C 浮动 %d 分钟（±8°C 日周期 + ±3°C 季节周期）"
        % (b["id"], b["name"], "+".join(b["elements"]), b["L"],
           b["atoms_per_element"], ANNEAL_MINUTES, HOLD_MINUTES))
    res["biome"]["seed"] = seed
    res["summary"]["runtime_s"] = round(time.time() - t_start, 1)
    res["summary"]["biome_id"] = b["id"]
    res["summary"]["biome_name"] = b["name"]
    json.dump(res, open(BASE + r"\t64_biome_%s_result.json" % b["id"], "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)
    state = env.export_state()
    state["biome_id"] = b["id"]
    json.dump(state, open(BASE + r"\t64_biome_%s_state.json" % b["id"], "w",
                          encoding="utf-8"), ensure_ascii=False, indent=1)
    print("[%s] %s  saved t64_biome_%s_result.json / _state.json  runtime %ss"
          % (b["id"], b["name"], b["id"], res["summary"]["runtime_s"]), flush=True)
    print(json.dumps(res["summary"], ensure_ascii=False, indent=1)[:1200], flush=True)
    return res


def run_control_b01(minutes=500):
    b = BIOME_BY_ID["B01"]
    spec = load_spec(b)
    K.set_geometry(b["L"])
    res = run_control(minutes=minutes, seed=SEED, load_spec=spec,
                      area_model="count")
    res["biome"] = {"id": b["id"], "name": b["name"], "L": b["L"],
                    "elements": list(b["elements"])}
    res["config"]["experiment"] = ("T64 B01 无化学对照：O/X/C 双原子单质、"
                                   "L=%d、%d 分钟" % (b["L"], minutes))
    json.dump(res, open(BASE + r"\t64_control_B01.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t64_control_B01.json", flush=True)
    print(json.dumps(res["stats"], ensure_ascii=False, indent=1)[:800], flush=True)
    return res


def update_index():
    rows = []
    for b in BIOMES:
        p = BASE + r"\t64_biome_%s_result.json" % b["id"]
        try:
            r = json.load(open(p, encoding="utf-8"))
        except FileNotFoundError:
            rows.append({"id": b["id"], "status": "pending"})
            continue
        rows.append({
            "id": b["id"], "name": b["name"], "status": "done",
            "file": "t64_biome_%s_result.json" % b["id"],
            "elements": r["biome"]["elements"], "L": r["biome"]["L"],
            "total_atoms": r["biome"]["total_atoms"],
            "runtime_s": r["summary"]["runtime_s"],
            "final_N": r["summary"]["final_N"],
            "final_atoms": r["summary"]["final_atoms"],
            "final_T": r["summary"]["final_T"],
            "reaction_counts": r["summary"]["reaction_counts"],
        })
    idx = {"experiment": "T64 生态群系", "schedule": schedule_info(),
           "biomes": rows}
    json.dump(idx, open(BASE + r"\t64_biome_index.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t64_biome_index.json", flush=True)
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--biome", default=None, help="群系 id，如 B01")
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
        run_control_b01()
        return
    if args.biome:
        run_biome(BIOME_BY_ID[args.biome], args.minutes)
        update_index()
        return
    design = build_design()
    json.dump(design, open(BASE + r"\t64_biomes.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t64_biomes.json：%d 群系" % len(BIOMES), flush=True)
    t0 = time.time()
    for b in BIOMES:
        run_biome(b, args.minutes)
        update_index()
    print("all done", round(time.time() - t0, 1), "s", flush=True)


if __name__ == "__main__":
    main()
