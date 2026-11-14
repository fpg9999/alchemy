# -*- coding: utf-8 -*-
"""枚举大锅产物"""
import itertools
import random
import sys
from collections import defaultdict
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from pot import simulate, result_formulas, result_signature, formula_of, VAL, ELEMS


def atoms_of(v):
    o, x, c = v
    return ["O"] * o + ["X"] * x + ["C"] * c


def vec_of_formula(f):
    """'O2X' -> (2,1,0)"""
    v = {"O": 0, "X": 0, "C": 0}
    i = 0
    while i < len(f):
        e = f[i]
        i += 1
        num = ""
        while i < len(f) and f[i].isdigit():
            num += f[i]
            i += 1
        v[e] += int(num) if num else 1
    return (v["O"], v["X"], v["C"])


def semigroup(vectors, N):
    """所有可由 vectors 非负整数组合得到、总原子数<=N 的向量"""
    reach = set()
    stack = [(0, 0, 0)]
    seen = {(0, 0, 0)}
    while stack:
        o, x, c = stack.pop()
        reach.add((o, x, c))
        for (do, dx, dc) in vectors:
            n = (o + do, x + dx, c + dc)
            if sum(n) <= N and n not in seen:
                seen.add(n)
                stack.append(n)
    return reach


def determinism_check(v, trials=4):
    base = result_signature(simulate(atoms_of(v)))
    for _ in range(trials):
        a = atoms_of(v)
        random.shuffle(a)
        s = result_signature(simulate(a))
        if s != base:
            return base, s
    return None


def main():
    N = 14
    # 先把所有可达向量找出来（逐步扩张）
    known = {}   # formula -> vector
    for f, v in [("O2", (2, 0, 0)), ("X2", (0, 2, 0)), ("C2", (0, 0, 2))]:
        known[f] = v
    prod_examples = {}   # formula -> 一个能产出它的输入向量
    fails = []
    amb = []
    simulated = {}
    for it in range(6):
        vecs = sorted(semigroup(list(known.values()), N))
        new = 0
        for v in vecs:
            if v in simulated:
                continue
            mols = simulate(atoms_of(v))
            simulated[v] = mols
            if mols is None:
                fails.append(v)
                continue
            for m in mols:
                f = formula_of(m["atoms"])
                if f not in known:
                    known[f] = vec_of_formula(f)
                    prod_examples[f] = v
                    new += 1
        print(f"iter {it}: reachable vecs={len(vecs)}, known formulas={len(known)}, new={new}")
        if new == 0:
            break

    print("\n=== 可产出物质（公式） ===")
    for f in sorted(known, key=lambda s: (len(s), s)):
        print(f"  {f:8s} vec={known[f]}  例:输入 {prod_examples.get(f)}")

    print("\n=== 失败输入（前 30） ===")
    for v in fails[:30]:
        print("  fail", v, "slots", 3 * v[0] + 2 * v[1] + v[2])

    print("\n=== 规模扫描（不要求可达，a,b,c<=7） ===")
    allf = set()
    big = []
    for a in range(8):
        for b in range(8):
            for c in range(8):
                if (a + c) % 2:
                    continue
                v = (a, b, c)
                mols = simulate(atoms_of(v))
                if mols is None:
                    continue
                fs = result_formulas(mols)
                allf |= set(fs)
                mx = max(len(m["atoms"]) for m in mols)
                if mx > 4:
                    big.append((v, fs))
    print("扫描出现的公式:", sorted(allf, key=lambda s: (len(s), s)))
    print("产物里出现 >4 原子的输入数:", len(big))
    for v, fs in big[:15]:
        print("   ", v, fs)


if __name__ == "__main__":
    main()
