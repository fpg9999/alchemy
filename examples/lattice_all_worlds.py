# -*- coding: utf-8 -*-
"""对**所有世界**跑同一个网格实验：接入质量轴（重力方向）+ 分子互不穿透。

覆盖 data/biomes/*.json（12 个）与根目录 t6x_biome_*_result.json（32 个），共 44 个世界。

用法
----
    python examples/lattice_all_worlds.py
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
from alchemy.core.elements import ORDER, parse_formula  # noqa: E402
from alchemy.attrs import MASS_W, STATE_W, THRESHOLDS  # noqa: E402

GRID = 48
FILL = 0.40
TICKS = 300
GRAV = 1.0
SEED = 20261120

# lattice_sim 内部用自己的 GRID 做边界判断，这里必须同步
L.GRID = GRID
L.FILL = FILL


def load_world(path: Path) -> dict:
    """返回 {name, comp: {formula: weight}}。"""
    d = json.loads(path.read_text(encoding="utf-8"))
    comp: dict[str, float] = {}
    if isinstance(d, dict) and "species" in d:
        for s in d["species"]:
            if not s.get("in_catalog"):
                continue
            comp[s["formula"]] = comp.get(s["formula"], 0) + s.get("count", 1)
        name = path.stem
    elif isinstance(d, dict) and "final_composition" in d:
        fc = d["final_composition"] or {}
        for k, v in fc.items():
            if isinstance(v, dict):
                v = v.get("count") or v.get("abundance") or 0
            comp[str(k)] = float(v)
        name = path.stem.replace("_result", "")
    else:
        return {"name": path.stem, "comp": {}}
    return {"name": name, "comp": comp}


def species_props(formula: str):
    v = parse_formula(formula)
    g = {e: v[ORDER.index(e)] for e in ORDER}
    n3 = sum(g[e] for e in ("O", "K", "P"))
    n2 = sum(g[e] for e in ("X", "A", "W"))
    mv = (sum(MASS_W[e] * g[e] for e in ("O", "K", "P")) / n3) if n3 else 0.0
    sv = (sum(STATE_W[e] * g[e] for e in ("X", "A", "W")) / n2) if n2 else 0.0
    lo_m, hi_m = THRESHOLDS["mass"]
    lo_s, hi_s = THRESHOLDS["state"]
    mt = "轻" if mv <= lo_m else ("中" if mv <= hi_m else "重")
    ct = "虚体" if sv <= lo_s else ("软体" if sv <= hi_s else "刚体")
    return mt, ct, mv, sv


def build(comp: dict, n_target: int, rng: random.Random):
    items = [(f, w) for f, w in comp.items() if w > 0]
    total = sum(w for _, w in items)
    mols = []
    for f, w in items:
        k = max(1, round(n_target * w / total))
        for _ in range(k):
            mols.append(L.Mol(f, 0, 0))
    rng.shuffle(mols)
    mols = mols[:n_target]
    cells = [(x, y) for x in range(GRID) for y in range(GRID)]
    rng.shuffle(cells)
    for m, (x, y) in zip(mols, cells):
        m.x, m.y = x, y
    grid = {(m.x, m.y): m for m in mols}
    return grid, mols


def run_world(comp: dict, rng: random.Random):
    n = int(GRID * GRID * FILL)
    grid, mols = build(comp, n, rng)
    for _ in range(TICKS):
        L.step(grid, mols, rng, gravity=GRAV, use_radial=True)
    # 分层度：各主要物种质心高度的离散程度
    cnt = Counter(m.formula for m in mols)
    main = [f for f, c in cnt.items() if c >= 0.05 * len(mols)]
    heights = {}
    for f in main:
        ys = [m.y for m in mols if m.formula == f]
        heights[f] = sum(ys) / len(ys)
    strat = (max(heights.values()) - min(heights.values())) / GRID if len(heights) > 1 else 0.0
    # 最大团
    seen, best = set(), 0
    for m in mols:
        if (m.x, m.y) in seen:
            continue
        q, seen = deque([(m.x, m.y)]), seen | {(m.x, m.y)}
        size = 0
        while q:
            x, y = q.popleft()
            size += 1
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if not (dx or dy):
                        continue
                    p = (x + dx, y + dy)
                    o = grid.get(p)
                    if o is not None and o.formula == m.formula and p not in seen:
                        seen.add(p)
                        q.append(p)
        best = max(best, size)
    dom = max(cnt, key=cnt.get)
    mt, ct, mv, sv = species_props(dom)
    band = max(1, GRID // 8)
    prof = [sum(1 for m in mols if m.y // band == i) / len(mols) for i in range(8)]
    return {"n_species": len(cnt), "dom": dom, "dom_share": cnt[dom] / len(mols),
            "mass": mt, "coll": ct, "strat": strat, "max_cluster": best,
            "profile": prof, "mols": mols, "main": len(main)}


def contact_sheet(rows, path="images/lattice_all_worlds.png", cell=96, cols=8):
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return
    n = len(rows)
    r = (n + cols - 1) // cols
    img = Image.new("RGB", (cols * cell, r * (cell + 14)), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for i, row in enumerate(rows):
        cx, cy = (i % cols) * cell, (i // cols) * (cell + 14)
        pal = {}
        colors = [(70, 185, 91), (245, 166, 35), (63, 208, 201), (142, 90, 168),
                  (59, 111, 212), (240, 122, 200), (231, 76, 60), (179, 179, 179)]
        s = cell / GRID
        for m in row["mols"]:
            if m.formula not in pal:
                pal[m.formula] = colors[len(pal) % len(colors)]
            d.rectangle([cx + m.x * s, cy + m.y * s,
                         cx + (m.x + 1) * s - 1, cy + (m.y + 1) * s - 1], fill=pal[m.formula])
        d.text((cx + 2, cy + cell + 1), row["name"][:16], fill=(0, 0, 0))
    img.save(path)


def main():
    worlds = []
    for p in sorted(Path("data/biomes").glob("*.json")):
        if p.name.startswith("_"):
            continue
        w = load_world(p)
        if w["comp"]:
            worlds.append(w)
    for p in sorted(Path(".").glob("t6*_biome_*_result.json")):
        w = load_world(p)
        if w["comp"]:
            worlds.append(w)

    print(f"共 {len(worlds)} 个世界，网格 {GRID}×{GRID}，{TICKS} tick，重力 {GRAV}\n")
    hdr = f"{'世界':22}{'物种':>4}{'主导':>12}{'占比':>7}{'质量':>5}{'碰撞':>5}{'分层度':>7}{'最大团':>7}"
    print(hdr)
    print("-" * len(hdr.encode('gbk', errors='ignore')))
    rows = []
    for w in worlds:
        rng = random.Random(SEED)
        r = run_world(w["comp"], rng)
        r["name"] = w["name"]
        rows.append(r)
        print(f"{r['name'][:20]:22}{r['n_species']:4}{r['dom'][:11]:>12}{r['dom_share']:7.1%}"
              f"{r['mass']:>5}{r['coll']:>5}{r['strat']:7.2f}{r['max_cluster']:7}")

    print()
    top = sorted(rows, key=lambda r: -r["strat"])[:5]
    print("分层最明显的 5 个世界：")
    for r in top:
        print(f"  {r['name'][:22]:24} 分层度 {r['strat']:.2f}  主导 {r['dom']}({r['mass']}·{r['coll']})")
    print()
    print("几乎不分层的世界：")
    for r in sorted(rows, key=lambda r: r["strat"])[:5]:
        print(f"  {r['name'][:22]:24} 分层度 {r['strat']:.2f}  主导 {r['dom']}({r['mass']}·{r['coll']})")

    contact_sheet(rows)
    print("\n图: images/lattice_all_worlds.png")


if __name__ == "__main__":
    main()
