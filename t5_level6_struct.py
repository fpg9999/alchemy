# -*- coding: utf-8 -*-
"""t5_level6_struct：6 级结束时组件结构统计（模板库、闭环/活跃组件、活跃原子数）。

复用 t5_level6 的 6 级过程逻辑，但返回组件图（元素标号），统计：
- 模板库（用 pot_all.mol_label 规范化）；
- 最大闭环组件（全部 rem=0）大小；
- 单组件最多活跃原子数。
"""
import json
import os
import sys
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
TYPES = ("O", "P", "K")


def level6_components(counts):
    atoms = []
    for e, c in zip(TYPES, counts):
        atoms += [e] * c
    n = len(atoms)
    if n == 0:
        return []
    rem = [3] * n
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

    while True:
        comp, groups, dists = comps()
        csize = [len(g) for g in groups]
        ctypes = [set(atoms[i] for i in g) for g in groups]
        crem = [sum(rem[i] for i in g) for g in groups]
        cands = []
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
                       ti + tj, min(ti, tj), max(ti, tj), -(ri + rj), -min(ri, rj))
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
    comp, groups, _ = comps()
    out = []
    for g in groups:
        gset = set(g)
        idx = {a: k for k, a in enumerate(g)}
        at = [atoms[i] for i in g]
        ed = []
        for a in range(len(g)):
            for b in range(a + 1, len(g)):
                m = bond[g[a]][g[b]]
                if m:
                    ed.append([a, b, m])
        active = sum(1 for i in g if rem[i] > 0)
        out.append({"atoms": at, "edges": ed, "size": len(g), "active": active,
                    "rem_sum": sum(rem[i] for i in g),
                    "label": P.mol_label(at, [tuple(e) for e in ed])})
    return out


def work(args):
    nO, NMAX = args
    max_closed = 0
    max_active = 0
    max_comp = 0
    templates = Counter()
    examples = {}
    for nP in range(NMAX + 1):
        for nK in range(NMAX + 1):
            comps = level6_components((nO, nP, nK))
            for c in comps:
                max_comp = max(max_comp, c["size"])
                if c["active"] == 0:
                    max_closed = max(max_closed, c["size"])
                max_active = max(max_active, c["active"])
                templates[c["label"]] += 1
                if c["label"] not in examples:
                    examples[c["label"]] = {"size": c["size"], "active": c["active"],
                                            "rem_sum": c["rem_sum"],
                                            "formula": "".join(e + (str(c["atoms"].count(e)) if c["atoms"].count(e) > 1 else "")
                                                               for e in P.ORDER if c["atoms"].count(e))}
    return nO, max_closed, max_active, max_comp, dict(templates), examples


def main():
    NMAX = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    jobs = int(sys.argv[2]) if len(sys.argv) > 2 else max(2, (os.cpu_count() or 4) - 2)
    g_closed = g_active = g_comp = 0
    templates = Counter()
    examples = {}
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for nO, mc, ma, mm, tp, exs in ex.map(work, [(nO, NMAX) for nO in range(NMAX + 1)]):
            g_closed = max(g_closed, mc)
            g_active = max(g_active, ma)
            g_comp = max(g_comp, mm)
            templates.update(tp)
            for k, v in exs.items():
                examples.setdefault(k, v)
    top = [(examples[k]["size"], v, examples[k]["active"], examples[k]["formula"])
           for k, v in sorted(templates.items(), key=lambda kv: -examples[kv[0]]["size"])[:20]]
    report = {"NMAX": NMAX, "max_component": g_comp, "max_closed_component": g_closed,
              "max_active_atoms_in_component": g_active,
              "n_templates": len(templates),
              "top_templates": top}
    json.dump(report, open(BASE + r"\t5_level6_struct.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
