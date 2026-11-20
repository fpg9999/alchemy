# -*- coding: utf-8 -*-
"""T88 环境群系：在 T87 规则下（连续重力 + 非对称力 + 骨架占格 + resolve + 10°C 恒温）
用不同元素子集构造环境群系，各跑一条轨迹并做对比分析。

元素子集（3~9 个）：
  B3_OFL    {O,F,L}    三族各取一个（聚3/散1/动2）
  B3_OXC    {O,X,C}    概念族全三价（无散素/动素）
  B4_OXKF   {O,X,K,F}  概念+散素（缺动素）
  B5_OXKAF  {O,X,K,A,F}
  B6_OXCKAF {O,X,C,K,A,F}  缺动素（P/W/L）
  B9_all9   九元素全开

投料：t4_catalog 中"元素集合 ⊆ 子集、2~8 原子"的稳定/有效分子式，
用 IPF 配平到各元素等份额（每种 1/|S|），取 n 个分子。
其余规则完全沿用 T87（连续重力 G=0.30、非对称力 KA=2.5/KR=0.5 无匹配度、
骨架 k 格占位、resolve 完全/不完全反应、2~4 分子同组、cap 36、温度 1000→10°C 后恒温）。

用法：
  python t88_biomes.py --biome all
  python t88_biomes.py --biome B3_OFL
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import re
import sys
import time

import t87_env_asym as T87
import t83_env_axes as T83
from alchemy.core.elements import ORDER as ELEM_ORDER

BASE = os.path.dirname(os.path.abspath(__file__))

ELEMS = list(ELEM_ORDER)          # ['O','X','C','P','W','L','K','A','F']

BIOMES = {
    "B3_OFL": (["O", "F", "L"], "三族各一：聚3/散1/动2"),
    "B3_OXC": (["O", "X", "C"], "概念族全三价：聚素齐全，无散/动"),
    "B4_OXKF": (["O", "X", "K", "F"], "概念+散素（缺动素）"),
    "B5_OXKAF": (["O", "X", "K", "A", "F"], "两种散素 + 一种动素缺失"),
    "B6_OXCKAF": (["O", "X", "C", "K", "A", "F"], "缺动素（P/W/L）：只有吸引与排斥的弱化版"),
    "B9_all9": (list(ELEMS), "九元素全开"),
}

VALENCE = {"O": 3, "X": 3, "F": 3, "K": 2, "W": 2, "L": 2,
           "P": 1, "A": 1, "C": 1}


# ---------------------------------------------------------------------------
def catalog():
    if not hasattr(catalog, "_recs"):
        catalog._recs = T83.catalog_index()
    return catalog._recs


def build_feed(subset, n_mol=2500, natoms_max=8, iters=250, damp=0.5,
               seed=20261120):
    """从目录中挑元素集合 ⊆ subset 的分子式，IPF 配平到等元素份额。"""
    recs = catalog()
    S = set(subset)
    cand = []
    for f, r in recs.items():
        at = r["atoms"]
        if not (2 <= len(at) <= natoms_max):
            continue
        if not set(at) <= S:
            continue
        cand.append((f, T83.comp_of(f)))
    if not cand:
        raise SystemExit("no candidates for subset %r" % (subset,))
    comps = [c for _, c in cand]
    target = {e: 1.0 / len(S) for e in S}
    w = [1.0] * len(cand)

    for _ in range(iters):
        cur = {e: 0.0 for e in S}
        for wi, comp in zip(w, comps):
            for e, k in comp.items():
                cur[e] += wi * k
        tot = sum(cur.values())
        if tot <= 0:
            break
        fac = {}
        for e in S:
            want = target[e] * tot
            fac[e] = (want / cur[e]) if cur[e] > 1e-12 else 1.0
        new = []
        for wi, comp in zip(w, comps):
            ni = float(sum(comp.values()))
            mult = 1.0
            for e, k in comp.items():
                mult *= fac[e] ** (k / ni)
            new.append(wi * (mult ** damp))
        s = sum(new)
        if s <= 0:
            break
        w = [x * n_mol / s for x in new]

    # 取整（最大余数）
    ints = [int(math.floor(x)) for x in w]
    rem = n_mol - sum(ints)
    order = sorted(range(len(w)), key=lambda i: -(w[i] - ints[i]))
    for i in order[:max(0, rem)]:
        ints[i] += 1
    while sum(ints) > n_mol:
        i = max(range(len(ints)), key=lambda k: ints[k])
        ints[i] -= 1
    feed = []
    for (f, _), c in zip(cand, ints):
        if c > 0:
            feed.extend([f] * c)

    # 统计
    cur = {e: 0.0 for e in S}
    atoms = 0
    for (f, comp), c in zip(cand, ints):
        for e, k in comp.items():
            cur[e] += c * k
        atoms += c * sum(comp.values())
    tot = sum(cur.values())
    share = {e: cur[e] / tot for e in S} if tot else {}
    val = {1: 0.0, 2: 0.0, 3: 0.0}
    for e in S:
        val[VALENCE[e]] += share.get(e, 0.0)
    meta = {"target": n_mol, "n_molecules": len(feed), "atoms": int(atoms),
            "atoms_per_mol": round(atoms / max(1, len(feed)), 2),
            "share": {e: round(v, 4) for e, v in share.items()},
            "valence_share": {str(k): round(v, 4) for k, v in val.items()},
            "n_species": sum(1 for c in ints if c > 0),
            "candidates": len(cand), "ipf_iters": iters}
    return feed, meta


# ---------------------------------------------------------------------------
def run_biome(name, subset, desc, W=240, H=160, seed=20261120,
              n_mol=2500, ticks=800, cool_ticks=400, cap=36,
              p_react=0.012, force_r=2, snap_every=100, track_every=25,
              out_dir=BASE):
    t_start = time.time()
    recs = catalog()
    feed, meta = build_feed(subset, n_mol=n_mol, seed=seed)
    w = T87.AsymWorld(W, H, seed, feed, recs, cap=cap, p_react=p_react,
                      force_r=force_r, t_end=10.0, cool_k=10.0,
                      cool_ticks=cool_ticks, track_every=track_every)
    w.ticks_total = ticks
    snaps = [w.snapshot(0)]
    el0 = w.elements()
    print("[%s] %s  world %dx%d  molecules=%d cells=%d species=%d  "
          "ticks=%d cool=%d" % (name, desc, W, H, len(feed),
                                w.n_cells_used, meta["n_species"],
                                ticks, cool_ticks), flush=True)
    for t in range(1, ticks + 1):
        w.t = t
        w.step()
        if t % snap_every == 0 or t == ticks:
            s = w.snapshot(t)
            snaps.append(s)
            print("  [%s] t=%4d T=%5.1f N=%5d cells=%5d dist=%4d "
                  "react=%5d [C%d I%d N%d] new=%4d max_cl=%4d y=%s  %.0fs"
                  % (name, t, s["T"], s["n"], s["cells_used"],
                     s["n_distinct"], s["n_react"], s["n_complete"],
                     s["n_incomplete"], s["n_none"], s["n_new_species"],
                     s["clusters"]["max"], s["y_mean_mass"],
                     time.time() - t_start), flush=True)
    el1 = w.elements()
    ok = el0 == el1
    comp = w.composition()
    top = sorted(comp.items(), key=lambda kv: (-kv[1], kv[0]))[:30]
    total = sum(comp.values()) or 1
    HHI = sum((c / total) ** 2 for c in comp.values())
    s = snaps[-1]
    result = {
        "config": {
            "engine": "T88 环境群系（T87 规则：连续重力 + 非对称力 + 骨架占格 + resolve）",
            "biome": name, "desc": desc, "subset": subset,
            "W": W, "H": H, "seed": seed, "ticks": ticks,
            "cool_ticks": cool_ticks, "T_end": w.t_end,
            "cap": cap, "p_react": p_react, "force_r": force_r,
            "snap_every": snap_every, "track_every": track_every,
            "feed": meta,
            "runtime_s": round(time.time() - t_start, 2),
        },
        "summary": {
            "n0": snaps[0]["n"], "n_final": s["n"],
            "cells_used": s["cells_used"], "cells_total": W * H,
            "n_distinct": s["n_distinct"],
            "n_complete": s["n_complete"], "n_incomplete": s["n_incomplete"],
            "n_none": s["n_none"], "n_decomp": s["n_decomp"],
            "n_react": s["n_react"], "n_react_fail": s["n_react_fail"],
            "n_new_species": s["n_new_species"],
            "conservation_ok": ok,
            "y_mean_mass": s["y_mean_mass"],
            "tiers": s["tiers"],
            "rho": {"mean": s["rho"]["mean"], "std": s["rho"]["std"]},
            "clusters": s["clusters"],
            "band_react": s["band_react"],
            "mode_counts": s.get("mode_counts", {}),
            "top": [[f, c] for f, c in top],
            "HHI": round(HHI, 4),
            "dominant_share": round(top[0][1] / total, 4) if top else 0.0,
        },
        "snapshots": snaps,
    }
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "t88_env_%s.json" % name.lower())
    io.open(out, "w", encoding="utf-8").write(
        json.dumps(result, ensure_ascii=False))
    print("[%s] saved %s  (%.1fs)  conservation=%s"
          % (name, out, time.time() - t_start, ok), flush=True)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--biome", default="all")
    ap.add_argument("--W", type=int, default=240)
    ap.add_argument("--H", type=int, default=160)
    ap.add_argument("--seed", type=int, default=20261120)
    ap.add_argument("--n-mol", type=int, default=2500)
    ap.add_argument("--ticks", type=int, default=800)
    ap.add_argument("--cool-ticks", type=int, default=400)
    ap.add_argument("--cap", type=int, default=36)
    ap.add_argument("--p-react", type=float, default=0.012)
    ap.add_argument("--snap-every", type=int, default=100)
    ap.add_argument("--out-dir", default=BASE)
    a = ap.parse_args(argv)

    names = list(BIOMES) if a.biome == "all" else [a.biome]
    for name in names:
        subset, desc = BIOMES[name]
        run_biome(name, subset, desc, W=a.W, H=a.H, seed=a.seed,
                  n_mol=a.n_mol, ticks=a.ticks, cool_ticks=a.cool_ticks,
                  cap=a.cap, p_react=a.p_react, snap_every=a.snap_every,
                  out_dir=a.out_dir)


if __name__ == "__main__":
    main()
