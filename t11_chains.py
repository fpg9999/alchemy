# -*- coding: utf-8 -*-
"""t11_chains.py：单产物反应构成的"增长链/合成路径"分析（29 种聚素）"""
import json
from collections import defaultdict

BASE = r"G:\AI work\deepseek\work1\alchemy"
tab = json.load(open(BASE + r"\t11_binary_ju.json", encoding="utf-8"))
data = json.load(open(BASE + r"\substances.json", encoding="utf-8"))
vec = {d["formula"]: tuple(d["vec"]) for d in data}

edges = defaultdict(set)
for t in tab:
    if t["ok"] and len(t["products"]) == 1:
        c = t["products"][0]
        edges[(t["A"], t["B"])].add(c)
        edges[(t["B"], t["A"])].add(c)

best = {"steps": -1, "chain": None}


def dfs(chain):
    """chain: 物质序列；最后两个单产物化合出下一个"""
    if len(chain) >= 2:
        a, b = chain[-2], chain[-1]
        for c in edges.get((a, b), ()):
            if c in chain:
                continue
            dfs(chain + [c])
    steps = len(chain) - 1
    if steps > best["steps"]:
        best["steps"] = steps
        best["chain"] = list(chain)


starts = set()
for (a, b) in edges:
    dfs([a, b])

print(f"最长单产物增长链：{best['steps']} 步")
print("  " + "  +".join(best["chain"][:2]) + " -> " + " -> ".join(best["chain"][2:]))

# 统计每条合成路线的"最小步数"（从两端单质开始）
base = ["O2", "X2", "C2"]
depth = {s: None for s in vec}
for b in base:
    depth[b] = 0
changed = True
while changed:
    changed = False
    for (a, b), cs in edges.items():
        if depth.get(a) is None or depth.get(b) is None:
            continue
        for c in cs:
            d = max(depth[a], depth[b]) + 1
            if depth.get(c) is None or d < depth[c]:
                depth[c] = d
                changed = True
print("\n从单质出发的最短合成步数：")
for s in sorted(depth, key=lambda x: (depth[x] is None, depth[x] or 0, x)):
    print(f"  {s:10s} 步数={depth[s]}")
unreach = [s for s in vec if depth[s] is None]
print("\n无法由单产物二元反应合成（从单质出发）:", unreach)

# 所有单产物反应按"加成键型"分类：元素单质加成 vs 分子间加成
print("\n单产物反应列表（按产物）:")
for (a, b), cs in sorted(edges.items()):
    if a < b:
        print(f"  {a} + {b} -> {sorted(cs)}")
