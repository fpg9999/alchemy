# -*- coding: utf-8 -*-
"""t6_active_exhaustive：对若干元素池穷举计数，检验「单组件活跃原子数」的常数上界（猜想 C）。

- 池：O/X/K（3 大类各一个 3 价，3 种类型）；纯大类 O/X/C。
- 对每个计数向量跑完整反应，记录全过程中"单个组件内 rem>0 的原子数"的最大值。
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


def max_active_component(atom_list):
    n = len(atom_list)
    rem = [P.VAL[e] for e in atom_list]
    if sum(rem) % 2:
        return None
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

    best = 0
    while True:
        comp, groups, dists = comps()
        act = [sum(1 for i in g if rem[i] > 0) for g in groups]
        if act:
            best = max(best, max(act))
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
        best_key = min(t[0] for t in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best_key]
        i, j = tied[0]
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
    return best


POOLS = {
    "OXK": ("O", "X", "K"),
    "OXC": ("O", "X", "C"),
}


def work(args):
    pool, idx, NMAX = args
    names = POOLS[pool]
    k = len(names)
    out = {}
    mx = 0
    ex = None
    for counts in itertools.product(range(NMAX + 1), repeat=k):
        if sum(counts) == 0:
            continue
        atoms = []
        for e, c in zip(names, counts):
            atoms += [e] * c
        m = max_active_component(atoms)
        if m is None:
            continue
        out[",".join(map(str, counts))] = m
        if m > mx:
            mx, ex = m, counts
    return pool, out, mx, ex


def main():
    NMAX = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    jobs = int(sys.argv[2]) if len(sys.argv) > 2 else max(2, (os.cpu_count() or 4) - 2)
    results = {}
    for pool in POOLS:
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            res = list(ex.map(work, [(pool, 0, NMAX)]))
        _, out, mx, exc = res[0]
        dist = Counter(out.values())
        results[pool] = {"NMAX": NMAX, "max_active_in_component": mx, "example": exc,
                         "distribution": dict(sorted(dist.items())), "n_cases": len(out)}
        print(pool, "NMAX", NMAX, "cases", len(out), "max active in component", mx, "example", exc, flush=True)
        print("  distribution:", results[pool]["distribution"], flush=True)
    json.dump(results, open(BASE + r"\t6_active_exhaustive.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
