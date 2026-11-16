# -*- coding: utf-8 -*-
"""t46_inspect.py：检查规则 10+11 下 (3,5,2) 的剩余歧义来自哪一步。"""
import sys
from collections import Counter, deque

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
from pot_v3 import rule9_extra
import t39_library_verify as V
import t45_rules1011 as T

VAL = P.VAL


def inspect(counts, use10=True, use11=True, rule10_mode="A"):
    atoms = []
    for e, c in zip(("O", "P", "K"), counts):
        atoms += [e] * c
    n = len(atoms)
    rem0 = [VAL[e] for e in atoms]
    dt = [[P.ptable_dist(atoms[i], atoms[j]) if i != j else 0 for j in range(n)] for i in range(n)]
    fam = [[P.family_rank(atoms[i], atoms[j]) if i != j else 0 for j in range(n)] for i in range(n)]
    seen = set()
    reps = {}

    def comps(bond):
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
                for v in range(n):
                    if comp[v] == -1 and bond[u][v] > 0:
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
                    for v in range(n):
                        if bond[u][v] > 0 and v not in dd:
                            dd[v] = dd[u] + 1
                            dq.append(v)
                d[s] = dd
            dists.append(d)
        return comp, groups, dists

    def ring_flags(adj):
        edges = [(i, j) for i in range(n) for j in adj[i] if i < j]
        ring = [False] * n

        def conn(u, v, skip):
            ss = {u}
            dq = [u]
            while dq:
                x = dq.pop()
                for y in adj[x]:
                    if (x, y) == skip or (y, x) == skip:
                        continue
                    if y not in ss:
                        ss.add(y)
                        dq.append(y)
            return v in ss

        for (u, v) in edges:
            if conn(u, v, (u, v)):
                ring[u] = ring[v] = True
        return ring

    def dfs(bond, rem, blocks, path):
        st = (tuple((i, j, bond[i][j]) for i in range(n) for j in range(i + 1, n) if bond[i][j]),
              tuple(rem), blocks)
        if st in seen:
            return
        seen.add(st)
        comp, groups, dists = comps(bond)
        adj = [dict({v: bond[u][v] for v in range(n) if bond[u][v] > 0}) for u in range(n)]
        rf = ring_flags(adj) if use11 else [0] * n
        blockid = [-1] * n
        if blocks is not None:
            for bi, (lab, mem) in enumerate(blocks):
                for v in mem:
                    blockid[v] = bi
        cands = []
        any6 = False
        csize = [len(g) for g in groups]
        ctypes = [set(atoms[i] for i in g) for g in groups]
        crem = [sum(rem[i] for i in g) for g in groups]
        celem = [Counter(atoms[i] for i in g) for g in groups]
        for i in range(n):
            if rem[i] == 0:
                continue
            for j in range(i + 1, n):
                if rem[j] == 0 or bond[i][j] >= 3:
                    continue
                if dt[i][j] == 6:
                    any6 = True
                ci, cj = comp[i], comp[j]
                cross = 0 if ci == cj else 1
                gd = dists[ci][i].get(j) if cross == 0 else 999
                ut = len(ctypes[ci] | ctypes[cj])
                ti, tj = len(ctypes[ci]), len(ctypes[cj])
                ri, rj = crem[ci], crem[cj]
                key = (-dt[i][j], -(rem[i] + rem[j]), fam[i][j], cross, gd,
                       min(csize[ci], csize[cj]), -max(csize[ci], csize[cj]), -ut,
                       ti + tj, min(ti, tj), max(ti, tj), -(ri + rj), -min(ri, rj),
                       rule9_extra(celem[ci], celem[cj]))
                if use10:
                    if rule10_mode == "A":
                        key = key + ((0 if (blockid[i] >= 0 and blockid[i] == blockid[j]) else
                                      (1 if blocks is not None else 0)),)
                    else:
                        gi, gj = comp[i], comp[j]
                        in_i = len(groups[gi]) >= 2
                        in_j = len(groups[gj]) >= 2
                        key = key + (0 if (in_i and in_j) else (1 if (in_i or in_j) else 2),)
                if use11:
                    key = key + (rf[i] + rf[j],)
                cands.append((key, i, j))
        if not cands:
            ms = []
            for mem in groups:
                ats = [atoms[v] for v in mem]
                es = []
                for a in range(len(mem)):
                    for b in range(a + 1, len(mem)):
                        m = bond[mem[a]][mem[b]]
                        if m:
                            es.append((a, b, m))
                ms.append(P.mol_label(ats, [tuple(e) for e in es]))
            sig = tuple(sorted(ms))
            if sig not in reps:
                reps[sig] = (list(path), blocks)
            return
        nb = blocks
        if blocks is None and not any6:
            nb = []
            for g in groups:
                if not any(atoms[v] in ("O", "P", "K") for v in g):
                    continue
                mem = sorted(g)
                ats = [atoms[v] for v in mem]
                es = []
                for a in range(len(mem)):
                    for b in range(a + 1, len(mem)):
                        m = bond[mem[a]][mem[b]]
                        if m:
                            es.append((a, b, m))
                nb.append((V.block_label(ats, es), tuple(mem)))
            nb = tuple(sorted(nb))
        best = min(c[0] for c in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        for (i, j) in tied:
            bond[i][j] += 1
            bond[j][i] += 1
            rem[i] -= 1
            rem[j] -= 1
            path.append(((i, j), len(tied)))
            dfs(bond, rem, nb, path)
            path.pop()
            bond[i][j] -= 1
            bond[j][i] -= 1
            rem[i] += 1
            rem[j] += 1

    dfs([[0] * n for _ in range(n)], list(rem0), None, [])
    return reps, len(seen)


if __name__ == "__main__":
    for label, u10, u11, mode in [("1-9", False, False, "A"),
                                  ("+11", False, True, "A"),
                                  ("+10+11(A)", True, True, "A"),
                                  ("+10+11(B)", True, True, "B")]:
        reps, nstates = inspect((3, 5, 2), u10, u11, mode)
        print("=" * 90)
        print(label, "states", nstates, "distinct final:", len(reps))
        for sig, (path, blocks) in reps.items():
            print("  final:", sig)
            print("  blocks:", [lab for (lab, mem) in blocks])
            print("  ties:", [p for p in path if p[1] > 1])
