# -*- coding: utf-8 -*-
"""t11_cycles2.py：快速寻找「能重新产出 A」的反应循环（允许副产物）
记有向边 X→Y：存在反应 X+Z -> 产物中含 Y（Y≠X）。
- 2-环：A→C 且 C→A
- 3/4-环：邻接集合上的有界 DFS（每个起点只找前若干个）
输出：环数量统计 + 每类若干实例（含完整反应式）。
"""
import json
import sys
from collections import defaultdict, Counter

BASE = r"G:\AI work\deepseek\work1\alchemy"


def load_rows(name):
    rows = json.load(open(BASE + "\\" + name, encoding="utf-8"))
    out = []
    for r in rows:
        if isinstance(r, dict):
            out.append((r["A"], r["B"], r["ok"], r["products"]))
        else:
            out.append((r[0], r[1], r[2], r[3]))
    return out


ju = load_rows("t11_binary_ju.json")
none = load_rows("t11_binary_none.json")
cross = load_rows("t11_binary_cross.json")

# 邻接：X -> {Y: (Z, products)}  （保留一个例子）
adj = defaultdict(dict)
nodes = set()
for rows in (ju, none, cross):
    for a, b, ok, p in rows:
        if not ok:
            continue
        for X, Z in ((a, b), (b, a)):
            nodes.add(X)
            nodes.add(Z)
            for Y in p:
                if Y == X:
                    continue
                if Y not in adj[X]:
                    adj[X][Y] = (Z, tuple(p))
                nodes.add(Y)

nodes = sorted(nodes)
print(f"节点数 {len(nodes)}，有出边的节点 {len(adj)}，边数 {sum(len(v) for v in adj.values())}")

# 1) 2-环
two = []
for a in nodes:
    for c in adj.get(a, {}):
        if a in adj.get(c, {}):
            z1, p1 = adj[a][c]
            z2, p2 = adj[c][a]
            two.append((a, c, z1, p1, z2, p2))
print(f"\n2-环数量: {len(two)}")
seen = set()
for t in two:
    key = tuple(sorted((t[0], t[1])))
    if key in seen:
        continue
    seen.add(key)
    print(f"  {t[0]} + {t[2]} → {list(t[3])}")
    print(f"  {t[1]} + {t[4]} → {list(t[5])}")
    if len(seen) >= 8:
        break

# 2) 3-环与4-环（限制搜索预算）
def find_cycles(maxlen, budget=200000):
    out = []
    seen = set()
    cnt = 0
    for s in nodes:
        stack = [(s, [s])]
        while stack:
            cnt += 1
            if cnt > budget:
                return out, cnt
            cur, path = stack.pop()
            if len(path) > maxlen:
                continue
            for nxt in adj.get(cur, {}):
                if nxt == s:
                    cyc = tuple(path + [s])
                    rots = [cyc[i:] + cyc[:i] for i in range(len(cyc) - 1)]
                    key = min(rots)
                    if key not in seen:
                        seen.add(key)
                        out.append(key)
                elif nxt not in path and len(path) < maxlen:
                    stack.append((nxt, path + [nxt]))
    return out, cnt

for L in (3, 4):
    cyc, cnt = find_cycles(L, 300000)
    print(f"\n{L}-环找到 {len(cyc)} 个（搜索步数 {cnt}），前 8 个:")
    for c in cyc[:8]:
        print("  ", " → ".join(c))

# 3) 指定物质能否回到自身（2..4 环）
for target in ["C2", "X2", "O2", "O3XC", "OXC", "O2X", "XC2", "A2", "WA", "X2C2"]:
    found = []
    # 2环
    for c in adj.get(target, {}):
        if target in adj.get(c, {}):
            found.append((target, c, target))
    # 3/4环
    cyc, _ = find_cycles(4, 20000)
    for c in cyc:
        if target in c:
            found.append(c)
            if len(found) > 6:
                break
    if found:
        print(f"\n{target} 的环（前 5）:")
        for f in found[:5]:
            print("   ", " → ".join(f))
    else:
        print(f"\n{target}: 未找到 2~4 环")
