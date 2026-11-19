# -*- coding: utf-8 -*-
"""接入恒素场与反应层：第一个"有化学"的世界。

每 tick 的顺序：
    1. 恒素场扩散
    2. 分子与恒素场交互（热吸收 / 冷推开）
    3. 物理步进（沉降 / 铺平 / 分子间力）
    4. 反应扫描（相邻 + 恒素阈值 → 微观反应事件）
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


def main():
    world = sys.argv[1] if len(sys.argv) > 1 else "t62_phaseB"
    ticks = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    pool = dict(collect())
    comp = pool.get(world)
    if not comp:
        print("找不到世界", world)
        return

    rng = random.Random(SEED)
    grid, mols = build(comp, int(GRID * GRID * FILL), rng)
    ef = EField(GRID, init=0.6, diffuse=0.08)
    rl = ReactionLayer()

    print(f"世界 {world}：{len(mols)} 个分子，{len({m.formula for m in mols})} 种")
    print(f"恒素场初始均值 {ef.mean():.3f}\n")
    print(f"{'tick':>5}{'反应':>6}{'无变化':>8}{'物种数':>7}{'ρ_E均':>7}{'最大e_load':>11}")

    total_events = []
    for t in range(1, ticks + 1):
        ef.diffuse_step()
        ef.interact(mols)
        L.step(grid, mols, rng, gravity=1.0, inertia=True)
        events = rl.try_react(grid, mols, ef, rng, max_events=20)
        total_events.extend(events)
        if t % 10 == 0 or t == 1:
            maxe = max((getattr(m, "e_load", 0) for m in mols), default=0)
            print(f"{t:5}{rl.stats['fired']:6}{rl.stats['no_change']:8}"
                  f"{len({m.formula for m in mols}):7}{ef.mean():7.2f}{maxe:11.0f}")

    print(f"\n反应统计: {rl.stats}")
    print(f"总事件 {len(total_events)}")
    if total_events:
        for e in total_events[:8]:
            print(f"  {e['reactants'][0]} + {e['reactants'][1]} → {' + '.join(e['products'])}")
    L.render(mols, f"images/reaction_{world}.png", by_state=False)
    print(f"\n图: images/reaction_{world}.png")


if __name__ == "__main__":
    main()
