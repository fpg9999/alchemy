# -*- coding: utf-8 -*-
"""t6_active：检验「每个组件的活跃原子数（rem>0）在反应过程中是否有常数上界」。

若存在常数 K 使任何时刻任何组件的活跃原子数 ≤ K，则结合「合并需要两端都有活跃原子」，
可以给出组件规模增长的控制（合并会消耗活跃原子）。
"""
import json
import random
import sys
from collections import deque

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def max_active_per_component(atom_list):
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

    best = 0
    best_comp_size = 0
    while True:
        comp, groups, dists = comps()
        act = [sum(1 for i in g if rem[i] > 0) for g in groups]
        if act:
            m = max(act)
            if m > best:
                best = m
                best_comp_size = max(len(g) for g in groups)
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
        best_key = min(t[0] for t in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best_key]
        i, j = tied[0]
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
    return best, best_comp_size


def main():
    rng = random.Random(808)
    cases = {
        "OXK42": [9, 10, 0, 0, 0, 0, 23, 0, 0],
        "OXK42x2": [18, 20, 0, 0, 0, 0, 46, 0, 0],
        "full97": [3, 8, 15, 10, 1, 0, 36, 22, 2],
        "full97x2": [6, 16, 30, 20, 2, 0, 72, 44, 4],
        "pure聚9": [2, 3, 4, 0, 0, 0, 0, 0, 0],
        "pure聚x8": [16, 24, 32, 0, 0, 0, 0, 0, 0],
    }
    out = {}
    for name, counts in cases.items():
        atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
        if sum(P.VAL[e] for e in atoms) % 2:
            print(name, "odd")
            continue
        r = max_active_per_component(atoms)
        out[name] = r
        print(name, "T", len(atoms), "max active per component =", r[0], "at component size", r[1], flush=True)
    # 随机投料
    worst = 0
    for T in (48, 96, 192):
        for _ in range(6):
            counts = [0] * 9
            for _ in range(T):
                counts[rng.randrange(9)] += 1
            atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
            if sum(P.VAL[e] for e in atoms) % 2:
                continue
            r = max_active_per_component(atoms)
            if r and r[0] > worst:
                worst = r[0]
    print("random feeds: worst max-active-per-component =", worst)
    out["random_worst"] = worst
    json.dump(out, open(BASE + r"\t6_active.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
