# -*- coding: utf-8 -*-
"""pot_v4 —— 正式模拟器（规则 1~11）

在 pot_v3（规则 1~9）的 key 之后追加两条并列判定：

规则 10（同中间态骨架内优先）：
    若规则 9 仍相同，优先连接「同一中间态骨架块」内的两个原子。
    中间态骨架块 = 6 级结束时的三价诱导连通块；6 级阶段尚未形成块，本项取常数 0。
规则 11（链优先于环）：
    若规则 10 仍相同，优先和链上的原子连接而非环上的原子。
    实现：候选两端原子各自的「是否在环上」标志（incident 非桥边）之和，小者优先。

其它（规则 1~9、输出格式、几何判定）与 pot_v3 完全一致。
"""
import sys
from collections import Counter, deque

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from pot_all import VAL, ptable_dist, family_rank
from pot_v3 import rule9_extra

TRI = {"O", "P", "K"}


def ring_flags(n, adj):
    """每个原子是否在某个环上（O(V+E) 桥检测）。adj: list of dict v->mult。"""
    disc = [-1] * n
    low = [0] * n
    ring = [False] * n
    timer = [0]

    def dfs(u, parent):
        disc[u] = low[u] = timer[0]
        timer[0] += 1
        for v in adj[u]:
            if v == parent:
                continue
            if disc[v] == -1:
                dfs(v, u)
                low[u] = min(low[u], low[v])
                if low[v] <= disc[u]:
                    ring[u] = True
                    ring[v] = True
            else:
                low[u] = min(low[u], disc[v])
                ring[u] = True
                ring[v] = True

    for s in range(n):
        if disc[s] == -1:
            dfs(s, -1)
    return ring


def simulate(atom_list, return_level6=False):
    """规则 1~11 跑一锅反应。返回产物分子列表（失败返回 None）。
    return_level6=True 时返回 (mols, level6_blocks)。"""
    n = len(atom_list)
    if n == 0:
        return ([] if not return_level6 else ([], []))
    if sum(VAL[e] for e in atom_list) % 2:
        return None if not return_level6 else (None, None)
    rem = [VAL[e] for e in atom_list]
    bond = [[0] * n for _ in range(n)]
    adj = [dict() for _ in range(n)]
    dt = [[0] * n for _ in range(n)]
    fam = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            dt[i][j] = dt[j][i] = ptable_dist(atom_list[i], atom_list[j])
            fam[i][j] = fam[j][i] = family_rank(atom_list[i], atom_list[j])

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

    level6 = None
    blockid = None
    while True:
        comp, groups, dists = comps()
        if level6 is None:
            blockid = None
        csize = [len(g) for g in groups]
        ctypes = [set(atom_list[i] for i in g) for g in groups]
        crem = [sum(rem[i] for i in g) for g in groups]
        celem = [Counter(atom_list[i] for i in g) for g in groups]
        if level6 is not None and blockid is None:
            blockid = [-1] * n
            for bi, blk in enumerate(level6):
                for v in blk[2]:
                    blockid[v] = bi
        rf = ring_flags(n, adj)
        cands = []
        any6 = False
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
                # 规则 10：同中间态骨架块内优先（6 级前本项无意义，取 0）
                if level6 is None:
                    key = key + (0,)
                else:
                    key = key + (0 if blockid[i] >= 0 and blockid[i] == blockid[j] else 1,)
                # 规则 11：链优先于环
                key = key + (rf[i] + rf[j],)
                cands.append((key, i, j))
        if not cands:
            break
        if level6 is None and not any6:
            level6 = []
            for g in groups:
                if not any(atom_list[v] in TRI for v in g):
                    continue
                mem = sorted(g)
                ats = [atom_list[v] for v in mem]
                es = []
                for a in range(len(mem)):
                    for b in range(a + 1, len(mem)):
                        m = bond[mem[a]][mem[b]]
                        if m:
                            es.append((a, b, m))
                level6.append((ats, es, tuple(mem)))
        best = min(c[0] for c in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        i, j = tied[0]
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
    if any(r > 0 for r in rem):
        return (None, None) if return_level6 else None
    if level6 is None:
        level6 = []
        for g in sorted(range(0)):
            pass
        for g in comps()[1]:
            if not any(atom_list[v] in TRI for v in g):
                continue
            mem = sorted(g)
            ats = [atom_list[v] for v in mem]
            es = []
            for a in range(len(mem)):
                for b in range(a + 1, len(mem)):
                    m = bond[mem[a]][mem[b]]
                    if m:
                        es.append((a, b, m))
            level6.append((ats, es, tuple(mem)))
    comp, groups, _ = comps()
    mols = []
    for mem in groups:
        ats = [atom_list[v] for v in mem]
        es = []
        for a in range(len(mem)):
            for b in range(a + 1, len(mem)):
                m = bond[mem[a]][mem[b]]
                if m:
                    es.append((a, b, m))
        mols.append({"atoms": ats, "edges": es})
    return (mols, level6) if return_level6 else mols


if __name__ == "__main__":
    from pot_all import vec_to_atoms, ORDER, formula_of
    cases = [
        ([3, 0, 0, 0, 1, 0, 0, 2, 1], ["O2WA", "OAF"]),
        ([0, 1, 0, 0, 1, 1, 2, 0, 1], ["WKF", "XLK"]),
        ([3, 0, 0, 5, 0, 0, 2, 0, 0], ["O3P5K2"]),
    ]
    for counts, expect in cases:
        mols = simulate(vec_to_atoms(tuple(counts), ORDER))
        got = sorted(formula_of(m["atoms"]) for m in mols) if mols else None
        print(counts, "->", got, "OK" if got == sorted(expect) else "MISMATCH")
