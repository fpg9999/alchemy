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
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    o = grid.get((m.x + dx, m.y + dy))
                    if o is None or id(o) in used:
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
                    self.stats["fired"] += 1
                    events.append({"reactants": [m.formula, o.formula],
                                   "products": list(prods), "breaks": breaks,
                                   "at": (m.x, m.y)})
                    break
        return events

    # ---------------- 放置产物
    def _place(self, grid, mols, a, b, prods, efield=None):
        from lattice_sim import Mol
        cells = [(a.x, a.y), (b.x, b.y)]
        n = len(prods)
        for r in (a, b):
            grid.pop((r.x, r.y), None)
            if r in mols:
                mols.remove(r)

        if n <= 2:
            # 产物少于反应物 → 剩下的格子成为空腔
            slots = cells[:n]
        else:
            slots = list(cells)
            cx = a.x
            top = min(a.y, b.y)
            for k in range(n - 2):
                ty = top - 1 - k
                if ty < 0:
                    return None
                # 从 ty 往上找第一个空格
                y = ty
                while y >= 0 and (cx, y) in grid:
                    y -= 1
                if y < 0:
                    return None
                # 把 [y, ty) 整段上移一格，腾出 ty
                for yy in range(y, ty):
                    mm = grid.pop((cx, yy))
                    mm.y = yy - 1
                    grid[(mm.x, mm.y)] = mm
                slots.append((cx, ty))

        for f, (sx, sy) in zip(prods, slots):
            nm = Mol(f, sx, sy)
            grid[(sx, sy)] = nm
            mols.append(nm)
        # 恒素净额为零：断键借入多少，成键就归还多少，无需记账
        return slots
