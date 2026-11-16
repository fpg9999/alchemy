# -*- coding: utf-8 -*-
"""fast_pot.py —— 与 pot_v4 规则 1~11 等价的加速版贪心成键引擎（T59 用）

目的：T58 暴露出 >16 原子、9 元素完全反应的 F 成本过高。本文件用
**增量并查集 + 分层字典序筛选** 重写 pot_v4.simulate 的贪心循环：

* 组件/组件统计用并查集增量维护（键只会让组件合并，不会分裂）；
* 候选对按 key 的层级逐层筛选（dt 最大 → rem 和最大 → family → cross → gd →
  组件大小/种类/剩余价 → 规则 9 → 规则 10 → 规则 11），
  只在仍有并列时才计算代价高的项（gd 最短路、规则 9 元素计数、规则 11 环标记）；
* 返回结果（分子原子/边、层级块）与 pot_v4 完全一致（用审计脚本逐条验证）。

对外接口：
    simulate(atom_list)          -> list[{"atoms","edges"}] 或 None
    simulate_with_base(atom_list, base_edges) -> 同上（不完全反应重结合用）
    simulate_level6(atom_list)   -> (mols, level6)（与 pot_v4.simulate(return_level6=True) 同构）
"""
import math
import sys
from collections import Counter

BASE = r"G:\AI work\deepseek\work1\alchemy"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from pot_all import VAL, ptable_dist, family_rank, ORDER
from pot_v3 import rule9_extra

TRI = {"O", "P", "K"}
_ORDER_IDX = {e: i for i, e in enumerate(ORDER)}
_PRIO = ("O", "X", "C", "K", "A", "F", "P", "W", "L")
_PRIO_IDX = [_ORDER_IDX[e] for e in _PRIO]


def _find(parent, x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def _union(parent, sz, cmask, crem, csize, celem, a, b):
    ra, rb = _find(parent, a), _find(parent, b)
    if ra == rb:
        return ra
    if sz[ra] < sz[rb]:
        ra, rb = rb, ra
    parent[rb] = ra
    sz[ra] += sz[rb]
    csize[ra] += csize[rb]
    cmask[ra] |= cmask[rb]
    crem[ra] += crem[rb]
    ea, eb = celem[ra], celem[rb]
    for k in range(9):
        ea[k] += eb[k]
    return ra


def _ring_flags(n, adj):
    """与 pot_v4.ring_flags 等价的桥检测。"""
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


def simulate(atom_list, base_edges=(), return_level6=False):
    atoms = list(atom_list)
    n = len(atoms)
    if n == 0:
        return ([], []) if return_level6 else []
    if sum(VAL[e] for e in atoms) % 2:
        return (None, None) if return_level6 else None
    rem = [VAL[e] for e in atoms]
    bond = [[0] * n for _ in range(n)]
    adj = [dict() for _ in range(n)]
    dt = [[0] * n for _ in range(n)]
    fam = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            dt[i][j] = dt[j][i] = ptable_dist(atoms[i], atoms[j])
            fam[i][j] = fam[j][i] = family_rank(atoms[i], atoms[j])
    for (a, b, m) in base_edges:
        a, b, m = int(a), int(b), int(m)
        if m <= 0:
            continue
        bond[a][b] += m
        bond[b][a] += m
        rem[a] -= m
        rem[b] -= m
        adj[a][b] = adj[a].get(b, 0) + m
        adj[b][a] = adj[b].get(a, 0) + m
    if any(r < 0 for r in rem):
        return (None, None) if return_level6 else None
    eidx = [_ORDER_IDX[e] for e in atoms]

    # 并查集 + 组件统计
    parent = list(range(n))
    sz = [1] * n
    cmask = [1 << eidx[i] for i in range(n)]
    crem = [rem[i] for i in range(n)]
    csize = [1] * n
    celem = [[0] * 9 for _ in range(n)]
    for i in range(n):
        celem[i][eidx[i]] = 1

    # base_edges 的组件先并起来（crem 初值=rem，合并时求和即正确）
    for (a, b, m) in base_edges:
        a, b, m = int(a), int(b), int(m)
        if m > 0:
            _union(parent, sz, cmask, crem, csize, celem, a, b)

    level6 = None
    blockid = None
    # 预先建候选对索引（i<j）
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    while True:
        use_rule10 = level6 is not None
        if use_rule10 and blockid is None:
            blockid = [-1] * n
            for bi, blk in enumerate(level6):
                for v in blk[2]:
                    blockid[v] = bi
        cand = []
        any6 = False
        rem_l = rem
        for (i, j) in pairs:
            if rem_l[i] > 0 and rem_l[j] > 0 and bond[i][j] < 3:
                cand.append((i, j))
                if dt[i][j] == 6:
                    any6 = True
        if not cand:
            break
        if level6 is None and not any6:
            # 捕获层级 6 块：当前组件中含三价元的连通块
            roots = {}
            for v in range(n):
                r = _find(parent, v)
                roots.setdefault(r, []).append(v)
            level6 = []
            for r, mem in roots.items():
                if not any(atoms[v] in TRI for v in mem):
                    continue
                mem = sorted(mem)
                local = {v: k for k, v in enumerate(mem)}
                ats = [atoms[v] for v in mem]
                es = []
                for a in range(len(mem)):
                    va = mem[a]
                    for b in range(a + 1, len(mem)):
                        m = bond[va][mem[b]]
                        if m:
                            es.append((local[va], local[mem[b]], m))
                level6.append((ats, es, tuple(mem)))
        # 组件的 root / 统计（find）
        roots = [0] * n
        for v in range(n):
            roots[v] = _find(parent, v)

        # 逐层筛选
        best = max(dt[i][j] for (i, j) in cand)
        cand = [(i, j) for (i, j) in cand if dt[i][j] == best]
        if len(cand) > 1:
            best = max(rem[i] + rem[j] for (i, j) in cand)
            cand = [(i, j) for (i, j) in cand if rem[i] + rem[j] == best]
        if len(cand) > 1:
            best = min(fam[i][j] for (i, j) in cand)
            cand = [(i, j) for (i, j) in cand if fam[i][j] == best]
        if len(cand) > 1:
            best = min(0 if roots[i] == roots[j] else 1 for (i, j) in cand)
            cand = [(i, j) for (i, j) in cand
                    if (0 if roots[i] == roots[j] else 1) == best]
        if len(cand) > 1:
            # gd：同组件内最短距离；跨组件 999
            dist_cache = {}

            def gd_of(i, j):
                if roots[i] != roots[j]:
                    return 999
                di = dist_cache.get(i)
                if di is None:
                    di = {i: 0}
                    dq = [i]
                    while dq:
                        u = dq.pop(0)
                        for v in adj[u]:
                            if v not in di:
                                di[v] = di[u] + 1
                                dq.append(v)
                    dist_cache[i] = di
                return di.get(j, 999)

            best = min(gd_of(i, j) for (i, j) in cand)
            cand = [(i, j) for (i, j) in cand if gd_of(i, j) == best]
        if len(cand) > 1:
            best = min(csize[roots[i]] if csize[roots[i]] < csize[roots[j]]
                       else csize[roots[j]] for (i, j) in cand)
            cand = [(i, j) for (i, j) in cand
                    if (csize[roots[i]] if csize[roots[i]] < csize[roots[j]]
                        else csize[roots[j]]) == best]
        if len(cand) > 1:
            best = max(csize[roots[i]] if csize[roots[i]] > csize[roots[j]]
                       else csize[roots[j]] for (i, j) in cand)
            cand = [(i, j) for (i, j) in cand
                    if (csize[roots[i]] if csize[roots[i]] > csize[roots[j]]
                        else csize[roots[j]]) == best]
        if len(cand) > 1:
            best = max((cmask[roots[i]] | cmask[roots[j]]).bit_count()
                       for (i, j) in cand)
            cand = [(i, j) for (i, j) in cand
                    if (cmask[roots[i]] | cmask[roots[j]]).bit_count() == best]
        if len(cand) > 1:
            def ti(i):
                return cmask[roots[i]].bit_count()
            best = min(ti(i) + ti(j) for (i, j) in cand)
            cand = [(i, j) for (i, j) in cand if ti(i) + ti(j) == best]
            if len(cand) > 1:
                best = min(min(ti(i), ti(j)) for (i, j) in cand)
                cand = [(i, j) for (i, j) in cand if min(ti(i), ti(j)) == best]
            if len(cand) > 1:
                best = min(max(ti(i), ti(j)) for (i, j) in cand)
                cand = [(i, j) for (i, j) in cand if max(ti(i), ti(j)) == best]
        if len(cand) > 1:
            best = max(crem[roots[i]] + crem[roots[j]] for (i, j) in cand)
            cand = [(i, j) for (i, j) in cand
                    if crem[roots[i]] + crem[roots[j]] == best]
            if len(cand) > 1:
                best = max(min(crem[roots[i]], crem[roots[j]]) for (i, j) in cand)
                cand = [(i, j) for (i, j) in cand
                        if min(crem[roots[i]], crem[roots[j]]) == best]
        if len(cand) > 1:
            # 规则 9：合并后元素计数（优先级 O,X,C,K,A,F,P,W,L）越大越优先
            def merged_counts(i, j):
                ca = celem[roots[i]]
                cb = celem[roots[j]]
                return tuple(-(ca[k] + cb[k]) for k in _PRIO_IDX)
            best = min(merged_counts(i, j) for (i, j) in cand)
            cand = [(i, j) for (i, j) in cand if merged_counts(i, j) == best]
        if len(cand) > 1 and use_rule10:
            best = min(0 if blockid[i] >= 0 and blockid[i] == blockid[j] else 1
                       for (i, j) in cand)
            cand = [(i, j) for (i, j) in cand
                    if (0 if blockid[i] >= 0 and blockid[i] == blockid[j] else 1) == best]
        if len(cand) > 1:
            rf = _ring_flags(n, adj)
            best = min(rf[i] + rf[j] for (i, j) in cand)
            cand = [(i, j) for (i, j) in cand if rf[i] + rf[j] == best]
        i, j = cand[0]
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
        if roots[i] == roots[j]:
            crem[roots[i]] -= 2
        else:
            crem[roots[i]] -= 1
            crem[roots[j]] -= 1
            _union(parent, sz, cmask, crem, csize, celem, i, j)
    if any(r > 0 for r in rem):
        return (None, None) if return_level6 else None
    # 构建分子
    groups = {}
    for v in range(n):
        groups.setdefault(_find(parent, v), []).append(v)
    if return_level6 and level6 is None:
        level6 = []
        for mem in groups.values():
            if not any(atoms[v] in TRI for v in mem):
                continue
            mem = sorted(mem)
            local = {v: k for k, v in enumerate(mem)}
            ats = [atoms[v] for v in mem]
            es = []
            for a in range(len(mem)):
                va = mem[a]
                for b in range(a + 1, len(mem)):
                    m = bond[va][mem[b]]
                    if m:
                        es.append((local[va], local[mem[b]], m))
            level6.append((ats, es, tuple(mem)))
    mols = []
    for r, mem in groups.items():
        mem = sorted(mem)
        local = {v: k for k, v in enumerate(mem)}
        ats = [atoms[v] for v in mem]
        es = []
        for a in range(len(mem)):
            va = mem[a]
            for b in range(a + 1, len(mem)):
                m = bond[va][mem[b]]
                if m:
                    es.append((local[va], local[mem[b]], m))
        mols.append({"atoms": ats, "edges": es})
    if return_level6:
        return mols, level6 or []
    return mols


def simulate_with_base(atom_list, base_edges):
    """不完全反应重结合用：在固定键 base_edges 基础上跑规则 1~11 贪心。"""
    return simulate(atom_list, base_edges=base_edges)


def simulate_level6(atom_list):
    """返回 (mols, level6)，与 pot_v4.simulate(..., return_level6=True) 同构。"""
    return simulate(atom_list, return_level6=True)


if __name__ == "__main__":
    import random
    import time
    import pot_v4
    from pot_all import formula_of

    rng = random.Random(7)
    cases = []
    for _ in range(200):
        n = rng.randint(2, 16)
        atoms = [rng.choice(ORDER) for _ in range(n)]
        cases.append(atoms)
    bad = 0
    t0 = time.time()
    for atoms in cases:
        a = simulate(atoms)
        b = pot_v4.simulate(atoms)
        fa = sorted(formula_of(m["atoms"]) for m in a) if a else None
        fb = sorted(formula_of(m["atoms"]) for m in b) if b else None
        if fa != fb:
            bad += 1
            print("MISMATCH", atoms, fa, fb)
            if bad > 5:
                break
    print("checked", len(cases), "mismatch", bad, "fast_before_slow", round(time.time() - t0, 2), "s")
