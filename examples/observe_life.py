# -*- coding: utf-8 -*-
"""观察三个"有生命"的世界：逐帧演化 + 结构追踪。

产物
----
- ``images/life_t63_phase2.png`` 等三张多帧对比图
- 终端报告：每个世界里"持久且移动"的结构的大小、寿命、位移

用法
----
    python examples/observe_life.py
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

WORLDS = ["t63_phase2", "t63_phase3", "t64_biome_B05"]
FRAMES = [0, 120, 240, 360, 480, 600]


def find_file(name: str) -> Path:
    for c in (Path("data/biomes") / f"{name}.json", Path(f"{name}_result.json")):
        if c.exists():
            return c
    raise FileNotFoundError(name)


def load_world(name: str):
    d = json.loads(find_file(name).read_text(encoding="utf-8"))
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


def snapshot(grid):
    seen, out = set(), []
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
            out.append({"mem": mem, "formula": m.formula,
                        "com": (sum(p[0] for p in mem) / len(mem),
                                sum(p[1] for p in mem) / len(mem))})
    return out


def run(name: str):
    comp = load_world(name)
    rng = random.Random(SEED)
    n = int(GRID * GRID * FILL)
    grid, mols = build(comp, n, rng)

    frames = {}
    chains, alive = [], []
    for t in range(TICKS + 1):
        if t in FRAMES:
            frames[t] = [(m.x, m.y, m.formula) for m in mols]
        if t == TICKS:
            break
        L.step(grid, mols, rng)
        if (t + 1) % SNAP:
            continue
        snaps = snapshot(grid)
        used, new_alive = set(), []
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
            if i not in used:
                new_alive.append({"mem": s["mem"], "formula": s["formula"],
                                  "coms": [s["com"]], "age": 1})
        alive = new_alive
    chains.extend(alive)

    movers = []
    for c in chains:
        if c["age"] < MIN_AGE:
            continue
        xs = [p[0] for p in c["coms"]]
        ys = [p[1] for p in c["coms"]]
        d = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
        if d >= MIN_MOVE:
            movers.append({"size": len(c["mem"]), "formula": c["formula"],
                           "life": c["age"] * SNAP, "move": d,
                           "traj": c["coms"]})
    movers.sort(key=lambda x: -x["move"])
    return {"name": name, "frames": frames, "movers": movers,
            "n_chains": len(chains), "mols": mols}


def render_world(res, path):
    from PIL import Image, ImageDraw
    cols = len(FRAMES)
    cell = 200
    img = Image.new("RGB", (cols * cell, cell + 18), (255, 255, 255))
    d = ImageDraw.Draw(img)
    colors = [(70, 185, 91), (245, 166, 35), (63, 208, 201), (142, 90, 168),
              (59, 111, 212), (231, 76, 60), (240, 122, 200), (179, 179, 179)]
    pal = {}
    s = cell / GRID
    for ci, t in enumerate(FRAMES):
        ox = ci * cell
        for (x, y, f) in res["frames"].get(t, []):
            if f not in pal:
                pal[f] = colors[len(pal) % len(colors)]
            d.rectangle([ox + x * s, y * s, ox + (x + 1) * s - 1, (y + 1) * s - 1],
                        fill=pal[f])
        d.text((ox + 4, cell + 3), f"t={t}", fill=(0, 0, 0))
    img.save(path)


def main():
    for name in WORLDS:
        res = run(name)
        print(f"=== {name} ===")
        print(f"  快照链总数 {res['n_chains']}，其中「持久且移动」{len(res['movers'])} 个")
        for m in res["movers"][:5]:
            traj = m["traj"]
            print(f"    结构: {m['formula']:10} 成员 {m['size']:3}  寿命 {m['life']:4} tick  "
                  f"位移 {m['move']:5.1f} 格  轨迹 {traj[0]} → {traj[-1]}")
        path = f"images/life_{name}.png"
        render_world(res, path)
        print(f"  图: {path}\n")


if __name__ == "__main__":
    main()
