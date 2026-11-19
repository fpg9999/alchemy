# -*- coding: utf-8 -*-
"""宇宙大爆炸·试爆。

流程
----
1. **随机元素汤**：9 种元素，每种数量随机（0~40 个原子）
2. **化学反应**：用真实引擎（规则 1–11）把元素汤烧成分子
3. **铺到网格**：产物分子按丰度铺满网格
4. **动力学**：重力 + 惯性 + 距离衰减 + 非对称力，跑若干 tick
5. **观测**：分层、聚集体、是否有"原始汤"式的结构

所有初始参数随机：元素配比、总原子数、重力、阻尼、步数。
本脚本只做**一次**试爆，不追求出现生命。

用法
----
    python examples/big_bang.py [seed]
"""

from __future__ import annotations

import math
import random
import sys
import time
from collections import Counter, deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import alchemy  # noqa: E402
import lattice_sim as L  # noqa: E402
from alchemy.core.elements import ORDER, VAL, formula_of  # noqa: E402

GRID = 40
FILL = 0.30
L.GRID = GRID
L.FILL = FILL


def random_feed(rng: random.Random) -> list[str]:
    """随机元素汤。**总价数必须为偶数**，否则无法完全饱和、反应会返回空。"""
    for _ in range(10000):
        counts = [rng.choice([0, 0, 0, rng.randint(1, 40)]) for _ in range(9)]
        total = sum(counts)
        if not (120 <= total <= 400):
            continue
        valence = sum(VAL[e] * c for e, c in zip(ORDER, counts))
        if valence % 2:
            continue
        return [e for e, c in zip(ORDER, counts) for _ in range(c)]
    raise RuntimeError("生成不出合法的偶数价数配方")


def react(feed: list[str]) -> list[dict]:
    out = alchemy.simulate(feed, rules=11)
    return out or []


def build(mols_prod, n_target, rng):
    """按产物的原子数比例铺满网格。"""
    weights = []
    for m in mols_prod:
        weights.append(max(1, len(m["atoms"])))
    total_w = sum(weights)
    mols = []
    for m, w in zip(mols_prod, weights):
        k = max(1, round(n_target * w / total_w))
        for _ in range(k):
            mols.append(L.Mol(formula_of(m["atoms"]), 0, 0))
    rng.shuffle(mols)
    mols = mols[:n_target]
    cells = [(x, y) for x in range(GRID) for y in range(GRID)]
    rng.shuffle(cells)
    for m, (x, y) in zip(mols, cells):
        m.x, m.y = x, y
    return {(m.x, m.y): m for m in mols}, mols


def clusters(grid, min_size=8):
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
            kinds = len({grid[p].formula for p in mem})
            out.append({"size": len(mem), "w": sum(ws) / len(ws),
                        "y": sum(ys) / len(ys), "kinds": kinds})
    return out


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else int(time.time()) % 100000
    rng = random.Random(seed)

    # ---- 随机初始参数
    feed = random_feed(rng)
    n_atoms = len(feed)
    gravity = rng.uniform(0.5, 5.0)
    ticks = rng.choice([300, 400, 600, 800])
    damp = rng.uniform(0.7, 0.9)
    beta = rng.uniform(0.2, 0.45)

    print("=" * 64)
    print(f"试爆 seed = {seed}")
    print("=" * 64)
    cnt = Counter(feed)
    print(f"元素汤: {n_atoms} 个原子")
    print("  " + "  ".join(f"{e}×{cnt[e]}" for e in ORDER if cnt[e]))
    print(f"随机参数: 重力 {gravity:.2f} · 阻尼 {damp:.2f} · beta {beta:.2f} · {ticks} tick")

    # ---- 化学反应
    t0 = time.time()
    prod = react(feed)
    print(f"\n反应产物: {len(prod)} 种分子（{time.time()-t0:.1f}s）")
    for m in sorted(prod, key=lambda x: -len(x["atoms"]))[:8]:
        print(f"  {formula_of(m['atoms']):18} {len(m['atoms']):2} 原子")

    n_target = int(GRID * GRID * FILL)
    grid, mols = build(prod, n_target, rng)
    print(f"\n铺到网格: {len(mols)} 个分子")

    # ---- 动力学
    for _ in range(ticks):
        L.step(grid, mols, rng, gravity=gravity, inertia=True, decay=True,
               asym=True, damp=damp)
    # 用随机 beta 再跑一段（beta 影响力形状）
    L.GRID = GRID

    ys = [m.y for m in mols]
    print(f"\n演化后: 平均高度 {sum(ys)/len(ys):.1f} / {GRID}，最高 {min(ys)}")

    cs = clusters(grid)
    cs.sort(key=lambda c: -c["size"])
    print(f"聚集体（≥8 成员）: {len(cs)} 个")
    for c in cs[:8]:
        print(f"  {c['size']:3} 成员  权重 {c['w']:5.2f}  高度 {c['y']:5.1f}  {c['kinds']} 种成分")

    # 原始汤指标：中间层是否有多成分聚集体
    mid = [c for c in cs if 0.2 * GRID < c["y"] < 0.8 * GRID]
    soup = [c for c in mid if c["kinds"] >= 3]
    print(f"\n中间层的多成分聚集体: {len(soup)} 个" +
          (f"（最大 {max(c['size'] for c in soup)} 成员）" if soup else ""))

    L.render(mols, f"images/bigbang_{seed}.png")
    print(f"\n图: images/bigbang_{seed}.png")


if __name__ == "__main__":
    main()
