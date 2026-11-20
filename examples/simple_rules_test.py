# -*- coding: utf-8 -*-
"""简化规则实测：重力当作力，只保留保序交换。

与现有 step（沉降+铺平+主导源+同种+阈值）对比。
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lattice_sim as L
from flow_census import build, collect, FILL, GRID

L.GRID = GRID
L.FILL = FILL


def step_simple(grid, mols, rng, gforce=1.0, dt=0.05, damp=0.8,
                max_step=2, thr=0.05):
    """重力作为力；移动只受保序交换约束。"""
    order = mols[:]
    rng.shuffle(order)
    moves = 0
    for m in order:
        if grid.get((m.x, m.y)) is not m:
            continue
        fx, fy = L.net_force(m, grid, 0.0, decay=True, asym=True)
        fy += gforce
        m.vx = (m.vx + fx * dt) * damp
        m.vy = (m.vy + fy * dt) * damp
        sp = math.hypot(m.vx, m.vy)
        if sp < thr:
            continue
        steps = min(max_step, max(1, int(sp * 2.0)))
        for _ in range(steps):
            sx = 0 if abs(m.vx) < 0.02 else (1 if m.vx > 0 else -1)
            sy = 0 if abs(m.vy) < 0.02 else (1 if m.vy > 0 else -1)
            if sx == 0 and sy == 0:
                break
            nx, ny = m.x + sx, m.y + sy
            if not (0 <= nx < GRID and 0 <= ny < GRID):
                break
            occ = grid.get((nx, ny))
            if occ is None:
                del grid[(m.x, m.y)]
                m.x, m.y = nx, ny
                grid[(nx, ny)] = m
                moves += 1
                continue
            if sx == 0:
                ok = ((sy > 0 and m.w_eff >= occ.w_eff)
                      or (sy < 0 and m.w_eff <= occ.w_eff))
            else:
                ok = True
            if not ok:
                break
            oldx, oldy = m.x, m.y
            grid[(oldx, oldy)] = occ
            occ.x, occ.y = oldx, oldy
            grid[(nx, ny)] = m
            m.x, m.y = nx, ny
            moves += 1
    return moves


def measure(grid, mols, stepper, ticks):
    rng = random.Random(7)
    for _ in range(ticks):
        stepper(rng)
    mv = 0
    for _ in range(20):
        mv += stepper(rng)
    same = diff = 0
    for (x, y), m in grid.items():
        for dx, dy in ((1, 0), (0, 1)):
            o = grid.get((x + dx, y + dy))
            if o is None:
                continue
            same += (o.formula == m.formula)
            diff += (o.formula != m.formula)
    sn = same / (same + diff) if same + diff else 0
    ys = [m.y for m in mols]
    return mv / 20 / len(mols), sn, sum(ys) / len(ys), max(ys)


def main():
    world = dict(collect())["t62_phaseB"]
    print("世界 t62_phaseB\n")
    print(f"{'规则':26}{'流动率':>8}{'同种邻接':>9}{'平均y':>7}{'最低y':>6}")
    for label, gforce in (("简化 g=1.0", 1.0), ("简化 g=2.0", 2.0),
                          ("简化 g=0.5", 0.5)):
        rng = random.Random(20261120)
        grid, mols = build(world, int(GRID * GRID * FILL), rng)
        st = lambda r, gf=gforce: step_simple(grid, mols, r, gforce=gf)
        r, sn, ay, my = measure(grid, mols, st, 400)
        print(f"{label:26}{r:8.1%}{sn:9.1%}{ay:7.1f}{my:6.0f}")
        L.render(mols, f"images/simple_{gforce}.png", by_state=False)
    # 对照：现有规则
    rng = random.Random(20261120)
    grid, mols = build(world, int(GRID * GRID * FILL), rng)
    st = lambda r: L.step(grid, mols, r, gravity=1.0, inertia=True, threshold=0.05)
    r, sn, ay, my = measure(grid, mols, st, 400)
    print(f"{'现有 10 条规则':26}{r:8.1%}{sn:9.1%}{ay:7.1f}{my:6.0f}")
    L.render(mols, "images/simple_current.png", by_state=False)
    print("\n图: images/simple_*.png")


if __name__ == "__main__":
    main()
