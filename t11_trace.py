# -*- coding: utf-8 -*-
"""t11_trace：在规则 1~8 + 规则 9d（大类数 + 大类原子数 聚>散>动）下，
定位残余分歧的首次并列点，并给出每个并列候选的大类原子计数，解释为何仍并列。"""
import random
import sys
from collections import Counter, deque

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
from t11_rule9d import comp_cat_counts, rule9d_extra

BASE = r"G:\AI work\deepseek\work1\alchemy"


def simulate_trace(atom_list, rng):
    n = len(atom_list)
    rem = [P.VAL[e] for e in atom_list]
    if sum(rem) % 2:
        return None, None
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

    first = None
    while True:
        comp, groups, dists = comps()
        csize = [len(g) for g in groups]
        ctypes = [set(atom_list[i] for i in g) for g in groups]
        crem = [sum(rem[i] for i in g) for g in groups]
        ccat = comp_cat_counts(groups, atom_list)
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
                extra = rule9d_extra(ccat[ci], ccat[cj])
                key = (-dt[i][j], -(rem[i] + rem[j]), fam[i][j], cross, gd,
                       min(csize[ci], csize[cj]), -max(csize[ci], csize[cj]), -ut,
                       ti + tj, min(ti, tj), max(ti, tj), -(ri + rj), -min(ri, rj), extra)
                cands.append((key, i, j, extra))
        if not cands:
            break
        best = min(t[0] for t in cands)
        tied = [(i, j, ex) for (k, i, j, ex) in cands if k == best]
        if len(tied) > 1 and first is None:
            first = {"n_tied": len(tied),
                     "tied_types": [atom_list[a] + atom_list[b] for (a, b, _e) in tied],
                     "extras": sorted(set(ex for (_a, _b, ex) in tied)),
                     "comp_sizes": [(len(groups[comp[a]]), len(groups[comp[b]])) for (a, b, _e) in tied]}
        i, j, _ex = rng.choice(tied)
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
    if any(r > 0 for r in rem):
        return None, first
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
    return tuple(sorted(out)), first


def divergence(counts, max_seeds=200):
    atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
    base_out, base_first = simulate_trace(atoms, random.Random(0))
    for seed in range(1, max_seeds):
        out, _ = simulate_trace(atoms, random.Random(seed))
        if out is not None and out != base_out:
            return {"feed": list(counts), "T": len(atoms),
                    "outcomeA": list(base_out), "outcomeB": list(out),
                    "first_tie": base_first}
    return {"feed": list(counts), "T": len(atoms), "outcomeA": list(base_out), "outcomeB": None}


if __name__ == "__main__":
    cases = [
        [1, 0, 1, 1, 0, 1, 4, 1, 0],
        [1, 0, 1, 4, 1, 0, 2, 0, 0],
        [2, 0, 0, 4, 1, 0, 1, 0, 1],
        [4, 1, 0, 1, 0, 1, 1, 0, 1],
    ]
    for c in cases:
        print(divergence(c), flush=True)
