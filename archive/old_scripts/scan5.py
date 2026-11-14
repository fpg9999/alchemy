# -*- coding: utf-8 -*-
"""最终扫描 v2：规则6=并集；区分"结构不同但公式相同"和"公式不同"(规则7)"""
import random
import sys
from collections import Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot3 as P


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


def run(v, rng=None):
    mols = P.simulate(atoms_of(v), rng)
    if mols is None:
        return None, "剩键"
    if not P.embed_all(mols):
        return None, "摆不出来"
    return mols, "ok"


def fset(mols):
    return tuple(sorted(P.formula_of(x["atoms"]) for x in mols))


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
rng = random.Random(11)
certain = {}
possible = {}
amb_struct = 0
amb_formula = []
reasons = Counter()
maxsize = 0
formula_all = Counter()
for total in range(1, N + 1):
    for a in range(total + 1):
        for b in range(total - a + 1):
            c = total - a - b
            if c < 0 or (a + c) % 2:
                continue
            v = (a, b, c)
            mols, why = run(v)
            if mols is None:
                reasons[why] += 1
                continue
            reasons["ok"] += 1
            outs = {P.signature(mols): mols}
            for _ in range(3):
                aa = atoms_of(v)
                rng.shuffle(aa)
                m2 = P.simulate(aa, rng)
                if m2 is not None and P.embed_all(m2):
                    outs[P.signature(m2)] = m2
            fsets = set(fset(m) for m in outs.values())
            for m in outs.values():
                for x in m:
                    maxsize = max(maxsize, len(x["atoms"]))
            if len(outs) > 1:
                if len(fsets) > 1:
                    amb_formula.append((v, fsets))
                else:
                    amb_struct += 1
            common = None
            for m in outs.values():
                fs = set(P.formula_of(x["atoms"]) for x in m)
                common = fs if common is None else (common & fs)
                for f in fs:
                    possible.setdefault(f, v)
            for f in common:
                certain.setdefault(f, v)

print(f"N={N}: 失败={dict(reasons)}")
print(f"确定公式={len(certain)}, 可能公式={len(possible)}, 仅结构不同的并列输入={amb_struct}, 公式不同的并列输入={len(amb_formula)}, 最大原子={maxsize}")
print("\n=== 公式不同的并列输入（规则7相关） ===")
for v, fs in amb_formula[:10]:
    print(" ", v)
    for f in fs:
        print("     ", f)
print("\n=== 确定公式 ===")
for f in sorted(certain, key=lambda s: (len(vec_of_formula(s)), s)):
    print(f"  {f:10s} vec={vec_of_formula(f)} 例:{certain[f]}")
print("\n=== 可能公式（只在并列分支里出现） ===")
for f in sorted(set(possible) - set(certain), key=lambda s: (len(vec_of_formula(s)), s)):
    print(f"  {f:10s} 例:{possible[f]}")
print("\nO4X3C2 in certain:", "O4X3C2" in certain, " in possible:", "O4X3C2" in possible)

print("\n=== 可达闭包（确定公式为生成元，N=%d）===" % N)
known = dict(certain)
example = dict(certain)
for f, v in [("O2", (2, 0, 0)), ("X2", (0, 2, 0)), ("C2", (0, 0, 2))]:
    known[f] = v
    example[f] = v
for it in range(10):
    vecs = sorted(semigroup(list(known.values()), N))
    new = 0
    for v in vecs:
        mols, why = run(v)
        if mols is None:
            continue
        base_sig = P.signature(mols)
        outs = {base_sig: mols}
        for _ in range(2):
            aa = atoms_of(v)
            rng.shuffle(aa)
            m2 = P.simulate(aa, rng)
            if m2 is not None and P.embed_all(m2):
                outs[P.signature(m2)] = m2
        fset_common = None
        for m in outs.values():
            fs = set(P.formula_of(x["atoms"]) for x in m)
            fset_common = fs if fset_common is None else (fset_common & fs)
        for f in fset_common:
            if f not in known:
                known[f] = vec_of_formula(f)
                example[f] = v
                new += 1
    print(f"  iter {it}: 可达向量={len(vecs)} 已知={len(known)} 新增={new}")
    if new == 0:
        break

print("\n=== 最终清单（%d 种） ===" % len(known))
for f in sorted(known, key=lambda s: (len(vec_of_formula(s)), s)):
    print(f"  {f:10s} vec={known[f]} 例:{example[f]}")
