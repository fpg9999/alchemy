# -*- coding: utf-8 -*-
"""t58_nine_elements.py —— T58：九种元素全部包含 + 物质库随机大投料的第四次环境实验

任务要求：九种元素全部包含；投入的具体物质任意，可从物质库随机选取，大量投入，
总量最好比之前都更庞大；整体原则沿用前几轮（2D 环境、1000→0°C、-0.2%/碰撞、
T35 判定、面积∝元素数、面积加权碰撞截面）。

本脚本的设定：
* 从 84,225 条大锅目录（t4_catalog_index.json）中**随机抽取 44 种物质**：
  每个原子数 n=2..12 随机抽 4 种，并自动补足缺失元素，保证 9 种元素都出现；
* 数量 ∝ 1/面积 ∝ 1/原子数（沿用 T57 的"面积越大数量越少"原则），总量目标 14000 个分子
  （比 T55 的 9000、T56 的 9200、T57 的 9002 都多；总原子约 7.3 万，是 T57 的 1.9 倍）；
* 环境扩大到 400000 × 400000（面积 1600 倍）：为了在"总量更庞大"的同时把碰撞频率/计算量
  控制在可跑范围；初速按 500 次穿越要求自动重算（v0≈8.85e5 单位/分钟）；
* 面积模型：A = πR0²·(n/2)，R = R0·sqrt(n/2)，R0=0.2，碰撞截面按面积加权、邻域按截面选伙伴；
* 计算保护：合并后 >20 原子的碰撞不执行反应（弹性），用于限制 >16 原子大分子体系的 F 成本
  （T58 的主要难点；20 原子仍大于 T57 的 9 原子上限）。该保护在报告"局限"中明确说明。

输出：t58_mixture.json（随机投料设计表）、t58_result.json（主实验）、
      t58_control_no_chem.json（无化学对照，500 分钟穿越验证）

用法：python t58_nine_elements.py [--minutes 1000] [--seed 20261120]
"""
import argparse
import json
import math
import random
import sys
import time

BASE = r"G:\AI work\deepseek\work1\alchemy"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import pot_all as P
import t55_kinetic_env as K
from t55_kinetic_env import KineticEnvironment, run_control

SEED = 20261120
TOTAL_MOLECULES = 14000
PER_SIZE = 4             # 每个原子数 n（2..12）随机抽 4 种
SIZE_MIN, SIZE_MAX = 2, 12
MAX_REACTION_ATOMS = 20  # 计算保护（合并后原子数上限）
ENV_L = 400000.0
SNAP_MINUTES = [0, 2, 5, 10, 25, 50, 100, 200, 300, 400,
                500, 600, 700, 800, 900, 950, 980, 995, 1000]


def load_index():
    return json.load(open(BASE + r"\t4_catalog_index.json", encoding="utf-8"))


def elems_of(f):
    return set(ch for ch in f if ch.isalpha() and ch.isupper())


def build_mixture(seed=SEED, total=TOTAL_MOLECULES):
    """随机抽取物质 + 按 1/面积 分配数量；返回 (load_spec, design, meta)。"""
    idx = load_index()
    rng = random.Random(seed)
    by_n = {}
    for r in idx:
        if SIZE_MIN <= r["natoms"] <= SIZE_MAX:
            by_n.setdefault(r["natoms"], []).append(r["formula"])
    species = []
    for n in range(SIZE_MIN, SIZE_MAX + 1):
        pool = by_n.get(n, [])
        species += rng.sample(pool, min(PER_SIZE, len(pool)))
    species = sorted(set(species))
    # 保证九种元素都出现
    have = set().union(*[elems_of(f) for f in species]) if species else set()
    for e in P.ORDER:
        if e not in have:
            cands = [f for n in range(SIZE_MIN, SIZE_MAX + 1)
                     for f in by_n.get(n, []) if e in elems_of(f) and f not in species]
            if cands:
                species.append(rng.choice(cands))
    species = sorted(set(species), key=lambda f: (sum(P.parse_formula(f)), f))
    inv = sum(1.0 / sum(P.parse_formula(f)) for f in species)
    Kc = total / inv
    rows = []
    for f in species:
        n = sum(P.parse_formula(f))
        count = max(20, int(round(Kc / n)))
        rad = K.RADIUS * math.sqrt(n / 2.0)
        rows.append({"formula": f, "atoms": n,
                     "radius": round(rad, 4),
                     "area": round(math.pi * rad * rad, 4),
                     "count": count,
                     "zh": "".join(P.CN[P.ORDER[i]] for i, c in enumerate(P.parse_formula(f))
                                   for _ in range(c))})
    load_spec = [("随机物质库", "%s(%d原子)" % (r["formula"], r["atoms"]),
                  r["formula"], r["count"]) for r in rows]
    total_n = sum(r["count"] for r in rows)
    total_atoms = sum(r["count"] * r["atoms"] for r in rows)
    el_counts = {e: 0 for e in P.ORDER}
    for r in rows:
        vec = P.parse_formula(r["formula"])
        for i, c in enumerate(vec):
            el_counts[P.ORDER[i]] += c * r["count"]
    by_n = {}
    for r in rows:
        by_n.setdefault(r["atoms"], []).append(r["count"])
    strict = all(min(by_n[n]) > max(by_n[n2])
                 for n in sorted(by_n) for n2 in sorted(by_n) if n < n2)
    meta = {
        "seed": seed,
        "selection": "从 84,225 目录按原子数 2..12 每档随机抽 4 种，并补足缺失元素",
        "n_species": len(rows),
        "total_molecules": total_n,
        "total_atoms": total_atoms,
        "mean_atoms": round(total_atoms / total_n, 3),
        "elements_covered": sorted([e for e, c in el_counts.items() if c > 0]),
        "element_atoms": {e: c for e, c in el_counts.items() if c > 0},
        "size_range": [min(r["atoms"] for r in rows), max(r["atoms"] for r in rows)],
        "area_range": [min(r["area"] for r in rows), max(r["area"] for r in rows)],
        "count_range": [min(r["count"] for r in rows), max(r["count"] for r in rows)],
        "strict_larger_area_fewer_count": bool(strict),
        "area_model": "A = π·R0²·(n/2)，R = R0·sqrt(n/2)，R0=0.2（T57 规则）",
        "count_model": "count = max(20, round(K/n_atoms))，K = total/Σ(1/n)",
        "max_reaction_atoms": MAX_REACTION_ATOMS,
        "env_L": ENV_L,
    }
    return load_spec, rows, meta


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args(argv)
    load_spec, rows, meta = build_mixture(args.seed)
    print("投料设计:", json.dumps(meta, ensure_ascii=False))
    json.dump({"meta": meta, "species": rows},
              open(BASE + r"\t58_mixture.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    known = {r["formula"] for r in load_index()}
    K.set_geometry(ENV_L)
    t_start = time.time()
    env = KineticEnvironment(minutes=args.minutes, seed=args.seed,
                             load_spec=load_spec, known_formulas=known,
                             area_model="count", weighted_partner=True,
                             max_reaction_atoms=MAX_REACTION_ATOMS,
                             color_mode="bitmask",
                             event_limit=30000, snap_minutes=SNAP_MINUTES)
    res = env.run()
    res["mixture_meta"] = meta
    res["mixture_species"] = rows
    res["config"]["experiment"] = "T58 九种元素全部包含 + 物质库随机大投料（L=400000）"
    res["summary"]["runtime_s"] = round(time.time() - t_start, 1)
    json.dump(res, open(BASE + r"\t58_result.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t58_result.json runtime", res["summary"]["runtime_s"], "s")
    print(json.dumps(res["summary"], ensure_ascii=False, indent=1)[:2500])
    # 无化学对照
    ctrl = run_control(minutes=500, seed=args.seed, load_spec=load_spec,
                       area_model="count")
    json.dump(ctrl, open(BASE + r"\t58_control_no_chem.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t58_control_no_chem.json:", json.dumps(ctrl["stats"], ensure_ascii=False))


if __name__ == "__main__":
    main()
