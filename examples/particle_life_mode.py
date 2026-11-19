# -*- coding: utf-8 -*-
"""Particle Life 模式：连续空间 + 短程斥力/中程引力 + 惯性。

与 Particle Life 的对应
-----------------------
- 力形状：dn<0.3 斥（对方的动素）、0.3~1 吸（自己的聚素）→ 短斥长吸 ✅
- **非对称**：k_ij = A_i − R_j ≠ k_ji ✅
- 作用半径由散素决定（每个分子不同）→ 比 Particle Life 更丰富
- 惯性 + 阻尼 ✅

扫描：阻尼 × 密度，寻找"既不死寂也不混沌"的有序运动区间。
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from alchemy.core.elements import ORDER, parse_formula, VAL  # noqa: E402

K = 8.0
A_MAX, R_MAX = 10.0, 10.0
D_MIN, D_MAX = 1.2, 8.0
W_S, W_OWN = 0.5, 0.25


def four_values(f):
    v = parse_formula(f)
    g = {e: v[ORDER.index(e)] for e in ORDER}
    sp = sum(VAL[e] * g[e] for e in ("O", "X", "C"))
    sm = sum(VAL[e] * g[e] for e in ("P", "W", "L"))
    ss = sum(VAL[e] * g[e] for e in ("K", "A", "F"))
    a, m, s = sp / (sp + K), sm / (sm + K), ss / (ss + K)
    att = A_MAX * a
    rep = R_MAX * m
    d_att = D_MIN + (D_MAX - D_MIN) * (W_S * s + W_OWN * a)
    d_rep = D_MIN + (D_MAX - D_MIN) * (W_S * s + W_OWN * m)
    return att, rep, d_att, d_rep


def simulate(types, n=700, steps=800, damp=0.92, dt=0.02, range_scale=0.10,
             vcap=2.0, seed=20261120):
    rng = np.random.default_rng(seed)
    nt = len(types)
    A = np.array([t[0] for t in types])
    R = np.array([t[1] for t in types])
    D = np.array([max(t[2], t[3]) for t in types])

    tid = rng.integers(0, nt, n)
    pos = rng.random((n, 2))
    vel = np.zeros((n, 2))
    Ai, Ri, Di = A[tid], R[tid], D[tid] * range_scale

    ke_hist = []
    for step in range(steps):
        dx = pos[None, :, 0] - pos[:, None, 0]
        dy = pos[None, :, 1] - pos[:, None, 1]
        dx -= np.round(dx)
        dy -= np.round(dy)
        dist = np.hypot(dx, dy)
        np.fill_diagonal(dist, np.inf)

        Dij = np.maximum(Di[:, None], Di[None, :])
        inside = dist < Dij
        near = dist < 0.3 * Dij

        f_att = np.broadcast_to(Ai[:, None], (n, n))
        f_rep = np.broadcast_to(Ri[None, :], (n, n))
        f = np.where(near, -f_rep, np.where(inside, f_att, 0.0))
        f = f * np.clip(dist / 0.01, 0.0, 1.0)
        np.fill_diagonal(f, 0.0)

        ux = np.where(np.isfinite(dist), dx / np.where(dist == 0, 1, dist), 0.0)
        uy = np.where(np.isfinite(dist), dy / np.where(dist == 0, 1, dist), 0.0)
        fx = (f * ux).sum(axis=1)
        fy = (f * uy).sum(axis=1)

        vel = (vel + np.stack([fx, fy], axis=1) * dt) * damp
        sp = np.hypot(vel[:, 0], vel[:, 1])
        over = sp > vcap
        if over.any():
            vel[over] *= (vcap / sp[over])[:, None]
        pos = (pos + vel * dt) % 1.0
        ke_hist.append(float((vel ** 2).sum() / n))

    ke = float((vel ** 2).sum() / n)
    speed = np.hypot(vel[:, 0], vel[:, 1])
    pol = float(np.hypot(vel[:, 0].sum(), vel[:, 1].sum()) / (speed.sum() + 1e-12))
    # 局部有序度：每个粒子与最近的 6 个邻居的速度方向一致性
    d2 = np.hypot(pos[None, :, 0] - pos[:, None, 0], pos[None, :, 1] - pos[:, None, 1])
    np.fill_diagonal(d2, np.inf)
    nb = np.argsort(d2, axis=1)[:, :6]
    order = 0.0
    for i in range(n):
        if speed[i] < 1e-9:
            continue
        vi = vel[i] / speed[i]
        for j in nb[i]:
            if speed[j] > 1e-9:
                order += float(vi @ (vel[j] / speed[j]))
    order /= max(1, n * 6)
    # 团块：30% 覆盖率的局部密度峰值数
    cnt = np.zeros((12, 12))
    for x, y in pos:
        cnt[int(x * 12) % 12, int(y * 12) % 12] += 1
    occ = (cnt > 0).sum()
    return {"ke": ke, "pol": pol, "order": order, "dens": n / occ,
            "ke_mean": sum(ke_hist) / len(ke_hist)}


def main():
    types = [four_values(f) for f in ("LF", "OXCPWKA", "OK", "XA", "CF", "L2", "WA", "F2")]
    print("8 种分子，连续空间，短程斥力 + 中程引力，非对称，惯性\n")
    print(f"{'阻尼':>6}{'半径':>7}{'动能':>9}{'极化':>8}{'局部有序':>9}{'拥挤度':>8}")
    for damp in (0.85, 0.90, 0.94, 0.97):
        for rs in (0.08, 0.12):
            r = simulate(types, damp=damp, range_scale=rs)
            print(f"{damp:6.2f}{rs:7.2f}{r['ke']:9.2f}{r['pol']:8.3f}"
                  f"{r['order']:9.3f}{r['dens']:8.2f}")


if __name__ == "__main__":
    main()
