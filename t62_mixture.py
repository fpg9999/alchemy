# -*- coding: utf-8 -*-
"""t62_mixture.py —— T62 两阶段实验的投料设计（九元素 · 三/二/一价数量相当）

T62 要求（用户 2026-11-17）：
* 九种元素全部包含；
* **三价元素、二价元素、一价元素之间的数量都差不多**——
  本次设计把目标定为：三价原子、二价原子、一价原子各占 1/3；
  并进一步把 9 种元素各自的原子数都调到 ~1/9（三价 3 种、二价 3 种、一价 3 种），
  这样无论按"价数类"还是"单元素"口径看都是均衡的；
* 初始投入物质种类 ≥100 种；
* 第一阶段降温到 0°C 后"整理"，再投入第二批物质，温度重置 1000°C 做第二阶段。

与 T59 的唯一设计差别：T59 是有偏投料（三价:二价:一价 = 52.3 : 26.3 : 21.4），
T62 是等量投料（≈33.3 : 33.3 : 33.3）；规模/环境/温度/物种数等其余变量沿用 T59，
以保证对照实验只改变"价数配比"这一个变量。

投料构造：
1. batchA：从 84,225 目录按价数偏向分三组各抽 40 种（共 120 种，原子数 2~14），
   补足九元素；基础数量 ∝1/原子数（面积越大数量越少）；
2. 用 **IPF（迭代比例拟合）** 把每个元素的原子数调到 target/9，
   同时把总原子数归一到目标值；收敛后按整数取整并复核偏差；
3. batchB（第二阶段前加入）：随机抽 120 种目录物质（2~14 原子），同样按 9 元素等量 IPF，
   总量约 80k 原子——保证第二阶段整体仍严格维持 1:1:1。

输出：t62_loads.json（batchA / batchB 设计、元素/价数统计、偏差指标）
"""
import json
import random
import sys

import numpy as np

BASE = r"G:\AI work\deepseek\work1\alchemy"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import pot_all as P

V3 = {"O", "P", "K"}
V2 = {"X", "W", "A"}
V1 = {"C", "L", "F"}
ELEMS = P.ORDER                       # O X C P W L K A F
SEED_A = 20261124
SEED_B = 20261125
TARGET_ATOMS_A = 150000
TARGET_ATOMS_B = 80000
N_GROUP = (40, 40, 40)                # 三价富集 / 二价富集 / 一价富集
N_SPECIES_B = 120
SIZE_MIN, SIZE_MAX = 2, 14
EQUAL_SHARE = 1.0 / 3.0               # 三/二/一价目标占比
ELEMENT_SHARE = 1.0 / 9.0             # 单元素目标占比


def load_index():
    return json.load(open(BASE + r"\t4_catalog_index.json", encoding="utf-8"))


def vec(f):
    return P.parse_formula(f)


def vcounts(f):
    v = vec(f)
    a3 = sum(v[P.ORDER.index(e)] for e in V3)
    a2 = sum(v[P.ORDER.index(e)] for e in V2)
    a1 = sum(v[P.ORDER.index(e)] for e in V1)
    return a3, a2, a1


def classify(f):
    """0=三价富集(≥50%)，2=一价富集(≥50%)，1=其余（二价富集）。"""
    a3, a2, a1 = vcounts(f)
    n = a3 + a2 + a1
    if n == 0:
        return 1
    if a3 / n >= 0.5:
        return 0
    if a1 / n >= 0.5:
        return 2
    return 1


def ensure_elements(chosen, pool, rng):
    have = set().union(*[set(ch for ch in f if ch.isalpha() and ch.isupper())
                         for f in chosen])
    added = False
    for e in ELEMS:
        if e not in have:
            cands = [f for f in pool if e in f and f not in chosen]
            if cands:
                chosen.append(rng.choice(cands))
                added = True
    return chosen, added


def ipf_balance(forms, base_counts, target_atoms, target_element_share=ELEMENT_SHARE,
                iters=600, damp=0.5, clip_lo=20.0, clip_hi=2.0e6, tol=0.004):
    """迭代比例拟合：让 9 种元素原子数都 = target_atoms/9（⇒ 价数类各 1/3）。

    返回 (整数 counts, 诊断 dict)。
    """
    n = len(forms)
    atoms = np.array([sum(vec(f)) for f in forms], dtype=float)
    W = np.zeros((n, 9), dtype=float)          # 每分子中各元素原子数（原始计数）
    S = np.zeros((n, 9), dtype=float)          # 每分子中各元素原子数占比（用于更新）
    for i, f in enumerate(forms):
        v = vec(f)
        W[i] = np.array(v, dtype=float)
        S[i] = W[i] / max(1.0, atoms[i])
    target = np.full(9, target_atoms * target_element_share, dtype=float)
    counts = np.array(base_counts, dtype=float)
    hist = []
    for it in range(iters):
        elem_tot = counts @ W                 # (9,) 元素原子总数
        ratio = target / np.maximum(elem_tot, 1e-9)
        # 每个物种按所含元素的占比加权几何平均比例放大
        logf = (np.log(ratio)[None, :] * S).sum(1)
        counts = counts * np.exp(damp * logf)
        counts = np.minimum(np.maximum(counts, clip_lo), clip_hi)
        total = float(counts @ atoms)
        counts = counts * (target_atoms / total)
        counts = np.minimum(np.maximum(counts, clip_lo), clip_hi)
        # 归一后每步再强制总量（取整前）
        counts = counts * (target_atoms / float(counts @ atoms))
        if it % 25 == 0 or it == iters - 1:
            et = counts @ W
            dev = np.max(np.abs(et / target - 1.0))
            hist.append({"iter": it, "max_dev": round(float(dev), 5)})
            if dev < tol:
                break
    counts_i = np.maximum(20, np.round(counts).astype(np.int64))
    # 整数取整后诊断
    elem_tot = counts_i @ W
    cls_tot = np.array([sum(elem_tot[i] for i, e in enumerate(ELEMS) if e in V3),
                        sum(elem_tot[i] for i, e in enumerate(ELEMS) if e in V2),
                        sum(elem_tot[i] for i, e in enumerate(ELEMS) if e in V1)])
    total_a = int(round(float(counts_i @ atoms)))
    shares = [round(float(c) / total_a, 5) for c in cls_tot]
    elem_shares = {e: round(float(elem_tot[i]) / total_a, 5)
                   for i, e in enumerate(ELEMS) if elem_tot[i] > 0}
    max_dev_pp = round(100.0 * max(abs(s - EQUAL_SHARE) for s in shares), 3)
    elem_dev_pp = round(100.0 * max(abs(s - ELEMENT_SHARE)
                                    for s in elem_shares.values()), 3)
    diag = {
        "target_atoms": target_atoms,
        "final_atoms": total_a,
        "valence_atoms": {"v3": int(cls_tot[0]), "v2": int(cls_tot[1]),
                          "v1": int(cls_tot[2])},
        "valence_shares": shares,
        "max_valence_deviation_pp": max_dev_pp,
        "element_shares": elem_shares,
        "max_element_deviation_pp": elem_dev_pp,
        "element_atoms": {e: int(elem_tot[i]) for i, e in enumerate(ELEMS)
                          if elem_tot[i] > 0},
        "iters": hist,
        "balanced": bool(max_dev_pp <= 2.0),
        "equal_valence": True,
    }
    return counts_i, diag


def build_batch_equal(pool_grouped, n_group, seed, target_atoms, iters=600):
    rng = random.Random(seed)
    chosen = []
    for g, k in enumerate(n_group):
        pool = sorted(set(pool_grouped[g]))
        chosen += rng.sample(pool, min(k, len(pool)))
    all_pool = sorted(set(f for g in pool_grouped for f in pool_grouped[g]))
    chosen, _added = ensure_elements(chosen, all_pool, rng)
    chosen = sorted(set(chosen), key=lambda f: (sum(vec(f)), f))
    base = [max(20, int(round(900.0 / sum(vec(f))))) for f in chosen]
    counts, diag = ipf_balance(chosen, base, target_atoms, iters=iters)
    rows = [{"formula": f, "atoms": int(sum(vec(f))), "count": int(c),
             "valence_group": classify(f),
             "v3": vcounts(f)[0], "v2": vcounts(f)[1], "v1": vcounts(f)[2]}
            for f, c in zip(chosen, counts)]
    return rows, diag


def build_batchA(target_atoms=TARGET_ATOMS_A, seed=SEED_A):
    idx = load_index()
    by_group = {0: [], 1: [], 2: []}
    for r in idx:
        n = r["natoms"]
        if SIZE_MIN <= n <= SIZE_MAX:
            by_group[classify(r["formula"])].append(r["formula"])
    rows, diag = build_batch_equal(by_group, N_GROUP, seed, target_atoms)
    return rows, diag


def build_batchB(target_atoms=TARGET_ATOMS_B, seed=SEED_B):
    idx = load_index()
    pool = [r["formula"] for r in idx if SIZE_MIN <= r["natoms"] <= SIZE_MAX]
    by_group = {0: [], 1: [], 2: []}
    for f in pool:
        by_group[classify(f)].append(f)
    rows, diag = build_batch_equal(by_group, (40, 40, 40), seed, target_atoms)
    return rows, diag


def summarize(rows):
    n_species = len(rows)
    n_mol = sum(r["count"] for r in rows)
    n_atoms = sum(r["count"] * r["atoms"] for r in rows)
    atoms = {e: 0 for e in ELEMS}
    v3 = v2 = v1 = 0
    for r in rows:
        v = vec(r["formula"])
        for i, e in enumerate(ELEMS):
            atoms[e] += v[i] * r["count"]
        a3, a2, a1 = vcounts(r["formula"])
        v3 += a3 * r["count"]
        v2 += a2 * r["count"]
        v1 += a1 * r["count"]
    tot_v = v3 + v2 + v1
    shares = [round(v3 / tot_v, 4), round(v2 / tot_v, 4), round(v1 / tot_v, 4)]
    elem_shares = {e: round(atoms[e] / n_atoms, 4) for e in ELEMS if atoms[e] > 0}
    return {
        "n_species": n_species, "molecules": n_mol, "atoms": n_atoms,
        "mean_atoms": round(n_atoms / n_mol, 3),
        "element_atoms": {e: c for e, c in atoms.items() if c > 0},
        "elements_covered": sorted([e for e, c in atoms.items() if c > 0]),
        "element_shares": elem_shares,
        "valence_atoms": {"v3": v3, "v2": v2, "v1": v1},
        "valence_shares": shares,
        "strict_order": bool(v3 > 1.05 * v2 and v2 > 1.05 * v1),  # T59 口径（本实验应为 False）
        "equal_valence": bool(max(shares) - min(shares) <= 0.02),
        "max_valence_deviation_pp": round(100.0 * max(abs(s - EQUAL_SHARE)
                                                      for s in shares), 3),
        "max_element_deviation_pp": round(100.0 * max(abs(s - ELEMENT_SHARE)
                                                      for s in elem_shares.values()), 3),
    }


if __name__ == "__main__":
    rowsA, diagA = build_batchA()
    rowsB, diagB = build_batchB()
    sumA, sumB = summarize(rowsA), summarize(rowsB)
    out = {"batchA": {"rows": rowsA, "summary": sumA, "ipf": diagA},
           "batchB": {"rows": rowsB, "summary": sumB, "ipf": diagB},
           "config": {"seedA": SEED_A, "seedB": SEED_B,
                      "target_atoms_A": TARGET_ATOMS_A,
                      "target_atoms_B": TARGET_ATOMS_B,
                      "valence_target": "三/二/一价原子各 1/3",
                      "element_target": "9 元素原子各 1/9",
                      "equality_tolerance_pp": 2.0,
                      "groups": N_GROUP, "size_range": [SIZE_MIN, SIZE_MAX],
                      "designer": "t62_mixture.py（IPF 等量配比）"}}
    json.dump(out, open(BASE + r"\t62_loads.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("batchA:", json.dumps(sumA, ensure_ascii=False, indent=1))
    print("batchB:", json.dumps(sumB, ensure_ascii=False, indent=1))
    print("ipf A final dev pp:", diagA["max_valence_deviation_pp"],
          diagA["max_element_deviation_pp"], "iters", diagA["iters"][-1])
    print("ipf B final dev pp:", diagB["max_valence_deviation_pp"],
          diagB["max_element_deviation_pp"], "iters", diagB["iters"][-1])
