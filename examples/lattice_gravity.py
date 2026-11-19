# -*- coding: utf-8 -*-
"""加入重力后的网格实验：对比三档重力强度下的沉降与分相。

重力是**世界级恒定外力**，暂不接入径向三轴（不做质量→重力方向、不做浮力）。

用法
----
    python examples/lattice_gravity.py
"""

from __future__ import annotations

import math
import random
import sys
from collections import Counter, deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lattice_sim as L  # noqa: E402

GRAVS = (0.0, 0.3, 1.0, 3.0)
TICKS = 300


def clusters(mols, grid):
    seen, out = set(), {}
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
        out.setdefault(m.formula, []).append(size)
    return out


def profile(mols):
    """竖直密度剖面：每 1/8 高度的占比。"""
    band = max(1, L.GRID // 8)
    cnt = Counter(m.y // band for m in mols)
    n = len(mols)
    return [cnt.get(i, 0) / n for i in range(8)]


def run(gravity: float, seed: int = L.SEED):
    rng = random.Random(seed)
    n = int(L.GRID * L.GRID * L.FILL)
    grid, mols = L.build(n, rng)
    for _ in range(TICKS):
        L.step(grid, mols, rng, gravity=gravity)
    cl = clusters(mols, grid)
    top = {f: max(v) for f, v in cl.items() if len(v) > 10}
    bands = profile(mols)
    mean_y = sum(m.y for m in mols) / len(mols)
    bottom = sum(1 for m in mols if m.y >= L.GRID * 0.75) / len(mols)
    return {"gravity": gravity, "bands": bands, "mean_y": mean_y,
            "bottom": bottom, "top": top, "mols": mols, "grid": grid}


def main():
    results = []
    for g in GRAVS:
        r = run(g)
        results.append(r)
        print(f"=== 重力 g = {g} ===")
        print(f"  平均高度 {r['mean_y']:.1f} / {L.GRID}（越小越靠上）")
        print(f"  底部 1/4 的分子占比: {r['bottom']:.1%}")
        print("  竖直剖面（上→下，8 段）: " +
              " ".join(f"{v:5.1%}" for v in r["bands"]))
        for f in ("OXCPWKA", "LF"):
            if f in r["top"]:
                print(f"  {f} 最大团: {r['top'][f]}")
        print()

    # 渲染重力 0 / 1.0 / 3.0 三张图
    for r in results:
        if r["gravity"] in (0.0, 1.0, 3.0):
            path = f"images/lattice_g{r['gravity']:.1f}.png"
            L.render(r["mols"], path)
            print(f"图: {path}")


if __name__ == "__main__":
    main()
