# -*- coding: utf-8 -*-
"""观察：引入反应后世界如何变化。

跑一个世界，记录物种数、反应事件、恒素地形，并输出连续快照。
"""
from __future__ import annotations

import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lattice_sim as L
from alchemy.efield import EField
from alchemy.reaction import ReactionLayer
from flow_census import collect, build, GRID, FILL

L.GRID = GRID
L.FILL = FILL
SEED = 20261120
FRAMES = [0, 60, 120, 200, 300, 400]


def main():
    world = sys.argv[1] if len(sys.argv) > 1 else "t62_phaseB"
    ticks = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    comp = dict(collect()).get(world)
    if not comp:
        print("找不到世界", world)
        return

    rng = random.Random(SEED)
    grid, mols = build(comp, int(GRID * GRID * FILL), rng)
    ef = EField(GRID, init=2.0, diffuse=0.08)
    rl = ReactionLayer()
    start_forms = Counter(m.formula for m in mols)

    from PIL import Image, ImageDraw
    cell = 260
    frames = []
    print(f"世界 {world} · {len(mols)} 分子 · {len(start_forms)} 种 · 初始 ρ_E = 2.0\n")
    print(f"{'tick':>5}{'反应':>6}{'低于阈值':>9}{'物种':>6}{'ρ最小':>8}{'ρ最大':>8}{'分子数':>7}")

    def snap(t):
        p = f"images/obs_{world}_{t}.png"
        L.render(mols, p, by_state=False)
        frames.append((t, p))

    for t in range(ticks + 1):
        if t in FRAMES:
            snap(t)
        if t == ticks:
            break
        ef.diffuse_step()
        ef.interact(mols)
        L.step(grid, mols, rng, gravity=1.0, inertia=True)
        rl.try_react(grid, mols, ef, rng, max_events=20)
        if t and t % 50 == 40:
            vals = [ef.rho[y][x] for y in range(GRID) for x in range(GRID)]
            print(f"{t:5}{rl.stats['fired']:6}{rl.stats['below_threshold']:9}"
                  f"{len({m.formula for m in mols}):6}{min(vals):8.2f}{max(vals):8.2f}"
                  f"{len(mols):7}")

    end_forms = Counter(m.formula for m in mols)
    print(f"\n=== 物种变化 ===")
    print(f"初始 {len(start_forms)} 种 → 最终 {len(end_forms)} 种")
    new = set(end_forms) - set(start_forms)
    gone = set(start_forms) - set(end_forms)
    if new:
        print("新出现: " + ", ".join(sorted(new)[:10]))
    if gone:
        print("消失: " + ", ".join(sorted(gone)[:10]))
    print("\n最终主要成分:")
    for f, c in end_forms.most_common(6):
        print(f"  {f:16} {c:4} 个 ({c/len(mols):.0%})")

    # 拼图
    cols = len(frames)
    sheet = Image.new("RGB", (cols * cell, cell + 20), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    for i, (t, p) in enumerate(frames):
        sheet.paste(Image.open(p).resize((cell, cell)), (i * cell, 0))
        d.text((i * cell + 5, cell + 4), f"t={t}", fill=(0, 0, 0))
    sheet.save(f"images/obs_{world}_strip.png")
    print(f"\n图: images/obs_{world}_strip.png")


if __name__ == "__main__":
    main()
