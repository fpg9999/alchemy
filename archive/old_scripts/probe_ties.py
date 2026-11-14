# -*- coding: utf-8 -*-
"""在规则1~6并列的候选里随机选，探测"规则7"到底会不会影响产物"""
import itertools
import random
import sys
from collections import defaultdict, deque, Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot2 as P

VAL = {"O": 3, "X": 2, "C": 1}
DIST = {("O", "O"): 0, ("X", "X"): 0, ("C", "C"): 0,
        ("O", "X"): 1, ("X", "O"): 1, ("O", "C"): 2, ("C", "O"): 2,
        ("X", "C"): 1, ("C", "X"): 1}
HEX_NBRS = P.HEX_NBRS


def simulate_rng(atom_list, rng):
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
                typesum = len(types[ci]) + len(types[cj])
                key = (-DIST[(atom_list[i], atom_list[j])], -(rem[i] + rem[j]), 0,
                       cross, gd, min(si, sj), -max(si, sj), -typesum)
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


def probe(v, trials=400, seed=1):
    rng = random.Random(seed)
    at = atoms_of(v)
    outs = Counter()
    for _ in range(trials):
        a = at[:]
        rng.shuffle(a)
        outs[sig(simulate_rng(a, rng))] += 1
    print(f"\n=== 投料 {v} ===")
    for s, c in outs.most_common():
        print(f"  {c:4d}x  {s}")


if __name__ == "__main__":
    for v in [(2, 2, 2), (2, 4, 0), (4, 3, 2), (4, 4, 4), (3, 3, 5), (2, 2, 0), (4, 2, 0)]:
        probe(v, trials=300)
