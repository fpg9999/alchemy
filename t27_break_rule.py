# -*- coding: utf-8 -*-
"""t27_break_rule.py：自然环境分解规则
- 键稳定性：元素周期表距离越小越不稳定；距离相同则键级越高越不稳定。
- 一次自然反应：在体系中找出最不稳定的键类 (距离 d, 键级 m)（d 最小，m 最大），
  所有带该类键的分子把该类键全部断开（没有该键的分子不分解）；
  然后所有当前碎片按大锅规则重新结合（已保留的键不动，只补新键）。
- 分析：结果是否还是原物质？是否产生新物质？是否循环？
"""
import json
import sys
from collections import Counter, defaultdict, deque
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
from pot_v3 import rule9_extra

BASE = r"G:\AI work\deepseek\work1\alchemy"
VAL = P.VAL
ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]
TRI = {"O", "P", "K"}


def formula(atoms):
    c = Counter(atoms)
    return "".join(s + (str(c[s]) if c[s] > 1 else "") for s in ORDER if c[s])


def wake(atom_list, edges):
    n = len(atom_list)
    bond = [[0] * n for _ in range(n)]
    for e in edges:
        i, j, m = e[0], e[1], (e[2] if len(e) > 2 else 1)
        bond[i][j] = bond[j][i] = m
    dt = [[0] * n for _ in range(n)]
    fam = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            dt[i][j] = dt[j][i] = P.ptable_dist(atom_list[i], atom_list[j])
            fam[i][j] = fam[j][i] = P.family_rank(atom_list[i], atom_list[j])
    return bond, dt, fam


def components(n, bond):
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
                if bond[u][v] > 0 and comp[v] == -1:
                    comp[v] = cid
                    st.append(v)
                    mem.append(v)
        groups.append(mem)
    return comp, groups


def dists(n, bond, comp, groups):
    d = [[999] * n for _ in range(n)]
    for mem in groups:
        for s in mem:
            d[s][s] = 0
            dq = deque([s])
            while dq:
                u = dq.popleft()
                for v in range(n):
                    if bond[u][v] > 0 and d[s][v] == 999:
                        d[s][v] = d[s][u] + 1
                        dq.append(v)
    return d


def break_worst(atom_list, bond, dt):
    """返回被断裂的键类与断裂后的 bond"""
    worst = None
    for i in range(len(atom_list)):
        for j in range(i + 1, len(atom_list)):
            m = bond[i][j]
            if m > 0:
                key = (dt[i][j], -m)
                if worst is None or key < worst:
                    worst = key
    if worst is None:
        return None, 0
    d, negm = worst
    mclass = -negm
    cnt = 0
    for i in range(len(atom_list)):
        for j in range(i + 1, len(atom_list)):
            if bond[i][j] == mclass and dt[i][j] == d:
                bond[i][j] = bond[j][i] = 0
                cnt += 1
    return (d, mclass), cnt


def recombine(atom_list, bond, dt, fam):
    n = len(atom_list)
    rem = [VAL[atom_list[i]] - sum(bond[i]) for i in range(n)]
    # 贪心按大锅规则
    steps = 0
    while True:
        comp, groups = components(n, bond)
        d = dists(n, bond, comp, groups)
        sizes = [len(g) for g in groups]
        ctypes = [set(atom_list[i] for i in g) for g in groups]
        crem = [sum(rem[i] for i in g) for g in groups]
        celem = [Counter(atom_list[i] for i in g) for g in groups]
        best = None
        for i in range(n):
            if rem[i] == 0:
                continue
            for j in range(i + 1, n):
                if rem[j] == 0 or bond[i][j] >= 3:
                    continue
                cross = 0 if comp[i] == comp[j] else 1
                gd = d[i][j] if cross == 0 else 999
                ut = len(ctypes[comp[i]] | ctypes[comp[j]])
                ti, tj = len(ctypes[comp[i]]), len(ctypes[comp[j]])
                ri, rj = crem[comp[i]], crem[comp[j]]
                key = (-dt[i][j], -(rem[i] + rem[j]), fam[i][j], cross, gd,
                       min(sizes[comp[i]], sizes[comp[j]]), -max(sizes[comp[i]], sizes[comp[j]]),
                       -ut, ti + tj, min(ti, tj), max(ti, tj), -(ri + rj), -min(ri, rj),
                       rule9_extra(celem[comp[i]], celem[comp[j]]))
                if best is None or key < best[0]:
                    best = (key, i, j)
        if best is None:
            break
        _, i, j = best
        bond[i][j] += 1
        bond[j][i] += 1
        rem[i] -= 1
        rem[j] -= 1
        steps += 1
    comp, groups = components(n, bond)
    prods = []
    for mem in groups:
        ats = [atom_list[i] for i in mem]
        es = []
        local = {g: k for k, g in enumerate(mem)}
        for a in range(len(mem)):
            for b in range(a + 1, len(mem)):
                m = bond[mem[a]][mem[b]]
                if m:
                    es.append((local[mem[a]], local[mem[b]], m))
        prods.append({"atoms": ats, "edges": es, "formula": formula(ats)})
    ok = all(r == 0 for r in rem)
    return prods, ok, steps


def react(system):
    """system: list of (atoms, edges) molecules"""
    atom_list = []
    edges = []
    for atoms, es in system:
        off = len(atom_list)
        atom_list += atoms
        for e in es:
            edges.append((e[0] + off, e[1] + off, e[2] if len(e) > 2 else 1))
    bond, dt, fam = wake(atom_list, edges)
    cls, nbrk = break_worst(atom_list, bond, dt)
    prods, ok, steps = recombine(atom_list, bond, dt, fam)
    return {"class": cls, "broken": nbrk, "ok": ok, "products": prods,
            "steps": steps, "formula_in": sorted(formula(a) for a, _ in system)}


def main():
    cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
    small = [r for r in cat if len(r["atoms"]) <= 8 and r.get("place")]
    byform = {r["formula"]: r for r in cat}
    cat_formula = set(byform)
    stats = Counter()
    examples = []
    for rec in small:
        atoms = rec["atoms"]
        edges = [tuple(e) for e in rec["edges"]]
        out = react([(atoms, edges)])
        prod_forms = sorted(p["formula"] for p in out["products"])
        stats["物质数"] += 1
        if out["class"] is None:
            stats["无键可断"] += 1
            continue
        stats["断裂事件"] += 1
        d, m = out["class"]
        stats[f"最不稳定类 d={d},m={m}"] += 1
        if not out["ok"]:
            stats["重结合失败"] += 1
            continue
        if prod_forms == [rec["formula"]]:
            stats["变回自身"] += 1
        else:
            stats["变成别的物质"] += 1
            new = [f for f in prod_forms if f not in cat_formula]
            if new:
                stats["含目录外新分子式"] += 1
                if len(examples) < 15:
                    examples.append({"in": rec["formula"], "class": out["class"],
                                     "broken": out["broken"], "out": prod_forms,
                                     "new": new})
    print("小物质:", stats["物质数"])
    for k, v in stats.items():
        if k != "物质数":
            print(f"  {k}: {v}")
    print("\n变化例子:")
    for e in examples:
        print(" ", e)
    json.dump({"stats": dict(stats), "examples": examples},
              open(BASE + r"\t27_break_rule.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t27_break_rule.json")


if __name__ == "__main__":
    main()
