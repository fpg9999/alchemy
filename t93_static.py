# -*- coding: utf-8 -*-
"""T93 静态分析：C 类低温分子能否做多分子生命的保护膜（保温 + 隔绝外来分子）。

不跑动态世界，只做目录级静态计算 + 一维热学/门控估算。

数据源
  t4_catalog_all_validated.json  (84,225 条，字段 formula/atoms/edges/...)
口径（全部来自既有文档，不新造参数）
  三素        alchemy/three_su.py；docs/THREE_SU_AXES.md
              A=P/n_att, B=Q/n_rng, D=S/n_rep；r_att/r_rep；w=Att-Rep
              Att=kA*sqrt(AiAj)/3*J_att*F, Rep=kR*sqrt(DiDj)/3*J_rep*F
              kA=2.5, kR=0.5, d=1 时 F=1，J=元素原子数 Jaccard
              w 档：w>=1.0 强粘；0.2<=w<1.0 弱粘；|w|<0.2 无作用；w<=-0.2 排斥
  三轴        alchemy/attrs.py；docs/MATERIAL_AXES.md
              mass/state/temperature 原始值与档名（轻/中/重、气/液/固、冷/温/热）
              THRESHOLDS: mass(1.67,2.30) state(1.70,2.22) temperature(1.50,2.00)
  温度 v2     docs/THERMAL_DIMENSION.md
              T_deg=n_L+2n_F；rho^=(3nO+2nK+nP)/(3N)；
              eta=(1-rho^)(T_deg+1)/(T_deg+4)
              kappa_ij=k0*sqrt(eta_i*eta_j)*g_geo，k0=0.35/拍；
              热惯性 C_i=N_i(1+rho^_i)/4；tau<-tau-Sum(q)/C+lam*(T0-tau)，
              lam=0.03，|d tau|<=1.5/拍
  骨架        alchemy/attrs.py skeleton_units：三价原子连通块，跨骨架二价桥共享；
              T90 的占地口径 k_of=max(1,len(units))。本脚本同时给 k_raw 与 k_eff。
  恒素门控    t83_env_axes.py:120 World(t0=1000,t_end=25) 与 :221-255 update_rho、
              :395 gate=0.15+0.85*rho；ambient_bonus=0.20*(Tamb-t_end)/(t0-t_end)

复现：
  cd "G:\\AI work\\deepseek\\work1\\alchemy"
  $env:PYTHONIOENCODING='utf-8'
  python t93_static.py

产物：
  alchemy/t93_candidates.json
  alchemy/images/t93_candidates.png
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import alchemy.attrs as AT  # noqa: E402
import alchemy.three_su as TS  # noqa: E402

# ----------------------------------------------------------------------------
# 常量（全部来自文档，改动会破坏与 THERMAL_DIMENSION.md 的可比性）
# ----------------------------------------------------------------------------
CATALOG = os.path.join(HERE, "t4_catalog_all_validated.json")
OUT_JSON = os.path.join(HERE, "t93_candidates.json")
OUT_PNG = os.path.join(HERE, "images", "t93_candidates.png")

KAPPA0 = 0.35          # 拍^-1，THERMAL_DIMENSION v2
LAM = 0.03             # 恒温回归率，同上
ETA_ENV = 0.35          # 环境导热因子，同上
ETA_CORE = 0.35         # 内腔（多分子生命内部）等效 eta；任务给定
C_CORE = 60.0           # 核心热惯性：24 x C3K3F2，每分子 N(1+rho^)/4=2.5
T_CORE = 4.0            # 核心设定温度：C3K3F2 的 T_deg=n_F*2=4
CLAMP_CAP = 10.0        # v2 clamp(tau,0,T0+10) 给冷壳的上限

T87_TOP10 = ["OK", "OP", "CL", "CF", "X2AF2", "C2", "XLF", "LF", "XCF", "X2WF2"]
REFS = ["OXC", "O2C", "XC2", "X2C2", "XO2C", "OXC2"]
ELEMS = ["O", "X", "C", "K", "A", "F", "P", "W", "L"]
ATTRS = ("mass", "state", "temperature")

T0_WORLD = 1000.0       # t83_env_axes.py:120
TEND_WORLD = 25.0


def comp_str(comp):
    return " ".join("%s%d" % (e, comp[e]) for e in ELEMS if comp.get(e))


def tiers_of(raw):
    return {ax: AT.tier_name(raw[ax], ax) for ax in ATTRS}


# ----------------------------------------------------------------------------
# 1. 全目录逐分子量
# ----------------------------------------------------------------------------
def measure_catalog():
    cat = json.load(open(CATALOG, encoding="utf-8"))
    rows = []
    for rec in cat:
        atoms = list(rec["atoms"])
        edges = [tuple(e) for e in rec["edges"]]
        comp = Counter(atoms)
        n = len(atoms)
        s = TS.scores(comp)
        raw = AT.molecule_attrs(atoms, edges)
        tiers = tiers_of(raw)
        nO, nX, nC = comp.get("O", 0), comp.get("X", 0), comp.get("C", 0)
        nK, nA, nF = comp.get("K", 0), comp.get("A", 0), comp.get("F", 0)
        nP, nW, nL = comp.get("P", 0), comp.get("W", 0), comp.get("L", 0)
        Tdeg = nL + 2 * nF
        rho = (3 * nO + 2 * nK + nP) / (3.0 * n)
        eta = (1.0 - rho) * (Tdeg + 1.0) / (Tdeg + 4.0)
        # 同种自粘：d=1, F=1, J=1  =>  w = (kA*A - kR*D)/3
        w_self = (TS.K_A * s["A"] - TS.K_R * s["D"]) / 3.0
        k_raw = len(AT.skeleton_units(atoms, edges))
        rows.append({
            "formula": rec["formula"],
            "n": n,
            "comp": {e: comp[e] for e in ELEMS if comp.get(e)},
            "A": s["A"], "B": s["B"], "D": s["D"],
            "r_att": s["r_att"], "r_rep": s["r_rep"],
            "P": s["P"], "Q": s["Q"], "S": s["S"],
            "mass": raw["mass"], "state": raw["state"],
            "temperature": raw["temperature"],
            "tier_mass": tiers["mass"], "tier_state": tiers["state"],
            "tier_temp": tiers["temperature"],
            "T_deg": Tdeg, "rho": rho, "eta": eta,
            "w_self": w_self, "k_raw": k_raw, "k_eff": max(1, k_raw),
            "source": rec.get("source", ""),
        })
    return cat, rows


def is_candidate(r):
    """任务口径：T_deg==0（无 F/L）+ 温度档冷 + 物态档固 + w_self>=1.0 + k>=1。

    k 用原始骨架块数（k_raw）。T90 实际占地用 max(1,k)，所以另给 k_eff 与
    relaxed 集合，供“无三价骨架但仍是固”的分子（XC2/X2C2）对照。
    """
    return (r["T_deg"] == 0 and r["tier_temp"] == "冷"
            and r["tier_state"] == "固" and r["w_self"] >= 1.0
            and r["k_raw"] >= 1)


def is_candidate_relaxed(r):
    return (r["T_deg"] == 0 and r["tier_temp"] == "冷"
            and r["tier_state"] == "固" and r["w_self"] >= 1.0)


# ----------------------------------------------------------------------------
# 2. 攻击池与成对 w
# ----------------------------------------------------------------------------
def build_attack_pool(rows):
    byname = {r["formula"]: r for r in rows}
    pool = []
    for f in T87_TOP10:
        if f in byname:
            pool.append(byname[f])
    # 2~4 原子、F+O 占一半以上的“小分子攻击物”（目录内全取，不自选）
    for r in rows:
        if r["formula"] in T87_TOP10:
            continue
        if 2 <= r["n"] <= 4 and (r["comp"].get("F", 0) + r["comp"].get("O", 0)) >= 0.5 * r["n"]:
            pool.append(r)
    return pool


def jaccard(ci, cj):
    num = sum(min(ci.get(e, 0), cj.get(e, 0)) for e in ELEMS)
    den = sum(max(ci.get(e, 0), cj.get(e, 0)) for e in ELEMS)
    return num / den if den else 0.0


def w_pair(a, b):
    """d=1（贴邻）的 w。与 TS.pair_force 等价，但复用已算好的 A/D/r。"""
    # d=1 时 F 恒等于 1（three_su.decay），所以 w 只由 A/D/J 决定
    j = jaccard(a["comp"], b["comp"])
    att = TS.K_A * math.sqrt(a["A"] * b["A"]) / 3.0 * j
    rep = TS.K_R * math.sqrt(a["D"] * b["D"]) / 3.0 * j
    return {"w": att - rep, "att": att, "rep": rep, "j": j}


def wclass(w):
    if w >= TS.W_STRONG:
        return "strong"
    if w >= TS.W_WEAK:
        return "weak"
    if w > -TS.W_WEAK:
        return "none"
    return "repel"


# ----------------------------------------------------------------------------
# 3. 一维热学
# ----------------------------------------------------------------------------
def kappa(e1, e2):
    return KAPPA0 * math.sqrt(e1 * e2)


def series_R(eta_s, d, eta_c=ETA_CORE):
    """一维串联热阻（单位面积）：核心-壳界面 + (d-1) 个壳内界面 + 壳-环境界面。"""
    if d <= 0:
        return 1.0 / kappa(eta_c, ETA_ENV)
    r = 1.0 / kappa(eta_c, eta_s)
    if d >= 2:
        r += (d - 1) / kappa(eta_s, eta_s)
    r += 1.0 / kappa(eta_s, ETA_ENV)
    return r


def t_in_series(Tenv, eta_s, d, eta_c=ETA_CORE, c_core=C_CORE):
    """模型 A：纯串联热阻 + 核心恒温回归（壳无 λ，被动隔热）。

    N = lam*C_core*R 为“热汇-热阻比”；稳态 T_in=(T_env+N*T0)/(1+N)。
    N->0 时 T_in->T_env（无保温），N->inf 时 T_in->T0（完美保温）。
    """
    R = series_R(eta_s, d, eta_c)
    N = LAM * c_core * R
    return (Tenv + N * T_CORE) / (1.0 + N), N, R


def thomas(a, b, c, rhs):
    n = len(b)
    cp = [0.0] * n
    dp = [0.0] * n
    cp[0] = c[0] / b[0]
    dp[0] = rhs[0] / b[0]
    for i in range(1, n):
        m = b[i] - a[i] * cp[i - 1]
        cp[i] = c[i] / m
        dp[i] = (rhs[i] - a[i] * dp[i - 1]) / m
    x = [0.0] * n
    x[-1] = dp[-1]
    for i in range(n - 2, -1, -1):
        x[i] = dp[i] - cp[i] * x[i + 1]
    return x


def t_in_fd(Tenv, eta_s, d, cs=1.0, taus=0.0, eta_c=ETA_CORE, c_core=C_CORE):
    """模型 B：按 v2 更新式做稳态差分。每个壳层也有 lam*(T0_s-tau) 回归，
    所以冷壳自身也是热汇（T0_s=0），T_in 低于模型 A。返回全部节点温度。
    """
    if d <= 0:
        R = 1.0 / kappa(eta_c, ETA_ENV)
        N = LAM * c_core * R
        return [(Tenv + N * T_CORE) / (1.0 + N)]
    n = d + 1
    a = [0.0] * n
    b = [0.0] * n
    c = [0.0] * n
    rhs = [0.0] * n
    gcs = kappa(eta_c, eta_s)
    gss = kappa(eta_s, eta_s)
    gse = kappa(eta_s, ETA_ENV)
    b[0] = gcs + LAM * c_core
    c[0] = -gcs
    rhs[0] = LAM * c_core * T_CORE
    for l in range(1, d + 1):
        gl = gcs if l == 1 else gss
        gr = gse if l == d else gss
        a[l] = -gl
        b[l] = gl + gr + LAM * cs
        c[l] = -gr if l < d else 0.0
        rhs[l] = LAM * cs * taus + (gse * Tenv if l == d else 0.0)
    return thomas(a, b, c, rhs)


def main():
    t_start = time.time()
    print("[T93] loading catalog ...")
    cat, rows = measure_catalog()
    byname = {r["formula"]: r for r in rows}
    n_all = len(rows)
    print("[T93] molecules=%d  natoms_max=%d" % (n_all, max(r["n"] for r in rows)))

    # -- 全目录统计 ---------------------------------------------------------
    tier_mass = Counter(r["tier_mass"] for r in rows)
    tier_state = Counter(r["tier_state"] for r in rows)
    tier_temp = Counter(r["tier_temp"] for r in rows)
    wcls = Counter(wclass(r["w_self"]) for r in rows)
    grid = Counter((r["tier_mass"], r["tier_state"], r["tier_temp"]) for r in rows)
    A0 = sum(1 for r in rows if r["A"] == 0)
    D0 = sum(1 for r in rows if r["D"] == 0)
    Td0 = sum(1 for r in rows if r["T_deg"] == 0)
    # 异种基线：固定种子的随机分子对
    rng = random.Random(20261123)
    hetero = Counter()
    hetero_min = (9.0, None, None)
    for _ in range(200000):
        a = rows[rng.randrange(n_all)]
        b = rows[rng.randrange(n_all)]
        if a["formula"] == b["formula"]:
            continue
        w = w_pair(a, b)["w"]
        hetero[wclass(w)] += 1
        if w < hetero_min[0]:
            hetero_min = (w, a["formula"], b["formula"])
    nh = sum(hetero.values())

    catalog_stats = {
        "n_molecules": n_all,
        "natoms_max": max(r["n"] for r in rows),
        "n_A0": A0, "n_D0": D0, "n_Tdeg0": Td0,
        "tier_mass": dict(tier_mass), "tier_state": dict(tier_state),
        "tier_temp": dict(tier_temp),
        "grid_nonempty": len(grid), "grid_total": 27,
        "w_class_self": {k: wcls.get(k, 0) for k in ("strong", "weak", "none", "repel")},
        "w_class_self_pct": {k: round(100.0 * wcls.get(k, 0) / n_all, 2)
                             for k in ("strong", "weak", "none", "repel")},
        "hetero_sample": {
            "n_pairs": nh,
            "class": {k: hetero.get(k, 0) for k in ("strong", "weak", "none", "repel")},
            "pct": {k: round(100.0 * hetero.get(k, 0) / nh, 2)
                    for k in ("strong", "weak", "none", "repel")},
            "w_min": hetero_min,
        },
    }
    print("[T93] same-species w class: %s" % catalog_stats["w_class_self_pct"])
    print("[T93] hetero sample repel=%.2f%% (T81: 0.37%%)" % catalog_stats["hetero_sample"]["pct"]["repel"])

    # -- 候选集 -------------------------------------------------------------
    cands = [r for r in rows if is_candidate(r)]
    cands_relaxed = [r for r in rows if is_candidate_relaxed(r)]
    cands_c = [r for r in cands if r["comp"].get("C", 0) > 0]
    cands_c_small = [r for r in cands_c if r["n"] <= 8]
    cands_small = [r for r in cands if r["n"] <= 8]
    cands_d0 = [r for r in cands if r["D"] == 0]
    cands_dpos = [r for r in cands if r["D"] > 0]
    cands_w = [r for r in cands if r["comp"].get("W", 0) > 0]
    only_extra = [r for r in cands_relaxed if not is_candidate(r)]
    print("[T93] candidates=%d (relaxed=%d, +%d k_raw=0)  C=%d  C&n<=8=%d  n<=8=%d  D=0=%d  D>0=%d"
          % (len(cands), len(cands_relaxed), len(only_extra), len(cands_c),
             len(cands_c_small), len(cands_small), len(cands_d0), len(cands_dpos)))

    def sort_key(r):
        return (-r["w_self"], r["eta"], -r["k_raw"], r["formula"])

    def row_out(r, keep_comp=True):
        d = {
            "formula": r["formula"], "n": r["n"],
            "comp": comp_str(r["comp"]),
            "A": round(r["A"], 4), "D": round(r["D"], 4),
            "r_att": r["r_att"], "r_rep": r["r_rep"],
            "T_deg": r["T_deg"], "rho": round(r["rho"], 4), "eta": round(r["eta"], 4),
            "w_self": round(r["w_self"], 4),
            "k_raw": r["k_raw"], "k_eff": r["k_eff"],
            "mass": round(r["mass"], 4), "state": round(r["state"], 4),
            "temperature": round(r["temperature"], 4),
            "tier": "%s·%s·%s" % (r["tier_mass"], r["tier_state"], r["tier_temp"]),
            "source": r["source"],
        }
        if keep_comp:
            d["comp_count"] = dict(r["comp"])
        return d

    candidate_rows = [row_out(r) for r in sorted(cands, key=sort_key)]

    def top(rs, k, brief=False):
        out = []
        for r in sorted(rs, key=sort_key)[:k]:
            d = row_out(r, keep_comp=False)
            if brief:
                d = {"formula": r["formula"], "n": r["n"], "A": round(r["A"], 3),
                     "D": round(r["D"], 3), "eta": round(r["eta"], 4),
                     "w_self": round(r["w_self"], 3), "k_raw": r["k_raw"],
                     "tier": d["tier"]}
            out.append(d)
        return out

    # -- 六参考分子 ---------------------------------------------------------
    refs = []
    for f in REFS:
        if f in byname:
            r = byname[f]
            refs.append({
                "formula": f, "in_catalog": True, "n": r["n"],
                "comp": comp_str(r["comp"]),
                "A": round(r["A"], 3), "D": round(r["D"], 3),
                "T_deg": r["T_deg"], "rho": round(r["rho"], 4),
                "eta": round(r["eta"], 4), "w_self": round(r["w_self"], 4),
                "k_raw": r["k_raw"], "k_eff": r["k_eff"],
                "tier": "%s·%s·%s" % (r["tier_mass"], r["tier_state"], r["tier_temp"]),
                "passes_filter": is_candidate(r),
                "passes_relaxed": is_candidate_relaxed(r),
            })
        else:
            comp = Counter(TS.parse_formula(f))
            s = TS.scores(comp)
            n = sum(comp.values())
            nO, nK = comp.get("O", 0), comp.get("K", 0)
            nL, nF = comp.get("L", 0), comp.get("F", 0)
            raw = {"mass": (3 * nO + 2 * nK) / max(1, sum(
                comp.get(e, 0) for e in ("O", "K", "P"))),
                   "state": 0.0,
                   "temperature": (3 * nF + 2 * nL + comp.get("C", 0)) / max(
                       1, sum(comp.get(e, 0) for e in ("C", "L", "F")))}
            Tdeg = nL + 2 * nF
            rho = (3 * nO + 2 * nK) / (3.0 * n)
            eta = (1 - rho) * (Tdeg + 1.0) / (Tdeg + 4.0)
            w = (TS.K_A * s["A"] - TS.K_R * s["D"]) / 3.0
            tr = tiers_of(raw)
            refs.append({
                "formula": f, "in_catalog": False, "n": n,
                "comp": comp_str(comp),
                "A": round(s["A"], 3), "D": round(s["D"], 3),
                "T_deg": Tdeg, "rho": round(rho, 4), "eta": round(eta, 4),
                "w_self": round(w, 4), "k_raw": None, "k_eff": None,
                "tier": "%s·%s·%s(推算式，k 取决于连接)" % (
                    tr["mass"], tr["state"], tr["temperature"]),
                "passes_filter": False, "passes_relaxed": False,
            })
    print("[T93] refs: " + ", ".join("%s:%s" % (r["formula"], "in" if r["in_catalog"] else "OUT") for r in refs))

    # -- 攻击池 -------------------------------------------------------------
    pool = build_attack_pool(rows)
    pool_rows = []
    for b in pool:
        pool_rows.append({
            "formula": b["formula"], "n": b["n"], "comp": comp_str(b["comp"]),
            "A": round(b["A"], 4), "D": round(b["D"], 4),
            "tier": "%s·%s·%s" % (b["tier_mass"], b["tier_state"], b["tier_temp"]),
            "in_t87_top10": b["formula"] in T87_TOP10,
        })
    print("[T93] attack pool=%d (T87 top10 + 2~4 原子 F/O 富集)" % len(pool))

    # -- 排斥统计 -----------------------------------------------------------
    def pair_stats(shells, pool_):
        cnt = Counter()
        min_w = (9.0, None, None)
        rep_list = []
        attr_list = []
        for a in shells:
            for b in pool_:
                r = w_pair(a, b)
                c = wclass(r["w"])
                cnt[c] += 1
                if r["w"] < min_w[0]:
                    min_w = (r["w"], a["formula"], b["formula"])
                if c == "repel":
                    rep_list.append((r["w"], a["formula"], b["formula"], r["att"], r["rep"], r["j"]))
                if c == "strong":
                    attr_list.append((r["w"], a["formula"], b["formula"], r["att"], r["rep"], r["j"]))
        tot = sum(cnt.values())
        rep_list.sort()
        attr_list.sort(reverse=True)
        return {
            "n_shells": len(shells), "n_attackers": len(pool_), "n_pairs": tot,
            "class": {k: cnt.get(k, 0) for k in ("strong", "weak", "none", "repel")},
            "pct": {k: round(100.0 * cnt.get(k, 0) / tot, 3) for k in ("strong", "weak", "none", "repel")},
            "w_min": {"w": round(min_w[0], 4), "shell": min_w[1], "attacker": min_w[2]},
            "n_repel": len(rep_list),
            "repel_list_top": [{"w": round(x[0], 4), "shell": x[1], "attacker": x[2],
                                "att": round(x[3], 4), "rep": round(x[4], 4), "j": round(x[5], 4)}
                               for x in rep_list[:5]],
            "strong_list_top": [{"w": round(x[0], 4), "shell": x[1], "attacker": x[2],
                                 "att": round(x[3], 4), "rep": round(x[4], 4), "j": round(x[5], 4)}
                                for x in attr_list[:5]],
        }

    groups = {
        "all": cands,
        "c_all": cands_c,
        "c_small": cands_c_small,
        "small": cands_small,
        "d0": cands_d0,
        "dpos": cands_dpos,
    }
    repulsion = {g: pair_stats(rs, pool) for g, rs in groups.items()}

    def per_attacker(shells):
        out = []
        for b in pool:
            cnt = Counter()
            for a in shells:
                cnt[wclass(w_pair(a, b)["w"])] += 1
            tot = sum(cnt.values())
            out.append({
                "attacker": b["formula"], "A": round(b["A"], 3), "D": round(b["D"], 3),
                "class_pct": {k: round(100.0 * cnt.get(k, 0) / tot, 2)
                              for k in ("strong", "weak", "none", "repel")},
            })
        return out

    repulsion["per_attacker_all"] = per_attacker(cands)
    repulsion["per_attacker_c_small"] = per_attacker(cands_c_small)

    # 几个具体例子
    examples = {}
    for f in ("OXC", "XC2", "X2C2", "O4XCK", "O10XK4"):
        if f not in byname:
            continue
        a = byname[f]
        examples[f] = {
            "self_w": round(a["w_self"], 4),
            "vs_t87": {b["formula"]: round(w_pair(a, b)["w"], 3)
                       for b in pool if b["formula"] in T87_TOP10},
            "vs_pool_pct": {k: round(100.0 * sum(
                1 for b in pool if wclass(w_pair(a, b)["w"]) == k) / len(pool), 2)
                for k in ("strong", "weak", "none", "repel")},
        }
    # 纯动素物种自斥（模型里“真正能斥”的少数情况）
    dyad = {}
    for f in ("P2", "W2", "L2", "WA", "XP2"):
        if f in byname:
            r = byname[f]
            dyad[f] = {"self_w": round(r["w_self"], 4),
                       "A": round(r["A"], 3), "D": round(r["D"], 3)}
    print("[T93] repulsion all: repel=%.3f%% min_w=%.3f | c_small: repel=%.3f%%"
          % (repulsion["all"]["pct"]["repel"], repulsion["all"]["w_min"]["w"],
             repulsion["c_small"]["pct"]["repel"]))

    # -- 热学 ---------------------------------------------------------------
    shells = [
        {"key": "ice_rock_O10XK4", "name": "冰岩 O10XK4 (eta=0.039)", "eta": 0.039,
         "formula": "O10XK4"},
        {"key": "OXC", "name": "冰岩 OXC (eta=0.167)", "eta": 0.167, "formula": "OXC"},
        {"key": "XC2", "name": "轻冰 XC2 (eta=0.250)", "eta": 0.250, "formula": "XC2"},
        {"key": "hot_F", "name": "热壳 F 富集 (eta=0.600)", "eta": 0.600, "formula": None},
    ]
    T_ENVS = [100.0, 300.0, 600.0, 1000.0]
    DS = [0, 1, 2, 3, 5]
    thermal = {
        "params": {
            "kappa0": KAPPA0, "lam": LAM, "eta_env": ETA_ENV, "eta_core": ETA_CORE,
            "c_core": C_CORE, "T_core": T_CORE, "clamp_cap": CLAMP_CAP,
            "T_env_list": T_ENVS, "d_list": DS,
            "kappa_core_env": kappa(ETA_CORE, ETA_ENV),
            "series_formula": "R(d)=1/kappa(eta_c,eta_s)+(d-1)/kappa(eta_s,eta_s)+1/kappa(eta_s,eta_env)",
            "steady_formula": "T_in=(T_env+lam*C*R*T_core)/(1+lam*C*R)",
            "fd_note": "模型B按 v2 更新式解三对角：每个壳层也有 lam*(T0_s-T_s)，T0_s=0，C_s=1.0",
        },
        "shells": [],
    }
    for sh in shells:
        e = sh["eta"]
        series = {}
        for Te in T_ENVS:
            series[str(int(Te))] = [round(t_in_series(Te, e, d)[0], 3) for d in DS]
        NbyD = [round(LAM * C_CORE * series_R(e, d), 2) for d in DS]
        RbyD = [round(series_R(e, d), 3) for d in DS]
        min_d = {}
        for Te in T_ENVS:
            md = None
            for d in range(0, 16):
                if t_in_series(Te, e, d)[0] <= 10.0:
                    md = d
                    break
            min_d[str(int(Te))] = md
        tmax = {}
        for d in (1, 2, 3, 5):
            N = LAM * C_CORE * series_R(e, d)
            tmax[str(d)] = round(10.0 * (1 + N) - N * T_CORE, 1)
        fd = {}
        for d in (1, 2, 3, 5):
            fd[str(d)] = [round(t_in_fd(Te, e, d)[0], 3) for Te in T_ENVS]
        transient = [{"d": d, "R": round(series_R(e, d), 2),
                      "tau_ticks": round(C_CORE * series_R(e, d), 0),
                      "t_half_ticks": round(C_CORE * series_R(e, d) * math.log(2), 0)}
                     for d in (1, 2, 3, 5)]
        thermal["shells"].append({
            "key": sh["key"], "name": sh["name"], "eta": e, "formula": sh["formula"],
            "R": RbyD, "N": NbyD, "T_in_series": series, "T_in_fd": fd,
            "min_d_for_10C": min_d, "T_env_max_for_10C": tmax,
            "transient": transient,
            "w_self": (round(byname[sh["formula"]]["w_self"], 4)
                       if sh["formula"] and sh["formula"] in byname else None),
        })
    # 热壳在 v2 全域 λ 下的差分（壳自身 T0=8，C_s=2）
    thermal["hot_shell_fd_taus8"] = {
        str(d): [round(t_in_fd(Te, 0.6, d, cs=2.0, taus=8.0)[0], 3) for Te in T_ENVS]
        for d in (1, 2, 3, 5)
    }
    # 体量敏感性：C_core 变化
    sens = {}
    for cc in (12.0, 60.0, 240.0):
        sens[str(int(cc))] = {
            "T_in_600_OXC_d3": round(t_in_series(600, 0.167, 3, c_core=cc)[0], 3),
            "T_in_600_bare": round(t_in_series(600, 0.167, 0, c_core=cc)[0], 3),
            "min_d_600": next((d for d in range(0, 16)
                               if t_in_series(600, 0.167, d, c_core=cc)[0] <= 10.0), None),
        }
    thermal["sensitivity_c_core"] = sens
    oxc_shell = [s for s in thermal["shells"] if s["key"] == "OXC"][0]
    print("[T93] thermal OXC T_in@600:", oxc_shell["T_in_series"]["600"],
          " min_d:", oxc_shell["min_d_for_10C"])

    # -- 恒素门控 -----------------------------------------------------------
    gate_rows = []
    for Te in T_ENVS:
        bonus = 0.20 * (Te - TEND_WORLD) / (T0_WORLD - TEND_WORLD)
        target_in = min(1.0, max(0.0, 0.5 - 0.30 + bonus))
        gate_in = 0.15 + 0.85 * target_in
        for fh in (0.3, 0.5, 0.8):
            target_out = min(1.0, max(0.0, 0.5 + 0.30 * (2 * fh - 1) + bonus))
            gate_out = 0.15 + 0.85 * target_out
            gate_rows.append({
                "T_env": Te, "ambient_bonus": round(bonus, 4),
                "hot_frac_out": fh,
                "target_in": round(target_in, 4), "gate_in": round(gate_in, 4),
                "target_out": round(target_out, 4), "gate_out": round(gate_out, 4),
                "ratio_in_out": round(gate_in / gate_out, 3),
            })
    print("[T93] gate@1000C: in=%.2f out(fh=.5)=%.2f ratio=%.2f"
          % (gate_rows[0]["gate_in"], gate_rows[3]["gate_out"], gate_rows[3]["ratio_in_out"]))

    # -- 环境条件结论的数据基础 --------------------------------------------
    env = {
        "bare_body": {str(int(Te)): {"T_in": round(t_in_series(Te, ETA_CORE, 0)[0], 2),
                                     "N": round(t_in_series(Te, ETA_CORE, 0)[1], 2)}
                      for Te in T_ENVS},
        "recommended": {},
        "gravity": {
            "heavy_shell": "OXC/O10XK4 等重档壳会沉底（T92 重档 y≈105~107/110 贴底）",
            "light_shell": "XC2/X2C2 等轻档壳会上浮（T92 轻档 y≈45~62）",
            "note": "膜要先在重力方向上稳定附着，再谈保温；微重力/高黏环境最有利",
        },
    }
    for sh in thermal["shells"]:
        env["recommended"][sh["key"]] = {
            "T_env_max_by_d": sh["T_env_max_for_10C"],
            "min_d_by_Tenv": sh["min_d_for_10C"],
        }

    runtime = round(time.time() - t_start, 1)

    out = {
        "meta": {
            "task": "T93 静态：C 类低温分子保护膜（保温 + 隔绝外来分子）",
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "catalog": os.path.basename(CATALOG),
            "n_catalog": n_all,
            "runtime_sec": runtime,
            "formulas_doc": ["docs/THREE_SU_AXES.md", "docs/MATERIAL_AXES.md",
                             "docs/THERMAL_DIMENSION.md", "docs/T87_ENV_ASYM.md",
                             "docs/T90_BODY_GROWTH.md"],
            "code_doc": ["alchemy/three_su.py", "alchemy/attrs.py"],
        },
        "params": {
            "K_A": TS.K_A, "K_R": TS.K_R, "W_STRONG": TS.W_STRONG, "W_WEAK": TS.W_WEAK,
            "THRESHOLDS": {k: list(v) for k, v in AT.THRESHOLDS.items()},
            "candidate_filter": {
                "T_deg": 0, "tier_temp": "冷", "tier_state": "固",
                "w_self_min": 1.0, "k_raw_min": 1,
                "note": "T90 占地口径 k=max(1,k_raw)，k_raw=0 的固体会被本滤波器排除（见 relaxed 集合）",
            },
            "thermal": thermal["params"],
            "gate": {"t0": T0_WORLD, "t_end": TEND_WORLD,
                     "formula": "target=0.5+0.30*(hot-cold)/cnt+ambient_bonus; gate=0.15+0.85*rho",
                     "ambient_bonus": "0.20*(Tamb-t_end)/(t0-t_end)"},
        },
        "catalog_stats": catalog_stats,
        "candidate_stats": {
            "n_candidates": len(cands),
            "n_candidates_relaxed": len(cands_relaxed),
            "n_extra_when_k_relaxed": len(only_extra),
            "n_contains_C": len(cands_c),
            "n_contains_C_small8": len(cands_c_small),
            "n_small8": len(cands_small),
            "n_D0": len(cands_d0),
            "n_Dpos": len(cands_dpos),
            "n_contains_W": len(cands_w),
            "pct_contains_C": round(100.0 * len(cands_c) / len(cands), 2),
            "pct_D0": round(100.0 * len(cands_d0) / len(cands), 2),
            "pct_Dpos": round(100.0 * len(cands_dpos) / len(cands), 2),
            "tier_composition": dict(Counter(
                "%s·%s·%s" % (r["tier_mass"], r["tier_state"], r["tier_temp"]) for r in cands)),
        },
        "candidates": candidate_rows,
        "tables": {
            "top30_all": top(cands, 30, brief=False),
            "top20_c_small8": top(cands_c_small, 20, brief=False),
            "top20_c_all": top(cands_c, 20, brief=False),
            "top20_small8_all": top(cands_small, 20, brief=False),
            "top10_dpos": top(cands_dpos, 10, brief=False),
            "top10_d0": top(cands_d0, 10, brief=False),
            "top10_w": top(cands_w, 10, brief=False),
        },
        "refs": refs,
        "attack_pool": pool_rows,
        "repulsion": repulsion,
        "repulsion_examples": examples,
        "dyad_self": dyad,
        "thermal": thermal,
        "gate": gate_rows,
        "env": env,
    }
    os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)
    out["_rows_full"] = rows  # 仅供画图，不写 JSON
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in out.items() if not k.startswith("_")}, f,
                  ensure_ascii=False, indent=1)
    print("[T93] wrote %s (%.1f KB)" % (OUT_JSON, os.path.getsize(OUT_JSON) / 1024.0))

    # -- 作图 ---------------------------------------------------------------
    try:
        render_png(out, rows)
        print("[T93] wrote %s" % OUT_PNG)
    except Exception as e:  # 画图失败不影响数据
        import traceback
        traceback.print_exc()
        print("[T93] PNG failed: %s" % e)

    # -- 控制台摘要 ---------------------------------------------------------
    t3 = out["tables"]["top20_c_small8"][:3]
    print("[T93] top3 C 类小冰壳: " + " | ".join(
        "%s n=%d A=%.2f eta=%.3f w=%.2f k=%d" %
        (r["formula"], r["n"], r["A"], r["eta"], r["w_self"], r["k_raw"]) for r in t3))
    print("[T93] done in %.1f s" % runtime)
    return out


# ----------------------------------------------------------------------------
# 4. 绘图（PIL，中文用 msyh.ttc）
# ----------------------------------------------------------------------------
FONT = r"C:\Windows\Fonts\msyh.ttc"
FONTB = r"C:\Windows\Fonts\msyhbd.ttc"
INK = (34, 38, 48)
GREY = (120, 126, 140)
GRID = (216, 220, 228)
BLUE = (38, 96, 178)
RED = (200, 54, 54)
ORANGE = (232, 138, 32)
GREEN = (44, 148, 96)
PURPLE = (132, 74, 170)


def fnt(sz, bold=False):
    try:
        return ImageFont.truetype(FONTB if bold else FONT, sz)
    except OSError:
        return ImageFont.load_default()


def draw_text(d, xy, s, sz=14, bold=False, fill=INK, anchor="la"):
    d.text(xy, s, font=fnt(sz, bold), fill=fill, anchor=anchor)


class Ax:
    def __init__(self, dr, box, xlim, ylim, title, xlabel, ylabel,
                 xticks=None, yticks=None, grid=True):
        self.d = dr
        self.x0, self.y0, self.x1, self.y1 = box
        self.xlim = (float(xlim[0]), float(xlim[1]))
        self.ylim = (float(ylim[0]), float(ylim[1]))
        dr.rectangle((self.x0, self.y0, self.x1, self.y1), fill=(255, 255, 255),
                     outline=(190, 196, 206), width=1)
        draw_text(dr, ((self.x0 + self.x1) / 2, self.y0 - 26), title, 15, True, INK, "ms")
        if xlabel:
            draw_text(dr, ((self.x0 + self.x1) / 2, self.y1 + 34), xlabel, 13, False, GREY, "ms")
        if ylabel:
            draw_text(dr, (self.x0 - 10, (self.y0 + self.y1) / 2), ylabel, 13, False,
                      GREY, "rm")
        self.xticks = xticks
        self.yticks = yticks
        if yticks:
            for tv, lab in yticks:
                if tv < self.ylim[0] or tv > self.ylim[1]:
                    continue
                y = self.Y(tv)
                if grid:
                    dr.line((self.x0, y, self.x1, y), fill=GRID)
                draw_text(dr, (self.x0 - 6, y), lab, 11, False, GREY, "rm")
        if xticks:
            for tv, lab in xticks:
                if tv < self.xlim[0] or tv > self.xlim[1]:
                    continue
                x = self.X(tv)
                if grid:
                    dr.line((x, self.y0, x, self.y1), fill=GRID)
                draw_text(dr, (x, self.y1 + 6), lab, 11, False, GREY, "mt")

    def X(self, v):
        return self.x0 + (v - self.xlim[0]) / (self.xlim[1] - self.xlim[0]) * (self.x1 - self.x0)

    def Y(self, v):
        return self.y1 - (v - self.ylim[0]) / (self.ylim[1] - self.ylim[0]) * (self.y1 - self.y0)


def render_png(out, rows):
    W, H = 1560, 1220
    img = Image.new("RGB", (W, H), (248, 249, 252))
    d = ImageDraw.Draw(img)
    draw_text(d, (W // 2, 16), "T93 静态：C 类低温分子保护膜（保温 + 隔绝外来分子）", 24, True,
              fill=(24, 28, 38), anchor="ma")
    draw_text(d, (W // 2, 48),
              "目录 84,225 条 · 候选 %d（含 C %d）· 攻击池 %d 种 · kappa0=0.35, lam=0.03, eta_core=0.35"
              % (out["candidate_stats"]["n_candidates"],
                 out["candidate_stats"]["n_contains_C"],
                 len(out["attack_pool"])), 13, False, GREY, "ma")

    # ---- (1) A vs T_deg 散布 ---------------------------------------------
    ax1 = Ax(d, (130, 120, 790, 400), (0, 12), (0, 3.1),
             "(1) 全目录 A vs T_deg：候选落在 T_deg=0 竖带上",
             "T_deg = n_L + 2n_F（>12 截断）", "A",
             [(0, "0"), (2, "2"), (4, "4"), (6, "6"), (8, "8"), (10, "10"), (12, "12")],
             [(0, "0"), (0.5, "0.5"), (1, "1"), (1.5, "1.5"), (2, "2"), (2.5, "2.5"), (3, "3")])
    # 背景点：按 2px 抽样减少绘制量
    # 全目录背景点（先画，避免压住候选高亮）
    for r in rows:
        x = min(12, r["T_deg"])
        d.point((ax1.X(x), ax1.Y(min(3.1, r["A"]))), fill=(205, 208, 216))
    n_c = n_csmall = 0
    for r in out["candidates"]:
        x = min(12, r["T_deg"])
        yv = min(3.1, r["A"])
        if r["comp_count"].get("C", 0) > 0 and r["n"] <= 8:
            d.ellipse((ax1.X(x) - 2, ax1.Y(yv) - 2, ax1.X(x) + 2, ax1.Y(yv) + 2),
                      fill=BLUE)
            n_csmall += 1
        else:
            d.ellipse((ax1.X(x) - 1, ax1.Y(yv) - 1, ax1.X(x) + 1, ax1.Y(yv) + 1),
                      fill=RED)
        n_c += 1
    draw_text(d, (ax1.X(3.6), ax1.Y(2.95)),
              "红：冷壳候选 %d 个（全在 T_deg=0）" % n_c, 12, True, RED)
    draw_text(d, (ax1.X(3.6), ax1.Y(2.78)),
              "蓝：含 C 且 n≤8 的小冰壳 %d 个" % n_csmall, 12, True, BLUE)
    draw_text(d, (ax1.X(3.6), ax1.Y(2.61)), "灰：其他 7.8 万条", 12, False, GREY)

    # ---- (2) w 分类堆叠条 -------------------------------------------------
    ax2 = Ax(d, (930, 120, 1500, 400), (0, 100), (0, 1),
             "(2) 候选壳 x 攻击池：w 分类占比（d=1）", "", "")
    groups = [("全体候选", "all"), ("含C", "c_all"), ("含C小分子", "c_small"),
              ("D=0 壳", "d0"), ("D>0 壳", "dpos")]
    seg_colors = {"strong": (40, 120, 70), "weak": (110, 170, 120),
                  "none": (222, 226, 233), "repel": (200, 54, 54)}
    bar_x0, bar_x1 = 940, 1490
    bar_y = 136
    bh = 24
    for label, key in groups:
        pct = out["repulsion"][key]["pct"]
        npair = out["repulsion"][key]["n_pairs"]
        draw_text(d, (bar_x0, bar_y - 2), "%s（%d 对）" % (label, npair), 10.5, True, INK)
        x = bar_x0
        for seg in ("strong", "weak", "none", "repel"):
            wpx = (bar_x1 - bar_x0) * pct[seg] / 100.0
            if wpx > 0.6:
                d.rectangle((x, bar_y + 12, x + wpx, bar_y + 12 + bh),
                            fill=seg_colors[seg], outline=(255, 255, 255))
                if wpx > 46:
                    draw_text(d, (x + wpx / 2, bar_y + 12 + bh / 2),
                              "%.1f%%" % pct[seg], 10.5, True,
                              (255, 255, 255) if seg != "none" else INK, "mm")
            x += wpx
        bar_y += 48
    draw_text(d, (950, 372), "排斥(红) = 0.00%%：全部 %d 对里仅 1 对 w=-0.200 的边界对"
              % out["repulsion"]["all"]["n_pairs"], 11.5, True, (200, 54, 54))
    draw_text(d, (950, 390), "绿=强粘(>=1.0) 浅绿=弱粘(0.2~1.0) 灰=无作用；无红=无净排斥",
              10.5, False, GREY)

    # ---- (3) T_in vs d ----------------------------------------------------
    ax3 = Ax(d, (130, 500, 790, 780), (0, 5.2), (0, 80),
             "(3) 内部稳态 T_in 随壳厚 d（模型 A：串联热阻 + 核心恒温回归）",
             "壳厚 d（分子层）", "T_in °C",
             [(0, "0"), (1, "1"), (2, "2"), (3, "3"), (4, "4"), (5, "5")],
             [(0, "0"), (10, "10"), (20, "20"), (40, "40"), (60, "60"), (80, "80")])
    tcol = {"100": BLUE, "300": GREEN, "600": ORANGE, "1000": RED}
    for sh in out["thermal"]["shells"]:
        hot = sh["key"] == "hot_F"
        for Te, col in tcol.items():
            ys = sh["T_in_series"][Te]
            pts = [(ax3.X(dd), ax3.Y(min(80, yv))) for dd, yv in zip([0, 1, 2, 3, 5], ys)]
            for i in range(len(pts) - 1):
                if hot:
                    # 虚线
                    (xa, ya), (xb, yb) = pts[i], pts[i + 1]
                    n = 9
                    for k in range(n):
                        if k % 2:
                            continue
                        d.line((xa + (xb - xa) * k / n, ya + (yb - ya) * k / n,
                                xa + (xb - xa) * (k + 1) / n, ya + (yb - ya) * (k + 1) / n),
                               fill=col, width=2)
                else:
                    d.line((pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]),
                           fill=col, width=3)
    d.line((ax3.x0, ax3.Y(10), ax3.x1, ax3.Y(10)), fill=(180, 40, 40), width=1)
    draw_text(d, (ax3.x1 - 6, ax3.Y(10) - 14), "T_in=10°C", 11, True, (180, 40, 40), "ra")
    draw_text(d, (ax3.X(2.0), ax3.Y(78)),
              "实线：OXC 冷壳 eta=0.167；虚线：F 富集热壳 eta=0.6", 10.5, False, INK)
    draw_text(d, (ax3.X(2.0), ax3.Y(72)),
              "蓝 100°C / 绿 300°C / 橙 600°C / 红 1000°C", 10.5, False, GREY)
    draw_text(d, (ax3.X(2.0), ax3.Y(66)),
              "d=0=裸体：100/300/600/1000°C 分别为 10.1/22.9/42.0/67.5°C", 10.5, False, GREY)

    # ---- (4) 最小壳厚热图 -------------------------------------------------
    ax4 = Ax(d, (930, 500, 1500, 780), (0, 4), (0, 4),
             "(4) T_in<=10°C 所需最小壳厚 d*（模型 A）", "T_env (°C)", "")
    col_x = {"100": 0.5, "300": 1.5, "600": 2.5, "1000": 3.5}
    for j, Te in enumerate(["100", "300", "600", "1000"]):
        xx = ax4.x0 + (j + 0.5) * (ax4.x1 - ax4.x0) / 4
        draw_text(d, (xx, ax4.y1 + 6), Te, 12, True, INK, "mt")
    for i, sh in enumerate(out["thermal"]["shells"]):
        yy = ax4.y0 + (i + 0.5) * (ax4.y1 - ax4.y0) / 4
        draw_text(d, (ax4.x0 - 6, yy), sh["name"].split("(")[0], 11, False, INK, "rm")
        for j, Te in enumerate(["100", "300", "600", "1000"]):
            md = sh["min_d_for_10C"][Te]
            xx = ax4.x0 + (j + 0.5) * (ax4.x1 - ax4.x0) / 4
            if md is None:
                col = (120, 30, 30)
                lab = "不可行"
            else:
                f = max(0.0, min(1.0, md / 6.0))
                col = (int(232 - 170 * f), int(240 - 120 * f), int(250 - 120 * f))
                lab = "d=%d" % md
            r = 26
            d.rectangle((xx - r, yy - 20, xx + r, yy + 20), fill=col, outline=(200, 204, 212))
            draw_text(d, (xx, yy), lab, 12, True, INK, "mm")

    # ---- (5) 门控 ---------------------------------------------------------
    ax5 = Ax(d, (130, 860, 790, 1120), (100, 1000), (0, 1.0),
             "(5) 恒素门控：壳内(全冷) vs 壳外(热占比 f_hot)",
             "环境温度 T_env (°C)", "gate",
             [(100, "100"), (300, "300"), (600, "600"), (1000, "1000")],
             [(0, "0"), (0.2, "0.2"), (0.4, "0.4"), (0.6, "0.6"), (0.8, "0.8"), (1.0, "1.0")])
    rowsg = out["gate"]
    series = {
        "shell_in (cold)": ([], (200, 70, 70)),
        "out f_hot=0.5": ([], (48, 108, 190)),
        "out f_hot=0.8": ([], (60, 150, 100)),
    }
    for Te in (100.0, 300.0, 600.0, 1000.0):
        for r in rowsg:
            if r["T_env"] != Te:
                continue
            if r["hot_frac_out"] == 0.3:
                series["shell_in (cold)"][0].append((Te, r["gate_in"]))
            if r["hot_frac_out"] == 0.5:
                series["out f_hot=0.5"][0].append((Te, r["gate_out"]))
            if r["hot_frac_out"] == 0.8:
                series["out f_hot=0.8"][0].append((Te, r["gate_out"]))
    for name, (pts, col) in series.items():
        p = [(ax5.X(x), ax5.Y(y)) for x, y in pts]
        for i in range(len(p) - 1):
            d.line((p[i][0], p[i][1], p[i + 1][0], p[i + 1][1]), fill=col, width=3)
        draw_text(d, (p[-1][0] - 4, p[-1][1] - 16), name.split(" ")[0], 11, True, col, "rm")
    g1000in = next(r["gate_in"] for r in rowsg if r["T_env"] == 1000.0)
    g1000out = next(r["gate_out"] for r in rowsg
                    if r["T_env"] == 1000.0 and r["hot_frac_out"] == 0.8)
    draw_text(d, (ax5.x0 + 8, ax5.y0 + 8),
              "低温壳内 rho 低 -> gate 低：1000°C 时 gate_in=%.2f vs gate_out=%.2f（f_hot=0.8）"
              % (g1000in, g1000out), 11, False, INK)
    draw_text(d, (ax5.x0 + 8, ax5.y0 + 26),
              "内部反应率被压到外部的 %.0f%%（双刃剑）" % (100.0 * g1000in / g1000out),
              11, True, (200, 54, 54))

    # ---- (6) 候选 w_self vs eta ------------------------------------------
    ax6 = Ax(d, (930, 860, 1500, 1120), (1.0, 2.5), (0, 0.28),
             "(6) 冷壳候选：自粘 w_self vs 导热 eta（左下=又粘又隔热）",
             "w_self（同种贴邻净力）", "eta",
             [(1.0, "1.0"), (1.5, "1.5"), (2.0, "2.0"), (2.5, "2.5")],
             [(0, "0"), (0.1, "0.1"), (0.2, "0.2")])
    for r in out["candidates"]:
        x = min(2.5, max(1.0, r["w_self"]))
        y = min(0.28, max(0.0, r["eta"]))
        col = BLUE if r["comp_count"].get("C", 0) > 0 else RED
        d.ellipse((ax6.X(x) - 1, ax6.Y(y) - 1, ax6.X(x) + 1, ax6.Y(y) + 1), fill=col)
    for f, lab, col in (("OXC", "OXC", (30, 30, 30)), ("O10XK4", "O10XK4", (30, 30, 30)),
                        ("O4XCK", "O4XCK", (30, 30, 30))):
        rr = next((r for r in out["candidates"] if r["formula"] == f), None)
        if rr:
            x = min(2.5, max(1.0, rr["w_self"]))
            y = min(0.28, max(0.0, rr["eta"]))
            d.ellipse((ax6.X(x) - 3, ax6.Y(y) - 3, ax6.X(x) + 3, ax6.Y(y) + 3),
                      outline=(20, 20, 20), width=2)
            draw_text(d, (ax6.X(x) + 5, ax6.Y(y) - 4), "%s(w=%.2f)" % (lab, rr["w_self"]),
                      10, True, INK)
    draw_text(d, (ax6.x0 + 8, ax6.y1 - 32), "红=不含 C 冰岩；蓝=含 C 冰壳；圈=文中示例",
              11, False, INK)

    draw_text(d, (W // 2, H - 18),
              "数据 alchemy/t93_candidates.json ｜ 复现 python t93_static.py ｜ "
              "模型 A=串联热阻+核心恒温回归；模型 B(v2全域λ)更低（见文档/JSON）",
              12, False, GREY, "ms")
    img.save(OUT_PNG)


if __name__ == "__main__":
    main()
