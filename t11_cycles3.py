# -*- coding: utf-8 -*-
"""t11_cycles3.py：真正的反应循环（每一步都是真正反应，含副产物），并给出净反应式
术语：
- 惰性步：X+Z 的产物多重集恰好 = {X,Z}（等于没反应）→ 这种边不算"真反应"。
- 真循环：环上每一步都是真反应，且起点物质 A 在最后一步被重新产出。
  此时 A 是"催化剂"：净反应里 A 被消掉，只转换其它物质。
"""
import json
from collections import Counter, defaultdict

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

# 真实边：X -> Y (Z, products)  仅当反应不是惰性
adj = defaultdict(dict)
inert_edges = 0
for rows in (ju, none, cross):
    for a, b, ok, p in rows:
        if not ok:
            continue
        if sorted(p) == sorted([a, b]):
            inert_edges += 1
            continue
        for X, Z in ((a, b), (b, a)):
            for Y in p:
                if Y == X:
                    continue
                adj[X].setdefault(Y, (Z, tuple(p)))
print("惰性反应对数:", inert_edges, "| 真反应边:",
      sum(len(v) for v in adj.values()), "节点:", len(adj))


def cyc_eqs(cycle, adj):
    """cycle: [A, C1, ..., Ck, A]；返回各步反应式与净反应式"""
    steps = []
    cons, prod = Counter(), Counter()
    for i in range(len(cycle) - 1):
        X, Y = cycle[i], cycle[i + 1]
        Z, P = adj[X][Y]
        steps.append((X, Z, P, Y))
        cons[X] += 1
        cons[Z] += 1
        for p in P:
            prod[p] += 1
    net = cons - prod
    # 净式中 A 两侧抵消
    return steps, net


def fmt_net(net):
    left = " + ".join(f"{k}" + (f"×{v}" if v > 1 else "") for k, v in sorted(net.items()) if v > 0)
    right = " + ".join(f"{k}" + (f"×{v}" if v > 1 else "") for k, v in sorted(net.items()) if v < 0)
    return f"{left or '∅'}  →  {right or '∅'}"


# 1) 真 2-环
two = []
for a in adj:
    for c in adj[a]:
        if a in adj.get(c, {}):
            two.append((a, c))
# 去重（无向对）
seen = set()
uniq = []
for a, c in two:
    k = tuple(sorted((a, c)))
    if k in seen:
        continue
    seen.add(k)
    uniq.append((a, c))
print(f"\n真 2-环数量（无向去重）: {len(uniq)}")
for a, c in uniq[:12]:
    steps, net = cyc_eqs([a, c, a], adj)
    print(f"\n  环 {a} → {c} → {a}")
    for (X, Z, P, Y) in steps:
        print(f"    {X} + {Z} → {' + '.join(P)}      （取其中的 {Y} 继续）")
    print(f"    净反应：{fmt_net(net)}      ← {a} 是催化剂（被再生）")

# 2) 真 3-环（预算受限）
def find(maxlen, budget=400000):
    out, seen2 = [], set()
    cnt = 0
    for s in adj:
        stack = [(s, [s])]
        while stack:
            cnt += 1
            if cnt > budget:
                return out
            cur, path = stack.pop()
            if len(path) > maxlen:
                continue
            for nxt in adj.get(cur, {}):
                if nxt == s:
                    cyc = tuple(path + [s])
                    rots = [cyc[i:] + cyc[:i] for i in range(len(cyc) - 1)]
                    key = min(rots)
                    if key not in seen2:
                        seen2.add(key)
                        out.append(cyc)
                elif nxt not in path and len(path) < maxlen:
                    stack.append((nxt, path + [nxt]))
    return out

for L in (3, 4):
    cyc = find(L)
    print(f"\n真 {L}-环找到 {len(cyc)} 个，示例:")
    for c in cyc[:6]:
        steps, net = cyc_eqs(list(c), adj)
        print(f"\n  环 " + " → ".join(c))
        for (X, Z, P, Y) in steps:
            print(f"    {X} + {Z} → {' + '.join(P)}      （取 {Y}）")
        print(f"    净反应：{fmt_net(net)}")

# 3) 统计哪些物质能做催化剂（出现在真 2-环里）
cat = Counter()
for a, c in uniq:
    cat[a] += 1
    cat[c] += 1
print("\n可作为催化剂（真 2-环中的 A）的物质:")
for s, n in cat.most_common(20):
    print(f"  {s}: 参与 {n} 个 2-环")
