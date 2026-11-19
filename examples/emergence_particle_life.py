# -*- coding: utf-8 -*-
"""涌现实验：非对称力 + 惯性 + 连续空间，看能否长出 Particle Life 式的结构。

力的规则（非对称的核心）
------------------------
对分子 i 与 j（距离 d，作用半径 D = max(D_i, D_j)）：

    近距  d < 0.5·D :  f = − R_j     ← 被“对方”的动素推开
    中距  d < D     :  f = + A_i     ← 被“自己”的聚素拉过去
    远处  d ≥ D     :  f = 0

于是 ``k_ij = A_i − R_j``，``k_ji = A_j − R_i``，**二者不等**——
牛顿第三定律被打破，系统才可能自推进。

用法
----
    python examples/emergence_particle_life.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lattice_sim import four_values  # noqa: E402

A_MAX, R_MAX = 10.0, 10.0
N = 700
STEPS = 1500
DT = 0.02
DAMP = 0.94
RANGE_SCALE = 1.0 / 6.0
SEED = 20261120


def load_types(world="data/biomes/t62_phaseA.json", top=10):
    d = json.loads(Path(world).read_text(encoding="utf-8"))
    sp = [s for s in d["species"] if s.get("in_catalog")]
    sp.sort(key=lambda s: -s["count"])
    out = []
    for s in sp[:top]:
        a, r, da, dr = four_values(s["formula"])
        out.append({"f": s["formula"], "a": a, "r": r,
                    "d": max(da, dr) * RANGE_SCALE})
    return out


def simulate(asymmetric: bool, types, seed=SEED):
    rng = np.random.default_rng(seed)
    ntype = len(types)
    A = np.array([t["a"] for t in types])
    R = np.array([t["r"] for t in types])
    D = np.array([t["d"] for t in types])

    tid = rng.integers(0, ntype, N)
    pos = rng.random((N, 2))
    vel = np.zeros((N, 2))

    # 每个分子的属性（按类型展开到个体）
    Ai = A[tid]
    Ri = R[tid]
    Di = D[tid]

    ke_hist = []
    for step in range(STEPS):
        # 周期位移矩阵
        dx = pos[None, :, 0] - pos[:, None, 0]
        dy = pos[None, :, 1] - pos[:, None, 1]
        dx -= np.round(dx)
        dy -= np.round(dy)
        dist = np.hypot(dx, dy)
        np.fill_diagonal(dist, np.inf)

        Dij = np.maximum(Di[:, None], Di[None, :])
        inside = dist < Dij
        near = dist < 0.5 * Dij

        if asymmetric:
            f_att = np.broadcast_to(Ai[:, None], (N, N))       # 我的聚素
            f_rep = np.broadcast_to(Ri[None, :], (N, N))       # 你的动素
        else:
            f_att = Ai[:, None] * Ai[None, :] / A_MAX
            f_rep = Ri[:, None] * Ri[None, :] / R_MAX

        f = np.where(near, -f_rep, np.where(inside, f_att, 0.0))
        # 近距软化，避免奇点
        soft = np.clip(dist / 0.01, 0.0, 1.0)
        f = f * soft
        np.fill_diagonal(f, 0.0)

        ux = np.where(np.isfinite(dist), dx / np.where(dist == 0, 1, dist), 0.0)
        uy = np.where(np.isfinite(dist), dy / np.where(dist == 0, 1, dist), 0.0)
        fx = (f * ux).sum(axis=1)
        fy = (f * uy).sum(axis=1)

        vel = (vel + np.stack([fx, fy], axis=1) * DT) * DAMP
        pos = (pos + vel * DT) % 1.0
        ke_hist.append(float((vel ** 2).sum() / N))

    return pos, vel, tid, ke_hist


def clusters(pos, tid, cut=0.06):
    """简单连通团：距离 < cut 且同类型视为同团。"""
    n = len(pos)
    seen = [False] * n
    groups = []
    for i in range(n):
        if seen[i]:
            continue
        stack, seen[i] = [i], True
        mem = []
        while stack:
            a = stack.pop()
            mem.append(a)
            d = np.hypot(*(pos - pos[a]).T)
            d = np.minimum(d, 1 - d)
            for b in np.where((d < cut) & (~np.array(seen)) & (tid == tid[a]))[0]:
                seen[b] = True
                stack.append(int(b))
        groups.append(mem)
    groups.sort(key=len, reverse=True)
    return groups


def render(pos, tid, types, path, size=420):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (size, size), (252, 252, 252))
    d = ImageDraw.Draw(img)
    colors = [(70, 185, 91), (245, 166, 35), (63, 208, 201), (142, 90, 168),
              (59, 111, 212), (231, 76, 60), (240, 122, 200), (179, 179, 179)]
    for (x, y), t in zip(pos, tid):
        cx, cy = x * size, y * size
        r = 3
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=colors[int(t) % len(colors)])
    img.save(path)


def main():
    types = load_types()
    print("参与实验的分子类型：")
    for t in types:
        print(f"  {t['f']:12} 引力 {t['a']:5.2f}  斥力 {t['r']:5.2f}  半径 {t['d']:.3f}")
    print()

    for asym in (False, True):
        pos, vel, tid, ke = simulate(asym, types)
        groups = clusters(pos, tid)
        big = [g for g in groups if len(g) >= 5]
        tag = "非对称" if asym else "对称（对照）"
        print(f"=== {tag} ===")
        print(f"  平均动能: 末段 {np.mean(ke[-100:]):.3e}   峰值 {max(ke):.3e}")
        print(f"  团数: {len(groups)}（≥5 个成员的团 {len(big)} 个）")
        print(f"  最大团: {len(groups[0]) if groups else 0} 个成员")
        # 大团的移动速度
        if big:
            speeds = []
            for g in big[:5]:
                v = vel[g]
                speeds.append(float(np.hypot(v[:, 0].mean(), v[:, 1].mean())))
            print(f"  最大 5 个团的质心速度: " + ", ".join(f"{s:.3f}" for s in speeds))
        print()
        render(pos, tid, types, f"images/emergence_{'asym' if asym else 'sym'}.png")

    print("图: images/emergence_sym.png / images/emergence_asym.png")


if __name__ == "__main__":
    main()
