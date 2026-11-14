# -*- coding: utf-8 -*-
"""t12b_embed.py —— 带状态与节点上限的 embedding（从 pot_v2.embed_mol2 复制并加状态）。

status: "ok" / "fail"（搜索穷尽，确定不可摆） / "timeout"（节点数超过 max_nodes，未判定）
"""
from collections import Counter

import pot_all as P

ALLOWED = P.allowed
classify = P.classify_offset
S_SET, C_SET, L_SET = P.S_SET, P.C_SET, P.L_SET


def embed_status(atoms, edges, max_nodes=300000):
    n = len(atoms)
    if n == 1:
        return {0: (0, 0)}, "ok"
    adj = [dict() for _ in range(n)]
    for (i, j, m) in edges:
        adj[i][j] = adj[j][i] = ALLOWED(atoms[i], atoms[j])
    start = max(range(n), key=lambda i: len(adj[i]))
    order = [start]
    seen = {start}
    while len(order) < n:
        bestu, bestkey = None, None
        for v in range(n):
            if v in seen:
                continue
            pn = sum(1 for u in adj[v] if u in seen)
            key = (-pn, -len(adj[v]))
            if bestu is None or key < bestkey:
                bestu, bestkey = v, key
        if bestu is None or bestkey[0] == 0:
            return None, "fail"
        seen.add(bestu)
        order.append(bestu)

    pos = [None] * n
    occ = set()
    lmid = Counter()
    state = {"nodes": 0, "timeout": False}

    def reps_for(allowed_set):
        reps = []
        for orbit in (S_SET, C_SET, L_SET):
            inter = allowed_set & orbit
            if inter:
                reps.append(min(inter))
        return reps

    def try_place(k):
        state["nodes"] += 1
        if state["nodes"] > max_nodes:
            state["timeout"] = True
            return False
        if k == n:
            return True
        v = order[k]
        placed_u = []
        if k == 0:
            cands = [(0, 0)]
        else:
            placed_u = [u for u in adj[v] if pos[u] is not None]
            if not placed_u:
                return False
            base = None
            for u in placed_u:
                s = {(pos[u][0] + dx, pos[u][1] + dy) for (dx, dy) in adj[u][v]}
                base = s if base is None else (base & s)
            cands = [p for p in base if p not in occ and lmid[p] == 0]
            if k == 1:
                u0 = order[0]
                reps = reps_for(adj[u0][v])
                want = set()
                for r in reps:
                    want.add((pos[u0][0] + r[0], pos[u0][1] + r[1]))
                cands = [p for p in cands if p in want]
        for p in cands:
            new_lmids = []
            ok = True
            for u in placed_u:
                d = (p[0] - pos[u][0], p[1] - pos[u][1])
                if classify(d) == "L":
                    mid = (pos[u][0] + d[0] // 2, pos[u][1] + d[1] // 2)
                    if mid in occ:
                        ok = False
                        break
                    new_lmids.append(mid)
            if not ok:
                continue
            pos[v] = p
            occ.add(p)
            for m in new_lmids:
                lmid[m] += 1
            if try_place(k + 1):
                return True
            pos[v] = None
            occ.discard(p)
            for m in new_lmids:
                lmid[m] -= 1
                if lmid[m] == 0:
                    del lmid[m]
            if state["timeout"]:
                return False
        return False

    if try_place(0):
        return {i: pos[i] for i in range(n)}, "ok"
    return None, ("timeout" if state["timeout"] else "fail")


def embed_all_status(mols, max_nodes=300000):
    """返回 (status, detail)：status 取最坏：fail > timeout > ok。"""
    worst = "ok"
    for m in mols:
        _, st = embed_status(m["atoms"], m["edges"], max_nodes=max_nodes)
        if st == "fail":
            return "fail", m
        if st == "timeout":
            worst = "timeout"
    return worst, None
