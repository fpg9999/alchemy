# -*- coding: utf-8 -*-
"""流动性普查：等重可交换时，有多少世界会变成"流动的汤"。"""
import sys
import random
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, "examples")

import json
import lattice_sim as L
from alchemy.core.elements import ORDER, parse_formula
from alchemy.attrs import MASS_W

GRID = 36
FILL = 0.32
L.GRID = GRID
L.FILL = FILL


def mass_of(f):
    v = parse_formula(f)
    g = {e: v[ORDER.index(e)] for e in ORDER}
    n3 = sum(g[e] for e in ("O", "K", "P"))
    return (sum(MASS_W[e] * g[e] for e in ("O", "K", "P")) / n3) if n3 else 0.0


def build(comp, n, rng):
    items = [(f, w) for f, w in comp.items() if w > 0]
    tot = sum(w for _, w in items)
    mols = []
    for f, w in items:
        for _ in range(max(1, round(n * w / tot))):
            mols.append(L.Mol(f, 0, 0))
    rng.shuffle(mols)
    mols = mols[:n]
    cells = [(x, y) for x in range(GRID) for y in range(GRID)]
    rng.shuffle(cells)
    for m, (x, y) in zip(mols, cells):
        m.x, m.y = x, y
    return {(m.x, m.y): m for m in mols}, mols


def eqprob(comp):
    tot = sum(comp.values())
    byw = {}
    for f, c in comp.items():
        k = round(mass_of(f), 4)
        byw[k] = byw.get(k, 0) + c
    return sum((c / tot) ** 2 for c in byw.values()) if tot else 0


def read_comp(p: Path):
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    comp = {}
    if isinstance(d, dict) and "species" in d:
        for s in d["species"]:
            if s.get("in_catalog"):
                comp[s["formula"]] = comp.get(s["formula"], 0) + s.get("count", 1)
    elif isinstance(d, dict) and "final_composition" in d:
        for k, v in (d["final_composition"] or {}).items():
            if isinstance(v, dict):
                v = v.get("count") or v.get("abundance") or 0
            comp[str(k)] = float(v)
    return comp or None


def collect():
    worlds = []
    for p in sorted(Path("data/biomes").glob("*.json")):
        if p.name.startswith("_"):
            continue
        c = read_comp(p)
        if c:
            worlds.append((p.stem, c))
    for p in sorted(Path(".").glob("t6*_biome_*_result.json")):
        c = read_comp(p)
        if c:
            worlds.append((p.stem.replace("_result", ""), c))
    return worlds


def main():
    worlds = collect()
    print(f"{len(worlds)} 个世界 · 等重可交换 · 物态不参与物理\n")
    print(f"{'世界':20}{'物种':>5}{'不同权重':>7}{'等重概率':>8}{'每tick移动':>10}{'占比':>7}{'同种邻接':>8}")
    rows = []
    for nm, comp in worlds:
        rng = random.Random(20261120)
        n = int(GRID * GRID * FILL)
        grid, mols = build(comp, n, rng)
        for _ in range(600):
            L.step(grid, mols, rng, gravity=1.0, inertia=True)
        prev = {id(m): (m.x, m.y) for m in mols}
        moved = 0
        for _ in range(50):
            L.step(grid, mols, rng, gravity=1.0, inertia=True)
            for m in mols:
                if (m.x, m.y) != prev[id(m)]:
                    moved += 1
                    prev[id(m)] = (m.x, m.y)
        rate = moved / 50 / len(mols)
        same = diff = 0
        for (x, y), m in grid.items():
            for dx, dy in ((1, 0), (0, 1)):
                o = grid.get((x + dx, y + dy))
                if o is None:
                    continue
                if o.formula == m.formula:
                    same += 1
                else:
                    diff += 1
        sn = same / (same + diff) if same + diff else 0
        ws = len({round(mass_of(f), 4) for f in comp})
        ep = eqprob(comp)
        rows.append((nm, len(comp), ws, ep, rate, sn))
        print(f"{nm[:18]:20}{len(comp):5}{ws:7}{ep:8.0%}{moved/50:10.1f}{rate:7.1%}{sn:8.1%}")

    print("\n=== 流动性分布 ===")
    buckets = {"稳定 (<5%)": 0, "轻微 (5-15%)": 0, "活跃 (15-30%)": 0, "流动的汤 (>30%)": 0}
    for r in rows:
        rate = r[4]
        if rate < 0.05:
            buckets["稳定 (<5%)"] += 1
        elif rate < 0.15:
            buckets["轻微 (5-15%)"] += 1
        elif rate < 0.30:
            buckets["活跃 (15-30%)"] += 1
        else:
            buckets["流动的汤 (>30%)"] += 1
    for k, v in buckets.items():
        print(f"  {k}: {v} 个世界 ({v/len(rows):.0%})")


if __name__ == "__main__":
    main()
