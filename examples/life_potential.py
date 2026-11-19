# -*- coding: utf-8 -*-
"""生命潜力统计：哪些世界含有足够的"平衡分子"（A≈R）。

判定
----
- 对每个分子算 ``|A − R|``（引力与斥力的失衡度）
- 世界平衡度 = 按丰度加权的 ``|A−R| ≤ 1.0`` 的分子占比
- 实际活性 = 网格模拟稳定后的每 tick 移动比例

用法
----
    python examples/life_potential.py
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lattice_sim as L
from alchemy.core.elements import ORDER, VAL, parse_formula
from flow_census import collect, build, GRID, FILL

L.GRID = GRID
L.FILL = FILL
SEED = 20261120
K = 8.0
A_MAX = 10.0
R_MAX = 10.0


def ar(f):
    v = parse_formula(f)
    g = {e: v[ORDER.index(e)] for e in ORDER}
    sp = sum(VAL[e] * g[e] for e in ("O", "X", "C"))
    sm = sum(VAL[e] * g[e] for e in ("P", "W", "L"))
    return A_MAX * sp / (sp + K), R_MAX * sm / (sm + K)


def balance(comp):
    tot = sum(comp.values()) or 1
    good = sum(w for f, w in comp.items() if abs(ar(f)[0] - ar(f)[1]) <= 1.0)
    gap = sum(w * abs(ar(f)[0] - ar(f)[1]) for f, w in comp.items()) / tot
    return good / tot, gap


def flow(comp, ticks=400):
    rng = random.Random(SEED)
    grid, mols = build(comp, int(GRID * GRID * FILL), rng)
    for _ in range(ticks):
        L.step(grid, mols, rng, gravity=1.0, inertia=True, swap_cooldown=3)
    hist = []
    for _ in range(30):
        hist.append({id(m): (m.x, m.y) for m in mols})
        L.step(grid, mols, rng, gravity=1.0, inertia=True, swap_cooldown=3)
    moved = 0
    for t in range(len(hist) - 1):
        for m in mols:
            if hist[t][id(m)] != hist[t + 1][id(m)]:
                moved += 1
    return moved / (len(hist) - 1) / len(mols)


def main():
    worlds = collect()
    print(f"{len(worlds)} 个世界 · 平衡度 vs 实际活性\n")
    print(f"{'世界':20}{'平衡分子占比':>12}{'平均|A-R|':>10}{'流动率':>8}{'判定':>8}")
    rows = []
    for nm, comp in worlds:
        bal, gap = balance(comp)
        fl = flow(comp)
        rows.append((nm, bal, gap, fl))
        verdict = "活" if fl >= 0.05 else ("微动" if fl >= 0.01 else "静止")
        print(f"{nm[:18]:20}{bal:12.0%}{gap:10.2f}{fl:8.2%}{verdict:>8}")

    rows.sort(key=lambda r: -r[3])
    print("\n=== 活性最高的 10 个世界 ===")
    for nm, bal, gap, fl in rows[:10]:
        print(f"  {nm:22} 流动率 {fl:6.2%}  平衡分子 {bal:4.0%}  平均失衡 {gap:.2f}")
    print("\n=== 最静止的 5 个世界 ===")
    for nm, bal, gap, fl in rows[-5:]:
        print(f"  {nm:22} 流动率 {fl:6.2%}  平衡分子 {bal:4.0%}  平均失衡 {gap:.2f}")

    alive = [r for r in rows if r[3] >= 0.05]
    print(f"\n有活性的世界: {len(alive)}/{len(rows)} = {len(alive)/len(rows):.0%}")


if __name__ == "__main__":
    main()
