# -*- coding: utf-8 -*-
"""世界终态快照：按分子种类着色，看它们最终停在什么结构。

选取 8 个代表性世界，跑 800 tick 到完全静止后渲染。
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
SEED = 20261120

WORLDS = [
    "t55_kinetic",     # 单一物种
    "t63_phase2",      # 纯吸引三方
    "t59_phaseA",      # 无聚类
    "t62_phaseA",      # 典型双主
    "t64_biome_B11",   # 24 种
    "t65_biome_C06",   # 91% 等重
    "t66_biome_E10",   # 29 种
    "t58",             # 101 种，最多样
]


def main():
    from PIL import Image, ImageDraw
    pool = dict(collect())
    cell = 300
    cols = 4
    rows_n = (len(WORLDS) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows_n * (cell + 22)), (255, 255, 255))
    d = ImageDraw.Draw(sheet)

    for i, nm in enumerate(WORLDS):
        comp = pool.get(nm)
        if not comp:
            print(f"{nm}: 无数据")
            continue
        rng = random.Random(SEED)
        grid, mols = build(comp, int(GRID * GRID * FILL), rng)
        for _ in range(800):
            L.step(grid, mols, rng, gravity=1.0, inertia=True)
        path = f"images/final_{nm}.png"
        L.render(mols, path, by_state=False)
        n_sp = len({m.formula for m in mols})
        top = max({m.formula for m in mols},
                  key=lambda f: sum(1 for m in mols if m.formula == f))
        share = sum(1 for m in mols if m.formula == top) / len(mols)
        print(f"{nm:20} {n_sp:3} 种  主导 {top}({share:.0%})")
        ox, oy = (i % cols) * cell, (i // cols) * (cell + 22)
        sheet.paste(Image.open(path).resize((cell, cell)), (ox, oy))
        d.text((ox + 5, oy + cell + 4),
               f"{nm}  {n_sp} 种", fill=(0, 0, 0))

    sheet.save("images/final_worlds.png")
    print("\n图: images/final_worlds.png")


if __name__ == "__main__":
    main()
