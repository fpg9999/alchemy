# -*- coding: utf-8 -*-
"""t28_rule_v2.py：自然环境分解规则 v2
规则：
- 键不稳定度：元素周期距离 d 越小越不稳定；d 相同时键级 m 越高越不稳定；
  可选第三级：按端元原子价数，低价的键先断（1价元素 > 2价元素 > 3价元素）。
- 一次事件：全局选最不稳定类 (d,m,v)；每条"该类的元素对"最多断 1 根键。
- 断键后所有分子（含未断者）按大锅规则 1~9 重结合；已保留键固定。
- 产物必须价数填满且几何可摆放；否则视为失败 → 不反应（原样返回）。
- 能量（可选）：拆 1 根键耗 1 能量；地图 1 单位 = 3 格（标准三元骨架三角形），每单位储能可配置。
"""
import json
import sys
from collections import Counter, deque
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v2
from pot_v3 import rule9_extra

BASE = r"G:\AI work\deepseek\work1\alchemy"
VAL = P.VAL
ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]


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


def dists(n, bond, groups):
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


def select_class(atom_list, bond, dt, use_valence=True):
    best = None
    for i in range(len(atom_list)):
        for j in range(i + 1, len(atom_list)):
            m = bond[i][j]
            if m <= 0:
                continue
            v = min(VAL[atom_list[i]], VAL[atom_list[j]]) if use_valence else 0
            key = (dt[i][j], -m, v)
            if best is None or key < best:
                best = key
    return best


def break_class(atom_list, bond, dt, cls, use_valence=True):
    d, negm, v = cls
    mclass = -negm
    broken = 0
    for i in range(len(atom_list)):
        for j in range(i + 1, len(atom_list)):
            if bond[i][j] != mclass or dt[i][j] != d:
                continue
            if use_valence and min(VAL[atom_list[i]], VAL[atom_list[j]]) != v:
                continue
            # 每对元素最多断 1 根
            bond[i][j] -= 1
            bond[j][i] -= 1
            broken += 1
    return broken


def recombine(atom_list, bond, dt, fam):
    n = len(atom_list)
    rem = [VAL[atom_list[i]] - sum(bond[i]) for i in range(n)]
    while True:
        comp, groups = components(n, bond)
        d = dists(n, bond, groups)
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
    comp, groups = components(n, bond)
    prods = []
    for mem in groups:
        local = {g: k for k, g in enumerate(mem)}
        ats = [atom_list[i] for i in mem]
        es = []
        for a in range(len(mem)):
            for b in range(a + 1, len(mem)):
                m = bond[mem[a]][mem[b]]
                if m:
                    es.append((local[mem[a]], local[mem[b]], m))
        prods.append({"atoms": ats, "edges": es, "formula": formula(ats)})
    ok = all(r == 0 for r in rem)
    return prods, ok


def validate_products(prods, max_nodes=200000):
    for p in prods:
        place = pot_v2.embed_mol2(p["atoms"], [tuple(e) for e in p["edges"]],
                                  max_nodes=max_nodes)
        if place is None:
            return False
        ok, msg = pot_v2.validate_place(place, p["atoms"], [tuple(e) for e in p["edges"]])
        if not ok:
            return False
        p["place"] = {str(k): list(v) for k, v in place.items()}
    return True


def react_v2(system, use_valence=True, check_geometry=True, energy=False,
             unit_atoms=3.0, storage_per_unit=1.0):
    atom_list = []
    edges = []
    for atoms, es in system:
        off = len(atom_list)
        atom_list += atoms
        for e in es:
            edges.append((e[0] + off, e[1] + off, e[2] if len(e) > 2 else 1))
    bond, dt, fam = wake(atom_list, edges)
    cls = select_class(atom_list, bond, dt, use_valence)
    if cls is None:
        return {"changed": False, "reason": "无键", "class": None}
    # 能量检查（按整个体系总大小）
    if energy:
        # 先数该类键（每元素对断 1 根）
        d, negm, v = cls
        mclass = -negm
        cost = 0
        for i in range(len(atom_list)):
            for j in range(i + 1, len(atom_list)):
                if bond[i][j] == mclass and dt[i][j] == d and \
                   (not use_valence or min(VAL[atom_list[i]], VAL[atom_list[j]]) == v):
                    cost += 1
        avail = len(atom_list) / unit_atoms * storage_per_unit
        if cost > avail:
            return {"changed": False, "reason": "能量不足", "class": cls,
                    "cost": cost, "avail": round(avail, 2)}
    broken = break_class(atom_list, bond, dt, cls, use_valence)
    if broken == 0:
        return {"changed": False, "reason": "无该类键", "class": cls}
    prods, ok = recombine(atom_list, bond, dt, fam)
    if not ok:
        return {"changed": False, "reason": "重结合失败", "class": cls}
    if check_geometry:
        okg = validate_products(prods)
        if not okg:
            return {"changed": False, "reason": "几何不合法", "class": cls}
    return {"changed": True, "class": cls, "broken": broken, "products": prods}


def to_system(rec):
    return (list(rec["atoms"]), [tuple(e) for e in rec["edges"]])


def main():
    cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
    small = [r for r in cat if 2 <= len(r["atoms"]) <= 8 and r.get("place")]
    print("小物质:", len(small))
    # 单分子
    same = diff = fails = 0
    for rec in small:
        out = react_v2([to_system(rec)], check_geometry=False)
        if not out["changed"]:
            fails += 1
        else:
            if [p["formula"] for p in out["products"]] == [rec["formula"]]:
                same += 1
            else:
                diff += 1
    print("单分子: 复原", same, "变化", diff, "失败/不反应", fails)
    # 分子对（无几何）
    rng = __import__("random").Random(7)
    import random
    stats = Counter()
    examples = []
    for _ in range(500):
        a, b = rng.sample(small, 2)
        out = react_v2([to_system(a), to_system(b)], check_geometry=False)
        if not out["changed"]:
            stats["不反应"] += 1
        else:
            stats["反应"] += 1
            forms = sorted(p["formula"] for p in out["products"])
            if forms == sorted([a["formula"], b["formula"]]):
                stats["复原"] += 1
            else:
                stats["变化"] += 1
                if any(p["formula"] not in {r["formula"] for r in cat} for p in out["products"]):
                    stats["含新分子式"] += 1
                if len(examples) < 10:
                    examples.append({"A": a["formula"], "B": b["formula"],
                                     "class": out["class"], "out": forms})
    print("分子对:", dict(stats))
    for e in examples:
        print(" ", e)
    json.dump({"single": {"same": same, "diff": diff, "fails": fails},
               "pairs": dict(stats), "examples": examples},
              open(BASE + r"\t28_rule_v2.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t28_rule_v2.json")


if __name__ == "__main__":
    main()
