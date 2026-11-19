# -*- coding: utf-8 -*-
"""侧向铺平效果：测量液体表面的粗糙度。

粗糙度 = 各列"液体最高点"的标准差。越小 = 越接近水平面。
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lattice_sim as L  # noqa: E402
from lattice_weight import load_world, build, GRID, FILL, SEED  # noqa: E402

L.GRID = GRID
L.FILL = FILL


def surface_roughness(mols, state="液"):
    """每列该物态的最高点（最小 y），返回标准差。"""
    tops = {}
    for m in mols:
        if m.state_simple != state:
            continue
        if m.x not in tops or m.y < tops[m.x]:
            tops[m.x] = m.y
    if len(tops) < 3:
        return float("nan")
    vs = list(tops.values())
    mu = sum(vs) / len(vs)
    return math.sqrt(sum((v - mu) ** 2 for v in vs) / len(vs))


def main():
    comp = load_world("t62_phaseB")
    print(f"网格 {GRID} · g=1.0 · 重力累积 · 600 tick\n")
    print(f"{'配置':22}{'液面粗糙度':>11}{'气面粗糙度':>11}{'液残留':>7}{'底1/4':>8}")
    for flatten in (False, True):
        rng = random.Random(SEED)
        n = int(GRID * GRID * FILL)
        grid, mols = build(comp, n, rng)
        for _ in range(600):
            L.step(grid, mols, rng, gravity=1.0, inertia=True,
                   pressure=True, settle_priority=True, flatten=flatten)
        liq_r = surface_roughness(mols, "液")
        gas_r = surface_roughness(mols, "气")
        res = sum(1 for m in mols if m.state_simple == "液" and m.y < 24)
        ys = [m.y for m in mols]
        bot = sum(1 for y in ys if y >= GRID * 3 // 4) / len(ys)
        tag = "侧向铺平" if flatten else "不铺平（对照）"
        print(f"{tag:22}{liq_r:11.2f}{gas_r:11.2f}{res:7}{bot:8.1%}")
        L.render(mols, f"images/flat_{'on' if flatten else 'off'}.png")
    print("\n图: images/flat_on.png / flat_off.png")


if __name__ == "__main__":
    main()
