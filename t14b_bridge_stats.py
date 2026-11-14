# -*- coding: utf-8 -*-
"""t14b：修正多重键邻居统计 + 更细的桥/端帽分类"""
import itertools
import json
from collections import Counter

BASE = r"G:\AI work\deepseek\work1\alchemy"
TRI = {"O", "P", "K"}
VAL = {"O": 3, "X": 2, "C": 1, "P": 3, "W": 2, "L": 1, "K": 3, "A": 2, "F": 1}
ONE = {"C", "L", "F"}
TWO = {"X", "W", "A"}


def cls_of(atoms, adj, i):
    nb = [atoms[j] for j in adj[i]]
    # 按邻居的价类：T(三价), W(二价), O(一价)
    tags = ["T" if x in TRI else ("O" if x in ONE else "W") for x in nb]
    return "+".join(sorted(tags))


def main():
    cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
    one_stats = Counter()
    two_stats = Counter()
    two_distinct = Counter()
    mol_bridge_ok = 0
    mol_cap_ok = 0
    mol_all_caps_ok = 0
    n = 0
    for rec in cat:
        atoms = rec["atoms"]
        n_atoms = len(atoms)
        adj = [[] for _ in range(n_atoms)]
        for e in rec["edges"]:
            i, j, m = e[0], e[1], (e[2] if len(e) > 2 else 1)
            for _ in range(m):
                adj[i].append(j)
                adj[j].append(i)
        n += 1
        # 1 价邻居
        for i in range(n_atoms):
            if atoms[i] in ONE:
                one_stats[cls_of(atoms, adj, i)] += 1
        # 2 价：按"不同邻居的价类组合"
        for i in range(n_atoms):
            if atoms[i] in TWO:
                nb = set(atoms[j] for j in adj[i])
                tags = set("T" if x in TRI else ("O" if x in ONE else "W") for x in nb)
                two_distinct["+".join(sorted(tags))] += 1
                two_stats[cls_of(atoms, adj, i)] += 1
        # 分子级：所有 2 价原子都必须"接两个不同三价原子"（纯桥）
        if any(a in TRI for a in atoms):
            ok_bridge = True
            for i in range(n_atoms):
                if atoms[i] in TWO:
                    nb = set(atoms[j] for j in adj[i])
                    if len(nb) != 2 or not all(x in TRI for x in nb):
                        ok_bridge = False
                        break
            if ok_bridge:
                mol_bridge_ok += 1
            # 所有 1 价原子都接在三价骨架上？
            ok_cap = True
            for i in range(n_atoms):
                if atoms[i] in ONE:
                    if not any(atoms[j] in TRI for j in adj[i]):
                        ok_cap = False
                        break
            if ok_cap:
                mol_all_caps_ok += 1
    print("物质数:", n)
    print("\n1 价原子（按邻居价类，多重键展开）:")
    for k, v in one_stats.most_common():
        print("  ", k, v)
    print("\n2 价原子（按邻居价类序列，多重键展开）:")
    for k, v in two_stats.most_common():
        print("  ", k, v)
    print("\n2 价原子（按不同邻居的价类组合）:")
    for k, v in two_distinct.most_common():
        print("  ", k, v)
    print("\n含三价分子中：所有 2 价原子都=纯桥（接两个不同三价原子）的分子数:", mol_bridge_ok)
    print("所有 1 价原子都接在三价原子上的分子数:", mol_all_caps_ok)
    json.dump({"one_stats": dict(one_stats), "two_stats": dict(two_stats),
               "two_distinct": dict(two_distinct),
               "mol_bridge_ok": mol_bridge_ok, "mol_all_caps_ok": mol_all_caps_ok,
               "n": n},
              open(BASE + r"\t14b_summary.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\nsaved t14b_summary.json")


if __name__ == "__main__":
    main()
