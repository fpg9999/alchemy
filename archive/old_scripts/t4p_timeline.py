# -*- coding: utf-8 -*-
"""t4p_timeline：记录反应过程中每根键后的组件大小，重点是各"距离级别"结束时的组件结构。"""
import sys
from collections import Counter
from collections import deque
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P


def run_timeline(elems, feed, verbose=True):
    atom_list = P.vec_to_atoms(tuple(feed), elems)
    n = len(atom_list)
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

    events = []
    cur_level = None
    level_snapshots = {}
    step = 0
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
        d = dt[i][j]
        if d != cur_level:
            if cur_level is not None:
                sizes = sorted([len(g) for g in groups], reverse=True)
                level_snapshots[cur_level] = {"sizes": sizes, "ncomp": len(groups),
                                              "rem_hist": dict(Counter(rem))}
            cur_level = d
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
        events.append((step, d, atom_list[i], atom_list[j], cur_level))
        step += 1
    comp, groups, dists = comps()
    sizes = sorted([len(g) for g in groups], reverse=True)
    level_snapshots[("end",)] = {"sizes": sizes, "ncomp": len(groups),
                                 "rem_hist": dict(Counter(rem))}
    if verbose:
        print(f"feed={dict(zip(elems,feed))} n={n} bonds={len(events)}")
        for k, v in level_snapshots.items():
            print(f"  level {k} 结束时: 组件数={v['ncomp']} 大小={v['sizes']} rem分布={v['rem_hist']}")
        # 每级事件数
        lv = Counter(e[1] for e in events)
        print(f"  各距离键数: {dict(sorted(lv.items(), reverse=True))}")
    return events, level_snapshots, (bond, adj, atom_list, comp, groups)


if __name__ == "__main__":
    cases = [
        (["O", "X", "K"], (18, 20, 46)),
        (["O", "X", "K"], (9, 10, 23)),
        (["O", "X", "K"], (27, 30, 69)),
        (["O", "X", "K"], (72, 80, 184)),
        (["O", "K"], (24, 16)),
        (["O", "X", "C"], (10, 15, 20)),
    ]
    for elems, feed in cases:
        run_timeline(elems, feed)
        print()
