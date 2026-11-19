# -*- coding: utf-8 -*-
"""种子搜索：哪些"大爆炸元素汤"会长出活世界？

流程
----
1. 随机元素汤（总价数为偶数）
2. 真实反应引擎 → 分子组成
3. 快速判定：主导物种占比 < 50% 才有可能是活世界
4. 通过初筛的，用网格模拟实测流动率

用法
----
    python examples/seed_search.py [样本数]
"""
from __future__ import annotations

import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import alchemy
import lattice_sim as L
from alchemy.core.elements import ORDER, VAL, formula_of
from flow_census import GRID, FILL

L.GRID = GRID
L.FILL = FILL
N = int(GRID * GRID * FILL)


def random_feed(rng):
    for _ in range(10000):
        counts = [rng.choice([0, 0, 0, rng.randint(1, 40)]) for _ in range(9)]
        total = sum(counts)
        if not (100 <= total <= 400):
            continue
        if sum(VAL[e] * c for e, c in zip(ORDER, counts)) % 2:
            continue
        return counts
    raise RuntimeError


def react(counts):
    atoms = [e for e, c in zip(ORDER, counts) for _ in range(c)]
    out = alchemy.simulate(atoms, rules=11)
    if not out:
        return None
    comp = Counter(formula_of(m["atoms"]) for m in out)
    tot = sum(comp.values())
    return {k: v / tot for k, v in comp.items()}


def build(comp, rng):
    mols = []
    for f, w in comp.items():
        for _ in range(max(1, round(N * w))):
            mols.append(L.Mol(f, 0, 0))
    rng.shuffle(mols)
    mols = mols[:N]
    cells = [(x, y) for x in range(GRID) for y in range(GRID)]
    rng.shuffle(cells)
    for m, (x, y) in zip(mols, cells):
        m.x, m.y = x, y
    return {(m.x, m.y): m for m in mols}, mols


def measure(comp, ticks=300):
    rng = random.Random(20261120)
    grid, mols = build(comp, rng)
    for _ in range(ticks):
        L.step(grid, mols, rng, gravity=1.0, inertia=True)
    prev = {id(m): (m.x, m.y) for m in mols}
    moved = 0
    for _ in range(30):
        L.step(grid, mols, rng, gravity=1.0, inertia=True)
        for m in mols:
            if (m.x, m.y) != prev[id(m)]:
                moved += 1
                prev[id(m)] = (m.x, m.y)
    return moved / 30 / len(mols)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    rng = random.Random(int(time.time()) % 100000)
    seeds = []
    print(f"搜索 {n} 个随机元素汤……\n")
    print(f"{'#':>3}{'原子数':>6}{'产物种':>6}{'主导占比':>8}{'流动率':>8}  主导分子")
    for i in range(1, n + 1):
        counts = random_feed(rng)
        comp = react(counts)
        if not comp:
            continue
        dom = max(comp.values())
        domf = max(comp, key=comp.get)
        if dom >= 0.5:
            print(f"{i:3}{sum(counts):6}{len(comp):6}{dom:8.0%}{'-':>8}  {domf}")
            continue
        fl = measure(comp)
        tag = "活" if fl >= 0.05 else ""
        print(f"{i:3}{sum(counts):6}{len(comp):6}{dom:8.0%}{fl:8.2%}  {domf} {tag}")
        if fl >= 0.05:
            seeds.append((counts, comp, fl))
    print(f"\n=== 找到 {len(seeds)} 个活世界种子 ===")
    for counts, comp, fl in sorted(seeds, key=lambda s: -s[2]):
        feed = {e: c for e, c in zip(ORDER, counts) if c}
        print(f"\n流动率 {fl:.1%}  组成 {len(comp)} 种")
        print(f"  元素汤: {feed}")
        print(f"  主要产物: " + ", ".join(
            f"{k}({v:.0%})" for k, v in sorted(comp.items(), key=lambda kv: -kv[1])[:5]))
    if seeds:
        out = [{"feed": dict(zip(ORDER, c)), "flow": f,
                "comp": comp} for c, comp, f in seeds]
        Path("reports/living_seeds.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print("\n已保存 reports/living_seeds.json")


if __name__ == "__main__":
    main()
