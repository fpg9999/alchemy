# -*- coding: utf-8 -*-
"""subset_growth：按"元素子集"判定哪些组合能出现任意大的分子（无限族），哪些封顶（有限块）。

对每个候选子集（至少跨两个大类），随机大投料 + 整锅成功判定 + 可摆放判定，
记录 T=16/20/24/28 时能成功的最大单分子尺寸。
"""
import itertools
import json
import random
import sys
import time

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

SCOPES = {
    3: ["O", "X", "C", "K", "A", "F"],
    4: ["O", "X", "C", "P", "W", "L"],
    5: ["P", "W", "L", "K", "A", "F"],
    6: P.ORDER,
}
BASE = r"G:\AI work\deepseek\work1\alchemy"


def rand_vec(total, k, rng):
    cuts = sorted(rng.sample(range(total + k - 1), k - 1)) if k > 1 else []
    out, prev = [], -1
    for c in cuts + [total + k - 1]:
        out.append(c - prev - 1)
        prev = c
    return out


def test_subset(elems, T, samples, rng, budget=200000):
    best = 0
    bestf = None
    for _ in range(samples):
        v = rand_vec(T, len(elems), rng)
        atoms = P.vec_to_atoms(tuple(v), elems)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        mols = P.simulate(atoms)
        if not mols:
            continue
        mx = max(len(m["atoms"]) for m in mols)
        if mx <= best:
            continue
        m = [x for x in mols if len(x["atoms"]) == mx][0]
        if P.embed_mol(m["atoms"], m["edges"], max_nodes=budget) is None:
            continue
        # 整锅成功需要所有产物可摆
        if not P.embed_all(mols):
            continue
        best = mx
        bestf = P.formula_of(m["atoms"])
    return best, bestf


def main():
    sid = int(sys.argv[1])
    samples = int(sys.argv[2]) if len(sys.argv) > 2 else 150
    elems_all = SCOPES[sid]
    rng = random.Random(31415)
    rows = []
    subsets = []
    for r in range(2, len(elems_all) + 1):
        for sub in itertools.combinations(elems_all, r):
            cats = {P.CAT[e] for e in sub}
            if len(cats) >= 2:
                subsets.append(sub)
    print(f"范围{sid}: {len(subsets)} 个跨类子集", flush=True)
    for sub in subsets:
        t = time.time()
        row = {"subset": list(sub), "cats": sorted({P.CAT[e] for e in sub})}
        for T in (16, 20, 24, 28):
            best, bestf = test_subset(list(sub), T, samples, rng)
            row[f"T{T}"] = {"max": best, "formula": bestf}
        # 判定：T=28 时仍能到 >=24 视为"疑似无限"
        row["infinite"] = row["T28"]["max"] >= 24
        rows.append(row)
        print(f"  {'/'.join(sub):14s} T16={row['T16']['max']:2d} T20={row['T20']['max']:2d} "
              f"T24={row['T24']['max']:2d} T28={row['T28']['max']:2d} "
              f"{'无限' if row['infinite'] else '有限'}  ({time.time()-t:.1f}s)", flush=True)
        json.dump(rows, open(BASE + rf"\scope{sid}_subset_growth.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print("saved", BASE + rf"\scope{sid}_subset_growth.json")


if __name__ == "__main__":
    main()
