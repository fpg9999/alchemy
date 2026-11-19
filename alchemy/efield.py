# -*- coding: utf-8 -*-
"""恒素密度场（ρ_E）——小数、无上限、大半径、温度驱动。

规格
----
- ρ_E 是**小数**，格内**不设上限**（可以很高，也可以被抽到 0）
- 每个格子每 tick 先**扩散**（向 8 邻域摊平）
- 分子按温度作用于**较大半径**的场：
    * 热分子（温度 > 中性）：从半径内吸收恒素 → ``e_load`` 上升
    * 冷分子（温度 < 中性）：把内圈的恒素推到外圈
    * 中性分子：不作用
- **温度决定两件事**：
    * **强度**：|ΔT| 越大，每 tick 吸收/排斥的量越大（有上限 max_rate）
    * **半径**：|ΔT| 越大，作用半径越大
- 只有**强度**有上限；``e_load`` / ``e_rep`` 不设总量上限
"""

from __future__ import annotations

import math
from typing import Iterable

from .core.elements import ORDER, parse_formula

NEUTRAL_TEMP = 1.85
DEFAULT_INIT = 0.6
DEFAULT_RATE = 0.30          # 每 tick 最大吸收/排斥量
DEFAULT_RADIUS = 2.0         # 基础半径
RADIUS_SCALE = 3.0           # 温度对半径的放大


def temp_of(formula: str) -> float:
    v = parse_formula(formula)
    g = {e: v[ORDER.index(e)] for e in ORDER}
    n = sum(g[e] for e in ("F", "L", "C"))
    if not n:
        return 0.0
    return sum({"F": 3, "L": 2, "C": 1}[e] * g[e] for e in ("F", "L", "C")) / n


class EField:
    def __init__(self, size: int, init: float = DEFAULT_INIT,
                 diffuse: float = 0.08):
        self.size = size
        self.diffuse_coef = diffuse
        self.rho = [[init] * size for _ in range(size)]

    # ---------------- 访问
    def get(self, x: int, y: int) -> float:
        return self.rho[y][x]

    def add(self, x: int, y: int, v: float) -> None:
        self.rho[y][x] = max(0.0, self.rho[y][x] + v)

    def total(self) -> float:
        return sum(sum(row) for row in self.rho)

    def mean(self) -> float:
        return self.total() / (self.size * self.size)

    # ---------------- 扩散
    def diffuse_step(self) -> None:
        k = self.diffuse_coef
        if k <= 0:
            return
        n = self.size
        new = [[0.0] * n for _ in range(n)]
        for y in range(n):
            for x in range(n):
                v = self.rho[y][x]
                acc = cnt = 0.0
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        acc += self.rho[(y + dy) % n][(x + dx) % n]
                        cnt += 1
                new[y][x] = v + k * (acc / cnt - v)
        self.rho = new

    # ---------------- 温度作用
    def strength_radius(self, temp: float,
                        neutral: float = NEUTRAL_TEMP,
                        max_rate: float = DEFAULT_RATE,
                        base_radius: float = DEFAULT_RADIUS,
                        radius_scale: float = RADIUS_SCALE
                        ) -> tuple[float, float]:
        """返回 (强度, 半径)；强度有上限，半径随 |ΔT| 增大。"""
        d = abs(temp - neutral)
        if d < 0.05:
            return 0.0, 0.0
        rate = min(max_rate, d * 0.15)
        radius = base_radius + d * radius_scale
        return rate, radius

    def interact(self, mols: Iterable, neutral: float = NEUTRAL_TEMP,
                 max_rate: float = DEFAULT_RATE,
                 base_radius: float = DEFAULT_RADIUS,
                 radius_scale: float = RADIUS_SCALE,
                 leak: float = 0.03) -> None:
        n = self.size
        for m in mols:
            # 自然泄漏：分子把一部分恒素还回所在格，使场不会被抽干
            if leak > 0:
                held = getattr(m, "e_load", 0.0)
                if held > 0:
                    give = held * leak
                    m.e_load = held - give
                    self.rho[m.y][m.x] += give
                rep = getattr(m, "e_rep", 0.0)
                if rep > 0:
                    m.e_rep = rep * (1.0 - leak)
            d = m.temp_val - neutral
            rate, radius = self.strength_radius(
                m.temp_val, neutral, max_rate, base_radius, radius_scale)
            if rate <= 0:
                continue
            r = int(round(radius))
            if r < 1:
                continue
            cells = []
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if dx == 0 and dy == 0:
                        continue
                    dd = math.hypot(dx, dy)
                    if dd > r:
                        continue
                    cells.append(((m.x + dx) % n, (m.y + dy) % n, dd))
            if not cells:
                continue
            if d > 0:
                # 热：按距离衰减地从内圈吸收
                budget = rate
                taken = 0.0
                weight = sum(1.0 / (1.0 + c[2]) for c in cells) or 1.0
                for cx, cy, dd in cells:
                    if budget <= 0:
                        break
                    w = 1.0 / (1.0 + dd) / weight
                    take = min(self.rho[cy][cx], budget * w * len(cells) / 8.0)
                    if take <= 0:
                        continue
                    self.rho[cy][cx] -= take
                    taken += take
                    budget -= take
                m.e_load = getattr(m, "e_load", 0.0) + taken
            else:
                # 冷：把内圈的恒素推到外圈
                budget = rate
                inner = [(cx, cy, dd) for cx, cy, dd in cells if dd <= max(1.0, r / 2)]
                outer = [(cx, cy, dd) for cx, cy, dd in cells if dd > max(1.0, r / 2)]
                if not inner or not outer:
                    continue
                moved = 0.0
                for cx, cy, dd in inner:
                    if budget <= 0:
                        break
                    take = min(self.rho[cy][cx], budget / max(1, len(inner)))
                    if take <= 0:
                        continue
                    self.rho[cy][cx] -= take
                    moved += take
                    budget -= take
                if outer and moved:
                    per = moved / len(outer)
                    for cx, cy, dd in outer:
                        self.rho[cy][cx] += per
                m.e_rep = getattr(m, "e_rep", 0.0) + moved
