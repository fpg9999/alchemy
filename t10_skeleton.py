# -*- coding: utf-8 -*-
"""t10_skeleton.py
研究「只含一种三价元素」的物质里，三价原子之间的骨架形式（induced subgraph on 三价原子）。
输出：每种三价元素（O/P/K）的骨架清单 + 统计 + 例子（含结构/摆放）。
"""
import itertools
import json
import sys
from collections import Counter, defaultdict

BASE = r"G:\AI work\deepseek\work1\alchemy"
TRI = {"O": "O", "P": "P", "K": "K"}
CAT = {"O": "聚", "P": "动", "K": "散"}


def induce(rec, t):
    idx = [i for i, a in enumerate(rec["atoms"]) if a == t]
    pos = {i: k for k, i in enumerate(idx)}
    n = len(idx)
    mult = [[0] * n for _ in range(n)]
    for e in rec["edges"]:
        i, j, m = e[0], e[1], (e[2] if len(e) > 2 else 1)
        if i in pos and j in pos:
            a, b = pos[i], pos[j]
            mult[a][b] += m
            mult[b][a] += m
    return n, mult


def canon(n, mult):
    """n 很小，暴力置换规范形；返回 (key, 度数序列, 边多重数多重集, 附挂数多重集)"""
    best = None
    degs = [sum(mult[i]) for i in range(n)]
    # 附挂数 = 3 - 用掉的键（仅对真正三价元素，O/P/K 都是 3 价）
    stubs = tuple(sorted(3 - d for d in degs))
    degseq = tuple(sorted(degs, reverse=True))
    edges_mlt = tuple(sorted([mult[i][j] for i in range(n) for j in range(i + 1, n)
                              if mult[i][j] for _ in range(mult[i][j])]))
    if n <= 8:
        for p in itertools.permutations(range(n)):
            s = []
            for a in range(n):
                for b in range(a + 1, n):
                    if mult[p[a]][p[b]]:
                        s.append((a, b, mult[p[a]][p[b]]))
            key = tuple(sorted(s))
            if best is None or key < best:
                best = key
    else:
        # 大骨架：用度数+多重边序列做近似 key（后面人工核对）
        best = ("approx", degseq, edges_mlt)
    return best, degs, edges_mlt, stubs


def main():
    data = json.load(open(BASE + r"\t9_single_trivalent.json", encoding="utf-8"))
    report = {}
    for t in ("O", "P", "K"):
        lst = data[t]
        sk = {}
        n_max = 0
        for rec in lst:
            n, mult = induce(rec, t)
            n_max = max(n_max, n)
            if n == 0:
                continue
            key, degs, em, stubs = canon(n, mult)
            if key not in sk:
                sk[key] = {"n": n, "degs": degs, "edges_mlt": em, "stubs": stubs,
                           "example": rec["formula"], "count": 0}
            sk[key]["count"] += 1
        n_dist = Counter(v["n"] for v in sk.values())
        max_edges = max(sum(v["edges_mlt"]) for v in sk.values())
        print(f"\n=== {t}（{CAT[t]}，{len(lst)} 种物质）===")
        print(f"  不同骨架数: {len(sk)}；骨架大小(三价原子数)分布: {dict(sorted(n_dist.items()))}")
        print(f"  最大骨架: {n_max} 个三价原子")
        # 按 (n, 边多重数模式) 展示
        for key, v in sorted(sk.items(), key=lambda kv: (kv[1]["n"], -sum(kv[1]["edges_mlt"]), str(kv[0]))):
            print(f"  n={v['n']} 度={v['degs']} 边多重={v['edges_mlt']} 附挂(剩余键)={v['stubs']} "
                  f"例={v['example']} 该骨架物质数={v['count']}")
        report[t] = {"n_skel": len(sk), "max_n": n_max,
                     "skels": [{"n": v["n"], "degs": v["degs"], "edges_mlt": list(v["edges_mlt"]),
                                "stubs": list(v["stubs"]), "example": v["example"],
                                "count": v["count"], "key": str(key)} for v in sk.values()]}
    json.dump(report, open(BASE + r"\t10_skeletons.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\nsaved t10_skeletons.json")


if __name__ == "__main__":
    main()
