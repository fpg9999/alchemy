# -*- coding: utf-8 -*-
"""接入径向三轴后的网格实验：质量决定重力方向，碰撞性决定能否被穿过。

用法
----
    python examples/lattice_radial.py
"""

from __future__ import annotations

import sys
from collections import Counter, deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lattice_sim as L  # noqa: E402

TICKS = 400


def describe(mols):
    c = Counter((m.formula, m.mass_tier, m.coll_tier) for m in mols)
    print("  主要组分的径向属性：")
    for (f, mt, ct), n in c.most_common(4):
        print(f"    {f:12} 质量档={mt}  碰撞档={ct}  ×{n}")


def bands(mols, k=8):
    band = max(1, L.GRID // k)
    cnt = Counter(m.y // band for m in mols)
    n = len(mols)
    return [cnt.get(i, 0) / n for i in range(k)]


def per_species_bands(mols, k=8):
    band = max(1, L.GRID // k)
    out = {}
    for f in {m.formula for m in mols}:
        sub = [m for m in mols if m.formula == f]
        if len(sub) < 20:
            continue
        cnt = Counter(m.y // band for m in sub)
        out[f] = [cnt.get(i, 0) / len(sub) for i in range(k)]
    return out


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


def run(g: float, use_radial: bool, seed: int = L.SEED):
    import random
    rng = random.Random(seed)
    n = int(L.GRID * L.GRID * L.FILL)
    grid, mols = L.build(n, rng)
    for _ in range(TICKS):
        L.step(grid, mols, rng, gravity=g, use_radial=use_radial)
    return grid, mols


def main():
    for g in (1.0,):
        for use_radial in (False, True):
            tag = "接入径向三轴" if use_radial else "统一重力（对照）"
            grid, mols = run(g, use_radial)
            print(f"=== g={g} · {tag} ===")
            if use_radial:
                describe(mols)
            b = bands(mols)
            print("  全体竖直剖面（上→下）: " + " ".join(f"{x:5.1%}" for x in b))
            for f, bb in per_species_bands(mols).items():
                if f in ("LF", "OXCPWKA"):
                    print(f"    {f:10} 剖面: " + " ".join(f"{x:5.1%}" for x in bb))
            cl = clusters(mols, grid)
            for f in ("OXCPWKA", "LF"):
                if f in cl:
                    print(f"    {f:10} 团数 {len(cl[f]):3}  最大团 {max(cl[f]):3}")
            L.render(mols, f"images/lattice_radial_{'on' if use_radial else 'off'}.png")
            print()


if __name__ == "__main__":
    main()
