# -*- coding: utf-8 -*-
"""t57_all29_area.py —— T57：全部 29 种纯聚素物质 + "面积∝元素数" 的第三次环境实验

用户假设：前两轮环境偏向单质/小分子，可能是因为每次碰撞参与反应的物质内元素数较少。
本轮改动：

1. **只投入聚素**（O/X/C），但投料包含全部 29 种纯聚素物质（substances.json）。
2. **每种物质设定面积**：面积 ∝ 元素数（原子数）：
      A(M) = π·R0²·(n_atoms/2)，碰撞半径 R(M) = R0·sqrt(n_atoms/2)，R0 = 0.2。
   于是 n=2（双原子单质）面积为 1 单位，n=9 的物质面积为 4.5 单位。
3. **面积越大投入数量越少**：数量 N(M) ∝ 1/面积 ∝ 1/n_atoms，
       N(M) = max(30, round(K/n_atoms))，K 取使总分子数 ≈ 9000。
4. **碰撞截面也随面积增大**：2D 硬圆碰撞率 ν_i ∝ v_i·(R_i+R̄)（而不是固定半径），
   并在局部邻域内按 (R_i+R_j) 加权选伙伴 —— 大分子更容易参与碰撞。
5. 环境/温度（10000²、1000→0°C、1000 分钟）、每次碰撞 -0.2% 速度与化学引擎不变。

为检验"面积假设"，同时跑两个对照：
  * `t57_area_control.json`：同一投料 + 面积模型，关闭化学（500 分钟穿越验证）；
  * `t57_uniform_result.json`：同一投料/数量，但碰撞半径固定 0.2（T55/T56 口径），
    用于比较"面积是否真的让环境更偏向大分子"。

输出：t57_area_result.json、t57_area_control.json、t57_uniform_result.json、
      t57_design.json（投料/面积/数量设计表）

用法：python t57_all29_area.py [--minutes 1000] [--seed 20261118] [--no-uniform]
"""
import argparse
import json
import math
import sys
import time

BASE = r"G:\AI work\deepseek\work1\alchemy"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from t55_kinetic_env import (
    KineticEnvironment, run_control, radius_for, RADIUS, DIAG, L, TARGET_CROSSINGS,
)

SEED = 20261118
TOTAL_MOLECULES = 9000
SNAP_MINUTES = [0, 2, 5, 10, 25, 50, 100, 200, 300, 400,
                500, 600, 700, 800, 900, 950, 980, 995, 1000]


def load_29():
    """全部 29 种纯聚素物质。"""
    subs = json.load(open(BASE + r"\substances.json", encoding="utf-8"))
    return subs


def build_load_spec(total=TOTAL_MOLECULES):
    """数量 ∝ 1/面积 ∝ 1/原子数；返回 (load_spec, design_rows, meta)。"""
    subs = load_29()
    inv = sum(1.0 / len(r["atoms"]) for r in subs)
    K = total / inv
    rows = []
    for r in sorted(subs, key=lambda x: (len(x["atoms"]), x["formula"])):
        n = len(r["atoms"])
        count = max(30, int(round(K / n)))
        rad = RADIUS * math.sqrt(n / 2.0)
        area = math.pi * rad * rad
        rows.append({
            "formula": r["formula"], "zh": r.get("zh", r["formula"]),
            "atoms": n, "radius": round(rad, 4), "area": round(area, 4),
            "count": count, "area_per_atom": round(area / n, 4),
        })
    load_spec = [("29聚素", "%s(%d原子)" % (x["formula"], x["atoms"]),
                  x["formula"], x["count"]) for x in rows]
    total_n = sum(x["count"] for x in rows)
    total_atoms = sum(x["count"] * x["atoms"] for x in rows)
    # 严格性校验：原子数越多 -> 面积越大 -> 数量越少
    by_n = {}
    for x in rows:
        by_n.setdefault(x["atoms"], []).append(x["count"])
    monotone = all(min(by_n[n]) > max(by_n[n2])
                   for n in sorted(by_n) for n2 in sorted(by_n) if n < n2)
    meta = {
        "n_species": len(rows),
        "total_molecules": total_n,
        "total_atoms": total_atoms,
        "area_model": "A = π·R0²·(n_atoms/2)，R = R0·sqrt(n/2)，R0=0.2",
        "count_model": "count = max(30, round(K/n_atoms))，K = total/Σ(1/n)",
        "K": round(K, 3),
        "strict_larger_area_fewer_count": bool(monotone),
        "molecule_range": [min(x["atoms"] for x in rows), max(x["atoms"] for x in rows)],
        "area_range": [min(x["area"] for x in rows), max(x["area"] for x in rows)],
        "count_range": [min(x["count"] for x in rows), max(x["count"] for x in rows)],
        "mean_atoms": round(total_atoms / total_n, 3),
    }
    return load_spec, rows, meta


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--no-uniform", action="store_true",
                    help="不跑固定半径对照（仅主实验 + 无化学对照）")
    args = ap.parse_args(argv)
    load_spec, rows, meta = build_load_spec()
    print("设计:", json.dumps(meta, ensure_ascii=False))
    json.dump({"meta": meta, "species": rows},
              open(BASE + r"\t57_design.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    known = {r["formula"] for r in load_29()}

    # 1) 主实验：面积∝元素数 + 数量∝1/面积
    t_start = time.time()
    env = KineticEnvironment(minutes=args.minutes, seed=args.seed,
                             load_spec=load_spec, known_formulas=known,
                             area_model="count", weighted_partner=True,
                             event_limit=30000, snap_minutes=SNAP_MINUTES)
    res = env.run()
    res["design_meta"] = meta
    res["design_species"] = rows
    res["config"]["experiment"] = "T57 全部29种聚素 + 面积∝元素数 + 数量∝1/面积"
    res["summary"]["runtime_s"] = round(time.time() - t_start, 1)
    json.dump(res, open(BASE + r"\t57_area_result.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t57_area_result.json runtime", res["summary"]["runtime_s"], "s")
    print(json.dumps(res["summary"], ensure_ascii=False, indent=1)[:1800])

    # 2) 无化学对照（同样是面积模型，验证穿越）
    ctrl = run_control(minutes=500, seed=args.seed, load_spec=load_spec,
                       area_model="count")
    json.dump(ctrl, open(BASE + r"\t57_area_control.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t57_area_control.json:", json.dumps(ctrl["stats"], ensure_ascii=False))

    # 3) 固定半径对照：同投料/数量，但碰撞半径固定（隔离"面积"的影响）
    if not args.no_uniform:
        t0 = time.time()
        ref = KineticEnvironment(minutes=args.minutes, seed=args.seed,
                                 load_spec=load_spec, known_formulas=known,
                                 area_model="uniform", weighted_partner=False,
                                 event_limit=30000, snap_minutes=SNAP_MINUTES)
        rres = ref.run()
        rres["design_meta"] = meta
        rres["design_species"] = rows
        rres["config"]["experiment"] = "T57 同投料固定半径对照（隔离面积效应）"
        rres["summary"]["runtime_s"] = round(time.time() - t0, 1)
        json.dump(rres, open(BASE + r"\t57_uniform_result.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("saved t57_uniform_result.json runtime", rres["summary"]["runtime_s"], "s")
        print("uniform summary:", json.dumps(rres["summary"], ensure_ascii=False)[:800])


if __name__ == "__main__":
    main()
