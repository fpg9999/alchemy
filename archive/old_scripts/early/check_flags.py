# -*- coding: utf-8 -*-
"""check_flags：对 verify_finite 里"有限类别却出现 >16 原子分子"的16个类别，
用完整的"整锅成功（所有产物可摆）"口径复核，判断是否真的能产出 >16 原子物质。

verify_finite 只看 simulate（没做几何判定），可能有假阳性。
"""
import json
import random
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
FLAG = [
    "O/X/W", "O/X/A", "O/P/K", "O/W/A", "X/P/W", "X/P/A", "X/W/K", "P/W/A",
    "W/K/A", "O/C/W/A", "O/W/A/F", "X/C/W/K", "X/P/L/A", "X/P/A/F", "X/W/L/K",
    "X/W/K/F",
]


def rand_vec(total, k, rng):
    cuts = sorted(rng.sample(range(total + k - 1), k - 1)) if k > 1 else []
    out, prev = [], -1
    for c in cuts + [total + k - 1]:
        out.append(c - prev - 1)
        prev = c
    return out


def task(args):
    elems, T, samples, seed = args
    rng = random.Random(seed)
    best = 0
    bestinfo = None
    for _ in range(samples):
        comp = rand_vec(T, len(elems), rng)
        v = [0] * 9
        for e, c in zip(elems, comp):
            v[P.ORDER.index(e)] = c
        atoms = P.vec_to_atoms(tuple(v), P.ORDER)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        mols = P.simulate(atoms)
        if not mols:
            continue
        mx = max(len(m["atoms"]) for m in mols)
        if mx <= 16 or mx <= best:
            continue
        ok = all(P.embed_mol(m["atoms"], m["edges"], max_nodes=80000) is not None
                 for m in mols)
        if not ok:
            continue
        m = [x for x in mols if len(x["atoms"]) == mx][0]
        best = mx
        bestinfo = (P.formula_of(m["atoms"]), list(v), len(mols))
    return "/".join(elems), T, best, bestinfo


if __name__ == "__main__":
    jobs = 8
    tasks = []
    for key in FLAG:
        elems = key.split("/")
        for T in (28, 32):
            tasks.append((elems, T, 2500, abs(hash((key, T))) & 0xffffffff))
    res = {}
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for key, T, best, info in pool.map(task, tasks):
            if key not in res or best > res[key][1]:
                res[key] = (T, best, info)
    for key in FLAG:
        T, best, info = res.get(key, (None, 0, None))
        print(f"{key:12s} T={T} 成功且整锅可摆的最大分子={best} {info}")
    json.dump({k: {"T": v[0], "max": v[1], "info": v[2]} for k, v in res.items()},
              open(BASE + r"\flags_recheck.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved flags_recheck.json")
