# -*- coding: utf-8 -*-
"""尝试"按轮匹配"模型：每轮每个原子最多连 1 根新键，一轮内按优先级配匹配方案"""
import sys
from collections import defaultdict, deque
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot3 as P

VAL = {"O": 3, "X": 2, "C": 1}
DIST = {frozenset("OO"): 0, frozenset("XX"): 0, frozenset("CC"): 0,
        frozenset("OX"): 1, frozenset("OC"): 2, frozenset("XC"): 1}


def sim_rounds(atom_list, r2="sum", r5="minmax", r6="union"):
    n = len(atom_list)
    rem = [VAL[e] for e in atom_list]
    bond = [[0] * n for _ in range(n)]
    adj = [dict() for _ in range(n)]

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
        cands = []
        for i in range(n):
            if rem[i] == 0:
                continue
            for j in range(i + 1, n):
                if rem[j] == 0 or bond[i][j] >= 3:
                    continue
                ci, cj = comp[i], comp[j]
                cross = 0 if ci == cj else 1
                gd = dists[ci][i][j] if cross == 0 else 10 ** 6
                si, sj = csize[ci], csize[cj]
                t = len(ctypes[ci] | ctypes[cj]) if r6 == "union" else (len(ctypes[ci]) + len(ctypes[cj]))
                d = DIST[frozenset((atom_list[i], atom_list[j]))]
                k2 = (-(rem[i] + rem[j]),) if r2 == "sum" else (-max(rem[i], rem[j]), -min(rem[i], rem[j]))
                mn, mx = min(si, sj), max(si, sj)
                k5 = (mn, -mx) if r5 == "minmax" else ((-mx, mn) if r5 == "maxmin" else (si + sj,))
                key = (-d,) + k2 + (0, cross, gd) + k5 + (-t,)
                cands.append((key, i, j))
        if not cands:
            break
        cands.sort()
        used = set()
        chosen = []
        for (k, i, j) in cands:
            if i in used or j in used:
                continue
            used.add(i)
            used.add(j)
            chosen.append((i, j))
        if not chosen:
            break
        for (i, j) in chosen:
            bond[i][j] += 1
            bond[j][i] += 1
            rem[i] -= 1
            rem[j] -= 1
            adj[i][j] = adj[i].get(j, 0) + 1
            adj[j][i] = adj[j].get(i, 0) + 1
    if any(r > 0 for r in rem):
        return None
    comp, groups, _ = comps()
    mols = []
    for mem in groups:
        edges = []
        for a in range(len(mem)):
            for b in range(a + 1, len(mem)):
                m = bond[mem[a]][mem[b]]
                if m:
                    edges.append((a, b, m))
        mols.append({"atoms": [atom_list[v] for v in mem], "edges": edges})
    return mols


def atoms(v):
    return ["O"] * v[0] + ["X"] * v[1] + ["C"] * v[2]


for r2 in ["sum", "minmax"]:
    for r5 in ["minmax", "maxmin", "sum"]:
        for r6 in ["union", "sum"]:
            hits = 0
            m432 = None
            m222 = None
            m240 = None
            for v in [(4, 3, 2), (2, 2, 2), (2, 4, 0)]:
                m = sim_rounds(atoms(v), r2, r5, r6)
                fs = None if m is None else [P.formula_of(x["atoms"]) for x in m]
                if v == (4, 3, 2):
                    m432 = fs
                if v == (2, 2, 2):
                    m222 = fs
                if v == (2, 4, 0):
                    m240 = fs
            good = (m222 == ["OXC", "OXC"])
            hit = (m432 == ["O4X3C2"])
            print(f"r2={r2} r5={r5} r6={r6}: (2,2,2)={m222} {'OK' if good else 'XX'} | (4,3,2)={m432} {'HIT' if hit else ''} | (2,4,0)={m240}")
