# -*- coding: utf-8 -*-
"""按物质类别着色：看三类粒子（聚主导 / 动主导 / 散主导）如何分布。

类别判定：比较该分子三个类别元素特征值之和，最大者为主导类别。
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
from alchemy.core.elements import ORDER, VAL, parse_formula  # noqa: E402
from lattice_weight import load_world, build, GRID, FILL, SEED  # noqa: E402

L.GRID = GRID
L.FILL = FILL

CAT_COLOR = {
    "聚": (70, 185, 91),       # 绿
    "动": (59, 111, 212),      # 蓝
    "散": (245, 166, 35),      # 橙
    "均衡": (150, 150, 150),   # 灰
}


def cat_of(formula: str) -> str:
    v = parse_formula(formula)
    g = {e: v[ORDER.index(e)] for e in ORDER}
    sp = sum(VAL[e] * g[e] for e in ("O", "X", "C"))
    sm = sum(VAL[e] * g[e] for e in ("P", "W", "L"))
    ss = sum(VAL[e] * g[e] for e in ("K", "A", "F"))
    best = max(sp, sm, ss)
    winners = [n for n, s in (("聚", sp), ("动", sm), ("散", ss)) if s == best]
    if len(winners) > 1 or best == 0:
        return "均衡"
    return winners[0]


def render(mols, path, scale=8):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (GRID * scale, GRID * scale), (252, 252, 252))
    d = ImageDraw.Draw(img)
    cache = {}
    for m in mols:
        if m.formula not in cache:
            cache[m.formula] = CAT_COLOR[cat_of(m.formula)]
        c = cache[m.formula]
        d.rectangle([m.x * scale, m.y * scale,
                     m.x * scale + scale - 1, m.y * scale + scale - 1], fill=c)
    img.save(path)


def main():
    comp = load_world("t62_phaseB")
    rng = random.Random(SEED)
    n = int(GRID * GRID * FILL)
    grid, mols = build(comp, n, rng)
    for _ in range(600):
        L.step(grid, mols, rng, gravity=1.0, inertia=True)

    cats = [cat_of(m.formula) for m in mols]
    print("=== 三类粒子的分布（t62_phaseB，稳定态）===\n")
    print(f"{'类别':6}{'数量':>6}{'占比':>7}{'平均高度':>9}{'质量(平均)':>11}{'物态构成':>22}")
    for c in ("聚", "动", "散", "均衡"):
        idx = [i for i, x in enumerate(cats) if x == c]
        if not idx:
            continue
        ys = [mols[i].y for i in idx]
        ws = [mols[i].mass_val for i in idx]
        states = Counter(mols[i].state_simple for i in idx)
        ss = " ".join(f"{k}{v}" for k, v in states.most_common())
        print(f"{c:6}{len(idx):6}{len(idx)/len(mols):7.0%}"
              f"{sum(ys)/len(ys):9.1f}{sum(ws)/len(ws):11.2f}{ss:>22}")

    print("\n=== 各物态里三类粒子的占比 ===")
    print(f"{'物态':6}" + "".join(f"{c:>8}" for c in ("聚", "动", "散", "均衡")))
    for s in ("固", "液", "气"):
        sub = [cat_of(m.formula) for m in mols if m.state_simple == s]
        if not sub:
            continue
        cnt = Counter(sub)
        print(f"{s:6}" + "".join(f"{cnt.get(c,0)/len(sub):8.0%}" for c in ("聚", "动", "散", "均衡")))

    render(mols, "images/by_category.png")
    print("\n图: images/by_category.png（绿=聚 蓝=动 橙=散 灰=均衡）")


if __name__ == "__main__":
    main()
