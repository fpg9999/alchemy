# -*- coding: utf-8 -*-
"""生命普查 v2：用**结构持久性 + 整体移动**衡量"活性"，而不是分子抖动率。

判据（比流动率严格得多）
------------------------
每隔 10 tick 拍一张快照，找出"同种分子连通、成员 ≥ 8"的团；
相邻快照间按成员重叠（Jaccard ≥ 0.5）匹配，形成"团的生命链"。

- **持久结构**：链长 ≥ 10 张快照（100 tick）
- **移动结构**：该链的质心在生命周期内位移 ≥ 3 格
- **生命指数** = 既持久又移动的结构的数量

只抖动、不解体的世界 → 团不断换成员 → 链很短 → 指数为 0。

用法
----
    python examples/life_census.py
"""

from __future__ import annotations

import json
import math
import random
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lattice_sim as L  # noqa: E402

GRID = 36
FILL = 0.32
TICKS = 600
SNAP = 10
MIN_SIZE = 8
JACCARD = 0.5
MIN_AGE = 10
MIN_MOVE = 3.0
SEED = 20261120
L.GRID = GRID
L.FILL = FILL


def load_world(path: Path):
    d = json.loads(path.read_text(encoding="utf-8"))
    comp: dict[str, float] = {}
    if isinstance(d, dict) and "species" in d:
        for s in d["species"]:
            if s.get("in_catalog"):
                comp[s["formula"]] = comp.get(s["formula"], 0) + s.get("count", 1)
    elif isinstance(d, dict) and "final_composition" in d:
        for k, v in (d["final_composition"] or {}).items():
            if isinstance(v, dict):
                v = v.get("count") or v.get("abundance") or 0
            comp[str(k)] = float(v)
    return path.stem.replace("_result", ""), comp


def build(comp, n_target, rng):
    items = [(f, w) for f, w in comp.items() if w > 0]
    total = sum(w for _, w in items)
    mols = []
    for f, w in items:
        for _ in range(max(1, round(n_target * w / total))):
            mols.append(L.Mol(f, 0, 0))
    rng.shuffle(mols)
    mols = mols[:n_target]
    cells = [(x, y) for x in range(GRID) for y in range(GRID)]
    rng.shuffle(cells)
    for m, (x, y) in zip(mols, cells):
        m.x, m.y = x, y
    return {(m.x, m.y): m for m in mols}, mols


def snapshot(grid):
    """返回当前所有 ≥MIN_SIZE 的同种连通团的成员集合与质心。"""
    seen = set()
    out = []
    for (x, y), m in list(grid.items()):
        if (x, y) in seen:
            continue
        q, seen = deque([(x, y)]), seen | {(x, y)}
        mem = set()
        while q:
            cx, cy = q.popleft()
            mem.add((cx, cy))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if not (dx or dy):
                        continue
                    p = (cx + dx, cy + dy)
                    o = grid.get(p)
                    if o is not None and o.formula == m.formula and p not in seen:
                        seen.add(p)
                        q.append(p)
        if len(mem) >= MIN_SIZE:
            cx = sum(p[0] for p in mem) / len(mem)
            cy = sum(p[1] for p in mem) / len(mem)
            out.append({"mem": mem, "com": (cx, cy)})
    return out


def census(comp):
    rng = random.Random(SEED)
    n = int(GRID * GRID * FILL)
    grid, mols = build(comp, n, rng)

    chains: list[dict] = []
    alive: list[dict] = []
    for t in range(TICKS):
        L.step(grid, mols, rng)
        if (t + 1) % SNAP:
            continue
        snaps = snapshot(grid)
        used = set()
        new_alive = []
        for c in alive:
            best, bestj, bi = None, 0.0, -1
            for i, s in enumerate(snaps):
                if i in used:
                    continue
                inter = len(c["mem"] & s["mem"])
                union = len(c["mem"] | s["mem"])
                j = inter / union if union else 0.0
                if j > bestj:
                    bestj, best, bi = j, s, i
            if bestj >= JACCARD:
                used.add(bi)
                c["mem"] = best["mem"]
                c["coms"].append(best["com"])
                c["age"] += 1
                new_alive.append(c)
            else:
                chains.append(c)
        for i, s in enumerate(snaps):
            if i in used:
                continue
            c = {"mem": s["mem"], "coms": [s["com"]], "age": 1}
            new_alive.append(c)
        alive = new_alive
    chains.extend(alive)

    persistent = [c for c in chains if c["age"] >= MIN_AGE]
    moving = []
    for c in persistent:
        xs = [p[0] for p in c["coms"]]
        ys = [p[1] for p in c["coms"]]
        d = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
        if d >= MIN_MOVE:
            moving.append((c, d))
    return {"persistent": len(persistent), "moving": len(moving),
            "max_age": max((c["age"] for c in chains), default=0),
            "mols": mols, "grid": grid}


def main():
    worlds = []
    for p in sorted(Path("data/biomes").glob("*.json")):
        if p.name.startswith("_"):
            continue
        nm, comp = load_world(p)
        if comp:
            worlds.append((nm, comp))
    for p in sorted(Path(".").glob("t6*_biome_*_result.json")):
        nm, comp = load_world(p)
        if comp:
            worlds.append((nm, comp))

    print(f"{len(worlds)} 个世界 · 默认规则 · 判据：团≥{MIN_SIZE} 人、存活≥{MIN_AGE*SNAP} tick、位移≥{MIN_MOVE} 格\n")
    print(f"{'世界':22}{'持久结构':>9}{'其中移动':>9}{'最长寿命':>9}")
    rows = []
    for nm, comp in worlds:
        r = census(comp)
        r["name"] = nm
        rows.append(r)
        print(f"{nm[:20]:22}{r['persistent']:9}{r['moving']:9}{r['max_age']*SNAP:9}")

    alive = [r for r in rows if r["moving"] > 0]
    print(f"\n=== 出现「持久且移动」结构的世界 ===")
    if alive:
        for r in sorted(alive, key=lambda x: -x["moving"]):
            print(f"  {r['name'][:24]:26} 移动结构 {r['moving']} 个")
    print(f"\n比例: {len(alive)}/{len(rows)} = {len(alive)/len(rows):.0%}")


if __name__ == "__main__":
    main()
