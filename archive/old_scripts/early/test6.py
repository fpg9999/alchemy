# -*- coding: utf-8 -*-
"""test6：测试唯一的"不含已发现最小无限集合"的 6 元子集是否有限。"""
import json
import random
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
ELEMS = ["X", "C", "W", "L", "A", "F"]


def rand_vec(total, k, rng):
    cuts = sorted(rng.sample(range(total + k - 1), k - 1)) if k > 1 else []
    out, prev = [], -1
    for c in cuts + [total + k - 1]:
        out.append(c - prev - 1)
        prev = c
    return out


def task(args):
    T, samples, seed = args
    rng = random.Random(seed)
    best = 0
    bestf = None
    for _ in range(samples):
        comp = rand_vec(T, len(ELEMS), rng)
        v = [0] * 9
        for e, c in zip(ELEMS, comp):
            v[P.ORDER.index(e)] = c
        atoms = P.vec_to_atoms(tuple(v), P.ORDER)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        mols = P.simulate(atoms)
        if not mols:
            continue
        mx = max(len(m["atoms"]) for m in mols)
        if mx > best:
            m = [x for x in mols if len(x["atoms"]) == mx][0]
            if P.embed_mol(m["atoms"], m["edges"], max_nodes=100000) is not None:
                best = mx
                bestf = P.formula_of(m["atoms"])
    return T, best, bestf


if __name__ == "__main__":
    tasks = [(T, 6000, T * 7) for T in (24, 28, 32)]
    with ProcessPoolExecutor(max_workers=3) as pool:
        for T, best, f in pool.map(task, tasks):
            print(f"T={T}: 最大可摆分子 {best} {f}", flush=True)
