# -*- coding: utf-8 -*-
"""t9_rule9b_rand：在“规则 1~8 + 用户规则 9（大类数）”下，用随机并列重跑，
检验产物分子式多重集是否唯一（残余并列不影响结果）。"""
import random
import sys
from collections import deque

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def simulate_rule9b(atom_list, rng):
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
        cats = []
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
            cats.append(set(P.CAT[atom_list[i]] for i in mem))
        return comp, groups, dists, cats

    while True:
        comp, groups, dists, cats = comps()
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
                       ti + tj, min(ti, tj), max(ti, tj), -(ri + rj), -min(ri, rj),
                       -len(cats[ci] | cats[cj]))
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
    if any(r > 0 for r in rem):
        return None
    seen = [-1] * n
    out = []
    for s in range(n):
        if seen[s] != -1:
            continue
        cid = len(out)
        seen[s] = cid
        st = [s]
        mem = [s]
        while st:
            u = st.pop()
            for v in adj[u]:
                if seen[v] == -1:
                    seen[v] = cid
                    st.append(v)
                    mem.append(v)
        out.append(P.formula_of([atom_list[i] for i in mem]))
    return tuple(sorted(out))


def test(counts, runs=12):
    atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
    if sum(P.VAL[e] for e in atoms) % 2:
        return ("odd", None)
    rng = random.Random(0)
    outs = set()
    for _ in range(runs):
        r = simulate_rule9b(atoms, rng)
        if r is None:
            return ("fail", None)
        outs.add(r)
    return (len(outs), list(outs)[:4])


if __name__ == "__main__":
    cases = {
        "O3FA2W": [3, 0, 0, 0, 1, 0, 0, 2, 1],
        "T29": [8, 0, 7, 0, 2, 0, 4, 3, 5],
        "T33": [0, 10, 0, 0, 9, 0, 6, 0, 8],
        "T6_XWLK2F": [0, 1, 0, 0, 1, 1, 2, 0, 1],
        "T6_OWLAF": [2, 0, 0, 0, 1, 1, 0, 1, 1],
    }
    for name, c in cases.items():
        print(name, test(c), flush=True)
