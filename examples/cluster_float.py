# -*- coding: utf-8 -*-
"""诊断：团块漂浮是否正常？

两种可能：
A. **团块本身轻**（成员多为零质量分子）→ 漂浮合理
B. **团块被架住**（下方被零质量分子占住 / 被斥力托住）→ 反常

判据：看团的"平均权重"与"平均高度"是否相关。
若相关 → A（轻的浮、重的沉，符合重力）；
若不相关 → B（高度由别的原因决定）。
"""

from __future__ import annotations

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


def clusters_with_weight(grid, min_size=8):
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
            ws = [grid[p].weight for p in mem]
            ys = [p[1] for p in mem]
            out.append({"size": len(mem), "w": sum(ws) / len(ws),
                        "y": sum(ys) / len(ys),
                        "zero_frac": sum(1 for x in ws if x == 0) / len(ws)})
    return out


def main():
    comp = load_world("t62_phaseB")
    rng = random.Random(SEED)
    n = int(GRID * GRID * FILL)
    grid, mols = build(comp, n, rng)
    for _ in range(500):
        L.step(grid, mols, rng, inertia=True)

    cs = clusters_with_weight(grid)
    cs.sort(key=lambda c: -c["size"])
    print(f"=== t62_phaseB 稳定后的聚集体（≥8 成员）：{len(cs)} 个 ===")
    print(f"{'成员数':>6}{'平均权重':>10}{'平均高度':>10}{'零质量占比':>11}")
    for c in cs[:12]:
        print(f"{c['size']:6}{c['w']:10.2f}{c['y']:10.1f}{c['zero_frac']:11.0%}")

    # 相关性：平均权重 vs 平均高度（负相关才正常：重的在下）
    if len(cs) >= 3:
        ws = [c["w"] for c in cs]
        ys = [c["y"] for c in cs]
        mw, my = sum(ws) / len(ws), sum(ys) / len(ys)
        num = sum((a - mw) * (b - my) for a, b in zip(ws, ys))
        den = math.sqrt(sum((a - mw) ** 2 for a in ws) * sum((b - my) ** 2 for b in ys)) or 1
        print(f"\n  r(团平均权重, 团平均高度) = {num/den:+.2f}")

    # 对照：把所有零质量分子删掉，看剩下的团会不会沉
    print("\n=== 对照实验：删掉零质量分子后，保留分子的平均高度 ===")
    for tag, keep_zero in (("保留", True), ("删除", False)):
        rng2 = random.Random(SEED)
        grid2, mols2 = build(comp, n, rng2)
        if not keep_zero:
            mols2 = [m for m in mols2 if m.weight > 0]
            grid2 = {(m.x, m.y): m for m in mols2}
        for _ in range(500):
            L.step(grid2, mols2, rng2, inertia=True)
        ys = [m.y for m in mols2]
        print(f"  {tag}零质量分子: {len(mols2):3} 个, 平均高度 {sum(ys)/len(ys):5.1f}, "
              f"最高处 {min(ys)}")


if __name__ == "__main__":
    main()
