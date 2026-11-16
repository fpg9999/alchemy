# -*- coding: utf-8 -*-
"""t41_all_intermediate.py：穷举「所有中间态骨架（6 级块）」

口径：规则 1~9（与 pot_v3 完全相同的 key），**不预设任何并列举措**——
对每个三价计数组合 (nO,nP,nK)，DFS 枚举 6 级阶段（只连 trivalent-trivalent、dt=6）
所有并列选择分支，收集结束时所有连通块形态（mol_label 规范形去重）。

不设原子数上限的做法：
  * 对 total ≤ MAX_T 的全部组合做「全分支穷举」；
  * 对更大的投料用默认裁决 + 随机并列大量抽样，检查是否出现新形态/更大块。

输出：t41_all_intermediate.json
"""
import json
import random
import sys
import time
from collections import Counter, deque

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
from pot_v3 import rule9_extra
import t39_library_verify as V

BASE = r"G:\AI work\deepseek\work1\alchemy"
TRI = {"O", "P", "K"}
VAL = P.VAL


def enum_composition(counts, libkeys, out, cap=5_000_000):
    """枚举一个三价计数组合在 6 级阶段的全部分支，把块形态写入 out（按 label 去重）。"""
    atoms = []
    for e, c in zip(("O", "P", "K"), counts):
        atoms += [e] * c
    n = len(atoms)
    if n == 0:
        return 0
    rem0 = [VAL[e] for e in atoms]
    dt = [[P.ptable_dist(atoms[i], atoms[j]) if i != j else 0 for j in range(n)] for i in range(n)]
    fam = [[P.family_rank(atoms[i], atoms[j]) if i != j else 0 for j in range(n)] for i in range(n)]
    seen = set()
    nstates = [0]

    def comps(bond):
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
                for v in range(n):
                    if comp[v] == -1 and bond[u][v] > 0:
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
                    for v in range(n):
                        if bond[u][v] > 0 and v not in dd:
                            dd[v] = dd[u] + 1
                            dq.append(v)
                d[s] = dd
            dists.append(d)
        return comp, groups, dists

    def dfs(bond, rem):
        nstates[0] += 1
        if nstates[0] > cap:
            raise RuntimeError("state cap")
        st = (tuple((i, j, bond[i][j]) for i in range(n) for j in range(i + 1, n) if bond[i][j]),
              tuple(rem))
        if st in seen:
            return
        seen.add(st)
        comp, groups, dists = comps(bond)
        cands = []
        csize = [len(g) for g in groups]
        ctypes = [set(atoms[k] for k in g) for g in groups]
        crem = [sum(rem[k] for k in g) for g in groups]
        celem = [Counter(atoms[k] for k in g) for g in groups]
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
                       ti + tj, min(ti, tj), max(ti, tj), -(ri + rj), -min(ri, rj),
                       rule9_extra(celem[ci], celem[cj]))
                cands.append((key, i, j))
        if not cands:
            for mem in groups:
                mem = sorted(mem)
                ats = [atoms[v] for v in mem]
                es = []
                for a in range(len(mem)):
                    for b in range(a + 1, len(mem)):
                        m = bond[mem[a]][mem[b]]
                        if m:
                            es.append((a, b, m))
                k = V.block_label(ats, es)
                if k not in out:
                    out[k] = {"atoms": ats, "edges": [list(e) for e in es],
                              "size": len(ats), "counts": list(counts),
                              "in_library": k in libkeys}
            return
        best = min(c[0] for c in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        for (i, j) in tied:
            bond[i][j] += 1
            bond[j][i] += 1
            rem[i] -= 1
            rem[j] -= 1
            dfs(bond, rem)
            bond[i][j] -= 1
            bond[j][i] -= 1
            rem[i] += 1
            rem[j] += 1

    dfs([[0] * n for _ in range(n)], list(rem0))
    return nstates[0]


def main():
    t0 = time.time()
    lib = V.load_library()
    libkeys = set(lib["multi"]) | set(lib["single"])
    MAX_T = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    out = {}
    per_total = {}
    total_states = 0
    for total in range(1, MAX_T + 1):
        tt = time.time()
        before = len(out)
        worst = 0
        for nO in range(total + 1):
            for nP in range(total - nO + 1):
                nK = total - nO - nP
                if nO == nP == nK == 0:
                    continue
                s = enum_composition((nO, nP, nK), libkeys, out)
                total_states += s
                worst = max(worst, s)
        new = len(out) - before
        per_total[total] = {"new_classes": new, "distinct_total": len(out),
                            "worst_states": worst,
                            "seconds": round(time.time() - tt, 1)}
        print(f"total={total}: new={new} distinct_total={len(out)} "
              f"worst_states={worst} {time.time()-tt:.0f}s", flush=True)
    outl = [v for v in out.values() if not v["in_library"]]
    res = {"max_trivalent_total": MAX_T,
           "distinct_block_classes": len(out),
           "sizes": dict(sorted(Counter(v["size"] for v in out.values()).items())),
           "out_of_library": len(outl),
           "out_of_library_examples": outl[:20],
           "per_total": per_total,
           "total_states": total_states,
           "seconds": round(time.time() - t0, 1),
           "blocks": list(out.values())}
    json.dump(res, open(BASE + r"\t41_all_intermediate.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"DONE: {len(out)} classes, out_of_library={len(outl)}, "
          f"states={total_states}, {time.time()-t0:.0f}s")
    print("saved t41_all_intermediate.json")


if __name__ == "__main__":
    main()
