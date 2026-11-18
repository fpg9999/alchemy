# -*- coding: utf-8 -*-
"""pot2：带诊断/可开关规则的模拟器"""
import itertools
from collections import defaultdict, deque

VAL = {"O": 3, "X": 2, "C": 1}
DIST = {("O", "O"): 0, ("X", "X"): 0, ("C", "C"): 0,
        ("O", "X"): 1, ("X", "O"): 1,
        ("O", "C"): 2, ("C", "O"): 2,
        ("X", "C"): 1, ("C", "X"): 1}
RANK = {"F": 0, "A": 1, "K": 2, "L": 3, "W": 4, "P": 5, "C": 6, "X": 7, "O": 8, "E": 9}
HEX_NBRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]


def formula_of(atoms):
    cnt = defaultdict(int)
    for e in atoms:
        cnt[e] += 1
    out = ""
    for e in ["O", "X", "C"]:
        if cnt[e]:
            out += e + (str(cnt[e]) if cnt[e] > 1 else "")
    return out


def embeddable(atoms, edges):
    """判定简单图能否作为六边形格子邻接图的子图摆出来（非边相邻允许）。
    修正：按 BFS 顺序放置（保证每个新原子都有已放置的邻居）。"""
    n = len(atoms)
    if n == 1:
        return True
    adj = [[] for _ in range(n)]
    for (i, j, _m) in edges:
        adj[i].append(j)
        adj[j].append(i)
    # 连通性 + BFS 顺序（从度数最大的点出发）
    start = max(range(n), key=lambda i: len(adj[i]))
    order = [start]
    seen = {start}
    qi = 0
    while qi < len(order):
        u = order[qi]
        qi += 1
        for v in sorted(adj[u], key=lambda t: -len(adj[t])):
            if v not in seen:
                seen.add(v)
                order.append(v)
    if len(order) != n:
        return False
    placed = {}
    cells = set()

    def dfs(k):
        if k == n:
            return True
        v = order[k]
        if k == 0:
            cands = [(0, 0)]
        else:
            base = None
            for u in adj[v]:
                if u in placed:
                    cx, cy = placed[u]
                    s = {(cx + dx, cy + dy) for dx, dy in HEX_NBRS}
                    base = s if base is None else (base & s)
            if not base:
                return False
            cands = [p for p in base if p not in cells]
            # 对称性剪枝：第二个原子只放在 3 个方向
            if k == 1:
                cands = [p for p in cands if p in ((1, 0), (0, 1), (1, -1))]
        for p in cands:
            ok = True
            for u in adj[v]:
                if u in placed:
                    ux, uy = placed[u]
                    if (p[0] - ux, p[1] - uy) not in HEX_NBRS:
                        ok = False
                        break
            if not ok:
                continue
            placed[v] = p
            cells.add(p)
            if dfs(k + 1):
                return True
            del placed[v]
            cells.discard(p)
        return False

    return dfs(0)


def simulate(atom_list, opts=None, diag=None):
    opts = opts or {}
    use_c5 = opts.get("c5", True)
    use_c6 = opts.get("c6", True)
    use_c7 = opts.get("c7", True)
    n = len(atom_list)
    if n == 0:
        return []
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
                typesum = len(types[ci] | types[cj])
                ri, rj = RANK[atom_list[i]], RANK[atom_list[j]]
                coarse = (-DIST[(atom_list[i], atom_list[j])],
                          -(rem[i] + rem[j]),
                          0 if False else 0,
                          cross,
                          gd)
                c5 = (min(si, sj), -max(si, sj)) if use_c5 else (0, 0)
                c6 = (-typesum,)
                c7 = (min(ri, rj), max(ri, rj)) if use_c7 else (0, 0)
                key = coarse + c5 + c6 + c7 + (i, j)
                # 诊断：只看 coarse（1~4 条）是否就有多个候选
                cands.append((key, coarse, i, j))
        if not cands:
            break
        cands.sort(key=lambda t: t[0])
        best_coarse = cands[0][1]
        same_coarse = [t for t in cands if t[1] == best_coarse]
        if diag is not None and len(same_coarse) > 1:
            # 看是否 C5~C7 都区分不了、只能靠下标
            k0 = cands[0][0][:-2]
            same_all = [t for t in cands if t[0][:-2] == k0]
            if len(same_all) > 1:
                diag["index_tie"] = diag.get("index_tie", 0) + 1
        key, coarse, i, j = cands[0]
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


def embed_all(mols):
    return all(embeddable(m["atoms"], m["edges"]) for m in mols)


def mol_label(m):
    atoms = m["atoms"]
    n = len(atoms)
    mat = [[0] * n for _ in range(n)]
    for (i, j, k) in m["edges"]:
        mat[i][j] = mat[j][i] = k
    groups = defaultdict(list)
    for i, e in enumerate(atoms):
        groups[e].append(i)
    keys = sorted(groups)
    perms = [list(itertools.permutations(groups[k])) for k in keys]
    best = None
    for combo in itertools.product(*perms):
        p = []
        for part in combo:
            p.extend(part)
        s = "".join(atoms[i] for i in p) + "|"
        for a in range(n):
            for b in range(a + 1, n):
                s += str(mat[p[a]][p[b]])
        if best is None or s < best:
            best = s
    return best


def signature(mols):
    if mols is None:
        return "FAIL"
    return " + ".join(sorted(mol_label(m) for m in mols))
