# -*- coding: utf-8 -*-
"""t14c：修正"不同邻居"统计（按原子编号，而非元素符号），精确分类 2 价原子角色"""
import json
from collections import Counter

BASE = r"G:\AI work\deepseek\work1\alchemy"
TRI = {"O", "P", "K"}
ONE = {"C", "L", "F"}
TWO = {"X", "W", "A"}


def cat_of(atoms, inc):
    """inc: [(neighbor_atom_idx, mult), ...]"""
    tags = []
    for j, m in inc:
        tags.append(("T" if atoms[j] in TRI else ("O" if atoms[j] in ONE else "W"), m))
    return tags


def main():
    cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
    one_nb = Counter()
    two_role = Counter()
    mol_all_bridge = 0
    mol_all_caps_on_T = 0
    n = 0
    chain_like = 0
    for rec in cat:
        atoms = rec["atoms"]
        na = len(atoms)
        inc = [[] for _ in range(na)]
        for e in rec["edges"]:
            i, j, m = e[0], e[1], (e[2] if len(e) > 2 else 1)
            inc[i].append((j, m))
            inc[j].append((i, m))
        n += 1
        # 1 价
        for i in range(na):
            if atoms[i] in ONE:
                t = "T" if atoms[inc[i][0][0]] in TRI else ("O" if atoms[inc[i][0][0]] in ONE else "W")
                one_nb[t] += 1
        # 2 价角色
        for i in range(na):
            if atoms[i] in TWO:
                incs = inc[i]
                cls = []
                for j, m in incs:
                    cls.append("T" if atoms[j] in TRI else ("O" if atoms[j] in ONE else "W"))
                if len(incs) == 1:
                    two_role[f"同一{cls[0]}原子 x{incs[0][1]}"] += 1
                elif len(incs) == 2:
                    two_role["+".join(sorted(cls))] += 1
                else:
                    two_role["多邻居"] += 1
        # 分子级：所有 2 价都=桥（两个不同三价邻居）
        if any(a in TRI for a in atoms):
            ok = True
            for i in range(na):
                if atoms[i] in TWO:
                    if len(inc[i]) != 2 or not all(atoms[j] in TRI for j, _ in inc[i]):
                        ok = False
                        break
            if ok:
                mol_all_bridge += 1
            ok2 = True
            for i in range(na):
                if atoms[i] in ONE:
                    if not any(atoms[j] in TRI for j, _ in inc[i]):
                        ok2 = False
                        break
            if ok2:
                mol_all_caps_on_T += 1
    print("物质数:", n)
    print("\n1 价原子邻居价类:", dict(one_nb))
    print("\n2 价原子角色分布:")
    for k, v in two_role.most_common():
        print("  ", k, v)
    print("\n含三价分子中，所有 2 价原子都是纯桥（两端不同三价原子）的分子数:", mol_all_bridge)
    print("所有 1 价原子都接在三价上的分子数:", mol_all_caps_on_T)
    json.dump({"one_nb": dict(one_nb), "two_role": dict(two_role),
               "mol_all_bridge": mol_all_bridge, "mol_all_caps_on_T": mol_all_caps_on_T, "n": n},
              open(BASE + r"\t14c_summary.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\nsaved t14c_summary.json")


if __name__ == "__main__":
    main()
