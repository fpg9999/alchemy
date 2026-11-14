# -*- coding: utf-8 -*-
"""pot_v2：在 pot_all 基础上修复 embed_mol 的 L 中间格 bug，并提供严格校验。

Bug：pot_all.embed_mol 用 set 记录 L 键中间格；回溯撤销时会把"另一个仍存在的 L 键
也共享的中间格"删掉，导致后续原子可以放到该中间格上，产出非法摆放（已验证：97 原子
一锅分子会出现 L 中点被占用）。

本模块：embed_mol2（lmid 用计数 dict + 结束前严格校验）、validate_place（严格校验）。
"""
import sys
from collections import Counter

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

ALLOWED = P.allowed
classify = P.classify_offset


def validate_place(place, atoms, edges):
    """严格校验摆放是否合法；返回 (ok, msg)。"""
    if place is None:
        return False, "None"
    n = len(atoms)
    pos = [tuple(place[i]) for i in range(n)]
    if len(set(pos)) != n:
        return False, "duplicate positions"
    occ = set(pos)
    for (i, j, m) in edges:
        d = (pos[j][0] - pos[i][0], pos[j][1] - pos[i][1])
        if d not in ALLOWED(atoms[i], atoms[j]):
            return False, f"offset {d} not allowed ({atoms[i]}-{atoms[j]})"
        if classify(d) == "L":
            mid = (pos[i][0] + d[0] // 2, pos[i][1] + d[1] // 2)
            if mid in occ:
                return False, f"L midpoint {mid} occupied"
            if mid == pos[i] or mid == pos[j]:
                return False, "L midpoint equals endpoint"
    return True, "ok"


def embed_mol2(atoms, edges, max_nodes=None, final_check=True):
    n = len(atoms)
    if n == 1:
        return {0: (0, 0)}
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
            return None
        seen.add(bestu)
        order.append(bestu)

    pos = [None] * n
    occ = set()
    lmid = Counter()
    nodes = [0]
    S_SET, C_SET, L_SET = P.S_SET, P.C_SET, P.L_SET

    def reps_for(allowed_set):
        reps = []
        for orbit in (S_SET, C_SET, L_SET):
            inter = allowed_set & orbit
            if inter:
                reps.append(min(inter))
        return reps

    def try_place(k):
        nodes[0] += 1
        if max_nodes is not None and nodes[0] > max_nodes:
            return False
        if k == n:
            if final_check:
                return validate_place({i: pos[i] for i in range(n)}, atoms, edges)[0]
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
        return False

    if try_place(0):
        return {i: pos[i] for i in range(n)}
    return None


def embed_all2(mols, max_nodes=None, final_check=True):
    for m in mols:
        if embed_mol2(m["atoms"], m["edges"], max_nodes=max_nodes, final_check=final_check) is None:
            return False
    return True


if __name__ == "__main__":
    cases = [
        ("T68", P.ORDER, [6, 2, 0, 24, 8, 8, 6, 6, 8]),
        ("T97", P.ORDER, [3, 8, 15, 10, 1, 0, 36, 22, 2]),
        ("T129", P.ORDER, [6, 12, 16, 13, 3, 0, 52, 24, 3]),
        ("T160", P.ORDER, [10, 20, 16, 15, 0, 1, 66, 30, 2]),
        ("OXKA154", ["O", "X", "K", "A"], [71, 35, 27, 28]),
        ("OK42", ["O", "X", "K"], [13, 16, 35]),
        ("XCKA33", ["X", "C", "K", "A"], [11, 15, 21, 17]),
    ]
    for name, elems, feed in cases:
        atoms = P.vec_to_atoms(tuple(feed), elems)
        mols = P.simulate(atoms)
        if not mols:
            print(name, "sim fail")
            continue
        big = max(mols, key=lambda m: len(m["atoms"]))
        r = embed_mol2(big["atoms"], big["edges"], max_nodes=3_000_000)
        ok, msg = validate_place(r, big["atoms"], big["edges"])
        print(f"{name}: n={len(big['atoms'])} embed={r is not None} valid={ok} msg={msg}", flush=True)
