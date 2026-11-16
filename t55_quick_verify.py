# -*- coding: utf-8 -*-
"""t55_quick_verify.py：>12 原子数骨架的快速验证（随机并列抽样）

  A) 三价总数 = 13 的全部 105 个组合：每个组合 100 次随机并列；
     统计 6 级块组合是否唯一（非同构）、是否全部在 38 库。
  B) 三价计数各 ≤30 的随机 1000 组（默认 + 2 次随机并列）：
     统计最大 6 级块尺寸、块类、库外块。
"""
import json
import random
import sys
import time
from collections import Counter, deque

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
from pot_v3 import rule9_extra
import pot_v4
import t39_library_verify as V

BASE = r"G:\AI work\deepseek\work1\alchemy"
TRI = {"O", "P", "K"}
VAL = P.VAL


def level6_blocks(counts, rng=None):
    atoms = []
    for e, c in zip(("O", "P", "K"), counts):
        atoms += [e] * c
    n = len(atoms)
    if n == 0:
        return []
    rem = [VAL[e] for e in atoms]
    bond = [[0] * n for _ in range(n)]
    adj = [dict() for _ in range(n)]
    dt = [[P.ptable_dist(atoms[i], atoms[j]) if i != j else 0 for j in range(n)] for i in range(n)]
    fam = [[P.family_rank(atoms[i], atoms[j]) if i != j else 0 for j in range(n)] for i in range(n)]

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

    def blocks_now(groups):
        out = []
        for g in groups:
            if not any(atoms[v] in TRI for v in g):
                continue
            mem = sorted(g)
            ats = [atoms[v] for v in mem]
            es = []
            for a in range(len(mem)):
                for b in range(a + 1, len(mem)):
                    m = bond[mem[a]][mem[b]]
                    if m:
                        es.append((a, b, m))
            out.append((ats, es))
        return out

    while True:
        comp, groups, dists = comps()
        csize = [len(g) for g in groups]
        ctypes = [set(atoms[i] for i in g) for g in groups]
        crem = [sum(rem[i] for i in g) for g in groups]
        celem = [Counter(atoms[i] for i in g) for g in groups]
        adj2 = [dict({v: bond[u][v] for v in range(n) if bond[u][v] > 0}) for u in range(n)]
        rf = pot_v4.ring_flags(n, adj2)
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
                       ti + tj, min(ti, tj), max(ti, tj), -(ri + rj), -min(ri, rj),
                       rule9_extra(celem[ci], celem[cj]), 0, rf[i] + rf[j])
                cands.append((key, i, j))
        if not any6:
            return blocks_now(groups)
        best = min(c[0] for c in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        i, j = (rng.choice(tied) if rng is not None else tied[0])
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1


def sig_of(blocks):
    return tuple(sorted(V.block_label(a, e) for a, e in blocks))


def main():
    t0 = time.time()
    lib = V.load_library()
    libkeys = set(lib["multi"]) | set(lib["single"])
    # A) total=13
    comps13 = []
    for nO in range(14):
        for nP in range(14 - nO):
            nK = 13 - nO - nP
            comps13.append((nO, nP, nK))
    amb = []
    nonlib = []
    for counts in comps13:
        sigs = set()
        for seed in range(100):
            blocks = level6_blocks(counts, random.Random(seed * 7919 + 13))
            s = sig_of(blocks)
            sigs.add(s)
            for k in s:
                if k not in libkeys:
                    nonlib.append((counts, k))
        if len(sigs) > 1:
            amb.append({"counts": counts, "n_sigs": len(sigs)})
    print(f"A) total=13: 组合 {len(comps13)}，有歧义组合 {len(amb)}，库外块命中 {len(nonlib)}，"
          f"{time.time()-t0:.0f}s", flush=True)

    # B) counts<=30 random
    rng = random.Random(2027)
    max_size = 0
    classes = set()
    nonlib_b = 0
    for t in range(1000):
        counts = (rng.randint(0, 30), rng.randint(0, 30), rng.randint(0, 30))
        if sum(counts) == 0:
            continue
        for rng2 in (None, random.Random(t), random.Random(t + 999)):
            for ats, es in level6_blocks(counts, rng2):
                max_size = max(max_size, len(ats))
                k = V.block_label(ats, es)
                classes.add(k)
                if k not in libkeys:
                    nonlib_b += 1
    print(f"B) 各≤30 随机1000组: 最大块 {max_size}，块类 {len(classes)}，库外块 {nonlib_b}，"
          f"{time.time()-t0:.0f}s", flush=True)
    out = {"total13": {"compositions": len(comps13), "ambiguous": amb,
                       "nonlibrary_hits": len(nonlib)},
           "random30": {"max_block": max_size, "classes": len(classes),
                        "nonlibrary_hits": nonlib_b},
           "seconds": round(time.time() - t0, 1)}
    json.dump(out, open(BASE + r"\t55_quick_verify.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t55_quick_verify.json")


if __name__ == "__main__":
    main()
