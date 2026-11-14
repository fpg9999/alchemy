# -*- coding: utf-8 -*-
"""t6_randtie：在"并列时随机裁决"下重跑反应，检验组件上界是否只依赖规则 1~3 的阶梯结构
（即：是否任何并列裁决都给出有界组件）。

对比：pot_all.simulate 在并列时取 tied[0]；这里改为随机取 tied[k]。
"""
import json
import random
import sys
import time
from collections import deque

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def simulate_rand(atom_list, rng, stop_level=None):
    n = len(atom_list)
    rem = [P.VAL[e] for e in atom_list]
    if sum(rem) % 2:
        return None
    bond = [[0] * n for _ in range(n)]
    adj = [dict() for _ in range(n)]
    dt = [[0] * n for _ in range(n)]
    fam = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            dt[i][j] = dt[j][i] = P.ptable_dist(atom_list[i], atom_list[j])
            fam[i][j] = fam[j][i] = P.family_rank(atom_list[i], atom_list[j])

    def comps():
        comp = [-1] * n
        groups = []
        for s in range(n):
            if comp[s] != -1:
                continue
            cid = len(groups)
            comp[s] = cid
            st = [s]
            mem = [s]
            while st:
                u = st.pop()
                for v in adj[u]:
                    if comp[v] == -1:
                        comp[v] = cid
                        st.append(v)
                        mem.append(v)
            groups.append(mem)
        dists = []
        for mem in groups:
            d = {}
            for s in mem:
                dd = {s: 0}
                dq = deque([s])
                while dq:
                    u = dq.popleft()
                    for v in adj[u]:
                        if v not in dd:
                            dd[v] = dd[u] + 1
                            dq.append(v)
                d[s] = dd
            dists.append(d)
        return comp, groups, dists

    while True:
        comp, groups, dists = comps()
        csize = [len(g) for g in groups]
        ctypes = [set(atom_list[i] for i in g) for g in groups]
        crem = [sum(rem[i] for i in g) for g in groups]
        cands = []
        for i in range(n):
            if rem[i] == 0:
                continue
            for j in range(i + 1, n):
                if rem[j] == 0 or bond[i][j] >= 3:
                    continue
                ci, cj = comp[i], comp[j]
                cross = 0 if ci == cj else 1
                gd = dists[ci][i].get(j) if cross == 0 else 999
                ut = len(ctypes[ci] | ctypes[cj])
                ti, tj = len(ctypes[ci]), len(ctypes[cj])
                ri, rj = crem[ci], crem[cj]
                key = (-dt[i][j], -(rem[i] + rem[j]), fam[i][j], cross, gd,
                       min(csize[ci], csize[cj]), -max(csize[ci], csize[cj]), -ut,
                       ti + tj, min(ti, tj), max(ti, tj), -(ri + rj), -min(ri, rj))
                cands.append((key, i, j))
        if not cands:
            break
        best = min(t[0] for t in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        i, j = rng.choice(tied)
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
    comp, groups, _ = comps()
    sizes = sorted((len(g) for g in groups), reverse=True)
    return sizes


def rand_feed(T, rng, k=9):
    counts = [0] * 9
    for _ in range(T):
        counts[rng.randrange(k)] += 1
    return counts


def main():
    rng = random.Random(99)
    # 随机投料：随机裁决下的最大组件
    for T in (24, 48, 96, 192):
        worst = 0
        for trial in range(8):
            counts = rand_feed(T, rng)
            atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
            if sum(P.VAL[e] for e in atoms) % 2:
                continue
            sizes = simulate_rand(atoms, rng)
            if sizes:
                worst = max(worst, sizes[0])
        print(f"T={T}: random-tie 最大组件（8 次随机投料）= {worst}", flush=True)

    # 特殊配比（会出大分子的族）
    families = {
        "O/X/K 42族": [9, 10, 0, 0, 0, 0, 23, 0, 0],
        "全9元素97族": [3, 8, 15, 10, 1, 0, 36, 22, 2],
        "O/X/K/A 大族": [38, 6, 0, 7, 0, 0, 20, 9, 0],
    }
    for name, counts in families.items():
        worst = 0
        for trial in range(12):
            atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
            sizes = simulate_rand(atoms, rng)
            if sizes:
                worst = max(worst, sizes[0])
        print(f"{name}: random-tie 最大组件 = {worst}", flush=True)


if __name__ == "__main__":
    main()
