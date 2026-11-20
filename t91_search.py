# -*- coding: utf-8 -*-
"""T91 v2: 搜索"主体 A + 锁住的 B + 只在 A 附近反应的 C"。

关键改动（对照 m03781 的要求）：
 - A+B 相邻不反应：用 resolve([A,B], T) 在"热区温度 T_hot"与"环境温度 T_env"都不反应（none）；
 - B+C 只在热区反应：resolve([B,C], T_hot) 产出含 A 的 complete/incomplete，
   而 resolve([B,C], T_env) 为 none；
 - 温度窗口：T_env < csum(B+C) <= T_hot < csum(A+B)，其中 T_hot = A 的温度轴（L=1,F=2）；
 - 吸引锁：A<->B 双向非对称力 >= LOCK_W；A 自粘 >= SELF_A；B、C 自粘 < SELF_BC；
 - A 小分子 5~10 原子，B、C 2~4 原子。
"""
import io
import json
import os
import sys
import time
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import natural_engine as E  # noqa: E402
from alchemy import three_su as TS  # noqa: E402
from alchemy.core.elements import ORDER  # noqa: E402

K_A, K_R = TS.K_A, TS.K_R
LOCK_W = 1.0
SELF_A = 1.2
SELF_BC = 0.6
T_ENV = 2.0
MAX_A = 12

_F_CACHE = {}


def load_catalog():
    path = os.path.join(BASE, "t4_catalog_all_validated.json")
    recs = json.load(io.open(path, encoding="utf-8"))
    idx = {}
    for r in recs:
        if r["formula"] not in idx:
            idx[r["formula"]] = r
    return idx


def comp_of(rec):
    c = Counter()
    for a in rec["atoms"]:
        c[a] += 1
    return c


def vec_of(comp):
    return [int(comp.get(e, 0)) for e in ORDER]


def therm_T(comp):
    return comp.get("L", 0) + 2 * comp.get("F", 0)


def cval(comp):
    return max(1, sum(comp.values()) - 1)


def f_products(vec):
    key = tuple(vec)
    if key in _F_CACHE:
        return _F_CACHE[key]
    try:
        prods = E.complete_products(list(vec))
    except Exception:
        prods = None
    out = sorted(p.get("formula", "?") for p in prods) if prods else None
    _F_CACHE[key] = out
    return out


def modict(rec, comp):
    """构造 resolve 需要的分子 dict。"""
    v = vec_of(comp)
    return {"formula": rec["formula"], "atoms": tuple(rec["atoms"]),
            "edges": [tuple(e) for e in rec["edges"]], "vec": v,
            "c": max(1, len(rec["atoms"]) - 1), "label": rec["formula"]}


def pair_w(ci, cj):
    si = TS.scores(ci)
    sj = TS.scores(cj)
    return K_A * si["A"] - K_R * sj["D"]


def main():
    t0 = time.time()
    cat = load_catalog()
    print("catalog:", len(cat))
    pool = [f for f, r in cat.items() if 2 <= r["natoms"] <= 5]
    pool.sort(key=lambda f: (cat[f]["natoms"], f))
    comps = {f: comp_of(cat[f]) for f in pool}
    print("small pool:", len(pool))

    triples, seen = [], set()
    n_pair = 0
    for i in range(len(pool)):
        B = pool[i]
        vB = vec_of(comps[B])
        for j in range(i + 1, len(pool)):
            C = pool[j]
            vC = vec_of(comps[C])
            tot = [a + b for a, b in zip(vB, vC)]
            if sum(tot) > MAX_A:
                continue
            n_pair += 1
            prods = f_products(tot)
            if not prods or len(prods) != 1:
                continue
            A = prods[0]
            if A not in cat or cat[A]["natoms"] > MAX_A:
                continue
            k = (A, B, C)
            if k in seen:
                continue
            seen.add(k)
            triples.append(k)
    print("pairs:", n_pair, " BC->A triples:", len(triples),
          "(%.1fs)" % (time.time() - t0))

    stage = Counter()
    rows = []
    for (A, B, C) in triples:
        cA, cB, cC = (comp_of(cat[A]), comps[B], comps[C])
        sA, sB, sC = TS.scores(cA), TS.scores(cB), TS.scores(cC)
        TA = therm_T(cA)
        csum_bc = cval(cB) + cval(cC)
        csum_ab = cval(cA) + cval(cB)

        # 温度窗口：热区必须高到能进 complete 分支（A+B 惰性、B+C 生成 A）
        if TA < csum_ab:
            stage["hot too low"] += 1
            continue
        if csum_bc > TA:
            stage["window_fail"] += 1
            continue
        # 吸引/自粘
        wAB, wBA = pair_w(cA, cB), pair_w(cB, cA)
        wAC = pair_w(cA, cC)
        wA_self = K_A * sA["A"] - K_R * sA["D"]
        wB_self = K_A * sB["A"] - K_R * sB["D"]
        wC_self = K_A * sC["A"] - K_R * sC["D"]
        if wAB < LOCK_W:
            stage["no_lock"] += 1
            continue
        if wA_self < SELF_A:
            stage["A not sticky"] += 1
            continue
        # resolve 行为
        mA, mB, mC = modict(cat[A], cA), modict(cat[B], cB), modict(cat[C], cC)
        try:
            r_ab_env = E.resolve([mA, mB], T_ENV)
            r_ab_hot = E.resolve([mA, mB], TA)
            r_bc_env = E.resolve([mB, mC], T_ENV)
            r_bc_hot = E.resolve([mB, mC], TA)
        except Exception:
            stage["resolve_error"] += 1
            continue
        t_ab_env, t_ab_hot = r_ab_env["type"], r_ab_hot["type"]
        t_bc_env, t_bc_hot = r_bc_env["type"], r_bc_hot["type"]
        ab_hot_p = sorted(p["formula"] for p in (r_ab_hot["products"] or []))
        bc_hot_p = sorted(p["formula"] for p in (r_bc_hot["products"] or []))
        if t_ab_hot != "complete" or ab_hot_p != sorted([A, B]):
            stage["A+B reacts (hot)"] += 1
            continue
        if t_bc_hot != "complete" or bc_hot_p != [A]:
            stage["B+C not clean A (hot)"] += 1
            continue
        if t_ab_env not in ("none", "complete") or (
                t_ab_env == "complete" and
                sorted(p["formula"] for p in (r_ab_env["products"] or [])) != sorted([A, B])):
            stage["A+B reacts (ambient)"] += 1
            continue
        hot_prods = bc_hot_p

        score = (0.40 * min(1.0, min(wAB, wBA) / 3.0) +
                 0.25 * min(1.0, wA_self / 2.5) +
                 0.20 * min(1.0, (TA - T_ENV) / 8.0) +
                 0.15 * (1.0 if A in hot_prods else 0.0))
        rows.append({
            "A": A, "B": B, "C": C, "A_atoms": cat[A]["natoms"],
            "wAB": round(wAB, 3), "wBA": round(wBA, 3),
            "wAC": round(wAC, 3),
            "A_self": round(wA_self, 3),
            "B_self": round(wB_self, 3), "C_self": round(wC_self, 3),
            "A_att": round(sA["A"], 2), "A_rep": round(sA["D"], 2),
            "A_ratt": sA["r_att"], "A_rrep": sA["r_rep"],
            "T_hot": TA, "T_env": T_ENV,
            "csum_BC": csum_bc, "csum_AB": csum_ab,
            "bc_env": t_bc_env, "bc_hot": t_bc_hot,
            "ab_env": t_ab_env, "ab_hot": t_ab_hot,
            "bc_hot_products": hot_prods,
            "score": round(score, 4),
        })
    rows.sort(key=lambda x: -x["score"])
    print("\nstage counts:", dict(stage))
    print("candidates:", len(rows))

    res = {"meta": {"engine": "natural_engine rules 1~11", "lock_w": LOCK_W,
                    "self_A": SELF_A, "self_BC": SELF_BC, "T_env": T_ENV,
                    "small_pool": len(pool), "pairs": n_pair,
                    "triples_bc_to_a": len(triples),
                    "stages": dict(stage), "elapsed_s": round(time.time() - t0, 1)},
           "candidates": rows}
    with io.open(os.path.join(BASE, "t91_candidates.json"), "w",
                 encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)

    print("\n== top 30 ==")
    print("%-2s %-11s %-6s %-6s %5s %5s %5s %6s %5s %4s %4s %6s" % (
        "#", "A", "B", "C", "wAB", "wBA", "Aself", "B/Cself", "Thot", "csBC", "csAB", "bc_hot"))
    for i, x in enumerate(rows[:30]):
        print("%-2d %-11s %-6s %-6s %5.2f %5.2f %5.2f %6.2f/%.2f %5d %4d %4d %6s" % (
            i + 1, x["A"], x["B"], x["C"], x["wAB"], x["wBA"], x["A_self"],
            x["B_self"], x["C_self"], x["T_hot"], x["csum_BC"], x["csum_AB"],
            x["bc_hot"]))
    print("\nsaved t91_candidates.json")


if __name__ == "__main__":
    main()
