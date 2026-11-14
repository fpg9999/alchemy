# -*- coding: utf-8 -*-
"""t6_priority_only：检验「只保留规则 1~3（距离、剩余和、族序），其余并列随机」时组件是否有界。

若在只保留 1~3 + 任意/随机并列的意义下组件仍有界，则有限性证明可大幅简化
（只需分析 (距离, 剩余和) 的阶梯结构，而不必精确刻画规则 4~8 的并列裁决）。
"""
import json
import random
import sys
from collections import Counter, deque

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def simulate_priority(atom_list, rng, only123=True):
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
                if only123:
                    key = (-dt[i][j], -(rem[i] + rem[j]), fam[i][j])
                else:
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
    return sorted((len(g) for g in groups), reverse=True)


def rand_feed(T, rng):
    counts = [0] * 9
    for _ in range(T):
        counts[rng.randrange(9)] += 1
    return counts


def main():
    rng = random.Random(4242)
    print("== 只保留规则 1~3 + 随机并列：随机投料 ==", flush=True)
    for T in (24, 48, 96, 192, 288):
        worst = 0
        for trial in range(10):
            counts = rand_feed(T, rng)
            atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
            if sum(P.VAL[e] for e in atoms) % 2:
                continue
            sizes = simulate_priority(atoms, rng)
            if sizes:
                worst = max(worst, sizes[0])
        print(f"T={T}: max component = {worst}", flush=True)

    print("== 只保留规则 1~3 + 随机并列：特殊/放大配比 ==", flush=True)
    families = {
        "O/X/K 42": [9, 10, 0, 0, 0, 0, 23, 0, 0],
        "O/X/K x2": [18, 20, 0, 0, 0, 0, 46, 0, 0],
        "O/X/K x4": [36, 40, 0, 0, 0, 0, 92, 0, 0],
        "全9 97": [3, 8, 15, 10, 1, 0, 36, 22, 2],
        "全9 97x2": [6, 16, 30, 20, 2, 0, 72, 44, 4],
        "纯聚 9": [2, 3, 4, 0, 0, 0, 0, 0, 0],
        "纯聚 x8": [16, 24, 32, 0, 0, 0, 0, 0, 0],
    }
    for name, counts in families.items():
        worst = 0
        for trial in range(15):
            atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
            if sum(P.VAL[e] for e in atoms) % 2:
                continue
            sizes = simulate_priority(atoms, rng)
            if sizes:
                worst = max(worst, sizes[0])
        print(f"{name}: max component = {worst}", flush=True)


if __name__ == "__main__":
    main()
