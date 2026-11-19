# -*- coding: utf-8 -*-
"""活世界的长期观察：t63_phase2（最活跃）与 t62_phaseB。

观察项
------
- 流动率是否稳定，还是会衰减/爆发
- 结构是否自组织（同种聚集度、空间密度方差）
- 是否出现持久的局部有序区
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lattice_sim as L
from flow_census import collect, build, GRID, FILL

L.GRID = GRID
L.FILL = FILL
TICKS = 2000
SAMPLE = 100
SEED = 20261120


def metrics(grid, mols, prev):
    moved = 0
    for m in mols:
        if (m.x, m.y) != prev[id(m)]:
            moved += 1
            prev[id(m)] = (m.x, m.y)
    # 同种邻接
    same = diff = 0
    for (x, y), m in grid.items():
        for dx, dy in ((1, 0), (0, 1)):
            o = grid.get((x + dx, y + dy))
            if o is None:
                continue
            same += (o.formula == m.formula)
            diff += (o.formula != m.formula)
    sn = same / (same + diff) if same + diff else 0
    # 密度方差（12×12 网格）
    cnt = [0] * 144
    for m in mols:
        cnt[(m.y // 3) * 12 + (m.x // 3)] += 1
    mu = sum(cnt) / 144
    var = sum((c - mu) ** 2 for c in cnt) / 144
    return moved / len(mols), sn, var


def main():
    world = sys.argv[1] if len(sys.argv) > 1 else "t63_phase2"
    pool = dict(collect())
    comp = pool[world]
    rng = random.Random(SEED)
    grid, mols = build(comp, int(GRID * GRID * FILL), rng)

    from PIL import Image, ImageDraw
    frames = []
    prev = {id(m): (m.x, m.y) for m in mols}
    print(f"世界 {world} · {len(mols)} 分子 · {len({m.formula for m in mols})} 种\n")
    print(f"{'tick':>6}{'流动率':>8}{'同种邻接':>9}{'密度方差':>9}{'物种数':>7}")

    for t in range(1, TICKS + 1):
        L.step(grid, mols, rng, gravity=1.0, inertia=True)
        if t % SAMPLE == 0:
            flow, sn, var = metrics(grid, mols, prev)
            print(f"{t:6}{flow:8.2%}{sn:9.1%}{var:9.1f}"
                  f"{len({m.formula for m in mols}):7}")
            if t in (SAMPLE, 500, 1000, 1500, 2000):
                p = f"images/long_{world}_{t}.png"
                L.render(mols, p, by_state=False)
                frames.append((t, p))

    cols = len(frames)
    cell = 240
    sheet = Image.new("RGB", (cols * cell, cell + 20), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    for i, (t, p) in enumerate(frames):
        sheet.paste(Image.open(p).resize((cell, cell)), (i * cell, 0))
        d.text((i * cell + 5, cell + 4), f"t={t}", fill=(0, 0, 0))
    sheet.save(f"images/long_{world}_strip.png")
    print(f"\n图: images/long_{world}_strip.png")


if __name__ == "__main__":
    main()
