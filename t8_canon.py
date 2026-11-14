# -*- coding: utf-8 -*-
"""t8_canon：规则 9（规范决胜）的原型实现与检验。

规则 9（草案）：
  当规则 1~8 判定有多个候选对并列时，对每个候选对 (i,j) 计算“加上这根键之后的全局状态”
  的**规范形**（canon），取 canon 字典序最小的候选；若多个候选的 canon 相同（状态同构），任取其一。
  因为 canon 只依赖状态同构类，规则 9 对原子命名/输入顺序不变，所以产物（分子式多重集）唯一确定。

本文件实现：
  - refine / canon_state：带颜色的多重图规范形（IR：个体化-细化），n 小时精确。
  - simulate_r9：规则 1~8 + 规则 9 的确定性模拟。
"""
import sys
from collections import deque

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

MAX_CANON_NODES = 200000


def _refine(colors, adj, n):
    """WL 颜色细化；返回排序后的颜色编号（规范：按签名排序）。"""
    while True:
        sigs = []
        for v in range(n):
            nb = sorted((adj[v].get(u, 0), colors[u]) for u in adj[v])
            sigs.append((colors[v], tuple(nb)))
        uniq = sorted(set(sigs))
        idx = {s: k for k, s in enumerate(uniq)}
        new = [idx[s] for s in sigs]
        if new == colors:
            return colors
        colors = new


def canon_state(types, adj, n, node_budget=MAX_CANON_NODES):
    """规范形：返回可比较的编码元组；同构状态编码相同。
    精确性依赖 IR 搜索完整（node_budget 内）；超大状态退化为细化后的编码（可能不完备）。"""
    # 初始颜色：元素序
    colors = [types[v] for v in range(n)]
    colors = _refine(colors, adj, n)
    nodes = [0]
    fallback = [False]

    def enc_from_colors(cols):
        order = sorted(range(n), key=lambda v: (cols[v], v))
        pos = {v: k for k, v in enumerate(order)}
        code = []
        for v in order:
            nb = tuple(sorted((pos[u], adj[v].get(u, 0)) for u in adj[v]))
            code.append((types[v], nb))
        return tuple(code)

    def search(cols, best):
        nodes[0] += 1
        if nodes[0] > node_budget:
            fallback[0] = True
            e = enc_from_colors(cols)
            return e if best is None or e < best else best
        cols = _refine(cols, adj, n)
        cells = {}
        for v, c in enumerate(cols):
            cells.setdefault(c, []).append(v)
        multi = [c for c in sorted(cells) if len(cells[c]) > 1]
        if not multi:
            e = enc_from_colors(cols)
            return e if best is None or e < best else best
        c = multi[0]
        cell = cells[c]
        for v in cell:
            nxt = list(cols)
            nxt[v] = max(cols) + 1
            best = search(nxt, best)
        return best

    best = search(colors, None)
    return best, fallback[0]


def _types_of(atom_list):
    idx = {e: k for k, e in enumerate(P.ORDER)}
    return [idx[e] for e in atom_list]


def simulate_r9(atom_list, record_ties=False):
    n = len(atom_list)
    rem = [P.VAL[e] for e in atom_list]
    total = sum(rem)
    if total % 2:
        return None
    types = _types_of(atom_list)
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

    tie_log = []
    fallbacks = 0
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
                       ti + tj, min(ti, tj), max(ti, tj), -(ri + rj), -min(ri, rj))
                cands.append((key, i, j))
        if not cands:
            break
        best = min(t[0] for t in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        if len(tied) == 1:
            i, j = tied[0]
        else:
            # 规则 9：比较加键后的规范形
            scored = []
            for (a, b) in tied:
                adj[a][b] = adj[a].get(b, 0) + 1
                adj[b][a] = adj[b].get(a, 0) + 1
                code, fb = canon_state(types, adj, n)
                if fb:
                    fallbacks += 1
                adj[a][b] -= 1
                if adj[a][b] == 0:
                    del adj[a][b]
                adj[b][a] -= 1
                if adj[b][a] == 0:
                    del adj[b][a]
                scored.append((code, a, b))
            scored.sort(key=lambda t: (t[0], t[1], t[2]))
            _, i, j = scored[0]
            if record_ties:
                tie_log.append({"step": len(tie_log), "n_tied": len(tied),
                                "chosen": (i, j),
                                "tied": [(types[a], types[b], a, b) for (a, b) in tied]})
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
    if any(r > 0 for r in rem):
        return None
    seen = [-1] * n
    out = []
    for s in range(n):
        if seen[s] != -1:
            continue
        cid = len(out)
        seen[s] = cid
        st = [s]
        mem = [s]
        while st:
            u = st.pop()
            for v in adj[u]:
                if seen[v] == -1:
                    seen[v] = cid
                    st.append(v)
                    mem.append(v)
        out.append(P.formula_of([atom_list[i] for i in mem]))
    out = tuple(sorted(out))
    if record_ties:
        return out, tie_log, fallbacks
    return out


if __name__ == "__main__":
    # 快速自检：规范形对置换不变
    import itertools, random
    a = ["O", "O", "A", "F", "W"]
    adj = [dict() for _ in a]
    adj[0][2] = 1
    adj[2][0] = 1
    adj[1][2] = 1
    adj[2][1] = 1
    types = _types_of(a)
    base, fb = canon_state(types, adj, len(a))
    print("canon base", base, "fallback", fb)
    n = len(a)
    rng = random.Random(0)
    ok = 0
    for _ in range(30):
        perm = list(range(n))
        rng.shuffle(perm)
        # 重命名顶点
        adj2 = [dict() for _ in range(n)]
        for i in range(n):
            for j, m in adj[i].items():
                adj2[perm[i]][perm[j]] = m
        types2 = [0] * n
        for i in range(n):
            types2[perm[i]] = types[i]
        c2, _ = canon_state(types2, adj2, n)
        if c2 == base:
            ok += 1
        else:
            print("MISMATCH", perm)
    print("permutation invariance:", ok, "/30")
