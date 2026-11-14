# -*- coding: utf-8 -*-
"""t5_levelbounds：记录"每一级键处理完后"的组件大小（随机/大投料），看各层级边界组件是否随规模增长。

用于判断 L3 缺口的形态：如果某一级边界组件随 T 增长，则说明有界性必须在更低的级别上被动力学压住。
"""
import json
import random
import sys
import time
from collections import deque

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def run_levels(atoms):
    """跑完整反应，返回每个 distance 级结束后的 (最大组件, 组件数, 总原子)。"""
    n = len(atoms)
    rem = [P.VAL[e] for e in atoms]
    bond = [[0] * n for _ in range(n)]
    adj = [dict() for _ in range(n)]
    dt = [[0] * n for _ in range(n)]
    fam = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            dt[i][j] = dt[j][i] = P.ptable_dist(atoms[i], atoms[j])
            fam[i][j] = fam[j][i] = P.family_rank(atoms[i], atoms[j])

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

    snaps = {}
    prev_level = None
    while True:
        comp, groups, dists = comps()
        maxlev = 0
        for i in range(n):
            if rem[i] == 0:
                continue
            for j in range(i + 1, n):
                if rem[j] > 0 and bond[i][j] < 3:
                    maxlev = max(maxlev, dt[i][j])
        if maxlev != prev_level:
            if prev_level is not None:
                sizes = [len(g) for g in groups]
                snaps[prev_level] = (max(sizes) if sizes else 0, len(sizes))
            prev_level = maxlev
        if maxlev == 0:
            # 全部为 0 级，继续跑完
            pass
        # 收集候选（当前最大距离层）
        cands = []
        for i in range(n):
            if rem[i] == 0:
                continue
            for j in range(i + 1, n):
                if rem[j] == 0 or bond[i][j] >= 3:
                    continue
                if dt[i][j] != maxlev:
                    continue
                ci, cj = comp[i], comp[j]
                cross = 0 if ci == cj else 1
                gd = dists[ci][i].get(j) if cross == 0 else 999
                ut = len(set(atoms[x] for x in groups[ci]) | set(atoms[x] for x in groups[cj]))
                ti = len(set(atoms[x] for x in groups[ci]))
                tj = len(set(atoms[x] for x in groups[cj]))
                ri = sum(rem[x] for x in groups[ci])
                rj = sum(rem[x] for x in groups[cj])
                key = (-dt[i][j], -(rem[i] + rem[j]), fam[i][j], cross, gd,
                       min(len(groups[ci]), len(groups[cj])), -max(len(groups[ci]), len(groups[cj])),
                       -ut, ti + tj, min(ti, tj), max(ti, tj), -(ri + rj), -min(ri, rj))
                cands.append((key, i, j))
        if not cands:
            # 记录当前层级边界
            sizes = [len(g) for g in groups]
            if prev_level is not None:
                snaps[prev_level] = (max(sizes) if sizes else 0, len(sizes))
            break
        _, i, j = min(cands, key=lambda t: t[0])
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        adj[i][j] = adj[i].get(j, 0) + 1
        adj[j][i] = adj[j].get(i, 0) + 1
    comp, groups, _ = comps()
    sizes = [len(g) for g in groups]
    final = (max(sizes) if sizes else 0, len(sizes))
    return snaps, final


def main():
    rng = random.Random(2026)
    out = []
    for T in (24, 48, 96, 192):
        for trial in range(3):
            counts = [0] * 9
            for _ in range(T):
                counts[rng.randrange(9)] += 1
            atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
            if sum(P.VAL[e] for e in atoms) % 2:
                counts[rng.randrange(9)] += 1
                atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
            t0 = time.time()
            snaps, final = run_levels(atoms)
            rec = {"T": len(atoms), "feed": counts, "final": final,
                   "boundaries": {str(k): v for k, v in sorted(snaps.items(), reverse=True)}}
            out.append(rec)
            print(f"T={len(atoms)} final={final} boundaries={rec['boundaries']} ({time.time()-t0:.1f}s)", flush=True)
    json.dump(out, open(BASE + r"\t5_levelbounds.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved")


if __name__ == "__main__":
    main()
