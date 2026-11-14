# -*- coding: utf-8 -*-
"""t11_cycles4.py：反应循环（真反应、允许副产物）——修正净反应式并分类
环定义：起点物质 A 最后被重新产出；每一步都是真反应（产物 ≠ 反应物多重集）。
净反应式：循环消耗的总物质 − 产出的总物质（A 两侧抵消）→ A 是催化剂。
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

adj = defaultdict(dict)       # X -> Y : (Z, products)
adj_src = defaultdict(dict)   # 记录来源表（'ju'/'none'/'cross'）
for name, rows in [("ju", ju), ("none", none), ("cross", cross)]:
    for a, b, ok, p in rows:
        if not ok or sorted(p) == sorted([a, b]):
            continue
        for X, Z in ((a, b), (b, a)):
            for Y in p:
                if Y == X:
                    continue
                if Y not in adj[X]:
                    adj[X][Y] = (Z, tuple(p))
                    adj_src[X][Y] = name


def steps_of(cycle):
    return [(cycle[i], cycle[i + 1]) for i in range(len(cycle) - 1)]


def equations(cycle):
    cons, prod = Counter(), Counter()
    eqs = []
    for (X, Y) in steps_of(cycle):
        Z, P = adj[X][Y]
        eqs.append((X, Z, P, Y))
        cons[X] += 1
        cons[Z] += 1
        for q in P:
            prod[q] += 1
    left = cons - prod
    right = prod - cons
    return eqs, left, right


def fmt(counter):
    return " + ".join(f"{k}" + (f"×{v}" if v > 1 else "") for k, v in sorted(counter.items()))


def net_str(cycle):
    _, left, right = equations(cycle)
    return f"{fmt(left) or '∅'} → {fmt(right) or '∅'}"


def classify(cycle, jspec, nspec):
    names = set(cycle)
    for (X, Y) in steps_of(cycle):
        Z, P = adj[X][Y]
        names.add(Z)
        names.update(P)
    if names <= jspec:
        return "聚素内"
    if names <= nspec:
        return "无三价内"
    return "跨类"


def find_2cycles():
    out, seen = [], set()
    for a in adj:
        for c in adj[a]:
            if a in adj.get(c, {}):
                key = tuple(sorted((a, c)))
                if key in seen:
                    continue
                seen.add(key)
                out.append((a, c))
    return out


def find_Nrings(maxlen, budget=600000):
    out, seen = [], set()
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
                    if key not in seen:
                        seen.add(key)
                        out.append(cyc)
                elif nxt not in path and len(path) < maxlen:
                    stack.append((nxt, path + [nxt]))
    return out


data = json.load(open(BASE + r"\substances.json", encoding="utf-8"))
t9 = json.load(open(BASE + r"\t9_single_trivalent.json", encoding="utf-8"))
jspec = {d["formula"] for d in data}
nspec = {r["formula"] for r in t9["none"]}
struct_names = set(jspec) | set(nspec)
for cat in ("O", "P", "K"):
    struct_names |= {r["formula"] for r in t9[cat]}

two = find_2cycles()
print(f"真 2-环（无向去重）: {len(two)}")
by_class = Counter()
examples = defaultdict(list)
for a, c in two:
    cls = classify([a, c, a], jspec, nspec)
    by_class[cls] += 1
    if len(examples[cls]) < 8:
        examples[cls].append((a, c))
print("分类:", dict(by_class))
for cls in ("聚素内", "无三价内", "跨类"):
    print(f"\n### {cls} 2-环示例:")
    for a, c in examples[cls]:
        cyc = [a, c, a]
        eqs, left, right = equations(cyc)
        print(f"  环 {a} → {c} → {a}")
        for (X, Z, P, Y) in eqs:
            print(f"    {X} + {Z} → {' + '.join(P)}   （取 {Y} 继续）")
        print(f"    净反应: {fmt(left)} → {fmt(right)}   （{a} 被再生 = 催化剂）")

# 三环节选（各类）
three = find_Nrings(3)
print(f"\n真 3-环: {len(three)}")
cls3 = Counter()
ex3 = defaultdict(list)
for cyc in three:
    cls = classify(list(cyc), jspec, nspec)
    cls3[cls] += 1
    if len(ex3[cls]) < 5:
        ex3[cls].append(cyc)
print("分类:", dict(cls3))
for cls in ("聚素内", "无三价内", "跨类"):
    print(f"\n### {cls} 3-环示例:")
    for cyc in ex3[cls][:3]:
        eqs, left, right = equations(cyc)
        print(f"  环 " + " → ".join(cyc))
        for (X, Z, P, Y) in eqs:
            print(f"    {X} + {Z} → {' + '.join(P)}   （取 {Y} 继续）")
        print(f"    净反应: {fmt(left)} → {fmt(right)}")

# 催化剂排行（2-环）
cat = Counter()
for a, c in two:
    cat[a] += 1
    cat[c] += 1
print("\n2-环中的催化剂排行（前 15）:")
for s, n in cat.most_common(15):
    print(f"  {s}: {n}")

# 保存结果
save = {"two_rings": [{"A": a, "C": c, "net": net_str([a, c, a]),
                       "class": classify([a, c, a], jspec, nspec),
                       "steps": [[X, Z, list(P), Y] for (X, Z, P, Y) in equations([a, c, a])[0]]}
                      for a, c in two]}
json.dump(save, open(BASE + r"\t11_cycles.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print("\nsaved t11_cycles.json")
