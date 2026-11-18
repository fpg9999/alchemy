# -*- coding: utf-8 -*-
"""记录 (4,3,2) 两种产物的连键路径，找出规则7真正起作用的并列点"""
import random
import sys
from collections import defaultdict, deque
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot2 as P

VAL = {"O": 3, "X": 2, "C": 1}
DIST = {("O", "O"): 0, ("X", "X"): 0, ("C", "C"): 0,
        ("O", "X"): 1, ("X", "O"): 1, ("O", "C"): 2, ("C", "O"): 2,
        ("X", "C"): 1, ("C", "X"): 1}


def simulate_log(atom_list, rng):
    n = len(atom_list)
    rem = [VAL[e] for e in atom_list]
    bond = [[0] * n for _ in range(n)]
    parent = list(range(n))
    size = [1] * n
    types = [{e} for e in atom_list]
    log = []

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
                typesum = len(types[ci]) + len(types[cj])
                key = (-DIST[(atom_list[i], atom_list[j])], -(rem[i] + rem[j]), 0,
                       cross, gd, min(si, sj), -max(si, sj), -typesum)
                cands.append((key, i, j))
        if not cands:
            break
        best = min(t[0] for t in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        if len(tied) > 1:
            log.append((len(log), [(i, atom_list[i], j, atom_list[j], rem[i], rem[j]) for (i, j) in tied]))
            i, j = rng.choice(tied)
        else:
            i, j = tied[0]
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        union(i, j)
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
    return mols, log


def atoms_of(v):
    return ["O"] * v[0] + ["X"] * v[1] + ["C"] * v[2]


v = (4, 3, 2)
rng = random.Random(0)
for trial in range(2000):
    a = atoms_of(v)
    rng.shuffle(a)
    mols, log = simulate_log(a, rng)
    s = " + ".join(sorted(P.mol_label(m) for m in mols))
    if "CCOOOOXXX" in s:
        print("找到产出 O4X3C2 的路径，trial", trial)
        print("产物:", s)
        for step, tied in log[:8]:
            print("  并列点", step, ":", tied)
        break
else:
    print("没抽到")
