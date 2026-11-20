# -*- coding: utf-8 -*-
"""极简力定律：三轴各管一件事，零拟合参数。

    聚 → 我的吸引力 A_i = a_i
    动 → 别人对我的排斥 R_j = m_j
    散 → 我能感知多远 r_i = 1.5 + 3·s_i
    F_ij = (A_i − R_j) · max(0, 1 − d/r_i)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alchemy.core.elements import ORDER, VAL, parse_formula  # noqa: E402

K_SAT = 8.0
R0, R1 = 1.5, 4.5


def axes(formula: str):
    v = parse_formula(formula)
    g = {e: v[ORDER.index(e)] if ORDER.index(e) < len(v) else 0 for e in ORDER}
    sp = sum(VAL[e] * g[e] for e in ("O", "X", "C"))
    sm = sum(VAL[e] * g[e] for e in ("P", "W", "L"))
    ss = sum(VAL[e] * g[e] for e in ("K", "A", "F"))
    return sp / (sp + K_SAT), sm / (sm + K_SAT), ss / (ss + K_SAT)


class MinimalWorld:
    def __init__(self, comp, n, w=40.0, h=30.0, seed=1):
        rng = np.random.default_rng(seed)
        names = list(comp)
        wts = np.array([comp[k] for k in names], float)
        wts /= wts.sum()
        self.n, self.w, self.h = n, w, h
        self.pos = np.stack([rng.random(n) * w, rng.random(n) * h], 1)
        self.vel = np.zeros((n, 2))
        self.t = rng.choice(len(names), size=n, p=wts)
        ax = np.array([axes(f) for f in names])
        A = ax[:, 0]
        R = ax[:, 1]
        rad = R0 + (R1 - R0) * ax[:, 2]
        self.A = A[self.t]
        self.R = R[self.t]
        self.rad = rad[self.t]
        self.M = A[:, None] - R[None, :]
        self.rcell = float(rad.max())
        self.dt, self.damp = 0.06, 0.97

    def neighbors(self):
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
            f = self.M[self.t[ii], self.t[jj]] * np.maximum(0.0, 1.0 - dist / self.rad[ii])
            np.add.at(fx, ii, f * dx / dist)
            np.add.at(fy, ii, f * dy / dist)
        self.vel[:, 0] = (self.vel[:, 0] + fx * self.dt) * self.damp
        self.vel[:, 1] = (self.vel[:, 1] + fy * self.dt) * self.damp
        self.pos += self.vel * self.dt
        for k, hi in ((0, self.w), (1, self.h)):
            lo_m = self.pos[:, k] < 0
            hi_m = self.pos[:, k] > hi
            self.pos[lo_m, k] = 0.0
            self.pos[hi_m, k] = hi
            self.vel[lo_m | hi_m, k] *= -0.3

    def clusters(self, link=1.0):
        n = self.n
        seen = np.zeros(n, bool)
        out = []
        cell = {}
        for i, (x, y) in enumerate(self.pos):
            cell.setdefault((int(x // link), int(y // link)), []).append(i)
        for i in range(n):
            if seen[i]:
                continue
            st = [i]
            seen[i] = True
            cnt = 0
            while st:
                j = st.pop()
                cnt += 1
                cx, cy = int(self.pos[j, 0] // link), int(self.pos[j, 1] // link)
                for ox in (-1, 0, 1):
                    for oy in (-1, 0, 1):
                        for q in cell.get((cx + ox, cy + oy), ()):
                            if not seen[q] and np.hypot(*(self.pos[q] - self.pos[j])) < link:
                                seen[q] = True
                                st.append(q)
            out.append(cnt)
        out.sort(reverse=True)
        return out


def render(world, path, scale=16, rad_px=3):
    from PIL import Image
    img = Image.new("RGB", (int(world.w * scale), int(world.h * scale)), (255, 255, 255))
    px = img.load()
    pal = [(220, 70, 60), (60, 130, 220), (70, 180, 90), (240, 170, 40),
           (150, 80, 200), (40, 180, 180), (200, 100, 60), (90, 90, 90)]
    for i in range(world.n):
        cx, cy = world.pos[i, 0] * scale, world.pos[i, 1] * scale
        c = pal[int(world.t[i]) % len(pal)]
        for a in range(int(cx - rad_px), int(cx + rad_px) + 1):
            for b in range(int(cy - rad_px), int(cy + rad_px) + 1):
                if (a - cx) ** 2 + (b - cy) ** 2 <= rad_px ** 2:
                    if 0 <= a < img.width and 0 <= b < img.height:
                        px[a, b] = c
    img.save(path)
