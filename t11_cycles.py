# -*- coding: utf-8 -*-
"""t11_cycles.py：寻找「能重新产出 A」的反应循环（允许副产物）
定义：若存在反应 X+Z -> 产物中包含 Y（Y≠X），记有向边 X→Y（携带反应细节）。
反应循环 = 有向图中的环，例如 A→C→A 表示：
  A+B -> ...C...   （C 为产物之一，其余为副产物）
  C+D -> ...A...   （A 为产物之一，其余为副产物）
"""
import json
import sys
from collections import defaultdict

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


def build_graph(rows, min_products=1):
    """返回 edge: X -> list of (Y, Z, products)"""
    edges = defaultdict(list)
    for a, b, ok, p in rows:
        if not ok:
            continue
        for X, Z in ((a, b), (b, a)):
            for Y in p:
                if Y == X:
                    continue
                edges[X].append((Y, Z, tuple(p)))
    return edges


def find_cycles(edges, nodes, maxlen=4):
    cycles = []
    seen = set()

    def dfs(start, cur, path):
        if len(path) > maxlen:
            return
        for (nxt, z, prods) in edges.get(cur, ()):
            if nxt == start and len(path) >= 1:
                cyc = tuple(path + [start])
                # 归一化：以最小元素旋转
                rots = [cyc[i:] + cyc[:i] for i in range(len(cyc) - 1)]
                key = min(rots)
                if key not in seen:
                    seen.add(key)
                    cycles.append((key, prods))
            elif nxt not in path and len(path) < maxlen:
                dfs(start, nxt, path + [nxt])

    for s in nodes:
        dfs(s, s, [s])
    return cycles


def main():
    ju = load_rows("t11_binary_ju.json")
    none = load_rows("t11_binary_none.json")
    cross = load_rows("t11_binary_cross.json")

    for label, rows in [("聚素29", ju), ("无三价175", none), ("交叉29x175", cross)]:
        edges = build_graph(rows)
        nodes = sorted(set(edges) | {y for v in edges.values() for (y, _, _) in v})
        cycles = find_cycles(edges, nodes, maxlen=4)
        print(f"\n=== {label}: 节点 {len(nodes)}，边 {sum(len(v) for v in edges.values())}，环 {len(cycles)} ===")
        for cyc, prods in cycles[:15]:
            print("  环:", " → ".join(cyc), "  (最后一步产物:", prods, ")")

    # 全并集（29+175 之间的所有反应表都在；节点把跨类产物也算进来）
    rows_all = ju + none + cross
    edges = build_graph(rows_all)
    allnodes = set(edges)
    for v in edges.values():
        for (y, _, _) in v:
            allnodes.add(y)
    print(f"\n=== 合并图: 节点 {len(allnodes)}，边 {sum(len(v) for v in edges.values())} ===")
    # 只展示节点都在这三个表里的环
    known = set()
    for rows in (ju, none, cross):
        for a, b, ok, p in rows:
            known.add(a)
            known.add(b)
            if ok:
                known.update(p)
    cycles = find_cycles(edges, sorted(known), maxlen=4)
    print(f"已知节点 {len(known)}，环数 {len(cycles)}")
    for cyc, prods in cycles[:20]:
        print("  环:", " → ".join(cyc))

    # 重点：2-环（A→C→A）直接列出
    two = []
    for a in sorted(known):
        for (c, z1, p1) in edges.get(a, ()):
            if c == a:
                continue
            for (y, z2, p2) in edges.get(c, ()):
                if y == a:
                    two.append((a, c, z1, p1, z2, p2))
    print(f"\n2-环（A→C→A）数量: {len(two)}")
    for t in two[:20]:
        print(f"  A={t[0]}, C={t[1]}；{t[0]}+{t[2]}->{t[3]}；{t[1]}+{t[4]}->{t[5]}")


if __name__ == "__main__":
    main()
