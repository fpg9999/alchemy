# -*- coding: utf-8 -*-
"""t4p_lemma_check：验证两个关键结构引理：
(L-mu) 若分子可由大锅产出，则所有 mu=0 的原子必为同一元素类型（mu=原子所有键中最小周期表距离）。
(L-cluster) 同类键(dt=0)子图的连通块有多大（经验上界）。
在 t4_enum_O_X_K 的 204 个物质 + substances_all 的 33091 个物质 + 随机投料直接模拟上检验。
"""
import json
import random
import sys
from collections import Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def mu_info(atoms, edges):
    n = len(atoms)
    mu = [None] * n
    for (i, j, m) in edges:
        d = P.ptable_dist(atoms[i], atoms[j])
        mu[i] = d if mu[i] is None else min(mu[i], d)
        mu[j] = d if mu[j] is None else min(mu[j], d)
    return mu


def check_lemmas(atoms, edges, verbose=False):
    """返回 (violC, n_zero_types, cluster_sizes)"""
    n = len(atoms)
    mu = mu_info(atoms, edges)
    viol = []
    for i in range(n):
        for j in range(i+1, n):
            d = P.ptable_dist(atoms[i], atoms[j])
            if max(mu[i], mu[j]) < d:
                viol.append((atoms[i], atoms[j], d, mu[i], mu[j]))
    zeros = [i for i in range(n) if mu[i] == 0]
    ztypes = set(atoms[i] for i in zeros)
    # dt=0 子图连通块（即同类键连通块）
    adj0 = [set() for _ in range(n)]
    for (i, j, m) in edges:
        if P.ptable_dist(atoms[i], atoms[j]) == 0:
            adj0[i].add(j)
            adj0[j].add(i)
    seen = [False]*n
    clusters = []
    for s in zeros:
        if seen[s]:
            continue
        st=[s]; seen[s]=True; comp=[]
        while st:
            u=st.pop(); comp.append(u)
            for v in adj0[u]:
                if not seen[v]:
                    seen[v]=True; st.append(v)
        clusters.append(comp)
    return viol, ztypes, clusters


def test_sim_random(nfeeds=300, maxn=26, seed=7):
    rng = random.Random(seed)
    bad = 0
    badclu = 0
    maxcluster = 0
    maxB = 0
    for _ in range(nfeeds):
        k = rng.randint(2, 6)
        elems = rng.sample(P.ORDER, k)
        T = rng.randint(2, maxn)
        feed = [0]*k
        for _ in range(T):
            feed[rng.randrange(k)] += 1
        atoms = P.vec_to_atoms(tuple(feed), elems)
        mols = P.simulate(atoms)
        if not mols:
            continue
        for m in mols:
            viol, ztypes, clusters = check_lemmas(m["atoms"], m["edges"])
            if viol:
                bad += 1
                print("  C-VIOL", P.formula_of(m["atoms"]), viol[:2], dict(zip(elems,feed)))
            if len(ztypes) > 1:
                badclu += 1
                print("  MULTI-ZERO-TYPE", P.formula_of(m["atoms"]), ztypes, dict(zip(elems,feed)))
            for c in clusters:
                maxcluster = max(maxcluster, len(c))
            nB = sum(len(c) for c in clusters)
            maxB = max(maxB, nB)
    print(f"随机 {nfeeds} 锅: C 违反={bad}, 多类型 mu=0={badclu}, 最大同类键块={maxcluster}, 单分子最大 mu=0 原子数={maxB}")


def test_catalog_oxk():
    data = json.load(open(BASE + r"\t4_enum_O_X_K.json", encoding="utf-8"))
    maxcluster = 0
    maxB = 0
    bad = 0
    badz = 0
    for s in data["substances"]:
        viol, ztypes, clusters = check_lemmas(s["atoms"], s["edges"])
        if viol: bad += 1
        if len(ztypes) > 1: badz += 1
        maxcluster = max(maxcluster, max((len(c) for c in clusters), default=0))
        maxB = max(maxB, sum(len(c) for c in clusters))
    print(f"O/X/K 204 物质: C违反={bad}, 多类型mu=0={badz}, 最大同类键块={maxcluster}, 最大mu=0原子数={maxB}")


def test_catalog_all(limit=None):
    d = json.load(open(BASE + r"\substances_all.json", encoding="utf-8"))
    if limit:
        d = d[:limit]
    maxcluster = 0
    maxB = 0
    bad = 0
    badz = 0
    import time
    t0 = time.time()
    for idx, s in enumerate(d):
        atoms, edges = s["atoms"], s["edges"]
        viol, ztypes, clusters = check_lemmas(atoms, edges)
        if viol:
            bad += 1
            if bad <= 5:
                print("  C-VIOL", s["formula"], viol[:2])
        if len(ztypes) > 1:
            badz += 1
            if badz <= 5:
                print("  MULTI-ZERO-TYPE", s["formula"], ztypes, "feed", s["feed"])
        maxcluster = max(maxcluster, max((len(c) for c in clusters), default=0))
        maxB = max(maxB, sum(len(c) for c in clusters))
        if idx % 5000 == 4999:
            print(f"  ...{idx+1}/{len(d)} 用时 {time.time()-t0:.0f}s")
    print(f"substances_all({len(d)}): C违反={bad}, 多类型mu=0={badz}, 最大同类键块={maxcluster}, 最大mu=0原子数={maxB}")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "sim"):
        test_sim_random()
    if which in ("all", "oxk"):
        test_catalog_oxk()
    if which in ("all", "cat"):
        test_catalog_all()
