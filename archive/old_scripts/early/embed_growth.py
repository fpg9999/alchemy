# -*- coding: utf-8 -*-
"""embed_growth：测"可几何摆放"的最大分子尺寸是否随投料增长（判定有限/无限）。

对随机投料，取产物中最大的单个分子，用带节点预算的回溯判定能否摆出。
"""
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


def rand_vec(total, k, rng):
    cuts = sorted(rng.sample(range(total + k - 1), k - 1)) if k > 1 else []
    out, prev = [], -1
    for c in cuts + [total + k - 1]:
        out.append(c - prev - 1)
        prev = c
    return out


def main():
    sid = int(sys.argv[1])
    samples = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    budget = int(sys.argv[3]) if len(sys.argv) > 3 else 300000
    elems = SCOPES[sid]
    rng = random.Random(2024)
    for T in range(16, 41, 4):
        t = time.time()
        best = 0
        best_info = None
        tried = 0
        for _ in range(samples):
            v = rand_vec(T, len(elems), rng)
            atoms = P.vec_to_atoms(tuple(v), elems)
            if sum(P.VAL[e] for e in atoms) % 2:
                continue
            mols = P.simulate(atoms)
            if not mols:
                continue
            m = max(mols, key=lambda x: len(x["atoms"]))
            if len(m["atoms"]) <= best:
                continue
            tried += 1
            place = P.embed_mol(m["atoms"], m["edges"], max_nodes=budget)
            if place is None:
                continue
            f = P.formula_of(m["atoms"])
            if len(m["atoms"]) > best:
                best = len(m["atoms"])
                best_info = (f, v)
        print(f"T={T:2d} 可摆最大分子={best:2d}  (试了 {tried} 个大分子, {time.time()-t:.1f}s) 例={best_info}", flush=True)


if __name__ == "__main__":
    main()
