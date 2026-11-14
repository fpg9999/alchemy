# -*- coding: utf-8 -*-
"""大范围验证 + 产物结构描述"""
import itertools
import random
import sys
from collections import defaultdict, Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot2 as P


def atoms_of(v):
    o, x, c = v
    return ["O"] * o + ["X"] * x + ["C"] * c


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


print("=== D. 更大范围验证：总原子 <= 24 全扫 ===")
N = 24
fs = {}
maxsize = 0
cnt = 0
for total in range(1, N + 1):
    for a in range(total + 1):
        for b in range(total - a + 1):
            c = total - a - b
            if c < 0 or (a + c) % 2:
                continue
            cnt += 1
            mols, why = run((a, b, c))
            if mols is None:
                continue
            for m in mols:
                maxsize = max(maxsize, len(m["atoms"]))
                fs.setdefault(P.formula_of(m["atoms"]), (a, b, c))
print(f"  扫描输入数={cnt}, 公式数={len(fs)}, 最大分子原子数={maxsize}")
print("  公式:", sorted(fs, key=lambda s: (len(vec_of_formula(s)), vec_of_formula(s))))

print("\n=== E. 随机大投料（总原子 25~60）看是否有新公式/大分子 ===")
random.seed(7)
newf = set()
big = 0
for _ in range(400):
    a = random.randint(0, 25)
    b = random.randint(0, 25)
    c = random.randint(0, 25)
    if (a + c) % 2 or a + b + c == 0:
        continue
    mols, why = run((a, b, c))
    if mols is None:
        continue
    for m in mols:
        if len(m["atoms"]) > 6:
            big += 1
            print("   !大分子", (a, b, c), P.formula_of(m["atoms"]))
        f = P.formula_of(m["atoms"])
        if f not in fs:
            newf.add(f)
            print("   新公式", (a, b, c), "->", f)
print("  新公式:", newf, " 大分子数:", big)

print("\n=== F. 若干大投料的产物组成（看是否是小分子重复） ===")
for v in [(10, 10, 10), (9, 0, 9), (0, 9, 9), (9, 9, 0), (12, 0, 0), (6, 6, 6),
          (8, 8, 8), (4, 8, 4), (8, 4, 8), (5, 9, 7), (12, 6, 0), (0, 12, 6)]:
    mols, why = run(v)
    if mols is None:
        print(f"  {v}: 失败({why})")
    else:
        c = Counter(P.formula_of(m["atoms"]) for m in mols)
        print(f"  {v}: {dict(c)}")

print("\n=== G. 18 种产物的结构 ===")
known = {"O2": (2, 0, 0), "X2": (0, 2, 0), "C2": (0, 0, 2)}
example = {"O2": (2, 0, 0), "X2": (0, 2, 0), "C2": (0, 0, 2)}
for it in range(6):
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
                example[f] = v
                new += 1
    if new == 0:
        break

for f in sorted(known, key=lambda s: (len(vec_of_formula(s)), vec_of_formula(s))):
    v = example[f]
    mols, why = run(v)
    m = [m for m in mols if P.formula_of(m["atoms"]) == f][0]
    atoms = m["atoms"]
    deg = Counter()
    for (i, j, k) in m["edges"]:
        deg[i] += k
        deg[j] += k
    edge_str = ", ".join(f"{atoms[i]}{'='*k if k>1 else '-'}{atoms[j]}" for (i, j, k) in m["edges"])
    print(f"  {f:8s} 原子={len(atoms)}  键: {edge_str}   投料例子{v}")


# 把输入向量拆成已知物质的组合
def decompose(vec, gens, memo=None):
    gens = sorted(gens.items(), key=lambda kv: -sum(kv[1]))
    best = None

    def rec(rem, used):
        nonlocal best
        if rem == (0, 0, 0):
            if best is None or len(used) < len(best):
                best = list(used)
            return
        if best is not None and len(used) >= len(best):
            return
        for f, g in gens:
            if all(g[i] <= rem[i] for i in range(3)):
                rec(tuple(rem[i] - g[i] for i in range(3)), used + [f])

    rec(vec, [])
    return best


print("\n=== H. 每个产物的投料配方（用已知物质凑） ===")
for f in sorted(known, key=lambda s: (len(vec_of_formula(s)), vec_of_formula(s))):
    d = decompose(example[f], known)
    print(f"  {f:8s} <- {example[f]}  拆成: {d}")
