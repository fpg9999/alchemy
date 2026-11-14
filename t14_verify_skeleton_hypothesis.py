# -*- coding: utf-8 -*-
"""t14_verify_skeleton_hypothesis.py
检验假说：所有物质 = 45 种骨架（3 无三价 + 7 单三价 + 35 双/三三价）
           + 二价元素作桥梁连接 + 一价元素作端帽。
统计：
1) 价数校验：每个原子的键数=价数
2) 三价诱导子图的连通块类型（按三价元素种类分组），与 3/7/35 对照
3) 1 价原子邻居类型；2 价原子邻居类型（是否在"桥"位置）
4) 分子中"2 价只在桥/链位置、1 价只在端帽位置"的比例
"""
import itertools
import json
import sys
from collections import Counter, defaultdict

BASE = r"G:\AI work\deepseek\work1\alchemy"
TRI = {"O", "P", "K"}
VAL = {"O": 3, "X": 2, "C": 1, "P": 3, "W": 2, "L": 1, "K": 3, "A": 2, "F": 1}
ONE = {"C", "L", "F"}
TWO = {"X", "W", "A"}


def canon(n, mult):
    if n <= 7:
        best = None
        for p in itertools.permutations(range(n)):
            s = []
            for a in range(n):
                for b in range(a + 1, n):
                    if mult[p[a]][p[b]]:
                        s.append((a, b, mult[p[a]][p[b]]))
            k = tuple(sorted(s))
            if best is None or k < best:
                best = k
        return ("exact", best)
    degs = tuple(sorted(sum(mult[i]) for i in range(n)))
    es = tuple(sorted(mult[i][j] for i in range(n) for j in range(i + 1, n) if mult[i][j]))
    return ("invar", degs, es)


def main():
    cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
    print("物质数:", len(cat), flush=True)
    stats = Counter()
    forms = defaultdict(Counter)     # triv-type-set -> canonical component forms
    one_nb = Counter()
    two_nb = Counter()
    strict_ok = 0
    strict_fail = Counter()
    max_comp = 0
    bad_val = 0
    for rec in cat:
        atoms = rec["atoms"]
        n = len(atoms)
        adj = [[] for _ in range(n)]
        mult = [[0] * n for _ in range(n)]
        for e in rec["edges"]:
            i, j, m = e[0], e[1], (e[2] if len(e) > 2 else 1)
            mult[i][j] += m
            mult[j][i] += m
            adj[i].append(j)
            adj[j].append(i)
        deg = [sum(mult[i]) for i in range(n)]
        for i in range(n):
            if deg[i] != VAL[atoms[i]]:
                bad_val += 1
        triv = [i for i in range(n) if atoms[i] in TRI]
        tset = "".join(sorted({atoms[i] for i in triv}))
        stats["triv_" + (tset or "none")] += 1
        # 三价诱导子图连通块
        seen = [False] * n
        comps = []
        for s in triv:
            if seen[s]:
                continue
            st = [s]
            seen[s] = True
            mem = [s]
            while st:
                u = st.pop()
                for v in adj[u]:
                    if atoms[v] in TRI and not seen[v]:
                        seen[v] = True
                        st.append(v)
                        mem.append(v)
            comps.append(mem)
        for mem in comps:
            max_comp = max(max_comp, len(mem))
            idx = {a: k for k, a in enumerate(mem)}
            sub = [[mult[a][b] for b in mem] for a in mem]
            forms[tset][canon(len(mem), sub)] += 1
        # 1 价原子邻居
        for i in range(n):
            if atoms[i] in ONE:
                nb = [atoms[j] for j in adj[i]]
                one_nb["+".join(sorted(nb))] += 1
        # 2 价原子邻居类型
        for i in range(n):
            if atoms[i] in TWO:
                nb = [atoms[j] for j in adj[i]]
                cls = []
                for j in adj[i]:
                    cls.append("T" if atoms[j] in TRI else ("O" if atoms[j] in ONE else "W"))
                two_nb["".join(sorted(cls))] += 1
        # 严格检验：2 价原子必须连接两个三价骨架（不同或相同块均可）→ 才算"桥"
        # 这里统计：每个 2 价原子的两个邻居都是三价（=桥），或一个三价一个一价（=臂），或含 2 价（链/环）
        ok = True
        if len(triv) > 0:
            comp_of = {}
            for ci, mem in enumerate(comps):
                for a in mem:
                    comp_of[a] = ci
            for i in range(n):
                if atoms[i] in TWO:
                    nb = adj[i]
                    if len(nb) != 2:
                        ok = False
                        continue
                    if all(atoms[j] in TRI for j in nb):
                        pass  # 桥（可能同块/不同块）
                    else:
                        ok = False
        if len(triv) > 0:
            if ok:
                strict_ok += 1
            else:
                strict_fail["含二价非桥"] += 1
    print("价数不符原子数:", bad_val)
    print("按三价元素种类分组计数:", dict(stats))
    print("三价诱导子图最大连通块:", max_comp)
    for tset, cnt in forms.items():
        if not tset:
            continue
        print(f"\n三价类型 [{tset}] 的连通块形态数: {len(cnt)}")
        for k, v in cnt.most_common(12):
            print("   ", k, "×", v)
    print("\n1 价原子邻居类型统计:")
    for k, v in one_nb.most_common():
        print("   ", k, v)
    print("\n2 价原子邻居类型统计 (T=三价, O=一价, W=二价):")
    for k, v in two_nb.most_common():
        print("   ", k, v)
    print("\n严格检验（所有 2 价原子都必须两端接三价=纯桥）:",
          strict_ok, "/", len(cat), " 不满足:", dict(strict_fail))
    json.dump({"stats": dict(stats),
               "one_nb": dict(one_nb), "two_nb": dict(two_nb),
               "strict_ok": strict_ok, "strict_fail": dict(strict_fail),
               "forms_counts": {k: len(v) for k, v in forms.items() if k},
               "bad_val": bad_val, "max_comp": max_comp},
              open(BASE + r"\t14_summary.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\nsaved t14_summary.json")


if __name__ == "__main__":
    main()
