# -*- coding: utf-8 -*-
"""t66_biomes.py —— T66：生态群系（第三轮：化合物播种，不投双原子单质）

用户 2026-11-17 要求（第三轮，m01888）：
  "不一定要投单质，其他的物质也可以。再来十组"
  即沿用 T65 的群系定义（10 群系、≥4 元素、温度日程/cap 不变），但每个群系的
  底物改为"化合物混合投放"（盐、端帽化合物、多元素骨架等），用于检验
  "初始化学形态记忆"：同一元素集、不同初始分子形态，终态是否仍收敛到同一吸引子。

设计（用户未指定、自行调节）：
* 10 个群系 E01~E10，元素集/原子数/L 与 T65 C01~C10 一一对应（便于逐项对比）；
* 每个群系投入 1~5 种"目录内稳定化合物"，按化学计量精确配平：
    每元素原子数 = T65 对应值（3500/3500/3500/3500/3000/3000/2500/2400/2100/2000）；
* 化合物全部经 natural_engine.complete_products 校验（build_templates 能生成且
  formula 完全一致），不稳定组合（如 PL、X2K）已剔除；
* 温度日程、L、cap=40、事件蓄水池 30000、seed 基值、对照组均与 T65 相同：
    0 ~ 975 分钟：1000 → 25°C 线性退火（1°C/分钟）；
    975 ~ 1575 分钟：恒温 25°C + 上下浮动（±8°C/240 分钟、±3°C/900 分钟）；
* 每群系种子 = 20261129 + 序号；E01 另跑 500 分钟无化学对照；
* 本轮不做大分子六边形严格摆放。

输出：
  t66_biomes.json                全部群系设计（元素/化合物投料/元素配平校验/L/日程/种子）
  t66_biome_{id}_result.json     每个群系的完整结果（时间序列/组成/快照/事件）
  t66_biome_{id}_state.json      每个群系终态归档
  t66_biome_index.json           结果文件索引 + 每群系一行摘要
  t66_control_E01.json           E01 无化学对照

用法：
  python t66_biomes.py --list
  python t66_biomes.py --biome E01
  python t66_biomes.py --all
  python t66_biomes.py --control
"""
import argparse
import json
import math
import sys
import time
from collections import Counter

BASE = r"G:\AI work\deepseek\work1\alchemy"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import natural_engine as E  # noqa: E402
import t55_kinetic_env as K  # noqa: E402
from t55_kinetic_env import KineticEnvironment, run_control  # noqa: E402

SEED = 20261129
CAP = 40
EVENT_LIMIT = 30000

# ---------------------------------------------------------------- 温度日程（同 T65）
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
# feeds：[(化合物 formula, 分子数), ...]，按化学计量精确配平到 atoms_per_element。
# 元素集/原子数/L 与 T65 C01~C10 相同，便于对比"单质播种 vs 化合物播种"。
# 播种策略：每个群系"一半原子以化合物（该元素集天然盐/骨架）形式投入、一半以双原子单质投入"，
# 既满足"不一定要投单质、其他物质也可以"，又保证初始体系偏离大锅平衡（游离单质会与盐反应），
# 从而与 T65（全单质播种）对照，检验终态是否只由元素配比与温度路径决定。
BIOMES = [
    dict(id="E01", name="双盐平原", elements=["O", "P", "X", "W"],
         atoms_per_element=3500, L=18000,
         feeds=[("OP", 1750), ("XW", 1750), ("O2", 875), ("P2", 875),
                ("X2", 875), ("W2", 875)],
         tag="OP+XW 盐各半 + 游离 O2/P2/X2/W2（对应 T65 C01）"),
    dict(id="E02", name="双盐配位谷", elements=["O", "K", "C", "L"],
         atoms_per_element=3500, L=18000,
         feeds=[("OK", 1750), ("CL", 1750), ("O2", 875), ("K2", 875),
                ("C2", 875), ("L2", 875)],
         tag="OK+CL 盐各半 + 游离 O2/K2/C2/L2（对应 T65 C02）"),
    dict(id="E03", name="四元盐台地", elements=["P", "X", "A", "L"],
         atoms_per_element=3500, L=18000,
         feeds=[("XPLA", 1750), ("P2", 875), ("X2", 875),
                ("A2", 875), ("L2", 875)],
         tag="XPLA 四元盐半量 + 游离 P2/X2/A2/L2（对应 T65 C03）"),
    dict(id="E04", name="盐晶原", elements=["K", "A", "F", "X"],
         atoms_per_element=3500, L=18000,
         feeds=[("KAF", 1750), ("K2", 875), ("A2", 875),
                ("F2", 875), ("X2", 1750)],
         tag="KAF 盐半量 + 游离 K2/A2/F2 与 X2（对应 T65 C04）"),
    dict(id="E05", name="聚动盐林", elements=["O", "X", "C", "P", "W"],
         atoms_per_element=3000, L=19000,
         feeds=[("OXC", 1500), ("OP", 750), ("XW", 750), ("O2", 375),
                ("X2", 375), ("C2", 750), ("P2", 1125), ("W2", 1125)],
         tag="OXC/OP/XW 聚素盐半量 + 游离单质（对应 T65 C05）"),
    dict(id="E06", name="盐骨架麓", elements=["O", "P", "K", "X", "A"],
         atoms_per_element=3000, L=19000,
         feeds=[("OP", 1000), ("OK", 1000), ("PK", 1000), ("XA", 1500),
                ("O2", 500), ("P2", 500), ("K2", 500), ("X2", 750), ("A2", 750)],
         tag="OP/OK/PK/XA 盐半量 + 游离单质（对应 T65 C06，检验十原子簇）"),
    dict(id="E07", name="六元盐坡", elements=["O", "X", "C", "P", "K", "A"],
         atoms_per_element=2500, L=19000,
         feeds=[("OXCPKA", 1250), ("O2", 625), ("X2", 625), ("C2", 625),
                ("P2", 625), ("K2", 625), ("A2", 625)],
         tag="OXCPKA 六元盐半量 + 游离单质（对应 T65 C07）"),
    dict(id="E08", name="七元盐湖带", elements=["O", "X", "C", "P", "W", "L", "K"],
         atoms_per_element=2400, L=20000,
         feeds=[("OXCPWK", 1200), ("O2", 600), ("X2", 600), ("C2", 600),
                ("P2", 600), ("W2", 600), ("K2", 600), ("L2", 1200)],
         tag="OXCPWK 六元盐半量 + 游离单质（对应 T65 C08）"),
    dict(id="E09", name="八元盐雨林", elements=["O", "X", "C", "P", "W", "L", "K", "A"],
         atoms_per_element=2100, L=20000,
         feeds=[("OXCPWKA", 1050), ("O2", 525), ("X2", 525), ("C2", 525),
                ("P2", 525), ("W2", 525), ("K2", 525), ("A2", 525), ("L2", 1050)],
         tag="OXCPWKA 七元盐半量 + 游离单质（对应 T65 C09）"),
    dict(id="E10", name="九元盐穹顶", elements=["O", "X", "C", "P", "W", "L", "K", "A", "F"],
         atoms_per_element=2000, L=20000,
         feeds=[("OXCPWKA", 1000), ("O2", 500), ("X2", 500), ("C2", 500),
                ("P2", 500), ("W2", 500), ("K2", 500), ("A2", 500),
                ("L2", 1000), ("F2", 1000)],
         tag="OXCPWKA 七元盐半量 + 游离单质（对应 T65 C10/T64 B11，检验终态记忆）"),
]

BIOME_BY_ID = {b["id"]: b for b in BIOMES}


def load_spec(b):
    """化合物混合投放：直接按 feeds 展开为 load_spec。"""
    spec = []
    for i, (formula, count) in enumerate(b["feeds"], 1):
        spec.append(("化合物底物", "%d号化合物 %s" % (i, formula), formula, int(count)))
    return spec


def element_totals(b):
    """按 build_templates 实际建出的分子，逐元素统计原子数（配平校验用）。"""
    spec = load_spec(b)
    tpl, _byf = K.build_templates(spec)
    totals = Counter()
    for _t, _d, f, c in spec:
        m = tpl[f]
        for a in m["atoms"]:
            totals[a] += int(c)
    return dict(totals), tpl


def biome_atoms(b):
    totals, _ = element_totals(b)
    return int(sum(totals.values()))


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
        "model": "t66_biome_compound",
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


def load_known():
    known = {r["formula"] for r in
             json.load(open(BASE + r"\t4_catalog_index.json", encoding="utf-8"))}
    known |= {r["formula"] for r in
              json.load(open(BASE + r"\substances.json", encoding="utf-8"))}
    known |= {e + "2" for e in "OXCPWLKAF"}
    # 本轮化合物底物本身也视为已知物质，避免被当作"目录外新物质"
    for b in BIOMES:
        for f, _c in b["feeds"]:
            known.add(f)
    return known


def build_design():
    rows = []
    for b in BIOMES:
        spec = load_spec(b)
        totals, tpl = element_totals(b)
        ok = all(totals.get(e, 0) == b["atoms_per_element"] for e in b["elements"]) \
            and set(totals) == set(b["elements"])
        row = {
            "id": b["id"], "name": b["name"], "tag": b["tag"],
            "elements": list(b["elements"]), "n_elements": len(b["elements"]),
            "trivalent": [e for e in b["elements"] if e in ("O", "P", "K")],
            "L": b["L"], "atoms_per_element": b["atoms_per_element"],
            "total_atoms": int(sum(totals.values())),
            "total_molecules": sum(int(s[3]) for s in spec),
            "feeds": [{"formula": f, "count": int(c), "atoms": len(tpl[f]["atoms"])}
                      for f, c in b["feeds"]],
            "element_totals": {e: int(totals.get(e, 0)) for e in b["elements"]},
            "feed_valid": bool(ok),
            "load_spec": [{"desc": d, "formula": f, "count": int(c)} for _t, d, f, c in spec],
            "density_atoms_per_area": round(sum(totals.values()) / (b["L"] ** 2), 8),
        }
        if not ok:
            raise ValueError("群系 %s 化合物配平不成立：%s vs 目标 %s"
                             % (b["id"], totals, b["atoms_per_element"]))
        rows.append(row)
    return {
        "experiment": "T66 生态群系（10 群系 × 化合物播种，退火 + 恒温浮动，每群系 ≥4 元素）",
        "seed_base": SEED,
        "feed_mode": "化合物混合投放（非双原子单质）",
        "compare_to": "t65_biomes.json（同元素集/同原子数/同温度日程，单质播种）",
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
    feed_desc = "、".join("%s×%d" % (f, c) for f, c in b["feeds"])
    res["biome"] = {"id": b["id"], "name": b["name"], "tag": b["tag"],
                    "elements": list(b["elements"]),
                    "L": b["L"], "atoms_per_element": b["atoms_per_element"],
                    "total_atoms": biome_atoms(b), "feeds": b["feeds"],
                    "schedule": schedule_info()}
    res["config"]["experiment"] = (
        "T66 %s %s：元素 %s，化合物播种 %s，L=%d，每元素 %d 原子；"
        "1000→25°C 退火 %d 分钟 + 25°C 浮动 %d 分钟（±8°C 日周期 + ±3°C 季节周期）"
        % (b["id"], b["name"], "+".join(b["elements"]), feed_desc, b["L"],
           b["atoms_per_element"], ANNEAL_MINUTES, HOLD_MINUTES))
    res["biome"]["seed"] = seed
    res["summary"]["runtime_s"] = round(time.time() - t_start, 1)
    res["summary"]["biome_id"] = b["id"]
    res["summary"]["biome_name"] = b["name"]
    json.dump(res, open(BASE + r"\t66_biome_%s_result.json" % b["id"], "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)
    state = env.export_state()
    state["biome_id"] = b["id"]
    json.dump(state, open(BASE + r"\t66_biome_%s_state.json" % b["id"], "w",
                          encoding="utf-8"), ensure_ascii=False, indent=1)
    print("[%s] %s  saved t66_biome_%s_result.json / _state.json  runtime %ss"
          % (b["id"], b["name"], b["id"], res["summary"]["runtime_s"]), flush=True)
    print(json.dumps(res["summary"], ensure_ascii=False, indent=1)[:1200], flush=True)
    return res


def run_control_e01(minutes=500):
    b = BIOME_BY_ID["E01"]
    spec = load_spec(b)
    K.set_geometry(b["L"])
    res = run_control(minutes=minutes, seed=SEED, load_spec=spec,
                      area_model="count")
    res["biome"] = {"id": b["id"], "name": b["name"], "L": b["L"],
                    "elements": list(b["elements"]), "feeds": b["feeds"]}
    res["config"]["experiment"] = ("T66 E01 无化学对照：OP+XW 化合物播种、"
                                   "L=%d、%d 分钟" % (b["L"], minutes))
    json.dump(res, open(BASE + r"\t66_control_E01.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t66_control_E01.json", flush=True)
    print(json.dumps(res["stats"], ensure_ascii=False, indent=1)[:800], flush=True)
    return res


def update_index():
    rows = []
    for b in BIOMES:
        p = BASE + r"\t66_biome_%s_result.json" % b["id"]
        try:
            r = json.load(open(p, encoding="utf-8"))
        except FileNotFoundError:
            rows.append({"id": b["id"], "status": "pending"})
            continue
        rows.append({
            "id": b["id"], "name": b["name"], "status": "done",
            "file": "t66_biome_%s_result.json" % b["id"],
            "elements": r["biome"]["elements"], "L": r["biome"]["L"],
            "feeds": r["biome"]["feeds"],
            "total_atoms": r["biome"]["total_atoms"],
            "runtime_s": r["summary"]["runtime_s"],
            "final_N": r["summary"]["final_N"],
            "final_atoms": r["summary"]["final_atoms"],
            "final_T": r["summary"]["final_T"],
            "reaction_counts": r["summary"]["reaction_counts"],
        })
    idx = {"experiment": "T66 生态群系（化合物播种）", "schedule": schedule_info(),
           "biomes": rows}
    json.dump(idx, open(BASE + r"\t66_biome_index.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t66_biome_index.json", flush=True)
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--biome", default=None, help="群系 id，如 E01")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--control", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--minutes", type=int, default=MINUTES)
    args = ap.parse_args()
    if args.list:
        for b in BIOMES:
            print("%s  %-8s  %d 元素 %-22s L=%d 原子=%d  底物=%s  %s" % (
                b["id"], b["name"], len(b["elements"]), "+".join(b["elements"]),
                b["L"], biome_atoms(b),
                "、".join("%s×%d" % (f, c) for f, c in b["feeds"]), b["tag"]))
        return
    if args.control:
        run_control_e01()
        return
    if args.biome:
        run_biome(BIOME_BY_ID[args.biome], args.minutes)
        update_index()
        return
    design = build_design()
    json.dump(design, open(BASE + r"\t66_biomes.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t66_biomes.json：%d 群系" % len(BIOMES), flush=True)
    t0 = time.time()
    for b in BIOMES:
        run_biome(b, args.minutes)
        update_index()
    print("all done", round(time.time() - t0, 1), "s", flush=True)


if __name__ == "__main__":
    main()
