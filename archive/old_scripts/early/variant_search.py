# -*- coding: utf-8 -*-
"""规则口径变体搜索：哪种口径能产出 O4X3C2（秩4晶3冰2）"""
import sys
from collections import defaultdict, deque
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot3 as P

VAL = {"O": 3, "X": 2, "C": 1}
DIST = {frozenset("OO"): 0, frozenset("XX"): 0, frozenset("CC"): 0,
        frozenset("OX"): 1, frozenset("OC"): 2, frozenset("XC"): 1}


def simulate(atom_list, r2="sum", r5="minmax", r6="union", r4="crossfirst"):
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
                if r2 == "sum":
                    k2 = (-(rem[i] + rem[j]),)
                elif r2 == "minmax":
                    k2 = (-max(rem[i], rem[j]), -min(rem[i], rem[j]))
                elif r2 == "prod":
                    k2 = (-(rem[i] * rem[j]),)
                else:
                    k2 = (0,)
                mn, mx = min(si, sj), max(si, sj)
                if r5 == "minmax":
                    k5 = (mn, -mx)
                elif r5 == "maxmin":
                    k5 = (-mx, mn)
                elif r5 == "sum":
                    k5 = (si + sj,)
                else:
                    k5 = (0,)
                if r4 == "crossfirst":
                    k4 = (cross, gd)
                elif r4 == "distfirst":
                    k4 = (gd, cross)
                else:
                    k4 = (0, 0)
                key = (-d,) + k2 + (0,) + k4 + k5 + (-t,)
                cands.append((key, i, j))
        if not cands:
            break
        best = min(t[0] for t in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        i, j = tied[0]
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


INPUTS = []
for total in range(1, 25):
    for a in range(total + 1):
        for b in range(total - a + 1):
            c = total - a - b
            if c < 0 or (a + c) % 2:
                continue
            INPUTS.append((a, b, c))

best = []
for r2 in ["sum", "minmax", "prod"]:
    for r5 in ["minmax", "maxmin", "sum", "none"]:
        for r6 in ["union", "sum"]:
            for r4 in ["crossfirst", "distfirst", "none"]:
                hits = []
                ok222 = True
                for v in INPUTS:
                    m = simulate(atoms(v), r2, r5, r6, r4)
                    if m is None:
                        continue
                    fs = [P.formula_of(x["atoms"]) for x in m]
                    if "O4X3C2" in fs and P.embed_all(m):
                        hits.append(v)
                    if v == (2, 2, 2):
                        ok222 = fs == ["OXC", "OXC"]
                if hits:
                    best.append((len(hits), r2, r5, r6, r4, hits[:6], ok222))
best.sort(reverse=True)
for row in best[:20]:
    print(row)
print("总计命中口径数:", len(best))
