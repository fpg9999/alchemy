# -*- coding: utf-8 -*-
"""verify_finite：对"有限类别"随机大投料，验证最大分子确实封顶（<=16 原子）。

依赖 minimal_infinite.json。输出 finite_verify.json。
"""
import itertools
import json
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def rand_vec(total, k, rng):
    cuts = sorted(rng.sample(range(total + k - 1), k - 1)) if k > 1 else []
    out, prev = [], -1
    for c in cuts + [total + k - 1]:
        out.append(c - prev - 1)
        prev = c
    return out


def vec_full(partial, elems):
    v = [0] * 9
    for e, c in zip(elems, partial):
        v[P.ORDER.index(e)] = c
    return tuple(v)


def test_pool(args):
    elems, T, samples, seed = args
    rng = random.Random(seed)
    best = 0
    bestf = None
    for _ in range(samples):
        comp = rand_vec(T, len(elems), rng)
        v = vec_full(comp, elems)
        atoms = P.vec_to_atoms(v, P.ORDER)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        mols = P.simulate(atoms)
        if not mols:
            continue
        mx = max(len(m["atoms"]) for m in mols)
        if mx > best:
            best = mx
            bestf = P.formula_of([m for m in mols if len(m["atoms"]) == mx][0]["atoms"])
    return list(elems), T, best, bestf


def main():
    minf = json.load(open(BASE + r"\minimal_infinite.json", encoding="utf-8"))
    minimal = [set(s.split("/")) for s in minf["minimal"]]
    pools = []
    for r in range(1, 10):
        for c in itertools.combinations(P.ORDER, r):
            cs = set(c)
            if any(m <= cs for m in minimal):
                continue
            pools.append(list(c))
    print("有限类别数:", len(pools), flush=True)
    jobs = max(4, (os.cpu_count() or 8) - 2)
    out = {}
    tasks = [(p, 30 if len(p) >= 6 else 28, 400, abs(hash(tuple(p))) & 0xffffffff) for p in pools]
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for elems, T, best, bestf in pool.map(test_pool, tasks):
            key = "/".join(elems)
            out[key] = {"T": T, "max": best, "formula": bestf}
            if best > 16:
                print(f"  !! 有限类别 {'/'.join(elems)} T={T} 出现 {best} 原子分子 {bestf}", flush=True)
    json.dump(out, open(BASE + r"\finite_verify.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    over = {k: v for k, v in out.items() if v["max"] > 16}
    print(f"验证完成: {len(out)} 个有限类别，其中 >16 原子的 {len(over)} 个")
    print("最大观测尺寸分布:", sorted({v["max"] for v in out.values()}))


if __name__ == "__main__":
    main()
