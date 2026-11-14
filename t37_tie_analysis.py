# -*- coding: utf-8 -*-
"""t37_tie_analysis.py：分析大锅反应中的并列候选（歧义）
新增规则：并列时优先结合「同一中间态骨架块内」的两个三价原子。
"""
import sys
from collections import Counter, deque
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
from pot_v3 import rule9_extra

BASE = r"G:\AI work\deepseek\work1\alchemy"
VAL = P.VAL
TRI = {"O", "P", "K"}


def run(atoms, policy="first", collect_ties=False, rng=None):
    n = len(atoms)
    if n == 0:
        return {"molecules": [], "ties": []}
    total_val = sum(VAL[e] for e in atoms)
    if total_val % 2:
        return None
    rem = [VAL[e] for e in atoms]
    bond = [[0] * n for _ in range(n)]
    adj = [dict() for _ in range(n)]
    dt = [[0] * n for _ in range(n)]
    fam = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            dt[i][j] = dt[j][i] = P.ptable_dist(atoms[i], atoms[j])
            fam[i][j] = fam[j][i] = P.family_rank(atoms[i], atoms[j])

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

    ties = []
    choices = []
    blocks = None
    block_structs = None
    while True:
        comp, groups, dists = comps()
        csize = [len(g) for g in groups]
        ctypes = [set(atoms[i] for i in g) for g in groups]
        crem = [sum(rem[i] for i in g) for g in groups]
        celem = [Counter(atoms[i] for i in g) for g in groups]
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
                       ti + tj, min(ti, tj), max(ti, tj), -(ri + rj), -min(ri, rj),
                       rule9_extra(celem[ci], celem[cj]))
                cands.append((key, i, j))
        if not cands:
            break
        # level6 结束：当前所有候选 dt<6（或一开始）
        if blocks is None and all(dt[i][j] < 6 for (_, i, j) in cands):
            blk = [-1] * n
            block_structs = []
            for cid, mem in enumerate(groups):
                if any(atoms[v] in TRI for v in mem):
                    for v in mem:
                        blk[v] = cid
                    mem2 = sorted(mem)
                    local = {v: k for k, v in enumerate(mem2)}
                    es2 = []
                    for a in range(len(mem2)):
                        for b in range(a + 1, len(mem2)):
                            m = bond[mem2[a]][mem2[b]]
                            if m:
                                es2.append((a, b, m))
                    block_structs.append({"atoms": [atoms[v] for v in mem2], "edges": es2})
            blocks = blk
        best = min(t[0] for t in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        if len(tied) > 1:
            intra = []
            if blocks is not None:
                for (i, j) in tied:
                    if atoms[i] in TRI and atoms[j] in TRI and blocks[i] >= 0 and blocks[i] == blocks[j]:
                        intra.append((i, j))
            if collect_ties:
                ties.append({"key": best, "pairs": tied,
                             "intra": intra,
                             "blocks_ready": blocks is not None,
                             "block_ids": [blocks[i] if blocks else None for (i, j) in tied],
                             "atoms": [atoms[i] + atoms[j] for (i, j) in tied]})
            if policy in ("intra", "intra_random") and intra:
                i, j = (rng.choice(intra) if rng is not None else intra[0])
            elif policy == "intra_random" and rng is not None:
                i, j = rng.choice(tied)
            elif policy == "random" and rng is not None:
                i, j = rng.choice(tied)
            else:
                i, j = tied[0]
        else:
            i, j = tied[0]
        choices.append({"key": best, "tied": tied, "chosen": (i, j),
                        "intra": intra if len(tied) > 1 and blocks is not None else [],
                        "blocks_ready": blocks is not None})
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
    if any(r > 0 for r in rem):
        return None
    comp, groups, _ = comps()
    mols = []
    for mem in groups:
        ats = [atoms[v] for v in mem]
        es = []
        for a in range(len(mem)):
            for b in range(a + 1, len(mem)):
                m = bond[mem[a]][mem[b]]
                if m:
                    es.append((a, b, m))
        mols.append({"atoms": ats, "edges": es})
    return {"molecules": mols, "ties": ties, "blocks": blocks, "choices": choices,
            "block_structs": block_structs}


def canon(mols):
    from t15_forms_examples import wl_key
    out = []
    for m in mols:
        out.append(wl_key(m["atoms"], [tuple(e) for e in m["edges"]]))
    return tuple(sorted(out, key=str))


def formula(atoms):
    c = Counter(atoms)
    ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]
    return "".join(s + (str(c[s]) if c[s] > 1 else "") for s in ORDER if c[s])


if __name__ == "__main__":
    import pot_all
    for f in ["O5X3KA", "O5X3PA", "OP5W3A", "OWK5A3", "OCP7W2KA2"]:
        atoms = pot_all.vec_to_atoms(pot_all.parse_formula(f), pot_all.ORDER)
        r1 = run(atoms, policy="first", collect_ties=True)
        r2 = run(atoms, policy="intra", collect_ties=True)
        print(f, "atoms", len(atoms))
        print("  first ties:", len(r1["ties"]), "outcomes:", [m["atoms"] for m in r1["molecules"]])
        if r1["ties"]:
            for t in r1["ties"][:5]:
                print("    tie", t)
        print("  intra ties:", len(r2["ties"]))
        print("  products:", [formula(m["atoms"]) for m in r1["molecules"]])
