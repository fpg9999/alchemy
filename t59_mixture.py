# -*- coding: utf-8 -*-
"""t59_mixture.py —— T59 两阶段实验的投料设计

T59 要求：
* 九种元素全部包含；
* **三价元素含量最多、一价元素含量最少**（三价元素 = O/P/K；二价 = X/W/A；一价 = C/L/F）；
* 初始投入物质种类 **≥100 种**；
* 数量足够多（规模目标：约 2~3 万分子 / 15~20 万原子，具体随优化后可行规模调整）；
* 第一阶段降温到 0°C 后"整理"，再投入一次随机大量物质，重置 1000°C 做第二阶段。

投料构造：
1. 从 84,225 目录按价数偏向分组随机抽取 120 种物质：
   - 60 种"三价丰富"（三价原子占比 ≥50%）
   - 40 种"二价丰富"（二价原子占比 ≥50%）
   - 20 种"一价丰富"（一价原子占比 ≥50%）
   并补足缺失元素，保证九元素都出现；
2. 每种物质基础数量 ∝1/原子数（面积越大数量越少）；
3. 解 3×3 线性方程，把三组的数量整体放大/缩小，使
   **三价:二价:一价 原子数 = 55% : 30% : 15%**（严格满足"三价最多、一价最少"）；
4. 第二批（第二阶段前加入）：另随机抽 120 种目录物质（不限制价数），数量按 1/原子数，
   总量约为第一批的 50%~60%。

输出：t59_loads.json（batchA / batchB 设计、元素/价数统计）
"""
import json
import math
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
ELEMS = P.ORDER
SEED_A = 20261122
SEED_B = 20261123
TARGET_ATOMS_A = 150000
VALENCE_SHARES = (0.55, 0.30, 0.15)
N_GROUP = (60, 40, 20)
SIZE_MIN, SIZE_MAX = 2, 14


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
    a3, a2, a1 = vcounts(f)
    n = a3 + a2 + a1
    if n == 0:
        return 1
    f3, f2, f1 = a3 / n, a2 / n, a1 / n
    if f3 >= 0.5:
        return 0
    if f1 >= 0.5:
        return 2
    return 1


def group_counts(forms, counts):
    A = np.zeros((3, 3), dtype=float)
    for f, c in zip(forms, counts):
        a3, a2, a1 = vcounts(f)
        g = classify(f)
        A[g] += np.array([a3, a2, a1], dtype=float) * c
    return A


def build_batchA(target_atoms=TARGET_ATOMS_A, seed=SEED_A):
    idx = load_index()
    rng = random.Random(seed)
    by_group = {0: [], 1: [], 2: []}
    for r in idx:
        n = r["natoms"]
        if SIZE_MIN <= n <= SIZE_MAX:
            by_group[classify(r["formula"])].append(r["formula"])
    chosen = []
    for g, k in enumerate(N_GROUP):
        pool = sorted(set(by_group[g]))
        chosen += rng.sample(pool, min(k, len(pool)))
    chosen = sorted(set(chosen))
    # 补足九元素
    have = set().union(*[set(ch for ch in f if ch.isalpha() and ch.isupper()) for f in chosen])
    for e in ELEMS:
        if e not in have:
            cands = [f for g in by_group for f in by_group[g]
                     if e in f and f not in chosen]
            if cands:
                chosen.append(rng.choice(cands))
    chosen = sorted(set(chosen), key=lambda f: (sum(vec(f)), f))
    base = [max(20, int(round(900.0 / sum(vec(f))))) for f in chosen]
    groups = [classify(f) for f in chosen]
    A = group_counts(chosen, base)
    target = np.array(VALENCE_SHARES) * target_atoms
    # A x = target（三组倍数）
    try:
        x = np.linalg.solve(A, target)
    except np.linalg.LinAlgError:
        x = np.ones(3)
    x = np.clip(x, 0.2, 20.0)
    counts = [max(20, int(round(b * x[g]))) for b, g in zip(base, groups)]
    # 若价数顺序不满足，微调：放大 3 价组或缩小 1 价组
    for _ in range(30):
        a3 = sum(c * vcounts(f)[0] for f, c in zip(chosen, counts))
        a2 = sum(c * vcounts(f)[1] for f, c in zip(chosen, counts))
        a1 = sum(c * vcounts(f)[2] for f, c in zip(chosen, counts))
        if a3 > a2 > a1:
            break
        for i, f in enumerate(chosen):
            g = groups[i]
            if g == 0:
                counts[i] = int(round(counts[i] * 1.15))
            elif g == 2 and a1 >= a2:
                counts[i] = max(20, int(round(counts[i] * 0.85)))
    # 按目标总量归一化到 150k 原子左右，同时不破坏价数比例
    total_atoms = sum(c * sum(vec(f)) for f, c in zip(chosen, counts))
    scale = target_atoms / total_atoms
    counts = [max(20, int(round(c * scale))) for c in counts]
    rows = [{"formula": f, "atoms": sum(vec(f)), "count": c,
             "valence_group": groups[i],
             "v3": vcounts(f)[0], "v2": vcounts(f)[1], "v1": vcounts(f)[2]}
            for i, (f, c) in enumerate(zip(chosen, counts))]
    return rows


def build_batchB(target_atoms=80000, seed=SEED_B):
    idx = load_index()
    rng = random.Random(seed)
    pool = [r["formula"] for r in idx if SIZE_MIN <= r["natoms"] <= SIZE_MAX]
    chosen = rng.sample(pool, 120)
    # 补足九元素
    have = set().union(*[set(ch for ch in f if ch.isalpha() and ch.isupper()) for f in chosen])
    for e in ELEMS:
        if e not in have:
            cands = [f for f in pool if e in f and f not in chosen]
            if cands:
                chosen.append(rng.choice(cands))
    chosen = sorted(set(chosen), key=lambda f: (sum(vec(f)), f))
    base = [max(20, int(round(600.0 / sum(vec(f))))) for f in chosen]
    total = sum(c * sum(vec(f)) for f, c in zip(chosen, base))
    scale = target_atoms / total
    counts = [max(20, int(round(c * scale))) for c in base]
    rows = [{"formula": f, "atoms": sum(vec(f)), "count": c,
             "v3": vcounts(f)[0], "v2": vcounts(f)[1], "v1": vcounts(f)[2]}
            for f, c in zip(chosen, counts)]
    return rows


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
    return {
        "n_species": n_species, "molecules": n_mol, "atoms": n_atoms,
        "mean_atoms": round(n_atoms / n_mol, 3),
        "element_atoms": {e: c for e, c in atoms.items() if c > 0},
        "elements_covered": sorted([e for e, c in atoms.items() if c > 0]),
        "valence_atoms": {"v3": v3, "v2": v2, "v1": v1},
        "valence_shares": [round(v3 / (v3 + v2 + v1), 4),
                           round(v2 / (v3 + v2 + v1), 4),
                           round(v1 / (v3 + v2 + v1), 4)],
        "strict_order": bool(v3 > v2 > v1),
    }


if __name__ == "__main__":
    rowsA = build_batchA()
    rowsB = build_batchB()
    out = {"batchA": {"rows": rowsA, "summary": summarize(rowsA)},
           "batchB": {"rows": rowsB, "summary": summarize(rowsB)},
           "config": {"seedA": SEED_A, "seedB": SEED_B,
                      "target_atoms_A": TARGET_ATOMS_A,
                      "valence_shares": VALENCE_SHARES,
                      "groups": N_GROUP}}
    json.dump(out, open(BASE + r"\t59_loads.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("batchA:", json.dumps(out["batchA"]["summary"], ensure_ascii=False, indent=1))
    print("batchB:", json.dumps(out["batchB"]["summary"], ensure_ascii=False, indent=1))
