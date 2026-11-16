# -*- coding: utf-8 -*-
"""t50_scan_block_ambiguity.py：规则 1~11 下「6 级骨架歧义」全扫描。

只枚举 6 级阶段（只连 dt=6 的键）的全部分支；到达 6 级结束（已无 dt=6 候选）时
记录所有三价连通块的规范形组合，统计同一投料是否会出现不同的骨架组合。

规则：
  1~9 与 pot_v3 相同；规则 10 在 6 级阶段取常数 0；规则 11 = 环上原子数之和（小者优先）。
输出：控制台 + t50_scan_block_ambiguity.json
"""
import json
import sys
import time
from collections import Counter, deque

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
from pot_v3 import rule9_extra
import t45_rules1011 as T
import t39_library_verify as V

BASE = r"G:\AI work\deepseek\work1\alchemy"
TRI = {"O", "P", "K"}
VAL = P.VAL


def enum_block_sigs(counts, cap=3_000_000):
    atoms = []
    for e, c in zip(("O", "P", "K"), counts):
        atoms += [e] * c
    n = len(atoms)
    if n == 0:
        return set(), 0
    rem0 = [VAL[e] for e in atoms]
    dt = [[P.ptable_dist(atoms[i], atoms[j]) if i != j else 0 for j in range(n)] for i in range(n)]
    fam = [[P.family_rank(atoms[i], atoms[j]) if i != j else 0 for j in range(n)] for i in range(n)]
    seen = set()
    sigs = set()
    states = [0]

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
        st = (tuple((i, j, bond[i][j]) for i in range(n) for j in range(i + 1, n) if bond[i][j]),
              tuple(rem))
        if st in seen:
            return
        seen.add(st)
        states[0] += 1
        if states[0] > cap:
            raise RuntimeError("cap")
        comp, groups, dists = comps(bond)
        cands = []
        csize = [len(g) for g in groups]
        ctypes = [set(atoms[i] for i in g) for g in groups]
        crem = [sum(rem[i] for i in g) for g in groups]
        celem = [Counter(atoms[i] for i in g) for g in groups]
        adj = [dict({v: bond[u][v] for v in range(n) if bond[u][v] > 0}) for u in range(n)]
        rf = T.ring_flags(n, adj)
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
                       rule9_extra(celem[ci], celem[cj]), 0, rf[i] + rf[j])
                cands.append((key, i, j))
        if not cands:
            sig = []
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
                sig.append(V.block_label(ats, es))
            sigs.add(tuple(sorted(sig)))
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
    return sigs, states[0]


def main():
    t0 = time.time()
    max_total = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    start_total = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    lib = V.load_library()
    libkeys = set(lib["multi"]) | set(lib["single"])
    out = {"max_total": max_total, "ambiguous": [], "out_of_library": [],
           "per_total": {}}
    for total in range(start_total, max_total + 1):
        t1 = time.time()
        amb = 0
        nonlib = 0
        worst_states = 0
        for nO in range(total + 1):
            for nP in range(total - nO + 1):
                nK = total - nO - nP
                if nO == nP == nK == 0:
                    continue
                sigs, st = enum_block_sigs((nO, nP, nK))
                worst_states = max(worst_states, st)
                if len(sigs) > 1:
                    amb += 1
                    out["ambiguous"].append({"counts": (nO, nP, nK),
                                             "n_sigs": len(sigs)})
                for sig in sigs:
                    for k in sig:
                        if k not in libkeys:
                            nonlib += 1
                            out["out_of_library"].append({"counts": (nO, nP, nK),
                                                          "label": k})
                            break
        out["per_total"][str(total)] = {"ambiguous_comps": amb,
                                        "out_of_library_hits": nonlib,
                                        "worst_states": worst_states,
                                        "seconds": round(time.time() - t1, 1)}
        print(f"total={total}: ambiguous={amb} nonlib={nonlib} "
              f"worst_states={worst_states} {time.time()-t1:.0f}s", flush=True)
    out["seconds"] = round(time.time() - t0, 1)
    json.dump(out, open(BASE + r"\t50_scan_block_ambiguity.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("DONE", out["seconds"], "s; ambiguous comps:", len(out["ambiguous"]),
          "out_of_library hits:", len(out["out_of_library"]))
    print("saved t50_scan_block_ambiguity.json")


if __name__ == "__main__":
    main()
