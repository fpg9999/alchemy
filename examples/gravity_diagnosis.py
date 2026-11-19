# -*- coding: utf-8 -*-
"""诊断：为什么粒子还在漂浮？

三个可能原因：
1. **零质量分子**：没有三价原子的分子 mass=0 → weight=0 → 完全不受重力
2. **重力太弱**：重力量级 vs 分子间力量级
3. **空间占位**：下方被占住无法下沉
"""

from __future__ import annotations

import json
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


def main():
    comp = load_world("t62_phaseB")
    rng = random.Random(SEED)
    n = int(GRID * GRID * FILL)
    grid, mols = build(comp, n, rng)

    print("=== 1. 权重分布 ===")
    w = [m.weight for m in mols]
    zero = sum(1 for x in w if x == 0.0)
    print(f"  分子数 {len(mols)}   权重为 0 的: {zero} ({zero/len(mols):.1%})")
    print(f"  权重范围 {min(w):.2f} ~ {max(w):.2f}   均值 {sum(w)/len(w):.2f}")
    c = Counter((m.state_simple, round(m.mass_val, 1), round(m.weight, 1)) for m in mols)
    print("  主要组合（物态, 质量, 权重）:")
    for k, v in c.most_common(6):
        print(f"    {k}  ×{v}")

    print("\n=== 2. 重力 vs 分子间力的量级 ===")
    g_force = [L.DEFAULT_GRAVITY * (m.weight / L.W_MAX) for m in mols]
    print(f"  重力: 均值 {sum(g_force)/len(g_force):.3f}  最大 {max(g_force):.3f}")
    # 抽样估计分子间合力
    mags = []
    for m in rng.sample(mols, 80):
        fx, fy = L.net_force(m, grid, 0.0, decay=True, asym=True)   # 不含重力
        mags.append(math.hypot(fx, fy))
    print(f"  分子间合力: 均值 {sum(mags)/len(mags):.3f}  最大 {max(mags):.3f}")

    print("\n=== 3. 加大重力会怎样 ===")
    for g in (1.0, 3.0, 8.0, 20.0):
        rng2 = random.Random(SEED)
        grid2, mols2 = build(comp, n, rng2)
        for _ in range(400):
            L.step(grid2, mols2, rng2, gravity=g, inertia=True)
        ys = [m.y for m in mols2]
        empty_top = sum(1 for y in range(GRID // 2)
                        if not any(m.y == y for m in mols2))
        print(f"  g={g:5.1f}  平均高度 {sum(ys)/len(ys):5.1f}  "
              f"上半区空行数 {empty_top}/{GRID//2}  "
              f"最高处有分子的行 {min(ys)}")


if __name__ == "__main__":
    main()
