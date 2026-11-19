# -*- coding: utf-8 -*-
"""恒素密度场（ρ_E）——守恒的重分布，不是被消耗的资源。

核心理解
--------
- **断键吸收恒素，成键释放恒素**；原子最终一定饱和，
  所以一次反应的吸收量 = 释放量，**净额恒为零**。
- 因此恒素**永远不会被消耗**，它只决定"反应能不能发生"。
- 反应阈值 = 两个分子的断键数之和；接触处 ρ_E 必须 ≥ 该阈值。

温度的作用（重分布，总量守恒）
------------------------------
- **热分子**：把大半径内的恒素**抽到自己所在格**（局部富集）
- **冷分子**：把自己格内的恒素**推到外圈**（局部稀薄）
- **中性分子**：不作用
- 强度有上限；**半径由温度决定**（越偏离中性，范围越大）

于是：热的物质周围恒素富集 → 反应容易发生；冷的物质周围稀薄 → 难以反应。
"""

from __future__ import annotations

import math
from typing import Iterable

from .core.elements import ORDER, parse_formula

NEUTRAL_TEMP = 1.85
DEFAULT_INIT = 0.6
DEFAULT_RATE = 0.30          # 每 tick 最大重分布量
DEFAULT_RADIUS = 2.0
RADIUS_SCALE = 3.0
STRENGTH_SCALE = 0.15


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
        self.initial_total = self.total()

    # ---------------- 访问
    def get(self, x: int, y: int) -> float:
        return self.rho[y][x]

    def add(self, x: int, y: int, v: float) -> None:
        self.rho[y][x] = max(0.0, self.rho[y][x] + v)

    def total(self) -> float:
        return sum(sum(row) for row in self.rho)

    def mean(self) -> float:
        return self.total() / (self.size * self.size)

    # ---------------- 扩散（守恒）
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

    # ---------------- 温度 → (强度, 半径)
    def strength_radius(self, temp: float,
                        neutral: float = NEUTRAL_TEMP,
                        max_rate: float = DEFAULT_RATE,
                        base_radius: float = DEFAULT_RADIUS,
                        radius_scale: float = RADIUS_SCALE
                        ) -> tuple[float, float]:
        d = abs(temp - neutral)
        if d < 0.05:
            return 0.0, 0.0
        return min(max_rate, d * STRENGTH_SCALE), base_radius + d * radius_scale

    # ---------------- 重分布（总量守恒）
    def interact(self, mols: Iterable, neutral: float = NEUTRAL_TEMP,
                 max_rate: float = DEFAULT_RATE,
                 base_radius: float = DEFAULT_RADIUS,
                 radius_scale: float = RADIUS_SCALE) -> None:
        n = self.size
        for m in mols:
            d = m.temp_val - neutral
            rate, radius = self.strength_radius(
                m.temp_val, neutral, max_rate, base_radius, radius_scale)
            if rate <= 0:
                continue
            r = int(round(radius))
            if r < 1:
                continue
            ring = []
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if dx == 0 and dy == 0:
                        continue
                    if math.hypot(dx, dy) <= r:
                        ring.append(((m.x + dx) % n, (m.y + dy) % n))
            if not ring:
                continue
            if d > 0:
                # 热：从外圈抽到中心（局部富集）
                share = rate / len(ring)
                moved = 0.0
                for cx, cy in ring:
                    take = min(self.rho[cy][cx], share)
                    if take <= 0:
                        continue
                    self.rho[cy][cx] -= take
                    moved += take
                self.rho[m.y][m.x] += moved
            else:
                # 冷：从中心推到外圈（局部稀薄）
                budget = min(rate, self.rho[m.y][m.x])
                if budget <= 0:
                    continue
                self.rho[m.y][m.x] -= budget
                share = budget / len(ring)
                for cx, cy in ring:
                    self.rho[cy][cx] += share
