# -*- coding: utf-8 -*-
"""T81 三素相互作用 全目录校准（只读）
统计：同种吸引/强粘比例、异种"双弱"比例、半径分布、27 格、敏感性。
"""
import io
import json
import os
import random
import statistics as st

from alchemy import three_su as TS

BASE = r"G:\AI work\deepseek\work1\alchemy"
CAT = os.path.join(BASE, "t4_catalog_all_validated.json")

records = json.load(io.open(CAT, encoding="utf-8"))
comps = [TS.parse_formula(r["formula"]) for r in records]
scs = [TS.scores(c) for c in comps]
N = len(comps)
print("catalog formulas:", N)

# ---------- 1. 单分子分布 ----------
for key in ("A", "B", "D"):
    xs = [s[key] for s in scs]
    q = st.quantiles(xs, n=3)
    z = sum(1 for x in xs if x == 0)
    print("%s mean %.2f median %.2f q33 %.2f q67 %.2f | 缺族 %d (%.1f%%)" % (
        key, st.fmean(xs), st.median(xs), q[0], q[1], z, 100.0 * z / N))
for key in ("r_att", "r_rep", "P", "Q", "S"):
    xs = [s[key] for s in scs]
    print("%s mean %.2f min %d max %d | hist %s" % (
        key, st.fmean(xs), min(xs), max(xs),
        {v: xs.count(v) for v in sorted(set(xs))} if key.startswith("r") else ""))

# ---------- 2. 同种（J=1, d=1） ----------
same = [TS.pair_force(c, c, 1) for c in comps]
w_self = [p["w"] for p in same]
att_self = [p["att"] for p in same]
rep_self = [p["rep"] for p in same]
for name, xs in (("w_self", w_self), ("att_self", att_self), ("rep_self", rep_self)):
    q = st.quantiles(xs, n=10)
    print("%s min %.2f q10 %.2f median %.2f q90 %.2f max %.2f" % (
        name, min(xs), q[0], st.median(xs), q[8], max(xs)))
for thr, lab in ((0.0, "w>0（净吸引）"), (0.2, "w≥0.2（吸引）"),
                 (1.0, "w≥1.0（强粘）"), (0.0, "w≤0（不吸/斥）")):
    c = sum(1 for w in w_self if (w > thr if thr == 0.0 and "净" in lab else w >= thr))
    if "≤" in lab:
        c = sum(1 for w in w_self if w <= 0)
    print("  同种 %s: %d (%.1f%%)" % (lab, c, 100.0 * c / N))

# 按"有聚素/无聚素"分
has_att = [s for s, c in zip(scs, comps) if s["A"] > 0]
print("有聚素分子 %d (%.1f%%), 其中 w_self>0: %.1f%%" % (
    len(has_att), 100.0 * len(has_att) / N,
    100.0 * sum(1 for s in has_att if True) / len(has_att)))

# ---------- 3. 异种随机对 ----------
random.seed(20261120)
K = 100000
pairs = []
while len(pairs) < K:
    i = random.randrange(N)
    j = random.randrange(N)
    if i != j:
        pairs.append((i, j))
res = []
for i, j in pairs:
    pf = TS.pair_force(comps[i], comps[j], 1)
    res.append((pf["att"], pf["rep"], pf["w"], pf["j_att"], pf["j_rep"]))
att = [r[0] for r in res]
rep = [r[1] for r in res]
w = [r[2] for r in res]
ja = [r[3] for r in res]
print("\n异种 %d 对：" % K)
print("  att mean %.2f median %.2f q10 %.2f q90 %.2f | rep mean %.3f median %.3f q90 %.3f" % (
    st.fmean(att), st.median(att), st.quantiles(att, n=10)[0], st.quantiles(att, n=10)[8],
    st.fmean(rep), st.median(rep), st.quantiles(rep, n=10)[8]))
print("  J_att mean %.2f median %.2f | J_att<0.1: %.1f%%" % (
    st.fmean(ja), st.median(ja), 100.0 * sum(1 for x in ja if x < 0.1) / K))
for A_TH, R_TH in ((0.5, 0.5), (0.6, 0.4), (0.3, 0.3), (1.0, 1.0)):
    both_weak = sum(1 for a, r, *_ in res if a < A_TH and r < R_TH)
    print("  双弱(att<%s,rep<%s): %.1f%%" % (A_TH, R_TH, 100.0 * both_weak / K))
for A_TH in (0.5, 1.0, 1.5):
    print("  异种强吸(att≥%.1f): %.1f%%" % (A_TH, 100.0 * sum(1 for a, *_ in res if a >= A_TH) / K))
print("  异种净斥(w<-0.2): %.1f%% | 净吸(w>0.2): %.1f%%" % (
    100.0 * sum(1 for x in w if x < -0.2) / K, 100.0 * sum(1 for x in w if x > 0.2) / K))

# ---------- 4. 27 格（A/B/D 各 1.5/2.5） ----------
def g(x):
    return 0 if x <= 1.5 else (1 if x <= 2.5 else 2)
cells = {}
for s in scs:
    k = (g(s["A"]), g(s["B"]), g(s["D"]))
    cells[k] = cells.get(k, 0) + 1
GN = {0: "低", 1: "中", 2: "高"}
print("\n27 格（A/B/D 阈值 1.5/2.5），覆盖 %d/27：" % len(cells))
for k in sorted(cells, key=lambda k: (-k[0], -k[1], -k[2])):
    print("  聚%s 散%s 动%s : %6d (%.1f%%)" % (GN[k[0]], GN[k[1]], GN[k[2]], cells[k], 100.0 * cells[k] / N))

# ---------- 5. 敏感性 κ ----------
base_K = 2.5
print("\n敏感性（同种 w>0 / 异种双弱(att<0.5,rep<0.5) / 异种强吸(att≥1)）：")
for ka, kr in ((2.0, 0.4), (2.5, 0.5), (3.0, 0.6), (2.5, 0.3), (2.5, 0.8), (2.0, 0.5)):
    sw = 0
    for c in comps:
        a, _, d, _ = TS.points(c)
        n_att = sum(x for el, x in c.items() if TS.FAM.get(el) == "att")
        n_rep = sum(x for el, x in c.items() if TS.FAM.get(el) == "rep")
        A = a / n_att if n_att else 0.0
        D = d / n_rep if n_rep else 0.0
        if ka * A / 3 - kr * D / 3 > 0:
            sw += 1
    cw = cen = 0
    for _ in range(5000):
        i = random.randrange(N)
        j = random.randrange(N)
        pf = TS.pair_force(comps[i], comps[j], 1, k_a=ka, k_r=kr)
        if pf["att"] < 0.5 and pf["rep"] < 0.5:
            cw += 1
        if pf["att"] >= 1.0:
            cen += 1
    print("  κA=%.1f κR=%.1f: 同种%.1f%% 双弱%.1f%% 强吸%.1f%%" % (
        ka, kr, 100.0 * sw / N, 100.0 * cw / 5000, 100.0 * cen / 5000))

# ---------- 6. 结构化输出 ----------
out = {
    "meta": {"catalog": N, "seed": 20261120, "pairs": K,
             "k_a": TS.K_A, "k_r": TS.K_R, "w_strong": TS.W_STRONG, "w_weak": TS.W_WEAK,
             "unit": TS.UNIT},
    "axes": {key: {"mean": round(st.fmean([s[key] for s in scs]), 4),
                   "median": round(st.median([s[key] for s in scs]), 4),
                   "zero": sum(1 for s in scs if s[key] == 0)} for key in ("A", "B", "D")},
    "radii": {key: {str(v): sum(1 for s in scs if s[key] == v) for v in (1, 2, 3)}
              for key in ("r_att", "r_rep")},
    "same": {
        "att_mean": round(st.fmean(att_self), 4),
        "rep_mean": round(st.fmean(rep_self), 4),
        "w_median": round(st.median(w_self), 4),
        "net_attract": sum(1 for x in w_self if x > 0),
        "attract_02": sum(1 for x in w_self if x >= 0.2),
        "strong_10": sum(1 for x in w_self if x >= 1.0),
        "none_or_repel": sum(1 for x in w_self if x <= 0),
    },
    "cross": {
        "att_mean": round(st.fmean(att), 4), "att_median": round(st.median(att), 4),
        "rep_mean": round(st.fmean(rep), 4), "rep_median": round(st.median(rep), 4),
        "double_weak_05": round(100.0 * sum(1 for a, r, *_ in res if a < 0.5 and r < 0.5) / K, 2),
        "double_weak_10": round(100.0 * sum(1 for a, r, *_ in res if a < 1.0 and r < 1.0) / K, 2),
        "strong_att_10": round(100.0 * sum(1 for a, *_ in res if a >= 1.0) / K, 2),
        "strong_att_15": round(100.0 * sum(1 for a, *_ in res if a >= 1.5) / K, 2),
        "net_repel": round(100.0 * sum(1 for x in w if x < -0.2) / K, 2),
    },
    "cells27": {"covered": len(cells), "counts": {"%d%d%d" % k: cells[k] for k in sorted(cells)}},
}
with io.open(os.path.join(BASE, "t81_calibration.json"), "w", encoding="utf-8") as fp:
    json.dump(out, fp, ensure_ascii=False, indent=1)
print("\nsaved t81_calibration.json")
