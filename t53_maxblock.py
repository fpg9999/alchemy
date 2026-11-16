# -*- coding: utf-8 -*-
"""t53_maxblock.py：规则 1~11 下，6 级块尺寸上界与库内性的更大范围检查。

  A) 三价计数各 ≤30 的全网格（29,791 组，默认裁决）：最大 6 级块、库外块；
  B) 随机大计数（每类 ≤100，1,000 组，默认裁决）：同上。
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


def level6_blocks(counts):
    atoms = []
    for e, c in zip(("O", "P", "K"), counts):
        atoms += [e] * c
    n = len(atoms)
    if n == 0:
        return None, []
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
            return None, blocks_now(groups)
        best = min(c[0] for c in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        i, j = tied[0]
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1


def main():
    t0 = time.time()
    lib = V.load_library()
    libkeys = set(lib["multi"]) | set(lib["single"])
    max_size = 0
    nonlib = {}
    classes = set()
    checked = 0
    for nO in range(0, 31):
        for nP in range(0, 31):
            for nK in range(0, 31):
                if nO + nP + nK == 0:
                    continue
                mols, blocks = level6_blocks((nO, nP, nK))
                checked += 1
                for ats, es in blocks:
                    max_size = max(max_size, len(ats))
                    k = V.block_label(ats, es)
                    classes.add(k)
                    if k not in libkeys:
                        nonlib.setdefault(k, {"atoms": ats,
                                              "edges": [list(e) for e in es],
                                              "counts": (nO, nP, nK)})
    print(f"A) 各≤30 网格：{checked} 组，最大块 {max_size}，块类 {len(classes)}，"
          f"库外 {len(nonlib)}，{time.time()-t0:.0f}s", flush=True)

    rng = random.Random(11)
    rmax = 0
    for t in range(1000):
        counts = (rng.randint(0, 100), rng.randint(0, 100), rng.randint(0, 100))
        mols, blocks = level6_blocks(counts)
        for ats, es in blocks:
            rmax = max(rmax, len(ats))
            k = V.block_label(ats, es)
            classes.add(k)
            if k not in libkeys:
                nonlib.setdefault(k, {"atoms": ats, "edges": [list(e) for e in es],
                                      "counts": counts})
    print(f"B) 随机大计数：最大块 {rmax}，块类 {len(classes)}，库外 {len(nonlib)}，"
          f"{time.time()-t0:.0f}s")
    out = {"grid_max": max_size, "random_max": rmax, "classes": len(classes),
           "nonlibrary": list(nonlib.values())[:20],
           "seconds": round(time.time() - t0, 1)}
    json.dump(out, open(BASE + r"\t53_maxblock.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t53_maxblock.json")


if __name__ == "__main__":
    main()
