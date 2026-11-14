# -*- coding: utf-8 -*-
"""t5_level6：子引理 L1 的穷举计算 —— 6 级（异类 3 价原子对）结束时的组件大小。

直接实现 6 级子过程（只允许 dist=6 的候选对；不要求价数接满），
穷举 (nO,nP,nK) 计数网格，检验"6 级结束组件有常数上界"。
"""
import json
import os
import sys
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def level6_sizes(counts, cap=None):
    atoms = []
    for e, c in zip(("O", "P", "K"), counts):
        atoms += [e] * c
    n = len(atoms)
    if n == 0:
        return 0, []
    rem = [3] * n
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

    while True:
        comp, groups, dists = comps()
        csize = [len(g) for g in groups]
        ctypes = [set(atoms[i] for i in g) for g in groups]
        crem = [sum(rem[i] for i in g) for g in groups]
        cands = []
        for i in range(n):
            if rem[i] == 0:
                continue
            for j in range(i + 1, n):
                if rem[j] == 0 or bond[i][j] >= 3 or dt[i][j] != 6:
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
        i, j = tied[0]
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
    comp, groups, _ = comps()
    sizes = sorted((len(g) for g in groups), reverse=True)
    return (sizes[0] if sizes else 0), sizes


def work(args):
    nO, NMAX = args
    out = {}
    mx = 0
    ex = None
    for nP in range(NMAX + 1):
        for nK in range(NMAX + 1):
            m, sizes = level6_sizes((nO, nP, nK))
            out[f"{nO},{nP},{nK}"] = [m, sizes[:10]]
            if m > mx:
                mx, ex = m, (nO, nP, nK, m, sizes[:10])
    return nO, out, mx, ex


def main():
    NMAX = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    jobs = int(sys.argv[2]) if len(sys.argv) > 2 else max(2, (os.cpu_count() or 4) - 2)
    results = {}
    gmax = 0
    gex = None
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for nO, out, mx, e in ex.map(work, [(nO, NMAX) for nO in range(NMAX + 1)]):
            results.update(out)
            if mx > gmax:
                gmax, gex = mx, e
    dist = Counter(v[0] for v in results.values())
    report = {"NMAX": NMAX, "max_component": gmax, "max_example": gex,
              "distribution": dict(sorted(dist.items())), "n_cases": len(results)}
    json.dump(report, open(BASE + r"\t5_level6.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("NMAX", NMAX, "cases", len(results), "max_component", gmax, "example", gex)
    print("distribution:", report["distribution"])


if __name__ == "__main__":
    main()
