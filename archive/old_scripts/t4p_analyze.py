# -*- coding: utf-8 -*-
"""t4p_analyze：分析反应的分级结构（距离阶梯）与产物图结构。
不改动既有文件；只读 pot_all / pot_v2 和已有 JSON。
"""
import json
import sys
from collections import defaultdict, Counter

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def simulate_trace(atom_list):
    """复制 simulate 的主循环，但记录每根键的距离、剩余和、族组合、以及时间。"""
    n = len(atom_list)
    total_val = sum(P.VAL[e] for e in atom_list)
    if total_val % 2:
        return None, []
    rem = [P.VAL[e] for e in atom_list]
    bond = [[0] * n for _ in range(n)]
    adj = [dict() for _ in range(n)]
    dt = [[0] * n for _ in range(n)]
    fam = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            dt[i][j] = dt[j][i] = P.ptable_dist(atom_list[i], atom_list[j])
            fam[i][j] = fam[j][i] = P.family_rank(atom_list[i], atom_list[j])

    def comps():
        from collections import deque
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
                       ti + tj, min(ti, tj), max(ti, tj),
                       -(ri + rj), -min(ri, rj))
                cands.append((key, i, j))
        if not cands:
            break
        best = min(t[0] for t in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        i, j = tied[0]
        trace.append({"i": i, "j": j, "dt": dt[i][j],
                      "ei": atom_list[i], "ej": atom_list[j],
                      "sum": rem[i] + rem[j],
                      "sizes": (csize[comp[i]], csize[comp[j]]),
                      "n_tied": len(tied)})
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
    ok = not any(r > 0 for r in rem)
    return (ok, rem, bond, atom_list), trace


def summarize_mol(atoms, edges):
    n = len(atoms)
    catpair = Counter()
    mult = Counter()
    deg = [0] * n
    for (i, j, m) in edges:
        cats = tuple(sorted((P.CAT[atoms[i]], P.CAT[atoms[j]])))
        catpair[cats] += m
        mult[m] += 1
        deg[i] += m
        deg[j] += m
    elems = Counter(atoms)
    return {"n": n, "elems": dict(elems), "catpair": {k: v for k, v in catpair.items()},
            "mult": dict(mult), "maxdeg": max(deg) if deg else 0,
            "deg_hist": dict(Counter(deg))}


def load_catalog(path):
    return json.load(open(BASE + "\\" + path, encoding="utf-8"))


def analyze_OXK():
    data = load_catalog("t4_enum_O_X_K.json")
    subs = data["substances"]
    print(f"O/X/K: {len(subs)} substances, max {data['max_atoms']} {data['max_formula']}")
    # 结构摘要，按原子数排序
    rows = []
    for s in subs:
        info = summarize_mol(s["atoms"], s["edges"])
        rows.append((info["n"], s["formula"], info, s["feed"]))
    rows.sort(reverse=True)
    for n, f, info, feed in rows[:8]:
        print(f"  {f:16s} n={n:2d} elems={info['elems']} catpair={info['catpair']} mult={info['mult']} deg={info['deg_hist']} feed={feed}")
    return subs


def trace_demo():
    cases = [
        ("OXK 1,1,1", ["O", "X", "K"], (1, 1, 1)),
        ("OK 3,3", ["O", "K"], (3, 3)),
        ("OXK 3,2,3", ["O", "X", "K"], (3, 2, 3)),
        ("OKX 9,10,23", ["O", "X", "K"], (9, 10, 23)),
        ("all9 97", P.ORDER, (3, 8, 15, 10, 1, 0, 36, 22, 2)),
    ]
    for name, elems, feed in cases:
        atoms = P.vec_to_atoms(tuple(feed), elems)
        res, trace = simulate_trace(atoms)
        if res is None:
            print(name, "sim fail"); continue
        ok, rem, bond, _ = res
        print(f"\n{name}: n={len(atoms)} ok={ok} bonds={len(trace)}")
        print("  距离序列:", "".join(str(t["dt"]) for t in trace))
        print("  rem-sum 序列:", [t["sum"] for t in trace][:40], "..." if len(trace) > 40 else "")
        big = None
        # 用 pot_all.simulate 拿最终分子
        mols = P.simulate(atoms)
        mols = [m for m in mols if m] if mols else []
        if mols:
            big = max(mols, key=lambda m: len(m["atoms"]))
            info = summarize_mol(big["atoms"], big["edges"])
            print(f"  最大分子 n={info['n']} elems={info['elems']} catpair={info['catpair']} mult={info['mult']} maxdeg={info['maxdeg']}")


def determinism_check():
    """随机 feed，检查不同并列选择是否导致不同产物（按分子式集合比较）。"""
    import random
    rng = random.Random(12345)
    bad = 0
    trials = 0
    for _ in range(400):
        elems = rng.sample(P.ORDER, rng.randint(2, 6))
        n = rng.randint(2, 18)
        feed = [rng.randint(0, n) for _ in elems]
        feed[rng.randrange(len(feed))] += 1
        atoms = P.vec_to_atoms(tuple(feed), elems)
        base = P.simulate(atoms)
        if base is None:
            continue
        basef = sorted(P.formula_of(m["atoms"]) for m in base)
        trials += 1
        for seed in range(6):
            r2 = random.Random(seed)
            mols = P.simulate(atoms, rng=r2)
            if mols is None:
                f2 = None
            else:
                f2 = sorted(P.formula_of(m["atoms"]) for m in mols)
            if f2 != basef:
                bad += 1
                print("TIE-DIFF", dict(zip(elems, feed)), "base", basef, "got", f2)
                break
    print(f"determinism: {trials} feeds, {bad} with different formula multiset")


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("all", "trace"):
        trace_demo()
    if what in ("all", "det"):
        determinism_check()
    if what in ("all", "oxk"):
        analyze_OXK()
