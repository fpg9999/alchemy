# -*- coding: utf-8 -*-
"""t8_analyze.py：形态规律校验 + 紧凑表格"""
import json
from collections import Counter, defaultdict

BASE = r"G:\AI work\deepseek\work1\alchemy"


def rel_type(dd):
    EDGE = {(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)}
    CORN = {(1, 1), (2, -1), (1, -2), (-1, -1), (-2, 1), (-1, 2)}
    LONG = {(2 * a, 2 * b) for (a, b) in EDGE}
    if dd in EDGE:
        return "S"
    if dd in CORN:
        return "C"
    if dd in LONG:
        return "L"
    return None


forms = json.load(open(BASE + r"\t8_forms.json", encoding="utf-8"))
print("总形态数:", len(forms))
bad_active = []
bad_closed = []
bond_stats = defaultdict(Counter)
for f in forms:
    atoms = f["atoms"]
    rems = f["rems"]
    edges = [tuple(e) for e in f["edges"]]
    place = {int(k): tuple(v) for k, v in f["place"].items()}
    # 1) 活跃原子类型单一?
    act_types = set(atoms[i] for i in range(len(atoms)) if rems[i] > 0)
    if len(act_types) > 1:
        bad_active.append((f["formula"], act_types))
    # 2) 闭合原子(rem=0)组成的连通块是否都是"2原子三键二聚体"
    closed = [i for i in range(len(atoms)) if rems[i] == 0]
    # 并查集
    par = {i: i for i in closed}

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    es = {}
    for (i, j, m) in edges:
        if i in par and j in par:
            par[find(i)] = find(j)
            es[(i, j)] = m
    groups = defaultdict(list)
    for i in closed:
        groups[find(i)].append(i)
    for g in groups.values():
        if len(g) == 2:
            m = es.get((min(g), max(g))) or es.get((max(g), min(g))) or 0
            ok = (m == 3)
        else:
            ok = False
        if not ok:
            bad_closed.append((f["formula"], len(g)))
    # 3) 键型统计
    for (i, j, m) in edges:
        dd = (place[j][0] - place[i][0], place[j][1] - place[i][1])
        bond_stats[f["types"]][rel_type(dd)] += m

print("活跃原子类型不单一的形态:", bad_active if bad_active else "无（全部单一）")
print("闭合原子块不是二聚体(2原子三键)的:", bad_closed if bad_closed else "无（全部为二聚体）")

for types in ["OP", "KO", "KP", "KOP"]:
    sub = [f for f in forms if f["types"] == types]
    sub.sort(key=lambda x: (x["size"], x["formula"]))
    print(f"\n===== {types} （{len(sub)} 种）键型统计 {dict(bond_stats[types])} =====")
    for f in sub:
        rem1 = all(r == 1 for r in f["rems"] if r > 0)
        rd = ",".join(f"{k}x{v}" for k, v in sorted(f["rem_dist"].items()))
        print(f"  {f['formula']:10s} size={f['size']:2d} active={f['active']:2d} rem={rd:14s} "
              f"{'★全rem=1' if rem1 else '  (含rem2)'}  pools={f['pools']}")
