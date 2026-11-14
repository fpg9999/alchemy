# -*- coding: utf-8 -*-
"""t20_divalent_stats.py：统计二价元素（X/W/A）在全部 84,225 种物质里的存在形式
- 角色分类（按两个邻居的价类/是否同一三价骨架块/多重键）
- 每个二价元素参与的键型（S/C/L，来自实际摆放坐标）
"""
import json
from collections import Counter, defaultdict

BASE = r"G:\AI work\deepseek\work1\alchemy"
TRI = {"O", "P", "K"}
ONE = {"C", "L", "F"}
TWO = {"X", "W", "A"}
EDGE = {(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)}
CORN = {(1, 1), (2, -1), (1, -2), (-1, -1), (-2, 1), (-1, 2)}
LONG = {(2 * a, 2 * b) for (a, b) in EDGE}


def rel_type(dq, dr):
    if (dq, dr) in EDGE:
        return "S"
    if (dq, dr) in CORN:
        return "C"
    if (dq, dr) in LONG:
        return "L"
    return "?"


def to_axial(xy):
    # catalog place 本身就是 axial 坐标
    return (int(xy[0]), int(xy[1]))


def main():
    cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
    roles = Counter()
    roles_by_el = defaultdict(Counter)
    bond_types = Counter()          # (element, other_class) -> Counter(type)
    bond_type_by_el = defaultdict(Counter)
    mol_role_patterns = Counter()
    no_triv = Counter()
    n_atoms_two = Counter()
    for rec in cat:
        atoms = rec["atoms"]
        n = len(atoms)
        place = {}
        if rec.get("place"):
            for k, v in rec["place"].items():
                place[int(k)] = to_axial(tuple(v))
        inc = [[] for _ in range(n)]
        for e in rec["edges"]:
            i, j, m = e[0], e[1], (e[2] if len(e) > 2 else 1)
            inc[i].append((j, m))
            inc[j].append((i, m))
        # 三价连通块（诱导子图）
        triv = [i for i in range(n) if atoms[i] in TRI]
        tcomp = {}
        cid = 0
        for s in triv:
            if s in tcomp:
                continue
            st = [s]
            tcomp[s] = cid
            while st:
                u = st.pop()
                for v, m in inc[u]:
                    if atoms[v] in TRI and v not in tcomp:
                        tcomp[v] = cid
                        st.append(v)
            cid += 1
        has_triv = bool(triv)
        if not has_triv:
            # 无三价：按拓扑分类
            deg = [len(inc[i]) for i in range(n)]
            # 环：边数>=点数
            if len(rec["edges"]) >= n:
                no_triv["环"] += 1
            elif all(atoms[i] in ONE for i in range(n)):
                no_triv["一价二聚"] += 1
            elif all(atoms[i] in TWO for i in range(n)) and n == 2:
                no_triv["二价二聚"] += 1
            else:
                no_triv["端帽链"] += 1
        pattern = []
        for i in range(n):
            if atoms[i] not in TWO:
                continue
            n_atoms_two[atoms[i]] += 1
            neigh = inc[i]
            cls = []
            for j, m in neigh:
                cls.append("T" if atoms[j] in TRI else ("O" if atoms[j] in ONE else "W"))
            # 角色
            if len(neigh) == 1:
                role = f"同一{cls[0]}原子 x{neigh[0][1]}"
            elif len(neigh) == 2 and cls[0] == "T" and cls[1] == "T" and neigh[0][0] != neigh[1][0]:
                same = (tcomp.get(neigh[0][0]) == tcomp.get(neigh[1][0]))
                role = "真桥(跨块)" if not same else "骨架内桥"
            elif len(neigh) == 2:
                role = "+".join(sorted(cls))
            else:
                role = "多邻居"
            roles[role] += 1
            roles_by_el[atoms[i]][role] += 1
            pattern.append(role)
            # 键型统计（用摆放坐标）
            if place and i in place:
                for j, m in neigh:
                    if j in place:
                        dq = place[j][0] - place[i][0]
                        dr = place[j][1] - place[i][1]
                        t = rel_type(dq, dr)
                        other = "T" if atoms[j] in TRI else ("O" if atoms[j] in ONE else "W")
                        bond_types[(atoms[i], other, t)] += m
                        bond_type_by_el[atoms[i]][t] += m
        mol_role_patterns["+".join(sorted(set(pattern)))] += 1
    print("二价原子数:", dict(n_atoms_two))
    print("\n角色总表:")
    for k, v in roles.most_common():
        print(f"  {k}: {v}")
    print("\n按元素（X/W/A）:")
    for el in ("X", "W", "A"):
        print(f"  [{el}] {dict(roles_by_el[el].most_common())}")
    print("\n键型（元素→键型）:")
    for el in ("X", "W", "A"):
        print(f"  [{el}] {dict(bond_type_by_el[el])}")
    print("\n(二价元素, 另一端类别, 键型):")
    for k, v in sorted(bond_types.items(), key=lambda kv: -kv[1])[:20]:
        print("  ", k, v)
    print("\n无三价物质形态:", dict(no_triv))
    json.dump({"roles": dict(roles), "roles_by_el": {k: dict(v) for k, v in roles_by_el.items()},
               "bond_type_by_el": {k: dict(v) for k, v in bond_type_by_el.items()},
               "bond_types": {str(k): v for k, v in bond_types.items()},
               "no_triv": dict(no_triv), "n_atoms_two": dict(n_atoms_two)},
              open(BASE + r"\t20_roles.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\nsaved t20_roles.json")


if __name__ == "__main__":
    main()
