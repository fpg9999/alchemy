# -*- coding: utf-8 -*-
"""random_growth：随机大投料，测"最大分子尺寸"是否随投料增长（判断有限/无限集）。"""
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
    samples = int(sys.argv[2]) if len(sys.argv) > 2 else 1500
    elems = SCOPES[sid]
    rng = random.Random(777)
    for T in (16, 20, 24, 28, 32, 36, 40):
        t = time.time()
        best = 0
        bestf = None
        hits = 0
        for _ in range(samples):
            v = rand_vec(T, len(elems), rng)
            atoms = P.vec_to_atoms(tuple(v), elems)
            if sum(P.VAL[e] for e in atoms) % 2:
                continue
            mols = P.simulate(atoms)
            if not mols:
                continue
            mx = max(len(m["atoms"]) for m in mols)
            if mx > best:
                best = mx
                f = [P.formula_of(m["atoms"]) for m in mols if len(m["atoms"]) == mx][0]
                bestf = (f, v)
            if mx >= 16:
                hits += 1
        print(f"T={T:2d} 最大分子={best:2d}  出现>=16原子的样本={hits}/{samples}  最好={bestf}  ({time.time()-t:.1f}s)", flush=True)


if __name__ == "__main__":
    main()
