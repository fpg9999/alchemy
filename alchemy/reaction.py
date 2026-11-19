# -*- coding: utf-8 -*-
"""反应层（v2）：自然不完全反应 + 恒素阈值 + 上顶/空腔。

新设定
------
1. **阈值 = 两个分子断键数之和**（不是全局常量）
2. **不完全反应**：只断最不稳定的键（周期表距离最小），存活键保留
3. **产物数量**：
   - 产物 > 反应物 → 多出的物质**向上顶**
   - 产物 < 反应物 → 留下**空腔**
4. **恒素上限**：每个分子有富集/排斥上限，防止恒素被无限抽干
"""

from __future__ import annotations

import random

from .natural import break_count, natural_products

#: 触发条件（整数）：ρ_E(中点) + e_load_a + e_load_b ≥ 断键数之和

#: 反应后恒素逸散回局部的比例
E_RELEASE = 0.8


class ReactionLayer:
    def __init__(self, max_products: int = 6):
        self.max_products = max_products
        self.stats = {"fired": 0, "blocked": 0, "no_change": 0, "below_threshold": 0}

    # ---------------- 主判定
    def try_react(self, grid: dict, mols: list, efield, rng: random.Random,
                  max_events: int = 40) -> list[dict]:
        events = []
        used = set()
        order = list(mols)
        rng.shuffle(order)
        alive = {id(m) for m in mols}
        for m in order:
            if len(events) >= max_events:
                break
            if id(m) not in alive or id(m) in used:
                continue
            if grid.get((m.x, m.y)) is not m:
                alive.discard(id(m))
                continue
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    o = grid.get((m.x + dx, m.y + dy))
                    if o is None or id(o) in used or id(o) not in alive:
                        continue
                    res = natural_products(m.formula, o.formula)
                    if res is None:
                        continue
                    prods, breaks = res
                    if not prods or len(prods) > self.max_products:
                        continue
                    if sorted(prods) == sorted((m.formula, o.formula)):
                        self.stats["no_change"] += 1
                        continue
                    # 阈值 = 两个分子的断键数之和；接触处的恒素密度必须达到它
                    need = max(1, breaks)
                    mx = (m.x + o.x) // 2
                    my = (m.y + o.y) // 2
                    pot = efield.get(int(mx), int(my))
                    if pot < need:
                        self.stats["below_threshold"] += 1
                        continue
                    placed = self._place(grid, mols, m, o, prods, efield)
                    if placed is None:
                        self.stats["blocked"] += 1
                        continue
                    used.add(id(m))
                    used.add(id(o))
                    alive = {id(x) for x in mols}      # 反应后刷新存活集合
                    self.stats["fired"] += 1
                    events.append({"reactants": [m.formula, o.formula],
                                   "products": list(prods), "breaks": breaks,
                                   "at": (m.x, m.y)})
                    break
        return events

    # ---------------- 放置产物（原子化：先检查全部，再改动）
    def _place(self, grid, mols, a, b, prods, efield=None):
        from lattice_sim import Mol
        if a not in mols or b not in mols:
            return None
        if grid.get((a.x, a.y)) is not a or grid.get((b.x, b.y)) is not b:
            return None
        try:
            from lattice_sim import GRID as GSIZE
        except Exception:
            GSIZE = 64
        cells = [(a.x, a.y), (b.x, b.y)]
        n = len(prods)

        # ---- 检查阶段
        if n <= 2:
            slots = cells[:n]
        else:
            need = n - 2
            cand = []
            for dy in range(1, 7):
                for dx in (0, -1, 1, -2, 2):
                    p = (a.x + dx, a.y - dy)
                    if not (0 <= p[0] < GSIZE and 0 <= p[1] < GSIZE):
                        continue
                    if p in grid or p in cells or p in cand:
                        continue
                    cand.append(p)
                    if len(cand) >= need:
                        break
                if len(cand) >= need:
                    break
            if len(cand) < need:
                return None
            slots = cells + cand

        # ---- 改动阶段
        for r in (a, b):
            grid.pop((r.x, r.y), None)
            if r in mols:
                mols.remove(r)
        for f, (sx, sy) in zip(prods, slots):
            nm = Mol(f, sx, sy)
            grid[(sx, sy)] = nm
            mols.append(nm)
        return slots
