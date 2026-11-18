# -*- coding: utf-8 -*-
"""更快的模拟器（优化版，规则6=并集）"""
from collections import defaultdict, deque

VAL = {"O": 3, "X": 2, "C": 1}
DIST = {(frozenset("OO")): 0, (frozenset("XX")): 0, (frozenset("CC")): 0,
        frozenset("OX"): 1, frozenset("OC"): 2, frozenset("XC"): 1}
HEX_NBRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]


def formula_of(atoms):
    cnt = defaultdict(int)
    for e in atoms:
        cnt[e] += 1
    return "".join(e + (str(cnt[e]) if cnt[e] > 1 else "") for e in ["O", "X", "C"] if cnt[e])


def embeddable(atoms, edges):
    n = len(atoms)
    if n == 1:
        return True
    adj = [[] for _ in range(n)]
    for (i, j, _m) in edges:
        adj[i].append(j)
        adj[j].append(i)
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
            if k == 1:
                cands = [p for p in cands if p in ((1, 0), (0, 1), (1, -1))]
        for p in cands:
            placed[v] = p
            cells.add(p)
            if dfs(k + 1):
                return True
            del placed[v]
            cells.discard(p)
        return False

    return dfs(0)


def embed_all(mols):
    return all(embeddable(m["atoms"], m["edges"]) for m in mols)


def simulate(atom_list, rng=None):
    """rng 不为 None 时，在规则1~6并列的候选里随机选（探测规则7）。"""
    n = len(atom_list)
    if n == 0:
        return []
    rem = [VAL[e] for e in atom_list]
    bond = [[0] * n for _ in range(n)]
    # 邻接（多重）
    adj = [dict() for _ in range(n)]

    def comps_and_dists():
        comp = [-1] * n
        comps = []
        for s in range(n):
            if comp[s] != -1:
                continue
            cid = len(comps)
            comp[s] = cid
            stack = [s]
            members = [s]
            while stack:
                u = stack.pop()
                for v in adj[u]:
                    if comp[v] == -1:
                        comp[v] = cid
                        stack.append(v)
                        members.append(v)
            comps.append(members)
        # 每个分量的距离
        dists = []
        for members in comps:
            ms = set(members)
            d = {}
            for s in members:
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
        return comp, comps, dists

    while True:
        comp, comps, dists = comps_and_dists()
        csize = [len(m) for m in comps]
        ctypes = [set(atom_list[i] for i in m) for m in comps]
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
                t = len(ctypes[ci] | ctypes[cj])
                d = DIST[frozenset((atom_list[i], atom_list[j]))]
                key = (-d, -(rem[i] + rem[j]), 0, cross, gd,
                       min(si, sj), -max(si, sj), -t)
                cands.append((key, i, j))
        if not cands:
            break
        best = min(t[0] for t in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        i, j = rng.choice(tied) if rng is not None else tied[0]
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
    if any(r > 0 for r in rem):
        return None
    # 分量
    comp, comps, _ = comps_and_dists()
    mols = []
    for members in comps:
        idx = {v: k for k, v in enumerate(members)}
        atoms = [atom_list[v] for v in members]
        edges = []
        for a in range(len(members)):
            for b in range(a + 1, len(members)):
                m = bond[members[a]][members[b]]
                if m:
                    edges.append((a, b, m))
        mols.append({"atoms": atoms, "edges": edges})
    return mols


def mol_label(m):
    import itertools
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
