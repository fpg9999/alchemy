# -*- coding: utf-8 -*-
"""t9_trace：在“规则 1~8 + 大类数规则 9”下，定位残余分歧的首次分歧步与并列候选的大类数。"""
import random
import sys
from collections import deque

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def simulate_trace(atom_list, rng):
    n = len(atom_list)
    rem = [P.VAL[e] for e in atom_list]
    if sum(rem) % 2:
        return None, []
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

    trace = []
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
                cands.append((key, i, j, len(cats[ci] | cats[cj]), frozenset(cats[ci] | cats[cj])))
        if not cands:
            break
        best = min(t[0] for t in cands)
        tied = [(i, j, cu, cu_set) for (k, i, j, cu, cu_set) in cands if k == best]
        i, j, cu, cu_set = rng.choice(tied)
        trace.append({"chosen": (i, j), "n_tied": len(tied),
                      "tied": [(atom_list[a] + atom_list[b], a, b, c)
                               for (a, b, c, _s) in tied],
                      "cat_union": cu})
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
    if any(r > 0 for r in rem):
        return None, trace
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
    return tuple(sorted(out)), trace


def first_divergence(counts, max_seeds=300):
    atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
    base_out, base_tr = simulate_trace(atoms, random.Random(0))
    for seed in range(1, max_seeds):
        out, tr = simulate_trace(atoms, random.Random(seed))
        if out is None or out == base_out:
            continue
        for k in range(min(len(base_tr), len(tr))):
            if base_tr[k]["chosen"] != tr[k]["chosen"]:
                return {"feed": list(counts), "T": len(atoms),
                        "outcomeA": list(base_out), "outcomeB": list(out),
                        "divergence_step": k,
                        "tied": base_tr[k]["tied"],
                        "n_tied": base_tr[k]["n_tied"],
                        "cat_union_counts": base_tr[k]["cat_union"]}
    return {"feed": list(counts), "T": len(atoms), "outcomeA": list(base_out),
            "outcomeB": None, "divergence_step": None}


if __name__ == "__main__":
    cases = [
        [0, 0, 1, 0, 0, 1, 0, 3, 2],   # T=7 C1 L1 A3 F2
        [0, 0, 0, 0, 1, 1, 5, 1, 0],   # T=8 W1 L1 K5 A1
        [0, 0, 1, 0, 0, 1, 3, 2, 1],   # T=8 C1 L1 K3 A2 F1
        [8, 0, 7, 0, 2, 0, 4, 3, 5],   # T=29
        [0, 10, 0, 0, 9, 0, 6, 0, 8],  # T=33
    ]
    for c in cases:
        print(first_divergence(c), flush=True)
