# -*- coding: utf-8 -*-
"""t4p_cascade：验证"逐级饱和/活跃类型级联"引理，并输出代表性大分子的级联表。
对随机投料与已知大分子：
  (i) 每级 d 结束后活跃原子集 U_d={mu<d} 中不存在距离恰为 d 的类型对（引理3的等价形式）；
  (ii) 6 级后活跃的 3 价原子至多来自一个大类；5 级后"c* 之外"的 2 价原子全部饱和等。
"""
import random
import sys
from collections import Counter, defaultdict
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def mu_of(atoms, edges):
    n = len(atoms)
    mu = [99] * n
    for (i, j, m) in edges:
        d = P.ptable_dist(atoms[i], atoms[j])
        mu[i] = min(mu[i], d)
        mu[j] = min(mu[j], d)
    return mu


def check_mol(atoms, edges):
    mu = mu_of(atoms, edges)
    n = len(atoms)
    ok = True
    for i in range(n):
        for j in range(i + 1, n):
            d = P.ptable_dist(atoms[i], atoms[j])
            if mu[i] < d and mu[j] < d:
                ok = False
    return ok, mu


def cascade_table(atoms, edges):
    mu = mu_of(atoms, edges)
    rows = []
    for d in range(6, 0, -1):
        active = [i for i in range(len(atoms)) if mu[i] < d]
        types = sorted(set(atoms[i] for i in active))
        three_cats = sorted(set(P.CAT[t] for t in types if P.VAL[t] == 3))
        rows.append((d, len(active), types, three_cats))
    return rows


def test_random(nfeeds=400, maxn=30, seed=11):
    rng = random.Random(seed)
    bad = 0
    bad6 = 0
    for _ in range(nfeeds):
        k = rng.randint(2, 9)
        elems = rng.sample(P.ORDER, k)
        T = rng.randint(2, maxn)
        feed = [0] * k
        for _ in range(T):
            feed[rng.randrange(k)] += 1
        atoms = P.vec_to_atoms(tuple(feed), elems)
        mols = P.simulate(atoms)
        if not mols:
            continue
        # 全局条件：对整个锅的所有原子检验（跨分子也成立）
        allats, alledges = [], []
        off = 0
        for m in mols:
            allats += m["atoms"]
            alledges += [(i + off, j + off, x) for (i, j, x) in m["edges"]]
            off += len(m["atoms"])
        ok, mu = check_mol(allats, alledges)
        if not ok:
            bad += 1
        active6 = [i for i in range(len(allats)) if mu[i] < 6]
        cats3 = set(P.CAT[allats[i]] for i in active6 if P.VAL[allats[i]] == 3)
        if len(cats3) > 1:
            bad6 += 1
    print(f"随机 {nfeeds} 锅（合并全部产物做全局检验）: 引理3 违反={bad}, 6级活跃3价跨类={bad6}")


def show_big():
    cases = [
        ("O/X/K 42原子 O9X10K23", ["O", "X", "K"], (9, 10, 23)),
        ("全9元素 97原子", P.ORDER, (3, 8, 15, 10, 1, 0, 36, 22, 2)),
        ("纯聚 O2X7(9原子)", ["O", "X", "C"], (2, 4, 3)),
    ]
    for name, elems, feed in cases:
        atoms = P.vec_to_atoms(tuple(feed), elems)
        mols = P.simulate(atoms)
        if not mols:
            print(name, "fail"); continue
        big = max(mols, key=lambda m: len(m["atoms"]))
        print(f"\n{name}: n={len(big['atoms'])}")
        for d, na, types, cats3 in cascade_table(big["atoms"], big["edges"]):
            print(f"  {d} 级结束后活跃 {na:3d} 原子, 类型={''.join(types):20s} 活跃3价大类={cats3}")


if __name__ == "__main__":
    test_random()
    show_big()
