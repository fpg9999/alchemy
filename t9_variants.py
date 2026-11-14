# -*- coding: utf-8 -*-
"""t9_variants：比较几种规则 9 变体消除并列歧义的效果。

变体：
  A) 用户方案：类别数（大类并集数）多者优先 = (-len(cat_union),)
  B) A + 元素对序：再按 (元素序 i, 元素序 j) 字典序小者优先
  C) B + 端点在各自组分中的规范细化颜色（近似规则 9 的规范决胜）
"""
import itertools
import json
import os
import sys
from collections import deque
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
RANK = {e: k for k, e in enumerate(P.ORDER)}
CATR = {c: k for k, c in enumerate(("聚", "动", "散"))}


def run_ties(atom_list, extra_fn, max_leaves=3000):
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
    outcomes = set()
    over = [False]
    leaves = [0]

    def rec(bond, rem, adj):
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
                extra = extra_fn(i, j, ci, cj, cats, groups, adj, dists, atom_list)
                cands.append((base_key + extra, i, j))
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
            leaves[0] += 1
            if leaves[0] > max_leaves:
                over[0] = True
                return
            outcomes.add(tuple(sorted(P.formula_of([atom_list[i] for i in mem]) for mem in comps)))
            return
        best = min(t[0] for t in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        for (i, j) in tied:
            bond[i][j] += 1
            bond[j][i] += 1
            rem[i] -= 1
            rem[j] -= 1
            adj[i][j] = adj[i].get(j, 0) + 1
            adj[j][i] = adj[j].get(i, 0) + 1
            rec(bond, rem, adj)
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

    rec([[0] * n for _ in range(n)], list(rem0), [dict() for _ in range(n)])
    if over[0]:
        return "over"
    return outcomes


def extra_A(i, j, ci, cj, cats, groups, adj, dists, atom_list):
    return (-len(cats[ci] | cats[cj]),)


def extra_B(i, j, ci, cj, cats, groups, adj, dists, atom_list):
    a, b = RANK[atom_list[i]], RANK[atom_list[j]]
    return (-len(cats[ci] | cats[cj]), min(a, b), max(a, b))


def extra_C(i, j, ci, cj, cats, groups, adj, dists, atom_list):
    # 端点度数（bond 数）与剩余键数作为再下一层；仍不完备
    a, b = RANK[atom_list[i]], RANK[atom_list[j]]
    return (-len(cats[ci] | cats[cj]), min(a, b), max(a, b),
            sum(1 for _ in adj[i]), sum(1 for _ in adj[j]))


def gen_compositions(total, k, prefix=()):
    if k == 1:
        yield prefix + (total,)
        return
    for x in range(total + 1):
        yield from gen_compositions(total - x, k - 1, prefix + (x,))


def scan_one(args):
    T, fn_name = args
    fn = {"A": extra_A, "B": extra_B, "C": extra_C}[fn_name]
    bad = []
    ncase = 0
    for counts in gen_compositions(T, 9):
        atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        ncase += 1
        r = run_ties(atoms, fn)
        if r == "over" or (r is not None and len(r) > 1):
            bad.append({"feed": list(counts), "outcomes": [list(k) for k in r] if r != "over" else "over"})
    return T, fn_name, ncase, bad


def main():
    Tmax = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    jobs = int(sys.argv[2]) if len(sys.argv) > 2 else max(2, (os.cpu_count() or 4) - 2)
    tasks = [(T, fn) for T in range(6, Tmax + 1) for fn in ("A", "B", "C")]
    results = {}
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for T, fn, ncase, bad in ex.map(scan_one, tasks):
            results[f"{T}_{fn}"] = {"ncase": ncase, "n_bad": len(bad), "examples": bad[:5]}
            print(f"T={T} 变体 {fn}: 投料 {ncase}, 仍歧义 {len(bad)}", flush=True)
    json.dump(results, open(BASE + r"\t9_variants.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
