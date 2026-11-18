# -*- coding: utf-8 -*-
"""t4p_mu：检验由"逐级饱和"导出的必要条件 (C)：
对分子中任意两原子 i,j，令 d=dt(i,j)，mu(i)=该原子所有键中距离的最小值；
必须 max(mu(i),mu(j)) >= d。
并在 O/X/K 的 204 个物质上验证，同时统计 mu 分布 / 分级结构。
"""
import json
import sys
from collections import Counter, defaultdict
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def check_C(atoms, edges):
    n = len(atoms)
    mu = [None] * n
    for (i, j, m) in edges:
        d = P.ptable_dist(atoms[i], atoms[j])
        mu[i] = d if mu[i] is None else min(mu[i], d)
        mu[j] = d if mu[j] is None else min(mu[j], d)
    assert all(x is not None for x in mu)
    viol = []
    for i in range(n):
        for j in range(i + 1, n):
            d = P.ptable_dist(atoms[i], atoms[j])
            if max(mu[i], mu[j]) < d:
                viol.append((i, j, atoms[i], atoms[j], d, mu[i], mu[j]))
    return mu, viol


def profile(atoms, edges):
    dh = Counter()
    for (i, j, m) in edges:
        dh[P.ptable_dist(atoms[i], atoms[j])] += m
    return tuple(sorted(dh.items(), reverse=True))


def main():
    data = json.load(open(BASE + r"\t4_enum_O_X_K.json", encoding="utf-8"))
    subs = data["substances"]
    bad = 0
    profcnt = Counter()
    rows = []
    for s in subs:
        atoms, edges = s["atoms"], s["edges"]
        mu, viol = check_C(atoms, edges)
        if viol:
            bad += 1
            print("VIOL", s["formula"], viol[:3])
        pr = profile(atoms, edges)
        profcnt[pr] += 1
        rows.append((len(atoms), s["formula"], pr, sorted(Counter(mu).items())))
    print(f"\n204 物质中违反 (C) 的：{bad}")
    print("\n所有分级结构(dt:键数) 分布（按 n 降序前 15）:")
    rows.sort(reverse=True)
    for n, f, pr, mu in rows[:15]:
        print(f"  n={n:2d} {f:14s} profile={pr} mu分布={mu}")
    print("\nprofile 频次:")
    for pr, c in profcnt.most_common():
        print(f"  {pr}: {c}")
    # 按 n 看 profile 的最大值
    best = {}
    for n, f, pr, mu in rows:
        best.setdefault(pr, []).append(n)
    print("\n每个 profile 的最大 n:")
    for pr, ns in sorted(best.items(), key=lambda t: -max(t[1])):
        print(f"  {pr}: max n={max(ns)} count={len(ns)}")


if __name__ == "__main__":
    main()
