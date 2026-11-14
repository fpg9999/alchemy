# -*- coding: utf-8 -*-
"""t17_history_fusion.py
检验「反应历史约束的融合」：对每种物质用它自己的投料( catalog feed )重跑反应，
记录 6 级结束时三价骨架块（T8 的 38 态），再验证终态三价连通块 = 这些 6 级块按后
续 0 级同类三价键"融合"的并集。

输出：t17_history.json（统计 + 例子）
"""
import json
import sys
from collections import Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from pot_all import VAL, CAT, ptable_dist, family_rank
from pot_v3 import rule9_extra
from collections import deque
from counter import Counter  # placeholder

TRI = {"O", "P", "K"}


def simulate_levels(atom_list):
    """按规则 1~9 模拟，返回 (level6_triv_components, final_triv_components, mols)"""
    n = len(atom_list)
    rem = [VAL[e] for e in atom_list]
    bond = [[0] * n for _ in range(n)]
    adj = [dict() for _ in range(n)]
    dt = [[0] * n for _ in range(n)]
    fam = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            dt[i][j] = dt[j][i] = ptable_dist(atom_list[i], atom_list[j])
            fam[i][j] = fam[j][i] = family_rank(atom_list[i], atom_list[j])

    def comps_of(indices=None):
        sel = list(range(n)) if indices is None else indices
        comp = {a: -1 for a in sel}
        groups = []
        for s in sel:
            if comp[s] != -1:
                continue
            cid = len(groups)
            comp[s] = cid
            st = [s]
            mem = [s]
            while st:
                u = st.pop()
                for v in adj[u]:
                    if v in comp and comp[v] == -1:
                        comp[v] = cid
                        st.append(v)
                        mem.append(v)
            groups.append(mem)
        return groups

    def triv_components():
        triv = [i for i in range(n) if atom_list[i] in TRI]
        return comps_of(triv)

    level6 = None
    steps = 0
    while True:
        groups = comps_of()
        csize = [len(g) for g in groups]
        ctypes = [set(atom_list[i] for i in g) for g in groups]
        crem = [sum(rem[i] for i in g) for g in groups]
        celem = [Counter(atom_list[i] for i in g) for g in groups]
        comp = {}
        for ci, g in enumerate(groups):
            for a in g:
                comp[a] = ci
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
                gd = None
                if cross == 0:
                    # 组件内最短距离
                    dd = {i: 0}
                    dq = deque([i])
                    while dq:
                        u = dq.popleft()
                        for v in adj[u]:
                            if v not in dd:
                                dd[v] = dd[u] + 1
                                dq.append(v)
                    gd = dd.get(j, 999)
                else:
                    gd = 999
                ut = len(ctypes[ci] | ctypes[cj])
                ti, tj = len(ctypes[ci]), len(ctypes[cj])
                ri, rj = crem[ci], crem[cj]
                key = (-dt[i][j], -(rem[i] + rem[j]), fam[i][j], cross, gd,
                       min(csize[ci], csize[cj]), -max(csize[ci], csize[cj]), -ut,
                       ti + tj, min(ti, tj), max(ti, tj),
                       -(ri + rj), -min(ri, rj),
                       rule9_extra(celem[ci], celem[cj]))
                cands.append((key, i, j))
        if level6 is None and not any6:
            level6 = [frozenset(g) for g in triv_components()]
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
        steps += 1
    if level6 is None:
        level6 = [frozenset(g) for g in triv_components()]
    final = [frozenset(g) for g in triv_components()]
    ok = (not any(r > 0 for r in rem))
    return level6, final, bond, atom_list, ok


def main():
    cat = json.load(open(r"G:\AI work\deepseek\work1\alchemy\t4_catalog_all_validated.json", encoding="utf-8"))
    print("catalog:", len(cat))
    # 选样例：按三价类型分层 + 指定公式
    import random
    rng = random.Random(7)
    picks = []
    bytype = {}
    for r in cat:
        trs = frozenset(a for a in r["atoms"] if a in TRI)
        bytype.setdefault(trs, []).append(r)
    for trs, lst in bytype.items():
        picks += rng.sample(lst, min(15, len(lst)))
    # 指定有趣公式
    want = {"O3P", "O2CK", "O2K4", "O2K6", "O2P6", "O5P5K2", "O3KA2", "CP2K3"}
    for r in cat:
        if r["formula"] in want:
            r = dict(r)
            r["_want"] = True
            picks.append(r)
    print("samples:", len(picks))

    stats = Counter()
    examples = []
    for r in picks:
        feed = r.get("feed")
        if not feed:
            stats["no_feed"] += 1
            continue
        ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]
        atoms = [s for s, c in zip(ORDER, feed) for _ in range(c)]
        try:
            level6, final, bond, ats, ok = simulate_levels(atoms)
        except Exception as e:
            stats["error"] += 1
            continue
        # 验证：每个 final 组件 = 若干 level6 组件并集
        bad = 0
        fusion = Counter()
        for fc in final:
            blocks = [lc for lc in level6 if lc <= fc]
            if not blocks:
                bad += 1
            # 覆盖检查
            cover = set()
            for b in blocks:
                cover |= b
            if cover != set(fc):
                bad += 1
            fusion[len(blocks)] += 1
        stats["ok" if bad == 0 else "bad"] += 1
        if len(examples) < 12:
            examples.append({"formula": r["formula"], "feed": feed,
                             "level6_blocks": [sorted(x) for x in level6],
                             "final_components": [sorted(x) for x in final],
                             "fusion_arity": dict(fusion), "bad": bad})
    print("stats:", dict(stats))
    json.dump({"stats": dict(stats), "examples": examples},
              open(r"G:\AI work\deepseek\work1\alchemy\t17_history.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t17_history.json")


if __name__ == "__main__":
    main()
