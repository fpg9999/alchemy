# -*- coding: utf-8 -*-
"""重力标定：固定同一个世界，只改重力，找最合理的值。

指标
----
- **分层度**：顶部 1/4 与底部 1/4 的密度差
- **聚集体**：≥8 成员的团数、最大团
- **成团率**：落在聚集体里的分子比例
- **紧凑度**：团的周长²/面积（越小越圆，越像"细胞"）

用法
----
    python examples/gravity_calibration.py
"""

from __future__ import annotations

import json
import math
import random
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lattice_sim as L  # noqa: E402
from lattice_weight import load_world, build, GRID, FILL, SEED  # noqa: E402

L.GRID = GRID
L.FILL = FILL
TICKS = 500
GRAVS = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 6.0, 10.0)


def aggregates(grid, min_size=8):
    seen, out = set(), []
    for p in list(grid.keys()):
        if p in seen:
            continue
        q, seen = deque([p]), seen | {p}
        mem = []
        while q:
            x, y = q.popleft()
            mem.append((x, y))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if not (dx or dy):
                        continue
                    n = (x + dx, y + dy)
                    if n in grid and n not in seen:
                        seen.add(n)
                        q.append(n)
        if len(mem) >= min_size:
            s = set(mem)
            perim = 0
            for (x, y) in mem:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    if (x + dx, y + dy) not in s:
                        perim += 1
            out.append({"size": len(mem), "compact": perim * perim / len(mem)})
    return out


def run(g, world="t62_phaseB"):
    comp = load_world(world)
    rng = random.Random(SEED)
    n = int(GRID * GRID * FILL)
    grid, mols = build(comp, n, rng)
    for _ in range(TICKS):
        L.step(grid, mols, rng, gravity=g, inertia=True)
    ys = [m.y for m in mols]
    band = max(1, GRID // 4)
    top = sum(1 for y in ys if y < band) / len(ys)
    bot = sum(1 for y in ys if y >= GRID - band) / len(ys)
    ag = aggregates(grid)
    in_ag = sum(a["size"] for a in ag) / len(mols)
    best_compact = min((a["compact"] for a in ag if 10 <= a["size"] <= 60), default=float("nan"))
    return {"g": g, "mean_y": sum(ys) / len(ys), "top": top, "bot": bot,
            "n_ag": len(ag), "max_ag": max((a["size"] for a in ag), default=0),
            "in_ag": in_ag, "compact": best_compact}


def main():
    print(f"固定世界 t62_phaseB · 网格 {GRID} · {TICKS} tick · 惯性开\n")
    print(f"{'重力':>6}{'平均高度':>9}{'顶层占比':>9}{'底层占比':>9}"
          f"{'团数':>6}{'最大团':>7}{'成团率':>8}{'最紧凑':>8}")
    rows = []
    for g in GRAVS:
        r = run(g)
        rows.append(r)
        print(f"{g:6.1f}{r['mean_y']:9.1f}{r['top']:9.1%}{r['bot']:9.1%}"
              f"{r['n_ag']:6}{r['max_ag']:7}{r['in_ag']:8.1%}{r['compact']:8.1f}")
    print("\n判据：")
    print("  · 底层占比高、顶层占比低 → 分层明显")
    print("  · 团数适中（5~20）、成团率高 → 有聚集结构但不成一坨")
    print("  · 最紧凑值低 → 团是圆的（像细胞）而不是拉长的网")


if __name__ == "__main__":
    main()
