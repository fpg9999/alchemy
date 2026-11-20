# -*- coding: utf-8 -*-
"""阶段 2：把 PL 系统搬进格子。

保持不变：随机 k 矩阵、PL 力形状（短斥长吸）、摩擦、dt 比例
只替换：连续坐标 → 格点；每 tick 移动 1 格；占位只能交换
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

GRID = 64
N_TYPES = 6
BETA = 0.3
R_MAX = 3.0
DT = 0.08
FRICTION = 0.97
MIN_SPEED = 0.02


def pl_force(dn):
    if dn >= 1.0:
        return 0.0
    if dn < BETA:
        return dn / BETA - 1.0
    return 1.0 - abs(2.0 * dn - 1.0 - BETA) / (1.0 - BETA)


def build(n_particles, seed):
    rng = random.Random(seed)
    cells = [(x, y) for x in range(GRID) for y in range(GRID)]
    rng.shuffle(cells)
    grid = {}
    mols = []
    for i, (x, y) in enumerate(cells[:n_particles]):
        t = i % N_TYPES
        m = {"x": x, "y": y, "t": t, "vx": 0.0, "vy": 0.0}
        grid[(x, y)] = m
        mols.append(m)
    return grid, mols, rng


def net_force(m, grid, k):
    fx = fy = 0.0
    R = int(math.ceil(R_MAX))
    for dx in range(-R, R + 1):
        for dy in range(-R, R + 1):
            if dx == 0 and dy == 0:
                continue
            o = grid.get((m["x"] + dx, m["y"] + dy))
            if o is None:
                continue
            d = math.hypot(dx, dy)
            if d >= R_MAX:
                continue
            f = pl_force(d / R_MAX) * k[m["t"]][o["t"]]
            fx += f * dx / d
            fy += f * dy / d
    return fx, fy


def step(grid, mols, rng, k, dt=DT):
    order = mols[:]
    rng.shuffle(order)
    moves = 0
    for m in order:
        if grid.get((m["x"], m["y"])) is not m:
            continue
        fx, fy = net_force(m, grid, k)
        m["vx"] = (m["vx"] + fx * dt) * FRICTION
        m["vy"] = (m["vy"] + fy * dt) * FRICTION
        sp = math.hypot(m["vx"], m["vy"])
        if sp < MIN_SPEED:
            continue
        sx = 0 if abs(m["vx"]) < 1e-3 else (1 if m["vx"] > 0 else -1)
        sy = 0 if abs(m["vy"]) < 1e-3 else (1 if m["vy"] > 0 else -1)
        if sx == 0 and sy == 0:
            continue
        nx, ny = m["x"] + sx, m["y"] + sy
        if not (0 <= nx < GRID and 0 <= ny < GRID):
            continue
        occ = grid.get((nx, ny))
        if occ is None:
            del grid[(m["x"], m["y"])]
            m["x"], m["y"] = nx, ny
            grid[(nx, ny)] = m
            moves += 1
        else:
            ox, oy = m["x"], m["y"]
            grid[(ox, oy)] = occ
            occ["x"], occ["y"] = ox, oy
            grid[(nx, ny)] = m
            m["x"], m["y"] = nx, ny
            moves += 1
    return moves


def clusters(grid, mols, link=1.45):
    seen = set()
    out = []
    for m in mols:
        p = (m["x"], m["y"])
        if p in seen:
            continue
        st = [p]
        seen.add(p)
        mem = []
        while st:
            x, y = st.pop()
            mem.append((x, y))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (x + dx, y + dy)
                    if q in grid and q not in seen:
                        seen.add(q)
                        st.append(q)
        out.append(mem)
    out.sort(key=len, reverse=True)
    return out


def render(grid, mols, path):
    from PIL import Image
    img = Image.new("RGB", (GRID * 5, GRID * 5), (255, 255, 255))
    px = img.load()
    pal = [(220, 70, 60), (60, 130, 220), (70, 180, 90), (240, 170, 40),
           (150, 80, 200), (40, 180, 180)]
    for (x, y), m in grid.items():
        c = pal[m["t"] % len(pal)]
        for i in range(5):
            for j in range(5):
                px[x * 5 + i, y * 5 + j] = c
    img.save(path)


def main():
    seed = 1
    n = 1600
    grid, mols, rng = build(n, seed)
    k = [[rng.uniform(-1.0, 1.0) for _ in range(N_TYPES)] for _ in range(N_TYPES)]
    print(f"格子版 PL · {GRID}×{GRID} · {N_TYPES} 种 · {n} 粒子 · k 随机")
    print(f"{'tick':>6}{'团块(≥5)':>10}{'最大团':>8}{'总成员':>8}{'平均速度':>10}")
    prev = None
    for t in range(1, 1201):
        step(grid, mols, rng, k)
        if t % 200 == 0:
            cs = [c for c in clusters(grid, mols) if len(c) >= 5]
            sp = sum(math.hypot(m["vx"], m["vy"]) for m in mols) / len(mols)
            print(f"{t:6}{len(cs):10}{cs[0][0] if False else (len(cs[0]) if cs else 0):8}"
                  f"{sum(len(c) for c in cs):8}{sp:10.3f}")
            if t % 400 == 0:
                render(grid, mols, f"images/lat_pl_{t}.png")
    print("图: images/lat_pl_*.png")


if __name__ == "__main__":
    main()
