# -*- coding: utf-8 -*-
"""终版普查：在"冻结但可解冻"的规则下，统计全世界的静止/流动分布。

规则（已固化在 lattice_sim 默认值里）：
- 沉降只看质量；物态不参与物理
- 等重可交换；交换必须降低势能
- 铺平只走"更低"的一侧（平衡后静止）
"""
from __future__ import annotations

import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lattice_sim as L
from flow_census import collect, build, eqprob, GRID, FILL

L.GRID = GRID
L.FILL = FILL
SEED = 20261120


def main():
    worlds = collect()
    print(f"{len(worlds)} 个世界 · 能量规则开 · 平衡侧移 · 等重可交换\n")
    hdr = (f"{'世界':20}{'物种':>5}{'等重':>6}{'每tick移动':>10}"
           f"{'占比':>7}{'同种邻接':>8}{'状态':>8}")
    print(hdr)
    rows = []
    for nm, comp in worlds:
        rng = random.Random(SEED)
        n = int(GRID * GRID * FILL)
        grid, mols = build(comp, n, rng)
        for _ in range(600):
            L.step(grid, mols, rng, gravity=1.0, inertia=True)
        prev = {id(m): (m.x, m.y) for m in mols}
        moved = 0
        for _ in range(50):
            L.step(grid, mols, rng, gravity=1.0, inertia=True)
            for m in mols:
                if (m.x, m.y) != prev[id(m)]:
                    moved += 1
                    prev[id(m)] = (m.x, m.y)
        rate = moved / 50 / len(mols)
        same = diff = 0
        for (x, y), m in grid.items():
            for dx, dy in ((1, 0), (0, 1)):
                o = grid.get((x + dx, y + dy))
                if o is None:
                    continue
                same += (o.formula == m.formula)
                diff += (o.formula != m.formula)
        sn = same / (same + diff) if same + diff else 0
        rows.append((nm, len(comp), eqprob(comp), rate, sn))
        st = "静止" if rate < 0.02 else ("微动" if rate < 0.10 else "流动")
        print(f"{nm[:18]:20}{len(comp):5}{eqprob(comp):6.0%}{moved/50:10.1f}"
              f"{rate:7.1%}{sn:8.1%}{st:>8}")

    print("\n=== 最终分布 ===")
    b = Counter()
    for r in rows:
        rate = r[3]
        if rate < 0.02:
            b["静止 (<2%)"] += 1
        elif rate < 0.10:
            b["微动 (2-10%)"] += 1
        else:
            b["流动 (>10%)"] += 1
    for k in ("静止 (<2%)", "微动 (2-10%)", "流动 (>10%)"):
        if b[k]:
            print(f"  {k}: {b[k]} 个世界 ({b[k]/len(rows):.0%})")
    print(f"\n平均同种邻接: {sum(r[4] for r in rows)/len(rows):.1%}（随机约 40%）")
    flowing = [r[0] for r in rows if r[3] >= 0.10]
    if flowing:
        print("仍在流动的世界: " + ", ".join(flowing))


if __name__ == "__main__":
    main()
