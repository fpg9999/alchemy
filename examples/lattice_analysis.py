# -*- coding: utf-8 -*-
"""对 lattice_sim 的结果做团块分析：最大连通团、各物种局部密度、被驱赶程度。"""
from __future__ import annotations

import math
import random
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lattice_sim as L  # noqa: E402


def clusters(mols, grid):
    """8 邻接的同类连通团。"""
    seen = set()
    out = {}
    for m in mols:
        if (m.x, m.y) in seen:
            continue
        q = deque([(m.x, m.y)])
        seen.add((m.x, m.y))
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


def quadrants(mols):
    """四个象限里的物种占比，用来看相分离。"""
    half = L.GRID // 2
    q = {}
    for name, (x0, x1, y0, y1) in {
        "左上": (0, half, 0, half), "右上": (half, L.GRID, 0, half),
        "左下": (0, half, half, L.GRID), "右下": (half, L.GRID, half, L.GRID),
    }.items():
        sub = [m for m in mols if x0 <= m.x < x1 and y0 <= m.y < y1]
        q[name] = len(sub)
    return q


def species_center(mols, f):
    pts = [(m.x, m.y) for m in mols if m.formula == f]
    if not pts:
        return None
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def main():
    rng = random.Random(L.SEED)
    n = int(L.GRID * L.GRID * L.FILL)
    grid, mols = L.build(n, rng)

    a0 = clusters(mols, grid)
    c0 = {f: (len(v), sorted(v, reverse=True)[:3]) for f, v in a0.items()}
    q0 = quadrants(mols)

    for t in range(1, L.TICKS + 1):
        L.step(grid, mols, rng)

    a1 = clusters(mols, grid)
    q1 = quadrants(mols)

    print(f"网格 {L.GRID}×{L.GRID}，分子 {len(mols)}")
    print(f"\n{'物种':10}{'t=0 团数':>9}{'t=0 最大':>9}{'t=300 团数':>11}{'t=300 最大':>11}{'最大占比':>9}")
    for f in sorted(a1, key=lambda k: -sum(a1[k])):
        n0, top0 = c0.get(f, (0, []))
        n1 = len(a1[f])
        top1 = max(a1[f]) if a1[f] else 0
        tot = sum(a1[f])
        print(f"{f:10}{n0:9}{max(top0) if top0 else 0:9}{n1:11}{top1:11}{top1/tot:9.0%}")

    print(f"\n{'象限':6}{'t=0':>7}{'t=300':>8}")
    for k in q0:
        print(f"{k:6}{q0[k]:7}{q1[k]:8}")

    print("\n各物种质心（看有没有被驱赶到角落）：")
    for f in ("LF", "OXCPWKA"):
        c = species_center(mols, f)
        if c:
            print(f"  {f:10} ({c[0]:.1f}, {c[1]:.1f})")

    # 混合度：跨物种接触 / 总接触
    grid_ = {(m.x, m.y): m for m in mols}
    same = diff = 0
    for m in mols:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if not (dx or dy):
                    continue
                o = grid_.get((m.x + dx, m.y + dy))
                if o is None:
                    continue
                if o.formula == m.formula:
                    same += 1
                else:
                    diff += 1
    print(f"\n同类接触 {same//2}，异类接触 {diff//2}，同类占比 {same/(same+diff):.1%}")


if __name__ == "__main__":
    main()
