# -*- coding: utf-8 -*-
"""团块存活测试：人工播种一个分子团，看它能否作为整体稳定存在并移动。

判据
----
- **保持紧凑**：成员的平均半径不随时间膨胀
- **整体移动**：质心位移显著
- **成员留存**：原本的成员没被替换掉（用 id 追踪）

对照组
------
- 单质团（同一种分子）→ 预期不成立
- 平衡混合团（多种互相吸引/排斥的分子交错）→ 预期成立
- 吸引+排斥对（一个拉、一个推）
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lattice_sim as L

GRID = 48
L.GRID = GRID
L.FILL = 0.30
SEED = 20261120


def seed_cluster(kinds, cx, cy, size=6, background=None, bg_density=0.0,
                 rng=None):
    """在 (cx,cy) 处铺一个 size×size 的团，分子种类按 kinds 循环交错。"""
    rng = rng or random.Random(SEED)
    grid = {}
    mols = []
    half = size // 2
    for i in range(size):
        for j in range(size):
            f = kinds[(i + j) % len(kinds)]
            m = L.Mol(f, cx - half + i, cy - half + j)
            grid[(m.x, m.y)] = m
            mols.append(m)
    if background:
        n_bg = int(GRID * GRID * bg_density)
        placed = 0
        while placed < n_bg:
            x, y = rng.randrange(GRID), rng.randrange(GRID)
            if (x, y) in grid:
                continue
            f = background[rng.randrange(len(background))]
            m = L.Mol(f, x, y)
            grid[(x, y)] = m
            mols.append(m)
            placed += 1
    return grid, mols


def track(cluster_members, ticks=200, gravity=0.0):
    rng = random.Random(SEED)
    grid, mols = seed_cluster(
        [m.formula for m in cluster_members], GRID // 2, GRID // 2)
    # 上面的 seed_cluster 会创建新对象；这里重建以保留引用
    return grid, mols


def run(kinds, size=6, ticks=200, gravity=0.0, background=None, bg_density=0.0):
    rng = random.Random(SEED)
    grid = {}
    mols = []
    members = []
    cx, cy = GRID // 2, GRID // 2
    half = size // 2
    for i in range(size):
        for j in range(size):
            f = kinds[(i + j) % len(kinds)]
            m = L.Mol(f, cx - half + i, cy - half + j)
            grid[(m.x, m.y)] = m
            mols.append(m)
            members.append(m)
    if background:
        n_bg = int(GRID * GRID * bg_density)
        placed = 0
        while placed < n_bg:
            x, y = rng.randrange(GRID), rng.randrange(GRID)
            if (x, y) in grid:
                continue
            m = L.Mol(background[rng.randrange(len(background))], x, y)
            grid[(x, y)] = m
            mols.append(m)
            placed += 1

    cx0 = sum(m.x for m in members) / len(members)
    cy0 = sum(m.y for m in members) / len(members)
    r0 = math.sqrt(sum((m.x - cx0) ** 2 + (m.y - cy0) ** 2
                       for m in members) / len(members))

    for _ in range(ticks):
        L.step(grid, mols, rng, gravity=gravity, inertia=True)

    alive = [m for m in members if grid.get((m.x, m.y)) is m]
    if not alive:
        return {"survive": 0.0, "disp": 0.0, "radius_ratio": float("nan"),
                "members": 0}
    cx1 = sum(m.x for m in alive) / len(alive)
    cy1 = sum(m.y for m in alive) / len(alive)
    r1 = math.sqrt(sum((m.x - cx1) ** 2 + (m.y - cy1) ** 2
                       for m in alive) / len(alive))
    return {"survive": len(alive) / len(members),
            "disp": math.hypot(cx1 - cx0, cy1 - cy0),
            "radius_ratio": r1 / r0 if r0 else float("nan"),
            "members": len(alive)}


def main():
    CASES = {
        "单质团 OXC": ["OXC"],
        "单质团 OXCPWKA": ["OXCPWKA"],
        "二种交错 OK/L2": ["OK", "L2"],
        "二种交错 OXC/LF": ["OXC", "LF"],
        "平衡混合": ["O2XP2WK2A2", "OXPWKAF", "PK", "O2XP2WK2A"],
        "强平衡混合": ["O9X11CK14A4", "PK", "O2XP2WK2A2", "L2"],
    }
    print(f"网格 {GRID}×{GRID}，团块 6×6=36 个分子，跑 200 tick\n")
    for g in (0.0, 1.0):
        print(f"=== 重力 {g} ===")
        print(f"{'团块类型':22}{'留存':>7}{'质心位移':>9}{'半径变化':>9}")
        for label, kinds in CASES.items():
            r = run(kinds, gravity=g)
            print(f"{label:22}{r['survive']:7.0%}{r['disp']:9.1f}{r['radius_ratio']:9.2f}")
        print()


if __name__ == "__main__":
    main()
