# -*- coding: utf-8 -*-
"""新力模型下的世界普查：44 个群系，看流动/静止的新分布。

力模型（2026-11-20 重构后）：
- 引力/斥力各自线性衰减到自己的半径
- r_att = 1.5 + 3.0·s        （散素给引力）
- r_rep = 1.5 + 3.0·(0.8(1−s) + 0.2m)
- 强度按幂次校准
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lattice_sim as L
from flow_census import collect, build, GRID, FILL

L.GRID = GRID
L.FILL = FILL
L.CROSS_K = 60.0      # 配对力交叉项
THRESH = 0.30         # 速度/力阈值
SEED = 20261120


def run(comp, ticks=400):
    rng = random.Random(SEED)
    grid, mols = build(comp, int(GRID * GRID * FILL), rng)
    for _ in range(ticks):
        L.step(grid, mols, rng, gravity=1.0, inertia=True, threshold=THRESH)
    prev = {id(m): (m.x, m.y) for m in mols}
    moved = 0
    for _ in range(40):
        L.step(grid, mols, rng, gravity=1.0, inertia=True, threshold=THRESH)
        for m in mols:
            if (m.x, m.y) != prev[id(m)]:
                moved += 1
                prev[id(m)] = (m.x, m.y)
    rate = moved / 40 / len(mols)
    same = diff = 0
    for (x, y), m in grid.items():
        for dx, dy in ((1, 0), (0, 1)):
            o = grid.get((x + dx, y + dy))
            if o is None:
                continue
            same += (o.formula == m.formula)
            diff += (o.formula != m.formula)
    sn = same / (same + diff) if same + diff else 0
    return rate, sn, len({m.formula for m in mols})


def main():
    worlds = collect()
    print(f"{len(worlds)} 个世界 · CROSS_K=60 · 速度阈值 0.30 · 400 tick\n")
    print(f"{'世界':20}{'物种':>5}{'流动率':>8}{'同种邻接':>9}{'判定':>6}")
    rows = []
    for nm, comp in worlds:
        rate, sn, nsp = run(comp)
        rows.append((nm, nsp, rate, sn))
        verdict = "活" if rate >= 0.05 else ("微动" if rate >= 0.01 else "静止")
        print(f"{nm[:18]:20}{nsp:5}{rate:8.2%}{sn:9.1%}{verdict:>6}")

    rows.sort(key=lambda r: -r[2])
    print("\n=== 活性最高的 10 个 ===")
    for nm, nsp, rate, sn in rows[:10]:
        print(f"  {nm:22} 流动 {rate:6.2%}  {nsp:3} 种  同种邻接 {sn:4.0%}")
    alive = [r for r in rows if r[2] >= 0.05]
    print(f"\n活世界: {len(alive)}/{len(rows)} = {len(alive)/len(rows):.0%}")
    mid = [r for r in rows if 0.01 <= r[2] < 0.05]
    print(f"微动: {len(mid)}  静止: {len(rows)-len(alive)-len(mid)}")


if __name__ == "__main__":
    main()
