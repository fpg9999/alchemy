# -*- coding: utf-8 -*-
"""为什么分层不彻底？

对"该沉却没沉"的分子做逐个归因：
- 下方有分子（被挡住 / 能被推开？）
- 净力朝上还是朝下（分子间力是否压过了重力）
- 速度是否为 0（惯性是否耗尽）
"""

from __future__ import annotations

import math
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lattice_sim as L  # noqa: E402
from lattice_weight import load_world, build, GRID, FILL, SEED  # noqa: E402

L.GRID = GRID
L.FILL = FILL
G = 1.0


def main():
    comp = load_world("t62_phaseB")
    rng = random.Random(SEED)
    n = int(GRID * GRID * FILL)
    grid, mols = build(comp, n, rng)
    for _ in range(600):
        L.step(grid, mols, rng, gravity=G, inertia=True)

    upper = GRID * 0.4          # 上半区
    print(f"=== 该沉却没沉的分子（位于上半区 y < {upper:.0f}）===\n")

    for state in ("液", "固"):
        bad = [m for m in mols if m.state_simple == state and m.y < upper]
        if not bad:
            print(f"{state}: 没有残余")
            continue
        reasons = Counter()
        for m in bad:
            below = (m.x, m.y + 1)
            occ_below = grid.get(below)
            fx, fy = L.net_force(m, grid, G * (m.weight / L.W_MAX),
                                 decay=True, asym=True)
            speed = math.hypot(m.vx, m.vy)
            if occ_below is None:
                reasons["下方为空却没下去"] += 1
            elif occ_below.weight >= m.weight:
                reasons["下方比自己重或等重（该被挡住）"] += 1
            elif fy < 0:
                reasons["分子间力把它往上拽（净力朝上）"] += 1
            elif speed < 0.05:
                reasons["速度耗尽（惯性为零）"] += 1
            else:
                reasons["其他"] += 1
        print(f"{state}: 上半区残留 {len(bad)} 个 / 共 {sum(1 for m in mols if m.state_simple == state)}")
        for k, v in reasons.most_common():
            print(f"    {k}: {v} ({v/len(bad):.0%})")
        print()

    # 全局：重力 vs 分子间力的平均强度
    gs, ps = [], []
    for m in rng.sample(mols, 100):
        gs.append(G * (m.weight / L.W_MAX))
        fx, fy = L.net_force(m, grid, 0.0, decay=True, asym=True)
        ps.append(math.hypot(fx, fy))
    print(f"=== 力的量级 ===")
    print(f"  重力均值 {sum(gs)/len(gs):.3f}")
    print(f"  分子间合力均值 {sum(ps)/len(ps):.3f}  最大 {max(ps):.3f}")
    print(f"  比值（分子间/重力） {sum(ps)/len(ps)/(sum(gs)/len(gs)):.1f} 倍")

    # 下方被占的比例
    blocked = sum(1 for m in mols if grid.get((m.x, m.y + 1)) is not None) / len(mols)
    print(f"\n  下方格子被占的分子比例: {blocked:.0%}")


if __name__ == "__main__":
    main()
