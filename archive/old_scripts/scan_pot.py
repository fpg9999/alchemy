# -*- coding: utf-8 -*-
"""枚举 + 确定性问题检测 + 失败原因"""
import itertools
import random
import sys
from collections import defaultdict, Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot
from pot import simulate, result_formulas, result_signature, formula_of, embeddable


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


def reason_of(v):
    """返回 (结果分子列表 or None, 原因)"""
    mols = simulate(atoms_of(v))
    if mols is None:
        # 判断是剩键还是摆放失败：重跑但不做几何检查
        mols2 = simulate_no_geo(atoms_of(v))
        if mols2 is None:
            return None, "剩键"
        return None, "摆不出来"
    return mols, "ok"


def simulate_no_geo(atom_list):
    old = embeddable
    try:
        pot.embeddable = lambda a, e: True
        return pot.simulate(atom_list)
    finally:
        pot.embeddable = old


def determinism_check(v, trials=6):
    base = result_signature(simulate(atoms_of(v)))
    bad = []
    for _ in range(trials):
        a = atoms_of(v)
        random.shuffle(a)
        s = result_signature(pot.simulate(a))
        if s != base:
            bad.append(s)
    return base, bad


def main():
    print("=== 1. 确定性与手算核对 ===")
    tests = [(2, 2, 0), (2, 0, 2), (2, 2, 2), (1, 1, 1), (2, 4, 2), (4, 4, 4), (2, 4, 0), (2, 2, 4)]
    for v in tests:
        base, bad = determinism_check(v)
        print(f"  {v}: {base}" + ("   !!! 不确定: " + str(bad) if bad else ""))

    print("\n=== 2. 大规模扫描所有 (a,b,c)<=9 出现的公式 ===")
    formulas = {}
    reasons = Counter()
    bigmol = []
    for a in range(10):
        for b in range(10):
            for c in range(10):
                if a + b + c == 0:
                    continue
                if (a + c) % 2:
                    continue
                v = (a, b, c)
                mols = simulate(atoms_of(v))
                if mols is None:
                    r = reason_of(v)[1]
                    reasons[r] += 1
                    continue
                reasons["ok"] += 1
                for m in mols:
                    f = formula_of(m["atoms"])
                    formulas.setdefault(f, v)
                    if len(m["atoms"]) >= 5:
                        bigmol.append((v, sorted(formula_of(mm["atoms"]) for mm in mols)))
    for f in sorted(formulas, key=lambda s: (len(vec_of_formula(s)), s)):
        print(f"  {f:8s} vec={vec_of_formula(f)}  最小例子输入={formulas[f]}")
    print("  失败原因统计:", dict(reasons))
    print(f"  产物里出现 >=5 原子的输入数: {len(bigmol)}")
    for v, fs in bigmol[:10]:
        print("    ", v, fs)

    print("\n=== 3. 大数字抽样（总原子 20~40，含极端比例） ===")
    random.seed(1)
    found = set(formulas)
    for _ in range(300):
        a = random.randint(0, 14)
        b = random.randint(0, 14)
        c = random.randint(0, 14)
        if (a + c) % 2 or a + b + c == 0:
            continue
        mols = simulate(atoms_of((a, b, c)))
        if mols is None:
            continue
        for m in mols:
            f = formula_of(m["atoms"])
            if f not in found:
                print("   新公式!", (a, b, c), "->", f)
                found.add(f)
    print("   抽样后公式总数:", len(found), sorted(found, key=lambda s: (len(vec_of_formula(s)), s)))


if __name__ == "__main__":
    main()
