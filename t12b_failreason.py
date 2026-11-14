# -*- coding: utf-8 -*-
"""t12b_failreason.py —— 失败向量细化：奇数价数 / 贪心剩键（剩哪些元素）/ 摆放失败。

输出 t12b_failreason.json
  detail: {ridx: {"kind": "odd"|"stuck"|"embed", "left": {elem: rem}, "n_left": k, "max_rem": m}}
  n_odd / n_stuck / n_embed
"""
import json
import sys
import time
from collections import Counter, deque
from multiprocessing import Pool

BASE = r"G:\AI work\deepseek\work1\alchemy"
sys.path.insert(0, BASE)
import pot_all as P

ORDER = P.ORDER
VAL = P.VAL
NPROC = 8


def simulate_diag(atom_list):
    """pot_all.simulate 的副本，但返回 (mols_or_None, rem)。"""
    n = len(atom_list)
    if n == 0:
        return [], []
    total_val = sum(VAL[e] for e in atom_list)
    if total_val % 2:
        return None, None
    rem = [VAL[e] for e in atom_list]
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
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
    if any(r > 0 for r in rem):
        left = Counter()
        for k, e in enumerate(atom_list):
            if rem[k] > 0:
                left[e] += rem[k]
        return None, dict(left)
    return [], None


def work(item):
    ridx, v = item
    atoms = [s for s, c in zip(ORDER, v) for _ in range(c)]
    if sum(VAL[e] for e in atoms) % 2:
        return ridx, {"kind": "odd"}
    mols, left = simulate_diag(atoms)
    if left is None:
        return ridx, {"kind": "embed"}
    return ridx, {"kind": "stuck", "left": left,
                  "n_left": sum(left.values()),
                  "max_rem": max(left.values())}


def main():
    t0 = time.time()
    data = json.load(open(BASE + r"\t12b_results.json", encoding="utf-8"))
    uniq = data["vecs"]
    res = data["res"]
    todo = [(k, tuple(v)) for k, v in enumerate(uniq) if res[k][0] in (1, 2)]
    print(f"失败向量 {len(todo)} / {len(uniq)}", flush=True)
    detail = {}
    with Pool(NPROC) as pool:
        for k, (ridx, d) in enumerate(pool.imap_unordered(work, todo, chunksize=8), 1):
            detail[str(ridx)] = d
            if k % 200 == 0 or k == len(todo):
                print(f"  {k}/{len(todo)} {time.time()-t0:.1f}s", flush=True)
    kinds = Counter(d["kind"] for d in detail.values())
    out = {"n_odd": kinds.get("odd", 0), "n_stuck": kinds.get("stuck", 0),
           "n_embed": kinds.get("embed", 0), "detail": detail,
           "sec": round(time.time() - t0, 1)}
    json.dump(out, open(BASE + r"\t12b_failreason.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"种类: {dict(kinds)}  耗时 {time.time()-t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
