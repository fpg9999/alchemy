# -*- coding: utf-8 -*-
"""t4p_levelcomp：记录每级结束时的最大组件大小（用于支持"逐级递推闭合"证明框架）。
对多种子集/投料规模做实验，输出 (6 级后, 5 级后, ..., 0 级后) 的最大组件大小。
"""
import random
import sys
from collections import deque
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def run(elems, feed):
    atom_list = P.vec_to_atoms(tuple(feed), elems)
    n = len(atom_list)
    if n == 0:
        return None
    if sum(P.VAL[e] for e in atom_list) % 2:
        return None
    rem = [P.VAL[e] for e in atom_list]
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

    snap = {}
    cur = None
    while True:
        comp, groups, dists = comps()
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
                       ti + tj, min(ti, tj), max(ti, tj),
                       -(ri + rj), -min(ri, rj))
                cands.append((key, i, j))
        if not cands:
            break
        best = min(t[0] for t in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        i, j = tied[0]
        d = dt[i][j]
        if cur is not None and d != cur:
            snap[cur] = max(len(g) for g in groups)
        cur = d
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
    comp, groups, _ = comps()
    snap[0] = max(len(g) for g in groups)
    return snap


def main():
    rng = random.Random(2026)
    subsets = [
        P.ORDER, ["O", "X", "K"], ["O", "X"], ["O", "K"], ["X", "K"], ["O", "W"],
        ["O", "P", "K"], ["X", "W", "A"], ["C", "L", "F"], ["O", "X", "P", "W"],
        ["O", "X", "K", "A"], ["X", "C", "P", "L", "A", "F"],
    ]
    for elems in subsets:
        rows = []
        for T in (24, 48, 96):
            feed = [0] * len(elems)
            for _ in range(T):
                feed[rng.randrange(len(elems))] += 1
            s = run(elems, feed)
            if s is None:
                rows.append((T, "FAIL"))
            else:
                rows.append((T, {d: s[d] for d in range(6, -1, -1) if d in s}))
        print("".join(elems), ":", rows)


if __name__ == "__main__":
    main()
