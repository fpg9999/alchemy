# -*- coding: utf-8 -*-
"""(4,3,2) 的决策树：找出规则6必须区分的并列点"""
import sys
from collections import defaultdict, deque, Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot3 as P

VAL = {"O": 3, "X": 2, "C": 1}
DIST = {frozenset("OO"): 0, frozenset("XX"): 0, frozenset("CC"): 0,
        frozenset("OX"): 1, frozenset("OC"): 2, frozenset("XC"): 1}
rng = None


def state_key(atom_list, rem, bond):
    # 用规范化的分子多重图做记忆化 key（粗略：按原子类型+剩余+键的多重集）
    n = len(atom_list)
    # 连通分量
    adj = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if bond[i][j]:
                adj[i].append(j)
                adj[j].append(i)
    seen = [False] * n
    comps = []
    for s in range(n):
        if seen[s]:
            continue
        stack = [s]
        seen[s] = True
        mem = []
        while stack:
            u = stack.pop()
            mem.append(u)
            for v in adj[u]:
                if not seen[v]:
                    seen[v] = True
                    stack.append(v)
        # 分量签名：原子类型 + 剩余 + 键
        sig = []
        for u in mem:
            sig.append((atom_list[u], rem[u], tuple(sorted((v, bond[u][v]) for v in adj[u] if v > u or True))))
        # 粗略排序即可
        comps.append(tuple(sorted(sig)))
    return tuple(sorted(comps))


def solve(atom_list, rem, bond, depth=0, memo=None, log=None):
    if memo is None:
        memo = {}
    n = len(atom_list)
    rem = list(rem)
    bond = [list(r) for r in bond]
    key = state_key(atom_list, rem, bond)
    if key in memo:
        return memo[key]

    # 连通分量 & 距离
    adj = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if bond[i][j]:
                adj[i].append(j)
                adj[j].append(i)
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
            t = len(ctypes[ci] | ctypes[cj])
            d = DIST[frozenset((atom_list[i], atom_list[j]))]
            # 规则1~5（不含规则6）
            key15 = (-d, -(rem[i] + rem[j]), 0, cross, gd, min(si, sj), -max(si, sj))
            cands.append((key15, i, j, (si, sj), (tuple(sorted(ctypes[ci])), tuple(sorted(ctypes[cj]))), t))
    if not cands:
        if any(rem):
            return ("FAIL",)
        # 结果：分子公式多重集
        out = []
        for g in groups:
            cnt = Counter(atom_list[i] for i in g)
            out.append("".join(e + (str(cnt[e]) if cnt[e] > 1 else "") for e in ["O", "X", "C"] if cnt[e]))
        return tuple(sorted(out))

    best = min(c[0] for c in cands)
    tied = [c for c in cands if c[0] == best]
    results = set()
    detail = []
    for (k15, i, j, sizes, tsets, t) in tied:
        rem2 = rem[:]
        bond2 = [row[:] for row in bond]
        rem2[i] -= 1
        rem2[j] -= 1
        bond2[i][j] += 1
        bond2[j][i] += 1
        r = solve(atom_list, tuple(rem2), tuple(tuple(row) for row in bond2), depth + 1, memo)
        results.add(r)
        detail.append((i, j, atom_list[i], atom_list[j], sizes, tsets, t, r))
    if len(results) > 1:
        print(f"\n[并列点 depth={depth}] 候选 {len(tied)} 个，规则6值不同：")
        for (i, j, ei, ej, sizes, tsets, t, r) in detail:
            print(f"   连 {i}{ei}-{j}{ej} 分子大小{sizes} 类型{tsets} union={t} -> {r}")
    memo[key] = tuple(sorted(results))
    return memo[key]


atom_list = ["O"] * 4 + ["X"] * 3 + ["C"] * 2
rem = tuple(VAL[e] for e in atom_list)
bond = tuple(tuple([0] * len(atom_list)) for _ in range(len(atom_list)))
res = solve(atom_list, rem, bond)
print("\n(4,3,2) 所有可能结果:")
for r in res:
    print("  ", r)
