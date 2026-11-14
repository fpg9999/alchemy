# -*- coding: utf-8 -*-
"""最终闭包（N=30）+ 只用单质能否产出 + O3C 专项检查"""
import sys
from collections import Counter, defaultdict
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot2 as P


def atoms_of(v):
    return ["O"] * v[0] + ["X"] * v[1] + ["C"] * v[2]


def vec_of_formula(f):
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


def run(v):
    mols = P.simulate(atoms_of(v))
    if mols is None:
        return None, "剩键"
    if not P.embed_all(mols):
        return None, "摆不出来"
    return mols, "ok"


def semigroup(vectors, N):
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


N = 30
known = {"O2": (2, 0, 0), "X2": (0, 2, 0), "C2": (0, 0, 2)}
first = {"O2": (2, 0, 0), "X2": (0, 2, 0), "C2": (0, 0, 2)}
for it in range(10):
    vecs = sorted(semigroup(list(known.values()), N))
    new = 0
    for v in vecs:
        mols, why = run(v)
        if mols is None:
            continue
        for m in mols:
            f = P.formula_of(m["atoms"])
            if f not in known:
                known[f] = vec_of_formula(f)
                first[f] = v
                new += 1
    print(f"iter {it}: reachable={len(vecs)} known={len(known)} new={new}")
    if new == 0:
        break

print("\n最终清单 (%d 种):" % len(known))
for f in sorted(known, key=lambda s: (len(vec_of_formula(s)), vec_of_formula(s))):
    print(f"  {f:8s} vec={known[f]}  首次出现投料={first[f]}")

# 只用三种单质（全偶数投料）能得到的
even_prod = set()
for total in range(2, 31, 2):
    for a in range(0, total + 1, 2):
        for b in range(0, total - a + 1, 2):
            c = total - a - b
            if c < 0 or c % 2:
                continue
            mols, why = run((a, b, c))
            if mols is None:
                continue
            even_prod |= {P.formula_of(m["atoms"]) for m in mols}
print("\n只用三种单质就能得到的 (%d 种):" % len(even_prod))
print(" ", sorted(even_prod, key=lambda s: (len(vec_of_formula(s)), vec_of_formula(s))))
print("\n需要把产物再投一次才能得到的:")
print(" ", sorted(set(known) - even_prod, key=lambda s: (len(vec_of_formula(s)), vec_of_formula(s))))

# O3C 专项：哪些输入能产出 O3C
print("\n=== 能产出 O3C 的输入 (总原子<=24) ===")
found = []
for total in range(1, 25):
    for a in range(total + 1):
        for b in range(total - a + 1):
            c = total - a - b
            if c < 0 or (a + c) % 2:
                continue
            v = (a, b, c)
            mols, why = run(v)
            if mols is None:
                continue
            if any(P.formula_of(m["atoms"]) == "O3C" for m in mols):
                found.append(v)
print(" ", found[:20], "共", len(found))
reach = semigroup(list(known.values()), 24)
print("  其中是否可达:", [v for v in found if v in reach])
