# -*- coding: utf-8 -*-
"""t7_tie_trace：对给定投料，找出"确定性裁决 vs 另一种并列裁决"的首次分歧点。

做法：用随机并列跑多次，直到产物分子式多重集与确定性裁决不同；
记录两条路径的选键序列，比较得到首次不同的步；输出该步的并列候选。
"""
import random
import sys
from collections import deque

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def simulate_choices(atom_list, picker):
    """picker(tied, step) -> chosen (i,j)。返回 (mols_formulas, trace)，trace 每步: (chosen, tied)。"""
    n = len(atom_list)
    rem = [P.VAL[e] for e in atom_list]
    if sum(rem) % 2:
        return None, []
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

    trace = []
    step = 0
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
        i, j = picker(tied, step)
        trace.append({"step": step, "chosen": (i, j), "tied": tied,
                      "type": atom_list[i] + "-" + atom_list[j]})
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
        step += 1
    if any(r > 0 for r in rem):
        return None, trace
    # 产物
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
    return tuple(sorted(out)), trace


def find_divergence(counts, max_seeds=200):
    atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
    det_out, det_trace = simulate_choices(atoms, lambda tied, st: tied[0])
    if det_out is None:
        return None
    rng = random.Random(0)
    for seed in range(max_seeds):
        rng2 = random.Random(seed)
        out, tr = simulate_choices(atoms, lambda tied, st, r=rng2: r.choice(tied))
        if out is None or out == det_out:
            continue
        # 首次分歧
        for k in range(min(len(det_trace), len(tr))):
            if det_trace[k]["chosen"] != tr[k]["chosen"]:
                return {
                    "feed": list(counts), "T": len(atoms),
                    "deterministic": list(det_out), "alternative": list(out),
                    "seed": seed,
                    "first_divergence_step": k,
                    "tied_candidates": [(atoms[i] + "-" + atoms[j], i, j)
                                        for (i, j) in det_trace[k]["tied"]],
                    "deterministic_choice": (atoms[det_trace[k]["chosen"][0]] + "-" +
                                             atoms[det_trace[k]["chosen"][1]],
                                             det_trace[k]["chosen"]),
                    "alternative_choice": (atoms[tr[k]["chosen"][0]] + "-" +
                                           atoms[tr[k]["chosen"][1]], tr[k]["chosen"]),
                }
        return {"feed": list(counts), "T": len(atoms), "deterministic": list(det_out),
                "alternative": list(out), "seed": seed, "first_divergence_step": None}
    return {"feed": list(counts), "T": len(atoms), "deterministic": list(det_out),
            "alternative": None}


if __name__ == "__main__":
    cases = [
        [8, 0, 7, 0, 2, 0, 4, 3, 5],   # O8 C7 W2 K4 A3 F5 (T=29)
        [0, 10, 0, 0, 9, 0, 6, 0, 8],  # X10 W9 K6 F8 (T=33)
        [3, 0, 0, 0, 1, 0, 0, 2, 1],   # O3 F A2 W (T=7)
    ]
    for c in cases:
        r = find_divergence(c)
        print(r)
