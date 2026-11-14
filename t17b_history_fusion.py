# -*- coding: utf-8 -*-
"""t17b_history_fusion.py：反应历史约束的融合检验（优化版）"""
import json
import sys
import random
from collections import Counter, deque
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from pot_all import VAL, ptable_dist, family_rank
from pot_v3 import rule9_extra

TRI = {"O", "P", "K"}
ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]


def simulate_record(atom_list, return_bond=False):
    n = len(atom_list)
    if n == 0:
        return [], [], None
    total_val = sum(VAL[e] for e in atom_list)
    if total_val % 2:
        return None, None, None
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

    def triv_comps():
        """三价诱导子图的连通块（只走三价-三价键）"""
        idx = [i for i in range(n) if atom_list[i] in TRI]
        m = len(idx)
        seen = [False] * m
        out = []
        for s in range(m):
            if seen[s]:
                continue
            st = [s]
            seen[s] = True
            mem = [s]
            while st:
                u = st.pop()
                for b in range(m):
                    if not seen[b] and bond[idx[u]][idx[b]] > 0:
                        seen[b] = True
                        st.append(b)
                        mem.append(b)
            out.append(frozenset(idx[k] for k in mem))
        return out

    level6 = None
    while True:
        comp, groups, dists = comps()
        csize = [len(g) for g in groups]
        ctypes = [set(atom_list[i] for i in g) for g in groups]
        crem = [sum(rem[i] for i in g) for g in groups]
        celem = [Counter(atom_list[i] for i in g) for g in groups]
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
                       ti + tj, min(ti, tj), max(ti, tj),
                       -(ri + rj), -min(ri, rj),
                       rule9_extra(celem[ci], celem[cj]))
                cands.append((key, i, j))
        if level6 is None and not any6:
            level6 = triv_comps()
            bond6 = [row[:] for row in bond] if return_bond else None
        if not cands:
            break
        best = min(t[0] for t in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        i, j = tied[0]
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
    if level6 is None:
        level6 = triv_comps()
        bond6 = [row[:] for row in bond] if return_bond else None
    final = triv_comps()
    ok = not any(r > 0 for r in rem)
    if return_bond:
        return level6, final, ok, bond6
    return level6, final, ok


def main():
    cat = json.load(open(r"G:\AI work\deepseek\work1\alchemy\t4_catalog_all_validated.json", encoding="utf-8"))
    rng = random.Random(7)
    bytype = {}
    for r in cat:
        trs = frozenset(a for a in r["atoms"] if a in TRI)
        bytype.setdefault(trs, []).append(r)
    picks = []
    for trs, lst in bytype.items():
        picks += rng.sample(lst, min(20, len(lst)))
    want = {"O3P", "O2CK", "O2K4", "O2K6", "O2P6", "O5P5K2", "O3KA2", "CP2K3", "O2X2C4"}
    for r in cat:
        if r["formula"] in want:
            r2 = dict(r)
            r2["_want"] = True
            picks.append(r2)
    print("samples:", len(picks), flush=True)
    stats = Counter()
    bad_examples = []
    fusion_stats = Counter()
    block_sizes = Counter()
    examples = []
    for r in picks:
        feed = r.get("feed")
        if not feed:
            stats["no_feed"] += 1
            continue
        atoms = [s for s, c in zip(ORDER, feed) for _ in range(c)]
        try:
            level6, final, ok = simulate_record(atoms)
        except Exception as e:
            stats["error"] += 1
            continue
        if level6 is None:
            stats["odd_valence"] += 1
            continue
        bad = 0
        for fc in final:
            blocks = [lc for lc in level6 if lc <= fc]
            cover = set()
            for b in blocks:
                cover |= b
            if not blocks or cover != set(fc):
                bad += 1
            fusion_stats[len(blocks)] += 1
        for b in level6:
            block_sizes[len(b)] += 1
        stats["ok" if bad == 0 else "bad"] += 1
        if bad and len(bad_examples) < 5:
            bad_examples.append({"formula": r["formula"], "bad": bad})
        if (r.get("_want") or (len(examples) < 8)) and len(examples) < 20:
            examples.append({"formula": r["formula"], "feed": list(feed),
                             "level6": [sorted(x) for x in level6],
                             "final": [sorted(x) for x in final],
                             "fusion_arity": dict(Counter(
                                 len([b for b in level6 if b <= fc]) for fc in final)),
                             "bad": bad})
    print("stats:", dict(stats))
    print("fusion arity (每终态组件由几个 6 级块融合):", dict(fusion_stats))
    print("6 级块大小分布:", dict(block_sizes))
    print("bad examples:", bad_examples)
    json.dump({"stats": dict(stats), "fusion": dict(fusion_stats),
               "block_sizes": dict(block_sizes), "examples": examples},
              open(r"G:\AI work\deepseek\work1\alchemy\t17_history.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t17_history.json")


if __name__ == "__main__":
    main()
