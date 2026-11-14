# -*- coding: utf-8 -*-
"""最终扫描（规则6=并集）+ 并列敏感性 + 可达闭包"""
import random
import sys
from collections import Counter, defaultdict
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
rng = random.Random(7)
certain = {}      # formula -> example input（并列不稳定时也出现在所有结果里）
possible = {}     # formula -> example input（只在并列分支之一出现）
amb = []
maxsize = 0
reasons = Counter()
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
            base_sig = P.signature(mols)
            outs = {base_sig: mols}
            for _ in range(3):
                aa = atoms_of(v)
                rng.shuffle(aa)
                m2 = P.simulate(aa, rng)
                if m2 is not None and P.embed_all(m2):
                    outs[P.signature(m2)] = m2
            if len(outs) > 1:
                amb.append((v, list(outs)))
            # 出现在所有结果里的公式 = certain
            common = None
            for m in outs.values():
                fs = set(P.formula_of(x["atoms"]) for x in m)
                common = fs if common is None else (common & fs)
                for f in fs:
                    possible.setdefault(f, v)
                    maxsize = max(maxsize, max(len(x["atoms"]) for x in m))
            for f in common:
                certain.setdefault(f, v)

print(f"N={N}: 失败统计={dict(reasons)}")
print(f"确定公式数={len(certain)}, 可能公式数={len(possible)}, 并列敏感输入数={len(amb)}, 最大原子数={maxsize}")
print("\n=== 并列敏感输入（前 10） ===")
for v, outs in amb[:10]:
    print(" ", v, "->", len(outs), "种结果")
    for m in outs:
        print("     ", P.signature(m))

print("\n=== 确定公式 ===")
for f in sorted(certain, key=lambda s: (len(vec_of_formula(s)), s)):
    print(f"  {f:10s} vec={vec_of_formula(f)} 例:{certain[f]}")
print("\n=== 只出现在并列分支里的公式 ===")
for f in sorted(set(possible) - set(certain), key=lambda s: (len(vec_of_formula(s)), s)):
    print(f"  {f:10s} 例:{possible[f]}")
print("\n秩4晶3冰2 (O4X3C2) 在确定集合?", "O4X3C2" in certain, " 在可能集合?", "O4X3C2" in possible)

print("\n=== 可达闭包（用确定公式作生成元，N=%d）===" % N)
known = dict(certain)
known.update({"O2": (2, 0, 0), "X2": (0, 2, 0), "C2": (0, 0, 2)})
example = dict(certain)
example.update({"O2": (2, 0, 0), "X2": (0, 2, 0), "C2": (0, 0, 2)})
for it in range(8):
    vecs = sorted(semigroup(list(known.values()), N))
    new = 0
    for v in vecs:
        mols, why = run(v)
        if mols is None:
            continue
        base_sig = P.signature(mols)
        outs = {base_sig}
        for _ in range(2):
            aa = atoms_of(v)
            rng.shuffle(aa)
            m2 = P.simulate(aa, rng)
            if m2 is not None and P.embed_all(m2):
                outs.add(P.signature(m2))
        common = None
        for s in outs:
            # 重新解析签名太麻烦，直接看公式
            pass
        for x in mols:
            f = P.formula_of(x["atoms"])
            if f not in known and len(outs) == 1:
                known[f] = vec_of_formula(f)
                example[f] = v
                new += 1
    print(f"  iter {it}: 可达向量={len(vecs)} 已知公式={len(known)} 新增={new}")
    if new == 0:
        break

print("\n=== 最终清单（%d 种） ===" % len(known))
for f in sorted(known, key=lambda s: (len(vec_of_formula(s)), s)):
    print(f"  {f:10s} vec={known[f]} 例:{example[f]}")
