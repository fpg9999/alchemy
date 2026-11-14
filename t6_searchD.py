# -*- coding: utf-8 -*-
"""t6_searchD：随机/爬山搜索"某个组件内 rem>=2 原子数 >3"的反例（检验猜想 D）。

若能在任何投料/时刻找到 4 个 rem>=2 原子在同一组件，则猜想 D 被推翻。
"""
import json
import os
import random
import sys
from collections import deque
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def max_high(atom_list, stop_if=4):
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
        hi = [sum(1 for i in g if rem[i] >= 2) for g in groups]
        if hi:
            m = max(hi)
            if m > best:
                best = m
                if best >= stop_if:
                    return best
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
        bk = min(t[0] for t in cands)
        tied = [(i, j) for (k, i, j) in cands if k == bk]
        i, j = tied[0]
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
    return best


def rand_feed(T, rng):
    counts = [0] * 9
    for _ in range(T):
        counts[rng.randrange(9)] += 1
    return counts


def work(seed):
    rng = random.Random(seed)
    best = 0
    bestfeed = None
    for trial in range(400):
        T = rng.randint(8, 80)
        counts = rand_feed(T, rng)
        atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        m = max_high(atoms)
        if m is None:
            continue
        if m > best:
            best, bestfeed = m, counts
            print(f"seed{seed} new best h={m} T={T} feed={counts}", flush=True)
    return best, bestfeed


def main():
    jobs = int(sys.argv[1]) if len(sys.argv) > 1 else max(2, (os.cpu_count() or 4) - 2)
    seeds = list(range(1000, 1000 + jobs * 2))
    overall = 0
    ex = None
    with ProcessPoolExecutor(max_workers=jobs) as exe:
        for best, feed in exe.map(work, seeds):
            if best > overall:
                overall, ex = best, feed
    print("overall max h:", overall, "feed:", ex)
    json.dump({"max_h": overall, "feed": ex}, open(BASE + r"\t6_searchD.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
