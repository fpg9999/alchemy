# -*- coding: utf-8 -*-
"""球形刚体粒子 + 重力：死世界沉降测试。

每个粒子是半径 r 的圆；碰撞用 PBD 迭代推开（不可重叠）。
死世界 = 无分子间作用力，只有重力 + 碰撞。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))


class RigidWorld:
    def __init__(self, n, w=40.0, h=20.0, r=0.5, seed=1, g=0.5):
        rng = np.random.default_rng(seed)
        self.n = n
        self.w, self.h = w, h
        self.r = r
        self.g = g
        self.dt = 0.05
        self.damp = 0.96
        self.iters = 4
        self.pos = np.stack([rng.random(n) * w, rng.random(n) * h], 1)
        self.vel = np.zeros((n, 2))
        self.rcell = 2 * r + 0.2

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
        m = ii < jj          # 每对只保留一次
        ii, jj = ii[m], jj[m]
        d = self.pos[jj] - self.pos[ii]
        dist = np.hypot(d[:, 0], d[:, 1])
        keep = dist < self.rcell
        return ii[keep], jj[keep], d[keep, 0], d[keep, 1], dist[keep] + 1e-12

    def step(self):
        # 重力积分
        self.vel[:, 1] += self.g * self.dt
        self.vel *= self.damp
        self.pos += self.vel * self.dt
        # 墙壁
        self.pos[:, 0] = np.clip(self.pos[:, 0], self.r, self.w - self.r)
        self.pos[:, 1] = np.clip(self.pos[:, 1], self.r, self.h - self.r)
        self.vel[self.pos[:, 1] >= self.h - self.r, 1] *= -0.2
        self.vel[self.pos[:, 1] <= self.r, 1] *= -0.2
        # 刚体碰撞：迭代推开
        d_min = 2 * self.r
        for _ in range(self.iters):
            ii, jj, dx, dy, dist = self.neighbors()
            if not len(ii):
                break
            ov = d_min - dist
            hit = ov > 0
            if not hit.any():
                break
            ii, jj = ii[hit], jj[hit]
            ov, dx, dy, dist = ov[hit], dx[hit], dy[hit], dist[hit]
            ux, uy = dx / dist, dy / dist
            push = ov * 0.5
            np.add.at(self.pos, (ii, 0), -ux * push)
            np.add.at(self.pos, (ii, 1), -uy * push)
            np.add.at(self.pos, (jj, 0), ux * push)
            np.add.at(self.pos, (jj, 1), uy * push)
            self.pos[:, 0] = np.clip(self.pos[:, 0], self.r, self.w - self.r)
            self.pos[:, 1] = np.clip(self.pos[:, 1], self.r, self.h - self.r)

    def thickness(self):
        """从底部往上，连续有多少行的占据率 > 60%。"""
        hist, _ = np.histogram(self.pos[:, 1], bins=int(self.h / (2 * self.r)),
                               range=(0, self.h))
        need = self.w / (2 * self.r) * 0.6
        solid = 0
        for c in hist[::-1]:
            if c > need:
                solid += 1
            else:
                break
        return solid, len(hist)


def render(w, path, scale=12):
    from PIL import Image
    img = Image.new("RGB", (int(w.w * scale), int(w.h * scale)), (255, 255, 255))
    px = img.load()
    rr = w.r * scale
    for i in range(w.n):
        x, y = w.pos[i]
        cx, cy = x * scale, y * scale
        for a in range(int(cx - rr), int(cx + rr) + 1):
            for b in range(int(cy - rr), int(cy + rr) + 1):
                if (a - cx) ** 2 + (b - cy) ** 2 <= rr * rr:
                    if 0 <= a < img.width and 0 <= b < img.height:
                        px[a, b] = (90, 120, 160)
    img.save(path)


def main():
    for n, r in ((500, 0.5), (800, 0.4), (400, 0.6)):
        w = RigidWorld(n, w=40.0, h=20.0, r=r, seed=1, g=0.5)
        for _ in range(400):
            w.step()
        s, tot = w.thickness()
        v = float(np.hypot(w.vel[:, 0], w.vel[:, 1]).mean())
        print(f"N={n} r={r}: 地面 {s}/{tot} 带 = {s/tot:.0%}  平均速度 {v:.3f}")
        render(w, f"images/rigid_{n}_{r}.png")
    print("图: images/rigid_*.png")


if __name__ == "__main__":
    main()
