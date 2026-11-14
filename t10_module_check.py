# -*- coding: utf-8 -*-
"""t10_module_check.py：验证「三价骨架 = 小模块的不交并」规律：
统计每个物质里三价原子诱导子图的最大连通块大小、连通块类型分布。"""
import json
import itertools
from collections import Counter, defaultdict

BASE = r"G:\AI work\deepseek\work1\alchemy"
data = json.load(open(BASE + r"\t9_single_trivalent.json", encoding="utf-8"))


def induced(rec, t):
    idx = [i for i, a in enumerate(rec["atoms"]) if a == t]
    pos = {i: k for k, i in enumerate(idx)}
    n = len(idx)
    mult = [[0] * n for _ in range(n)]
    for e in rec["edges"]:
        i, j = e[0], e[1]
        m = e[2] if len(e) > 2 else 1
        if i in pos and j in pos:
            a, b = pos[i], pos[j]
            mult[a][b] += m
            mult[b][a] += m
    return n, mult


def canon_comp(n, mult):
    best = None
    for p in itertools.permutations(range(n)):
        s = []
        for a in range(n):
            for b in range(a + 1, n):
                if mult[p[a]][p[b]]:
                    s.append((a, b, mult[p[a]][p[b]]))
        key = tuple(sorted(s))
        if best is None or key < best:
            best = key
    return best


def components(n, mult):
    seen = [False] * n
    comps = []
    for s in range(n):
        if seen[s]:
            continue
        stack = [s]
        seen[s] = True
        mem = [s]
        while stack:
            u = stack.pop()
            for v in range(n):
                if mult[u][v] and not seen[v]:
                    seen[v] = True
                    stack.append(v)
                    mem.append(v)
        comps.append(mem)
    return comps


for t in ("O", "P", "K"):
    lst = data[t]
    maxc = 0
    ntr = Counter()
    comp_types = Counter()
    max_example = None
    stub_ok = True
    for rec in lst:
        n, mult = induced(rec, t)
        ntr[n] += 1
        for mem in components(n, mult):
            if len(mem) == 1:
                ctype = "单原子"
            else:
                sub = [[mult[a][b] for b in mem] for a in mem]
                key = canon_comp(len(mem), sub)
                degs = tuple(sorted(sum(sub[i]) for i in range(len(mem))))
                ms = tuple(sorted(x[2] for x in key))
                ctype = f"n={len(mem)} 度={degs} 边多重={ms}"
            comp_types[ctype] += 1
            if len(mem) > maxc:
                maxc = len(mem)
                max_example = rec["formula"]
        # stub 校验：sum stubs = 3n - 2E
        E = sum(mult[i][j] for i in range(n) for j in range(i + 1, n))
        if 3 * n - 2 * E < 0:
            stub_ok = False
    print(f"\n=== {t}（{len(lst)} 种）最大连通块={maxc} 例={max_example} stub校验={stub_ok}")
    print("  三价原子数分布:", dict(sorted(ntr.items())))
    print("  连通块类型分布:")
    for k, v in sorted(comp_types.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"    {k}: {v}")
