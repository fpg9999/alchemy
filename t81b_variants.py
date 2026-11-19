# -*- coding: utf-8 -*-
"""T81b J 归一化方案对比（max 归一 vs Jaccard）"""
import io
import json
import os
import random
import statistics as st

from alchemy import three_su as TS

BASE = r"G:\AI work\deepseek\work1\alchemy"
records = json.load(io.open(os.path.join(BASE, "t4_catalog_all_validated.json"), encoding="utf-8"))
comps = [TS.parse_formula(r["formula"]) for r in records]
scs = [TS.scores(c) for c in comps]
N = len(comps)


def overlap_jac(ci, cj):
    s_att = sum(min(ci.get(e, 0), cj.get(e, 0)) * TS.PTS[e] for e in TS.ATT_ELS)
    s_rep = sum(min(ci.get(e, 0), cj.get(e, 0)) * TS.PTS[e] for e in TS.REP_ELS)
    pi, _, si, _ = TS.points(ci)
    pj, _, sj, _ = TS.points(cj)
    ui = pi + pj - s_att
    uj = si + sj - s_rep
    return (s_att / ui if ui else 0.0), (s_rep / uj if uj else 0.0)


def pair(ci, cj, d, ka, kr, jac):
    si, sj = TS.scores(ci), TS.scores(cj)
    r_att = max(si["r_att"], sj["r_att"])
    r_rep = max(si["r_rep"], sj["r_rep"])
    j_att, j_rep = (overlap_jac(ci, cj) if jac else TS.overlap(ci, cj))
    att = ka * ((si["A"] * sj["A"]) ** 0.5) / 3.0 * j_att * TS.decay(d, r_att)
    rep = kr * ((si["D"] * sj["D"]) ** 0.5) / 3.0 * j_rep * TS.decay(d, r_rep)
    return att, rep


random.seed(7)
K = 60000
pairs = []
while len(pairs) < K:
    i, j = random.randrange(N), random.randrange(N)
    if i != j:
        pairs.append((i, j))

for jac in (False, True):
    for ka, kr in ((2.0, 0.4), (2.5, 0.5), (2.5, 0.3), (2.0, 0.3)):
        # same
        sw = sstrong = 0
        for c in comps:
            a, r = pair(c, c, 1, ka, kr, jac)
            if a > r:
                sw += 1
            if a - r >= 1.0:
                sstrong += 1
        # cross
        atts = []
        reps = []
        for i, j in pairs:
            a, r = pair(comps[i], comps[j], 1, ka, kr, jac)
            atts.append(a)
            reps.append(r)
        dw = sum(1 for a, r in zip(atts, reps) if a < 0.5 and r < 0.5)
        st_att = sum(1 for a in atts if a >= 1.0)
        print("J=%s κA=%.1f κR=%.1f | 同种净吸 %.1f%% 强粘 %.1f%% | 异种 att mean %.2f med %.2f 双弱(0.5) %.1f%% 强吸(≥1) %.1f%%" % (
            "Jaccard" if jac else "max", ka, kr,
            100.0 * sw / N, 100.0 * sstrong / N,
            st.fmean(atts), st.median(atts), 100.0 * dw / K, 100.0 * st_att / K))
