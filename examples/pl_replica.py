# -*- coding: utf-8 -*-
"""阶段 1：忠实复刻 Particle Life（连续空间、随机 k 矩阵、无重力）。

这是基线：先确认"在这个实现里，细胞/追逐能出现"。
之后每一步只替换一个部分，定位生命消失的原因。
"""
from __future__ import annotations

import argparse
import math

import numpy as np

BETA = 0.3          # 斥力区间占 r_max 的比例
R_MAX = 0.1         # 作用半径（世界坐标）
DT = 0.02
FRICTION = 0.85


def force_table(dn, beta):
    """Particle Life 的力形状：dn<beta 斥，beta~1 吸，>1 为零。"""
    f = np.zeros_like(dn)
    m = dn < beta
    f[m] = dn[m] / beta - 1.0
    m2 = (dn >= beta) & (dn < 1.0)
    f[m2] = 1.0 - np.abs(2.0 * dn[m2] - 1.0 - beta) / (1.0 - beta)
    return f


def step(pos, vel, k, n_types, rng, box=1.0):
    n = len(pos)
    # 全对距离（小规模直接用矩阵）
    d = pos[:, None, :] - pos[None, :, :]
    d -= np.round(d / box) * box          # 周期边界
    dist = np.sqrt((d ** 2).sum(-1)) + 1e-12
    np.fill_diagonal(dist, 1e9)
    dn = dist / R_MAX
    fmag = force_table(dn, BETA)
    kij = k[np.arange(n)[:, None] % n_types, np.arange(n)[None, :] % n_types]
    # 对每一对：f 是力的大小，方向沿 -d
    unit = d / dist[..., None]
    fvec = (fmag * kij)[..., None] * (-unit)
    acc = fvec.sum(1)
    vel[:] = (vel + acc * DT) * FRICTION
    pos[:] = (pos + vel * DT) % box
    return dist, fmag


def cluster_sizes(pos, box=1.0, link=1.6 * R_MAX):
    n = len(pos)
    d = pos[:, None, :] - pos[None, :, :]
    d -= np.round(d / box) * box
    dist = np.sqrt((d ** 2).sum(-1))
    seen = np.zeros(n, bool)
    sizes = []
    for i in range(n):
        if seen[i]:
            continue
        stack = [i]
        seen[i] = True
        cnt = 0
        while stack:
            j = stack.pop()
            cnt += 1
            nb = np.where((dist[j] < link) & (~seen))[0]
            for q in nb:
                seen[q] = True
                stack.append(q)
        sizes.append(cnt)
    sizes.sort(reverse=True)
    return sizes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--types", type=int, default=6)
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--ticks", type=int, default=2000)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    pos = rng.random((args.n, 2))
    vel = np.zeros((args.n, 2))
    k = rng.uniform(-1.0, 1.0, (args.types, args.types))

    print(f"PL 复刻 · {args.types} 种 · {args.n} 粒子 · seed={args.seed}")
    print(f"{'tick':>6}{'团块数':>8}{'最大团':>8}{'次大':>6}{'第三':>6}{'平均速度':>10}")
    for t in range(1, args.ticks + 1):
        step(pos, vel, k, args.types, rng)
        if t % 250 == 0:
            sizes = cluster_sizes(pos)
            big = [s for s in sizes if s >= 20]
            print(f"{t:6}{len(big):8}{(big[0] if big else 0):8}"
                  f"{(big[1] if len(big) > 1 else 0):6}"
                  f"{(big[2] if len(big) > 2 else 0):6}"
                  f"{np.sqrt((vel**2).sum(1)).mean():10.4f}")


if __name__ == "__main__":
    main()
