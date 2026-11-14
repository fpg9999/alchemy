# -*- coding: utf-8 -*-
"""t9_rule9b：验证用户提出的规则 9 方案——
「若规则 1~8 仍相同，则优先选择“结合后分子式包含的大类（聚/动/散）更多”的候选对」。

实现：在规则 1~8 的 key 后再加一项 -len(大类并集数)，并列时穷举剩余并列（DFS），
若仍有 >1 种产物分子式多重集 → 仍存在歧义。
"""
import itertools
import json
import os
import sys
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def cat_of(e):
    return P.CAT[e]


def run_ties_rule9b(atom_list, max_leaves=5000):
    n = len(atom_list)
    rem0 = [P.VAL[e] for e in atom_list]
    if sum(rem0) % 2:
        return None
    dt = [[0] * n for _ in range(n)]
    fam = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            dt[i][j] = dt[j][i] = P.ptable_dist(atom_list[i], atom_list[j])
            fam[i][j] = fam[j][i] = P.family_rank(atom_list[i], atom_list[j])

    outcomes = Counter()
    first_tie = {"step": None, "tied": None, "n_tied": 0, "cat_counts": None}
    leaves = [0]
    over = [False]

    def rec(bond, rem, adj, step_no):
        if over[0]:
            return
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
        cats = []
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
            cats.append(set(P.CAT[atom_list[i]] for i in mem))
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
                base_key = (-dt[i][j], -(rem[i] + rem[j]), fam[i][j], cross, gd,
                            min(csize[ci], csize[cj]), -max(csize[ci], csize[cj]), -ut,
                            ti + tj, min(ti, tj), max(ti, tj), -(ri + rj), -min(ri, rj))
                # 用户规则 9：结合后（两大类并集）大类数更多者优先
                cat_union = cats[ci] | cats[cj]
                key = base_key + (-len(cat_union),)
                cands.append((key, i, j, len(cat_union)))
        if not cands:
            if any(r > 0 for r in rem):
                return
            seen = [-1] * n
            comps = []
            for s in range(n):
                if seen[s] != -1:
                    continue
                cid = len(comps)
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
                comps.append(mem)
            forms = tuple(sorted(P.formula_of([atom_list[i] for i in mem]) for mem in comps))
            leaves[0] += 1
            if leaves[0] > max_leaves:
                over[0] = True
                return
            outcomes[forms] += 1
            return
        best = min(t[0] for t in cands)
        tied = [(i, j) for (k, i, j, cu) in cands if k == best]
        if len(tied) > 1 and first_tie["step"] is None:
            first_tie["step"] = step_no
            first_tie["tied"] = [(atom_list[i] + "-" + atom_list[j], i, j) for (i, j) in tied]
            first_tie["n_tied"] = len(tied)
            first_tie["cat_counts"] = sorted(set(cu for (k, i, j, cu) in cands if k == best))
        for (i, j) in tied:
            bond[i][j] += 1
            bond[j][i] += 1
            rem[i] -= 1
            rem[j] -= 1
            adj[i][j] = adj[i].get(j, 0) + 1
            adj[j][i] = adj[j].get(i, 0) + 1
            rec(bond, rem, adj, step_no + 1)
            if over[0]:
                return
            adj[i][j] -= 1
            if adj[i][j] == 0:
                del adj[i][j]
            adj[j][i] -= 1
            if adj[j][i] == 0:
                del adj[j][i]
            rem[i] += 1
            rem[j] += 1
            bond[i][j] -= 1
            bond[j][i] -= 1

    rec([[0] * n for _ in range(n)], list(rem0), [dict() for _ in range(n)], 0)
    info = dict(first_tie)
    info["over"] = over[0]
    return outcomes, info


def gen_compositions(total, k, prefix=()):
    if k == 1:
        yield prefix + (total,)
        return
    for x in range(total + 1):
        yield from gen_compositions(total - x, k - 1, prefix + (x,))


def analyze(counts, max_leaves=2000):
    atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
    r = run_ties_rule9b(atoms, max_leaves=max_leaves)
    if r is None:
        return None
    outcomes, info = r
    if len(outcomes) <= 1:
        return None
    return {"feed": list(counts), "T": len(atoms),
            "outcomes": [{"products": list(k), "paths": v} for k, v in outcomes.items()],
            "first_tie": info}


def work(args):
    T, limit = args
    found = []
    ncase = 0
    for counts in gen_compositions(T, 9):
        atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        ncase += 1
        res = analyze(counts)
        if res:
            found.append(res)
            if len(found) >= limit:
                break
    return T, ncase, found


def main():
    Tmax = int(sys.argv[1]) if len(sys.argv) > 1 else 9
    jobs = int(sys.argv[2]) if len(sys.argv) > 2 else max(2, (os.cpu_count() or 4) - 2)
    results = {}
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for T, ncase, found in ex.map(work, [(T, 100000) for T in range(3, Tmax + 1)]):
            results[str(T)] = {"ncase": ncase, "n_ambiguous": len(found), "examples": found}
            print(f"T={T}: 投料 {ncase}, 规则9(大类数)后仍歧义 {len(found)}", flush=True)
            for f in found[:5]:
                print("   ", f["feed"], "->", [o["products"] for o in f["outcomes"]], flush=True)
    json.dump(results, open(BASE + r"\t9_rule9b_scan.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
