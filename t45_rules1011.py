# -*- coding: utf-8 -*-
"""t45_rules1011.py：检验「规则 10 + 规则 11」能否消除大锅反应的骨架歧义

规则 10（用户）：若规则 9 仍相同，优先连接「中间态骨架内」的元素。
  实现 A（T37 定义）：中间态骨架 = 6 级结束时的三价块；6 级之后，两原子同块者优先。
  实现 B（当前分量定义）：两原子都已处在非平凡分量（已成形的部分骨架）者优先。
规则 11（用户）：若规则 10 仍相同，优先和链上的元素连接而非环上的元素。
  实现：候选对两端原子各自的「是否在环上」标志之和，小者优先（链原子优先）。

本脚本：
  * 对若干计数组合，枚举全部并列分支，统计不同结果类别（6 级块类、最终结构类）；
  * 对比：规则1-9 / +10 / +11 / +10+11；
  * 如多类结果仍 >1，说明仍有歧义（并列出例子）。
"""
import sys
from collections import Counter, deque

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
from pot_v3 import rule9_extra
import t39_library_verify as V

VAL = P.VAL


# ---------------------------------------------------------------- 环判定
def ring_flags(n, adj):
    """每个原子是否在某个环上（O(V+E) 桥检测）。adj: list of dict v->mult。"""
    disc = [-1] * n
    low = [0] * n
    ring = [False] * n
    timer = [0]

    def dfs(u, parent):
        disc[u] = low[u] = timer[0]
        timer[0] += 1
        for v in adj[u]:
            if v == parent:
                continue
            if disc[v] == -1:
                dfs(v, u)
                low[u] = min(low[u], low[v])
                if low[v] <= disc[u]:
                    ring[u] = True
                    ring[v] = True
            else:
                low[u] = min(low[u], disc[v])
                ring[u] = True
                ring[v] = True

    for s in range(n):
        if disc[s] == -1:
            dfs(s, -1)
    return ring


# ---------------------------------------------------------------- 核心模拟（可枚举分支）
def key_rule10_A(blockid, i, j):
    return 0 if (blockid[i] >= 0 and blockid[i] == blockid[j]) else 1


def key_rule10_B(groups, comp, i, j):
    """两原子是否都已处在非平凡分量（size>=2）；都处在→0，否则→1。"""
    gi, gj = comp[i], comp[j]
    in_i = len(groups[gi]) >= 2
    in_j = len(groups[gj]) >= 2
    return 0 if (in_i and in_j) else (1 if (in_i or in_j) else 2)


def enumerate_outcomes(counts, use10, use11, rule10_mode="A", cap=2_000_000):
    atoms = []
    for e, c in zip(("O", "P", "K"), counts):
        atoms += [e] * c
    n = len(atoms)
    if n == 0:
        return None
    rem0 = [VAL[e] for e in atoms]
    dt = [[P.ptable_dist(atoms[i], atoms[j]) if i != j else 0 for j in range(n)] for i in range(n)]
    fam = [[P.family_rank(atoms[i], atoms[j]) if i != j else 0 for j in range(n)] for i in range(n)]
    seen = set()
    finals = set()
    blocksigs = set()
    solver = V.load_library()
    libkeys = set(solver["multi"]) | set(solver["single"])
    stats = {"states": 0, "finals": 0, "blocks": 0,
             "final_out_of_lib": 0, "block_out_of_lib": 0}

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

    def dfs(bond, rem, blocks):
        st = (tuple((i, j, bond[i][j]) for i in range(n) for j in range(i + 1, n) if bond[i][j]),
              tuple(rem), tuple(blocks) if blocks is not None else None)
        if st in seen:
            return
        stats["states"] += 1
        if stats["states"] > cap:
            raise RuntimeError("cap")
        seen.add(st)
        comp, groups, dists = comps(bond)
        blockid = [-1] * n
        if blocks is not None:
            for bi, (lab, mem) in enumerate(blocks):
                for v in mem:
                    blockid[v] = bi
        # 规则 11 需要邻接
        if use11:
            adj = [dict({v: bond[u][v] for v in range(n) if bond[u][v] > 0}) for u in range(n)]
            rf = ring_flags(n, adj)
        else:
            rf = [0] * n
        csize = [len(g) for g in groups]
        ctypes = [set(atoms[i] for i in g) for g in groups]
        crem = [sum(rem[i] for i in g) for g in groups]
        celem = [Counter(atoms[i] for i in g) for g in groups]
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
                       rule9_extra(celem[ci], celem[cj]))
                if use10:
                    if rule10_mode == "A":
                        key = key + ((0 if (blockid[i] >= 0 and blockid[i] == blockid[j]) else
                                      (1 if blocks is not None else 0)),)
                    else:
                        key = key + (key_rule10_B(groups, comp, i, j),)
                if use11:
                    key = key + (rf[i] + rf[j],)
                cands.append((key, i, j))
        if not cands:
            molsigs = []
            for mem in groups:
                ats = [atoms[v] for v in mem]
                es = []
                for a in range(len(mem)):
                    for b in range(a + 1, len(mem)):
                        m = bond[mem[a]][mem[b]]
                        if m:
                            es.append((a, b, m))
                molsigs.append(P.mol_label(ats, [tuple(e) for e in es]))
            finals.add(tuple(sorted(molsigs)))
            bsig = [lab for (lab, mem) in blocks] if blocks is not None else []
            blocksigs.add(tuple(sorted(bsig)))
            return
        newblocks = blocks
        if blocks is None and not any6:
            nb = []
            for g in groups:
                if not any(atoms[v] in ("O", "P", "K") for v in g):
                    continue
                mem = sorted(g)
                ats = [atoms[v] for v in mem]
                es = []
                for a in range(len(mem)):
                    for b in range(a + 1, len(mem)):
                        m = bond[mem[a]][mem[b]]
                        if m:
                            es.append((a, b, m))
                nb.append((V.block_label(ats, es), tuple(mem)))
            newblocks = tuple(sorted(nb))
        best = min(c[0] for c in cands)
        tied = [(i, j) for (k, i, j) in cands if k == best]
        for (i, j) in tied:
            bond[i][j] += 1
            bond[j][i] += 1
            rem[i] -= 1
            rem[j] -= 1
            dfs(bond, rem, newblocks)
            bond[i][j] -= 1
            bond[j][i] -= 1
            rem[i] += 1
            rem[j] += 1

    try:
        dfs([[0] * n for _ in range(n)], list(rem0), None)
    except RuntimeError:
        return {"cap": True, "states": stats["states"]}
    for bsig in blocksigs:
        for k in bsig:
            if k not in libkeys:
                stats["block_out_of_lib"] += 1
                break
    return {"states": stats["states"],
            "distinct_final_classes": len(finals),
            "distinct_block_classes": len(blocksigs),
            "has_out_of_library_block": any(
                any(k not in libkeys for k in bsig) for bsig in blocksigs),
            "final_out_of_lib": sum(1 for f in finals if f not in libkeys),
            "cap": False}


def main():
    tests = [(3, 5, 2), (3, 5, 3), (4, 4, 4), (2, 3, 2), (4, 5, 2), (5, 3, 3)]
    print("计数组合 | 口径 | 状态数 | 最终结构类 | 6级块类 | 有库外块")
    for counts in tests:
        for label, use10, use11, mode in [
            ("规则1-9", False, False, "A"),
            ("+10(同块)", True, False, "A"),
            ("+11", False, True, "A"),
            ("+10+11(A)", True, True, "A"),
            ("+10+11(B)", True, True, "B"),
        ]:
            r = enumerate_outcomes(counts, use10, use11, mode, cap=800_000)
            if r is None:
                print(counts, label, "empty")
                continue
            print(f"{str(counts):<10} | {label:<10} | {r.get('states')} | "
                  f"{r.get('distinct_final_classes')} | {r.get('distinct_block_classes')} | "
                  f"{r.get('has_out_of_library_block')}  {'' if not r.get('cap') else 'CAP'}")
        print("-")


if __name__ == "__main__":
    main()
