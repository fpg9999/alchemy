# -*- coding: utf-8 -*-
"""网格 + 距离衰减 + 非对称力：打磨后的规则实验。

对照四组：
    对称/非对称  ×  恒力/衰减力

观测量：
- **流动率**：每个 tick 移动的分子比例（持续 >0 说明系统不在平衡态）
- **团块**：连通团数量与最大团
- **位移**：分子从初始位置移动的平均距离（越大越"活"）

用法
----
    python examples/lattice_decay.py
"""

from __future__ import annotations

import math
import random
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lattice_sim as L  # noqa: E402

GRID = 48
FILL = 0.35
TICKS = 600
GRAV = 0.0
SEED = 20261120
L.GRID = GRID


def clusters(grid, mols):
    seen, best, groups = set(), 0, []
    for m in mols:
        if (m.x, m.y) in seen:
            continue
        q, seen = deque([(m.x, m.y)]), seen | {(m.x, m.y)}
        size = 0
        while q:
            x, y = q.popleft()
            size += 1
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if not (dx or dy):
                        continue
                    p = (x + dx, y + dy)
                    o = grid.get(p)
                    if o is not None and o.formula == m.formula and p not in seen:
                        seen.add(p)
                        q.append(p)
        best = max(best, size)
        groups.append(size)
    return groups, best


def run(decay: bool, asym: bool, ticks=TICKS):
    rng = random.Random(SEED)
    n = int(GRID * GRID * FILL)
    grid, mols = L.build(n, rng)
    start = [(m.x, m.y) for m in mols]
    rates = []
    for t in range(ticks):
        moved = L.step(grid, mols, rng, gravity=GRAV, use_radial=False,
                       decay=decay, asym=asym)
        rates.append(moved / len(mols))
    groups, best = clusters(grid, mols)
    disp = sum(math.hypot(m.x - sx, m.y - sy) for m, (sx, sy) in zip(mols, start)) / len(mols)
    return {"rate_last": sum(rates[-50:]) / 50, "rate_mean": sum(rates) / len(rates),
            "groups": len(groups), "best": best, "disp": disp,
            "mols": mols, "grid": grid}


def main():
    print(f"网格 {GRID}×{GRID}，分子 {int(GRID*GRID*FILL)}，{TICKS} tick\n")
    print(f"{'配置':24}{'末段流动率':>11}{'平均流动率':>11}{'团数':>6}{'最大团':>7}{'平均位移':>9}")
    rows = []
    for decay in (False, True):
        for asym in (False, True):
            tag = ("衰减力" if decay else "恒力") + " + " + ("非对称" if asym else "对称")
            r = run(decay, asym)
            r["tag"] = tag
            rows.append(r)
            print(f"{tag:24}{r['rate_last']:11.1%}{r['rate_mean']:11.1%}"
                  f"{r['groups']:6}{r['best']:7}{r['disp']:9.2f}")
    print()
    for r in rows:
        L.render(r["mols"], f"images/decay_{'d' if '衰减' in r['tag'] else 'c'}"
                            f"{'a' if '非对称' in r['tag'] else 's'}.png")
    print("图: images/decay_*.png")


if __name__ == "__main__":
    main()
