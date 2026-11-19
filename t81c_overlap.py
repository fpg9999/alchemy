# -*- coding: utf-8 -*-
"""T81c 配对归一化方案三选一：family-Jaccard / atom-Jaccard / atom-cosine"""
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


def j_atom(ci, cj):
    num = sum(min(ci.get(e, 0), cj.get(e, 0)) for e in TS.PTS)
    den = sum(max(ci.get(e, 0), cj.get(e, 0)) for e in TS.PTS)
    return num / den if den else 0.0


def j_cos(ci, cj):
    num = sum(ci.get(e, 0) * cj.get(e, 0) for e in TS.PTS)
    a = sum(ci.get(e, 0) ** 2 for e in TS.PTS) ** 0.5
    b = sum(cj.get(e, 0) ** 2 for e in TS.PTS) ** 0.5
    return num / (a * b) if a and b else 0.0


def pair(ci, cj, ka, kr, mode):
    si, sj = TS.scores(ci), TS.scores(cj)
    r_att = max(si["r_att"], sj["r_att"])
    r_rep = max(si["r_rep"], sj["r_rep"])
    if mode == "family":
        j_att, j_rep = TS.overlap(ci, cj)
    elif mode == "atom":
        j_att = j_rep = j_atom(ci, cj)
    else:
        j_att = j_rep = j_cos(ci, cj)
    att = ka * ((si["A"] * sj["A"]) ** 0.5) / 3.0 * j_att
    rep = kr * ((si["D"] * sj["D"]) ** 0.5) / 3.0 * j_rep
    return att, rep


random.seed(11)
K = 60000
pairs = []
while len(pairs) < K:
    i, j = random.randrange(N), random.randrange(N)
    if i != j:
        pairs.append((i, j))

for mode in ("family", "atom", "cos"):
    for ka, kr in ((2.5, 0.5), (2.0, 0.4)):
        sw = sstrong = 0
        for c in comps:
            a, r = pair(c, c, ka, kr, mode)
            if a > r:
                sw += 1
            if a - r >= 1.0:
                sstrong += 1
        atts, reps = [], []
        for i, j in pairs:
            a, r = pair(comps[i], comps[j], ka, kr, mode)
            atts.append(a)
            reps.append(r)
        dw = sum(1 for a, r in zip(atts, reps) if a < 0.5 and r < 0.5)
        weak = sum(1 for a, r in zip(atts, reps) if a < 1.0 and r < 1.0)
        st_att = sum(1 for a in atts if a >= 1.0)
        print("%-7s κA=%.1f κR=%.1f | 同种净吸 %.1f%% 强粘 %.1f%% | 异种 att 均 %.2f 双弱(0.5) %.1f%% 双弱(1.0) %.1f%% 强吸 %.1f%%" % (
            mode, ka, kr, 100.0 * sw / N, 100.0 * sstrong / N,
            st.fmean(atts), 100.0 * dw / K, 100.0 * weak / K, 100.0 * st_att / K))
