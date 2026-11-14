# -*- coding: utf-8 -*-
"""pot_v3 —— 正式模拟器（规则 1~9）。

与 pot_all.simulate 的唯一区别：在规则 1~8 的 key 之后加入**规则 9（元素优先级）**：

    规则 9：若规则 1~8 仍相同，则按结合后分子式（两分子并集）内各元素的数量比较，
            优先级为 秩(O) > 晶(X) > 凝/冰(C) > 沌(K) > 气(A) > 焰(F) > 势(P) > 流(W) > 电(L)。
            先比秩元素数量（多者优先），相同则比晶，依次类推。

即候选对 (i,j) 的完整 key 为：
    ( -周期表距离, -(rem_i+rem_j), 族组合序号, cross, 分子内距离,
      min(size_i,size_j), -max(size_i,size_j),
      -并集种类数, 自身种类数和, min(自身种类), max(自身种类),
      -(总剩余键和), -min(总剩余键),
      *(-结合后各元素数量，按 秩>晶>冰>沌>气>焰>势>流>电 顺序) )

产物输出格式与 pot_all.simulate 完全一致（list of {"atoms":[...], "edges":[(a,b,mult),...]}）。
几何可实现性判定请继续使用 pot_v2.embed_mol2 / validate_place。
"""
import sys
from collections import Counter, deque

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from pot_all import VAL, CAT, ptable_dist, family_rank

# 规则 9 的元素优先级（用户正式确认：秩 > 晶 > 凝/冰 > 沌 > 气 > 焰 > 势 > 流 > 电）
RULE9_PRIORITY = ("O", "X", "C", "K", "A", "F", "P", "W", "L")


def rule9_extra(celem_i, celem_j):
    """规则 9 的 key 分量：结合后各元素数量（按优先级），多者优先（取负）。"""
    return tuple(-(celem_i.get(e, 0) + celem_j.get(e, 0)) for e in RULE9_PRIORITY)


def simulate(atom_list, rng=None):
    """按规则 1~9 跑一锅反应。返回产物分子列表；失败返回 None。

    注：规则 9 之后理论上仍可能有完全并列（同一元素对、结合后元素计数完全相同）；
    实测 T≤9 全量无歧义。若有残留并列，这里按候选顺序取第一个（确定性）。
    rng 参数保留用于 API 兼容（规则 9 下不再需要随机裁决）。
    """
    n = len(atom_list)
    if n == 0:
        return []
    total_val = sum(VAL[e] for e in atom_list)
    if total_val % 2:
        return None
    rem = [VAL[e] for e in atom_list]
    bond = [[0] * n for _ in range(n)]
    adj = [dict() for _ in range(n)]
    dt = [[0] * n for _ in range(n)]
    fam = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            dt[i][j] = dt[j][i] = ptable_dist(atom_list[i], atom_list[j])
            fam[i][j] = fam[j][i] = family_rank(atom_list[i], atom_list[j])

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
        celem = [Counter(atom_list[i] for i in g) for g in groups]
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
                       -(ri + rj), -min(ri, rj),
                       rule9_extra(celem[ci], celem[cj]))
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
        return None
    comp, groups, _ = comps()
    mols = []
    for mem in groups:
        atoms = [atom_list[v] for v in mem]
        edges = []
        for a in range(len(mem)):
            for b in range(a + 1, len(mem)):
                m = bond[mem[a]][mem[b]]
                if m:
                    edges.append((a, b, m))
        mols.append({"atoms": atoms, "edges": edges})
    return mols


if __name__ == "__main__":
    from pot_all import vec_to_atoms, ORDER, formula_of
    # 自检：规则 9 官方自检案例
    cases = [
        ([3, 0, 0, 0, 1, 0, 0, 2, 1], ["O2WA", "OAF"]),   # O3 F A2 W
        ([0, 1, 0, 0, 1, 1, 2, 0, 1], ["WKF", "XLK"]),   # X1 W1 L1 K2 F1
        ([9, 10, 0, 0, 0, 0, 23, 0, 0], ["O9X10K23"]),   # O/X/K 42 原子族
    ]
    for counts, expect in cases:
        mols = simulate(vec_to_atoms(tuple(counts), ORDER))
        got = sorted(formula_of(m["atoms"]) for m in mols) if mols else None
        print(counts, "->", got, "OK" if got == sorted(expect) else "MISMATCH")
