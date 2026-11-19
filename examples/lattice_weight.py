# -*- coding: utf-8 -*-
"""新分层规则实验：权重 = 物态基底 + 连续质量（固体 > 液体 > 气体）。

默认规则：网格 + 重力常开 + 惯性 + 距离衰减 + 非对称力。

观测量
------
- **分层是否正确**：重物是否都在下方、轻物是否都在上方
- **物态排序**：固/液/气 的平均高度是否满足 固 < 液 < 气（y 越小越靠上）
- **活性**：是否存在"非贴边、持续移动、成分混合"的聚集体

用法
----
    python examples/lattice_weight.py
"""

from __future__ import annotations

import json
import math
import random
import sys
from collections import Counter, deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lattice_sim as L  # noqa: E402

GRID = 36
FILL = 0.32
TICKS = 500
SNAP = 10
SEED = 20261120
L.GRID = GRID
L.FILL = FILL


def load_world(name: str):
    p = Path("data/biomes") / f"{name}.json"
    if not p.exists():
        p = Path(f"{name}_result.json")
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    comp: dict[str, float] = {}
    if "species" in d:
        for s in d["species"]:
            if s.get("in_catalog"):
                comp[s["formula"]] = comp.get(s["formula"], 0) + s.get("count", 1)
    else:
        for k, v in (d.get("final_composition") or {}).items():
            if isinstance(v, dict):
                v = v.get("count") or v.get("abundance") or 0
            comp[str(k)] = float(v)
    return comp


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


def spatial_clusters(grid, min_size=15):
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
            xs = [a for a, _ in mem]
            ys = [b for _, b in mem]
            kinds = len({grid[p].formula for p in mem})
            out.append({"mem": set(mem), "com": (sum(xs) / len(xs), sum(ys) / len(ys)),
                        "size": len(mem), "kinds": kinds})
    return out


def run(name: str, inertia: bool = True):
    comp = load_world(name)
    if comp is None:
        return None
    rng = random.Random(SEED)
    n = int(GRID * GRID * FILL)
    grid, mols = build(comp, n, rng)
    chains, alive = [], []
    for t in range(TICKS):
        L.step(grid, mols, rng, inertia=inertia)
        if (t + 1) % SNAP:
            continue
        snaps = spatial_clusters(grid)
        used, new_alive = set(), []
        for c in alive:
            best, bj, bi = None, 0.0, -1
            for i, s in enumerate(snaps):
                if i in used:
                    continue
                inter = len(c["mem"] & s["mem"])
                union = len(c["mem"] | s["mem"])
                j = inter / union if union else 0.0
                if j > bj:
                    bj, best, bi = j, s, i
            if bj >= 0.5:
                used.add(bi)
                c["mem"] = best["mem"]
                c["coms"].append(best["com"])
                c["age"] += 1
                new_alive.append(c)
            else:
                chains.append(c)
        for i, s in enumerate(snaps):
            if i not in used:
                new_alive.append({"mem": s["mem"], "coms": [s["com"]], "age": 1})
        alive = new_alive
    chains.extend(alive)

    # 分层质量
    by_state = {}
    for s in ("固", "液", "气"):
        ys = [m.y for m in mols if m.state_simple == s]
        if ys:
            by_state[s] = sum(ys) / len(ys)
    # 权重与高度的相关（应为负：越重越低）
    ws = [m.weight for m in mols]
    ys = [m.y for m in mols]
    mw, my = sum(ws) / len(ws), sum(ys) / len(ys)
    num = sum((a - mw) * (b - my) for a, b in zip(ws, ys))
    den = math.sqrt(sum((a - mw) ** 2 for a in ws) * sum((b - my) ** 2 for b in ys)) or 1
    corr = num / den

    movers = 0
    for c in chains:
        if c["age"] < 10:
            continue
        xs = [p[0] for p in c["coms"]]
        yy = [p[1] for p in c["coms"]]
        d = math.hypot(max(xs) - min(xs), max(yy) - min(yy))
        meanY = sum(yy) / len(yy)
        if d >= 3 and not (meanY < GRID * 0.2 or meanY > GRID * 0.8):
            movers += 1
    return {"by_state": by_state, "corr": corr, "movers": movers,
            "mols": mols, "grid": grid}


def main():
    names = ["t55_kinetic", "t57_area", "t62_phaseA", "t62_phaseB",
             "t63_phase2", "t63_phase3", "t64_biome_B05", "t64_biome_B11",
             "t59_phaseA", "t66_biome_E10"]
    print(f"网格 {GRID} · 重力常开 · 惯性开 · 权重 = 物态基底 + 连续质量\n")
    print(f"{'世界':18}{'固均高':>7}{'液均高':>7}{'气均高':>7}{'r(质量,高度)':>13}{'自由移动聚集':>13}")
    for nm in names:
        r = run(nm)
        if r is None:
            continue
        b = r["by_state"]
        print(f"{nm:18}{b.get('固', float('nan')):7.1f}{b.get('液', float('nan')):7.1f}"
              f"{b.get('气', float('nan')):7.1f}{r['corr']:13.2f}{r['movers']:13}")
        L.render(r["mols"], f"images/weight_{nm}.png")
    print("\n（y 越小越靠上；固均高应 > 液均高 > 气均高）")


if __name__ == "__main__":
    main()
