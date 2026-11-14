# -*- coding: utf-8 -*-
"""t10_rule9c：验证用户优化后的规则 9：
  - 优先：结合后分子式（两分子并集）包含的大类数更多；
  - 大类数相同：按“分子式内包含的大类”的优先级比较，聚素 > 散素 > 动素。

实现：在规则 1~8 后追加 key：
  (-|CAT_union|, tuple(sorted(CAT_RANK[c] for c in CAT_union)))
其中 CAT_RANK = 聚0 < 散1 < 动2（越小越优先）；等价于：先比大类数（多者优先），
再比大类集合的字典序（优先含聚，其次含散，最后动）。
"""
import json
import os
import random
import sys
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
CAT_RANK = {"聚": 0, "散": 1, "动": 2}


def rule9c_extra(cats_union):
    return (-len(cats_union), tuple(sorted(CAT_RANK[c] for c in cats_union)))


def simulate_rule9c(atom_list, rng=None):
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
            cats.append(frozenset(P.CAT[atom_list[i]] for i in mem))
        return comp, groups, dists, cats

    while True:
        comp, groups, dists, cats = comps()
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
                       ti + tj, min(ti, tj), max(ti, tj), -(ri + rj), -min(ri, rj),
                       rule9c_extra(cats[ci] | cats[cj]))
                cands.append((key, i, j))
        if not cands:
            break
        best = min(t[0] for t in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        i, j = rng.choice(tied) if rng is not None else tied[0]
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
    if any(r > 0 for r in rem):
        return None
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
    return tuple(sorted(out))


def test_outcomes(counts, runs=12):
    atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
    if sum(P.VAL[e] for e in atoms) % 2:
        return "odd"
    rng = random.Random(0)
    outs = set()
    for _ in range(runs):
        r = simulate_rule9c(atoms, rng)
        if r is None:
            return "invalid"
        outs.add(r)
    return outs


def gen_compositions(total, k, prefix=()):
    if k == 1:
        yield prefix + (total,)
        return
    for x in range(total + 1):
        yield from gen_compositions(total - x, k - 1, prefix + (x,))


def work(args):
    T, runs = args
    rng = random.Random(2000 + T)
    ncase = 0
    amb = []
    for counts in gen_compositions(T, 9):
        atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        ncase += 1
        outs = set()
        bad = False
        for _ in range(runs):
            r = simulate_rule9c(atoms, rng)
            if r is None:
                bad = True
                break
            outs.add(r)
        if bad:
            continue
        if len(outs) > 1:
            amb.append({"feed": list(counts), "outcomes": [list(o) for o in list(outs)[:4]]})
    return T, ncase, amb


def main():
    Tmax = int(sys.argv[1]) if len(sys.argv) > 1 else 9
    runs = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    jobs = int(sys.argv[3]) if len(sys.argv) > 3 else max(2, (os.cpu_count() or 4) - 2)
    results = {}
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for T, ncase, amb in ex.map(work, [(T, runs) for T in range(3, Tmax + 1)]):
            results[str(T)] = {"ncase": ncase, "runs": runs,
                               "rule9c_ambiguous": len(amb), "examples": amb[:8]}
            print(f"T={T}: 投料 {ncase}, 规则9c 后仍歧义 {len(amb)}", flush=True)
            for e in amb[:3]:
                print("   ", e["feed"], "->", e["outcomes"], flush=True)
    json.dump(results, open(BASE + r"\t10_rule9c_scan.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
