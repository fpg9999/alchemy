# -*- coding: utf-8 -*-
"""t6_excess：搜索"单组件 Σ(rem-1)（rem>0 原子的额外键容量）"的最大值。

观察到反例（4 个 rem=2 的 P 原子同组件）给出 excess=4。检验是否能超过 4。
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


def max_excess(atom_list):
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
        for g in groups:
            ex = sum(rem[i] - 1 for i in g if rem[i] > 0)
            if ex > best:
                best = ex
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


def hill(T, rng, iters=200):
    cur = rand_feed(T, rng)
    cur_sc = max_excess(P.vec_to_atoms(tuple(cur), P.ORDER))
    if cur_sc is None:
        return 0, cur
    for it in range(iters):
        cand = list(cur)
        i, j = rng.randrange(9), rng.randrange(9)
        if cand[i] > 0:
            cand[i] -= 1
            cand[j] += 1
        if sum(P.VAL[e] * c for e, c in zip(P.ORDER, cand)) % 2:
            continue
        m = max_excess(P.vec_to_atoms(tuple(cand), P.ORDER))
        if m is None:
            continue
        if m > cur_sc:
            cur, cur_sc = cand, m
    return cur_sc, cur


def work(seed):
    rng = random.Random(seed)
    best = 0
    case = None
    for T in (12, 16, 24, 32, 48, 64):
        for _ in range(3):
            sc, feed = hill(T, rng)
            if sc > best:
                best, case = sc, (T, feed)
                print(f"seed{seed}: new max excess={sc} T={T} feed={feed}", flush=True)
    return best, case


def main():
    jobs = int(sys.argv[1]) if len(sys.argv) > 1 else max(2, (os.cpu_count() or 4) - 2)
    seeds = list(range(700, 700 + jobs * 2))
    overall, case = 0, None
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for best, c in ex.map(work, seeds):
            if best > overall:
                overall, case = best, c
    print("overall max excess:", overall, "case:", case)
    json.dump({"max_excess": overall, "case": case}, open(BASE + r"\t6_excess.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
