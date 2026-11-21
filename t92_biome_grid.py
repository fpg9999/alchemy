# -*- coding: utf-8 -*-
"""T92: 元素子集群系网格 —— 对 9 元素的所有 3/4/5 元子集各跑一次小型环境，
统计终态多样性/优势度/分层/反应类型，输出一个汇总 JSON，供分类与作图。

复用 T88 的投料配平（build_feed）与 T87 的 AsymWorld（连续重力 + 非对称力 +
骨架占格 + resolve 完全/不完全反应 + 10°C 恒温），只是把规模缩小以便覆盖全部
子集：W=160, H=110, n_mol=700, ticks=400, cool_ticks=250。

用法：
  python t92_biome_grid.py                    # 全部 3/4/5 元子集（336 个）
  python t92_biome_grid.py --sizes 3          # 只跑 3 元（84 个）
  python t92_biome_grid.py --quick            # 每个子集 150 拍，冒烟用
"""
import argparse
import io
import itertools
import json
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import t87_env_asym as T87          # noqa: E402
import t88_biomes as B              # noqa: E402

ELEMS = ["O", "X", "C", "K", "A", "F", "P", "W", "L"]


def classify(dom, top2_sum):
    if dom >= 0.30:
        return "A 单主"
    if dom >= 0.15:
        return "B 主辅"
    if top2_sum >= 0.50:
        return "C 双主"
    return "D 多主"


def run_one(subset, args, recs):
    subset = tuple(sorted(subset))
    name = "B%d_%s" % (len(subset), "".join(subset))
    t0 = time.time()
    feed, meta = B.build_feed(list(subset), n_mol=args.n_mol, seed=args.seed)
    w = T87.AsymWorld(args.W, args.H, args.seed, feed, recs,
                      cap=args.cap, p_react=args.p_react,
                      force_r=args.force_r, t_end=10.0, cool_k=10.0,
                      cool_ticks=args.cool_ticks, track_every=10 ** 9)
    w.ticks_total = args.ticks
    s0 = w.snapshot(0)
    el0 = w.elements()
    for t in range(1, args.ticks + 1):
        w.t = t
        w.step()
    s1 = w.snapshot(args.ticks)
    el1 = w.elements()
    comp = w.composition()
    total = sum(comp.values()) or 1
    top = sorted(comp.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
    hhi = sum((c / total) ** 2 for c in comp.values())
    dom = top[0][1] / total if top else 0.0
    top2 = sum(c for _, c in top[:2]) / total if top else 0.0
    rec = {
        "name": name,
        "subset": list(subset),
        "n_elem": len(subset),
        "feed_pool": meta.get("n_species"),
        "n0": s0["n"], "n_final": s1["n"],
        "cells_used": s1["cells_used"],
        "n_distinct": s1["n_distinct"],
        "n_react": s1["n_react"],
        "n_complete": s1["n_complete"],
        "n_incomplete": s1["n_incomplete"],
        "n_none": s1["n_none"],
        "n_new": s1["n_new_species"],
        "hhi": round(hhi, 4),
        "dominant": top[0][0] if top else "",
        "dominant_share": round(dom, 4),
        "top2_share": round(top2, 4),
        "top": [[f, c] for f, c in top],
        "y_mean_mass": s1["y_mean_mass"],
        "tiers_mass": s1.get("tiers", {}).get("mass"),
        "clusters": {"n": s1["clusters"]["n_components"],
                     "max": s1["clusters"]["max"],
                     "in_big": s1["clusters"]["in_big"]},
        "band_react": s1.get("band_react"),
        "mode_counts": s1.get("mode_counts", {}),
        "rho_mean": s1["rho"]["mean"],
        "conservation_ok": el0 == el1,
        "runtime_s": round(time.time() - t0, 2),
    }
    rec["type"] = classify(dom, top2)
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="+", default=[3, 4, 5])
    ap.add_argument("--W", type=int, default=160)
    ap.add_argument("--H", type=int, default=110)
    ap.add_argument("--n-mol", type=int, default=700)
    ap.add_argument("--ticks", type=int, default=400)
    ap.add_argument("--cool-ticks", type=int, default=250)
    ap.add_argument("--cap", type=int, default=36)
    ap.add_argument("--p-react", type=float, default=0.012)
    ap.add_argument("--force-r", type=int, default=2)
    ap.add_argument("--seed", type=int, default=20261120)
    ap.add_argument("--out", default=os.path.join(BASE, "t92_biome_grid.json"))
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args(argv)
    if a.quick:
        a.ticks = 150
        a.cool_ticks = 100
        a.n_mol = 300

    recs = B.catalog()
    subsets = []
    for n in a.sizes:
        subsets += [tuple(c) for c in itertools.combinations(ELEMS, n)]
    print("[grid] subsets=%d  sizes=%s  W=%d H=%d n_mol=%d ticks=%d"
          % (len(subsets), a.sizes, a.W, a.H, a.n_mol, a.ticks), flush=True)

    out = {"config": {"W": a.W, "H": a.H, "n_mol": a.n_mol,
                      "ticks": a.ticks, "cool_ticks": a.cool_ticks,
                      "cap": a.cap, "p_react": a.p_react,
                      "force_r": a.force_r, "seed": a.seed,
                      "rules": "T87: 连续重力+非对称力+骨架占格+resolve(完全/不完全)+10C恒温",
                      "elements": ELEMS},
           "biomes": []}
    t_all = time.time()
    for idx, subset in enumerate(subsets):
        try:
            rec = run_one(subset, a, recs)
        except Exception as e:  # 不让单个子集打断整夜
            print("[grid][ERR] %s: %r" % ("".join(subset), e), flush=True)
            continue
        out["biomes"].append(rec)
        io.open(a.out, "w", encoding="utf-8").write(
            json.dumps(out, ensure_ascii=False))
        print("[grid] %3d/%d  %-18s pool=%4d N=%4d dist=%4d HHI=%.3f "
              "dom=%.2f %-6s %s  %.1fs"
              % (idx + 1, len(subsets), rec["name"], rec["feed_pool"],
                 rec["n_final"], rec["n_distinct"], rec["hhi"],
                 rec["dominant_share"], rec["type"],
                 "ok" if rec["conservation_ok"] else "EL-BAD",
                 rec["runtime_s"]), flush=True)
    print("[grid] done  biomes=%d  total=%.1fs  -> %s"
          % (len(out["biomes"]), time.time() - t_all, a.out), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
