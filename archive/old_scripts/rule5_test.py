# -*- coding: utf-8 -*-
"""规则5各种口径对照（规则6固定为并集去重）"""
import random
import sys
from collections import defaultdict, deque, Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot2 as P

VAL = {"O": 3, "X": 2, "C": 1}
DIST = {("O", "O"): 0, ("X", "X"): 0, ("C", "C"): 0,
        ("O", "X"): 1, ("X", "O"): 1, ("O", "C"): 2, ("C", "O"): 2,
        ("X", "C"): 1, ("C", "X"): 1}


def sim(atom_list, rng, r5="min-max"):
    n = len(atom_list)
    rem = [VAL[e] for e in atom_list]
    bond = [[0] * n for _ in range(n)]
    parent = list(range(n))
    size = [1] * n
    types = [{e} for e in atom_list]

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if size[ra] < size[rb]:
            ra, rb = rb, ra
        parent[rb] = ra
        size[ra] += size[rb]
        types[ra] |= types[rb]

    def bfs_dist(a, b):
        if a == b:
            return 0
        seen = {a}
        dq = deque([(a, 0)])
        while dq:
            u, d = dq.popleft()
            for v in range(n):
                if bond[u][v] and v not in seen:
                    if v == b:
                        return d + 1
                    seen.add(v)
                    dq.append((v, d + 1))
        return 10 ** 6

    while True:
        cands = []
        for i in range(n):
            if rem[i] == 0:
                continue
            for j in range(i + 1, n):
                if rem[j] == 0 or bond[i][j] >= 3:
                    continue
                ci, cj = find(i), find(j)
                cross = 0 if ci == cj else 1
                gd = bfs_dist(i, j) if cross == 0 else 10 ** 6
                si, sj = size[ci], size[cj]
                t = len(types[ci] | types[cj])
                mn, mx = min(si, sj), max(si, sj)
                if r5 == "min-max":
                    k5 = (mn, -mx)
                elif r5 == "max-min":
                    k5 = (-mx, mn)
                elif r5 == "min-min":
                    k5 = (mn, mx)
                elif r5 == "sum":
                    k5 = (si + sj,)
                elif r5 == "none":
                    k5 = (0,)
                key = (-DIST[(atom_list[i], atom_list[j])], -(rem[i] + rem[j]), 0,
                       cross, gd) + k5 + (-t,)
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
        union(i, j)
    if any(r > 0 for r in rem):
        return None
    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    mols = []
    for g in groups.values():
        edges = []
        for ii in range(len(g)):
            for jj in range(ii + 1, len(g)):
                a, b = g[ii], g[jj]
                if bond[a][b]:
                    edges.append((ii, jj, bond[a][b]))
        mols.append({"atoms": [atom_list[v] for v in g], "edges": edges})
    return mols


def atoms_of(v):
    return ["O"] * v[0] + ["X"] * v[1] + ["C"] * v[2]


def sig(mols):
    if mols is None:
        return "FAIL(剩键)"
    if not P.embed_all(mols):
        return "FAIL(摆不出来)"
    return " + ".join(sorted(P.mol_label(m) for m in mols))


CASES = [(3, 3, 5), (4, 3, 2), (6, 5, 4), (5, 5, 6), (3, 5, 4), (5, 4, 3)]
for r5 in ["min-max", "max-min", "min-min", "sum", "none"]:
    print(f"\n########## 规则5 = {r5} ##########")
    for v in CASES:
        rng = random.Random(5)
        outs = Counter()
        for _ in range(150):
            a = atoms_of(v)
            rng.shuffle(a)
            outs[sig(sim(a, rng, r5))] += 1
        tag = "唯一" if len(outs) == 1 else f"{len(outs)}种"
        print(f"  {v}: {tag}")
        if len(outs) > 1:
            for s, c in outs.most_common(4):
                print(f"      {c:3d}/150  {s}")
