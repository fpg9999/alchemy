# -*- coding: utf-8 -*-
"""纯连续粒子引擎：无格子、无交换、无推动。

- 位置/速度为连续浮点
- 空间哈希只用于找邻居
- 力来自分子的四值模型（A, R, r_att, r_rep）
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lattice_sim import four_values  # noqa: E402

DT = 0.06
DAMP = 0.97
SPEED_EPS = 1e-4


class World:
    def __init__(self, comp, n, w=64.0, h=48.0, seed=1, radius_mul=1.0):
        rng = np.random.default_rng(seed)
        names = list(comp)
        weights = np.array([comp[k] for k in names], float)
        weights /= weights.sum()
        self.types = names
        self.n = n
        self.w, self.h = w, h
        self.pos = np.stack([rng.random(n) * w, rng.random(n) * h], 1)
        self.vel = np.zeros((n, 2))
        idx = rng.choice(len(names), size=n, p=weights)
        self.t = idx
        vals = np.array([four_values(f) for f in names])
        self.att = vals[idx, 0]
        self.rep = vals[idx, 1]
        self.ra = vals[idx, 2] * radius_mul
        self.rr = vals[idx, 3] * radius_mul
        self.rcell = max(self.ra.max(), self.rr.max())

    def neighbors(self):
        """空间哈希（全向量化）：返回 (i, j, dx, dy, d)。"""
        cell = self.rcell
        ci = np.floor(self.pos / cell).astype(np.int64)
        ch = int(self.h / cell) + 2
        key = ci[:, 0] * ch + ci[:, 1]
        order = np.argsort(key, kind="stable")
        sk = key[order]
        n = self.n
        base = np.arange(n)
        los, cnts = [], []
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                nk = key + ox * ch + oy
                lo = np.searchsorted(sk, nk, "left")
                hi = np.searchsorted(sk, nk, "right")
                los.append(lo)
                cnts.append(hi - lo)
        los = np.concatenate(los)
        cnts = np.concatenate(cnts)
        tot = int(cnts.sum())
        if tot == 0:
            z = np.array([], int)
            return z, z, np.array([]), np.array([]), np.array([])
        starts = np.repeat(los, cnts)
        offs = np.arange(tot) - np.repeat(np.cumsum(cnts) - cnts, cnts)
        jj = order[starts + offs]
        ii = np.repeat(np.tile(base, 9), cnts)
        m = ii != jj
        ii, jj = ii[m], jj[m]
        d = self.pos[jj] - self.pos[ii]
        dist = np.hypot(d[:, 0], d[:, 1])
        keep = dist < self.rcell
        return ii[keep], jj[keep], d[keep, 0], d[keep, 1], dist[keep] + 1e-12

    def step(self):
        n = self.n
        fx = np.zeros(n)
        fy = np.zeros(n)
        ii, jj, dx, dy, dist = self.neighbors()
        if len(ii):
            # 引力：用 i 的 A 和 r_att
            fa = np.maximum(0.0, 1.0 - dist / self.ra[ii]) * self.att[ii]
            # 斥力：用 j 的 R 和 r_rep
            fr = np.maximum(0.0, 1.0 - dist / self.rr[jj]) * self.rep[jj]
            f = fa - fr
            ux, uy = dx / dist, dy / dist
            np.add.at(fx, ii, f * ux)
            np.add.at(fy, ii, f * uy)
        self.vel[:, 0] = (self.vel[:, 0] + fx * DT) * DAMP
        self.vel[:, 1] = (self.vel[:, 1] + fy * DT) * DAMP
        self.pos += self.vel * DT
        # 边界反弹（有墙）
        for k, hi in ((0, self.w), (1, self.h)):
            lo_m = self.pos[:, k] < 0
            hi_m = self.pos[:, k] > hi
            self.pos[lo_m, k] = 0.0
            self.pos[hi_m, k] = hi
            self.vel[lo_m | hi_m, k] *= -0.5


def cluster_sizes(pos, link):
    n = len(pos)
    seen = np.zeros(n, bool)
    sizes = []
    d = pos[:, None, :] - pos[None, :, :]
    dist = np.hypot(d[..., 0], d[..., 1])
    for i in range(n):
        if seen[i]:
            continue
        st = [i]
        seen[i] = True
        c = 0
        while st:
            j = st.pop()
            c += 1
            nb = np.where((dist[j] < link) & (~seen))[0]
            for q in nb:
                seen[q] = True
                st.append(q)
        sizes.append(c)
    sizes.sort(reverse=True)
    return sizes


def render(world, path, scale=6):
    from PIL import Image
    img = Image.new("RGB", (int(world.w * scale), int(world.h * scale)), (255, 255, 255))
    px = img.load()
    pal = [(220, 70, 60), (60, 130, 220), (70, 180, 90), (240, 170, 40),
           (150, 80, 200), (40, 180, 180), (200, 100, 60), (90, 90, 90)]
    for i in range(world.n):
        x, y = world.pos[i]
        c = pal[int(world.t[i]) % len(pal)]
        a, b = int(x * scale), int(y * scale)
        for di in range(2):
            for dj in range(2):
                if 0 <= a + di < img.width and 0 <= b + dj < img.height:
                    px[a + di, b + dj] = c
    img.save(path)


def main():
    from flow_census import collect
    worlds = dict(collect())
    name = "t62_phaseB"
    comp = worlds[name]
    w = World(comp, 700, seed=1)
    print(f"{name}: {len(comp)} 种 · 700 粒子 · {w.w:.0f}×{w.h:.0f} 连续空间")
    print(f"{'tick':>5}{'团块(≥10)':>10}{'最大':>6}{'≥10成员':>9}{'平均速度':>10}")
    for t in range(1, 1201):
        w.step()
        if t % 200 == 0:
            cs = [c for c in cluster_sizes(w.pos, link=2.0) if c >= 10]
            sp = float(np.hypot(w.vel[:, 0], w.vel[:, 1]).mean())
            print(f"{t:5}{len(cs):10}{cs[0] if cs else 0:6}{sum(cs):9}{sp:10.3f}")
            if t % 400 == 0:
                render(w, f"images/free_{t}.png")
    print("图: images/free_*.png")


if __name__ == "__main__":
    main()
