# -*- coding: utf-8 -*-
"""能不能涌现出 Particle Life 那样的结构？——用空间网格加速版。

对照实验：同样的分子与参数，只改变**力的对称性**与**是否有惯性**。
关键观测量是**平均动能**：对称力（牛顿第三定律）无法产生净推进，
系统只会结晶；非对称力可以持续驱动结构。

用法
----
    python examples/particle_life_test.py
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lattice_sim import four_values  # noqa: E402

A_MAX, R_MAX = 10.0, 10.0
N = 300
STEPS = 1200
DT = 0.03
DAMP = 0.93
SEED = 20261120
RANGE_SCALE = 1.0 / 25.0      # 把“格”缩放到归一化空间
TYPES = ["LF", "OXCPWKA", "OK", "XA"]


def simulate(asymmetric: bool, inertia: bool):
    rng = random.Random(SEED)
    P = {}
    for t in TYPES:
        a, r, da, dr = four_values(t)
        P[t] = (a, r, da * RANGE_SCALE, dr * RANGE_SCALE)
    rmax = max(max(v[2], v[3]) for v in P.values())

    mols = []
    for i in range(N):
        t = TYPES[i % len(TYPES)]
        mols.append([t, rng.random(), rng.random(), 0.0, 0.0])

    ncell = max(4, int(1.0 / rmax))
    for step in range(STEPS):
        # 空间网格（周期边界）
        buckets: dict[tuple[int, int], list[int]] = {}
        for idx, m in enumerate(mols):
            cx, cy = int(m[1] * ncell) % ncell, int(m[2] * ncell) % ncell
            buckets.setdefault((cx, cy), []).append(idx)

        forces = [[0.0, 0.0] for _ in range(N)]
        for idx, m in enumerate(mols):
            ai, ri, di, si = P[m[0]]
            cx, cy = int(m[1] * ncell) % ncell, int(m[2] * ncell) % ncell
            fx = fy = 0.0
            for ox in (-1, 0, 1):
                for oy in (-1, 0, 1):
                    for j in buckets.get(((cx + ox) % ncell, (cy + oy) % ncell), ()):
                        if j == idx:
                            continue
                        o = mols[j]
                        dx = o[1] - m[1]
                        dy = o[2] - m[2]
                        dx -= round(dx)
                        dy -= round(dy)
                        d = math.hypot(dx, dy)
                        if d < 1e-9 or d > rmax:
                            continue
                        aj, rj, dj, sj = P[o[0]]
                        d_att, d_rep = max(di, dj), max(si, sj)
                        ux, uy = dx / d, dy / d
                        f = 0.0
                        if d <= d_att:
                            f += ai if asymmetric else ai * aj / A_MAX
                        if d <= d_rep:
                            f -= ri if asymmetric else ri * rj / R_MAX
                        if d < 0.01:
                            f *= d / 0.01
                        fx += f * ux
                        fy += f * uy
            forces[idx][0], forces[idx][1] = fx, fy

        for idx, m in enumerate(mols):
            fx, fy = forces[idx]
            if inertia:
                m[3] = (m[3] + fx * DT) * DAMP
                m[4] = (m[4] + fy * DT) * DAMP
                m[1] = (m[1] + m[3] * DT) % 1.0
                m[2] = (m[2] + m[4] * DT) % 1.0
            else:
                mag = math.hypot(fx, fy)
                if mag > 1e-9:
                    m[1] = (m[1] + fx / mag * 0.001) % 1.0
                    m[2] = (m[2] + fy / mag * 0.001) % 1.0
                m[3] = m[4] = 0.0

    ke = sum(m[3] ** 2 + m[4] ** 2 for m in mols) / N
    cells = {}
    for m in mols:
        k = (int(m[1] * 12) % 12, int(m[2] * 12) % 12)
        cells[k] = cells.get(k, 0) + 1
    occ = len(cells)
    return {"ke": ke, "occ": occ, "dens": N / max(1, occ),
            "maxcell": max(cells.values())}


def main():
    print(f"N={N}, steps={STEPS}, 相互作用半径≈{max(four_values(t)[2] for t in TYPES)/25:.3f}\n")
    print(f"{'配置':22}{'平均动能':>11}{'占据格数':>9}{'平均每格':>9}{'最密格':>8}")
    for asym in (False, True):
        for inertia in (False, True):
            tag = ("非对称" if asym else "对称") + "+" + ("惯性" if inertia else "无惯性")
            r = simulate(asym, inertia)
            print(f"{tag:22}{r['ke']:11.2e}{r['occ']:9}{r['dens']:9.2f}{r['maxcell']:8}")


if __name__ == "__main__":
    main()
