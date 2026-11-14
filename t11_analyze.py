# -*- coding: utf-8 -*-
"""t11_analyze.py：29 种聚素物质二元反应的规律分析"""
import json
from collections import Counter, defaultdict

BASE = r"G:\AI work\deepseek\work1\alchemy"
tab = json.load(open(BASE + r"\t11_binary_ju.json", encoding="utf-8"))
data = json.load(open(BASE + r"\substances.json", encoding="utf-8"))
vec = {d["formula"]: tuple(d["vec"]) for d in data}

ok = [t for t in tab if t["ok"]]
fail = [t for t in tab if not t["ok"]]
inert = [t for t in ok if sorted(t["products"]) == sorted([t["A"], t["B"]])]
single = [t for t in ok if len(t["products"]) == 1]
multi = [t for t in ok if len(t["products"]) > 1 and t not in inert]

print("=== 失败对（不相容）===")
for t in fail:
    print("  ", t["A"], "+", t["B"], "->", t["reason"])

print("\n=== 惰性对（反应后原样返回）===", len(inert))
for t in inert:
    print("  ", t["A"], "+", t["B"], "->", t["products"])

print("\n=== 单一产物（化合）===", len(single))
for t in single:
    print(f"  {t['A']} + {t['B']} -> {t['products'][0]}   （向量 {vec[t['A']]}+{vec[t['B']]}）")

print("\n=== 多产物（复分解/歧化）前 25 例 ===")
for t in multi[:25]:
    print(f"  {t['A']} + {t['B']} -> {t['products']}")

# 等价类：按总向量分组
cls = defaultdict(list)
for t in ok + fail:
    cls[vec[t["A"]] + vec[t["B"]]].append((t["A"], t["B"], tuple(t["products"]) if t["ok"] else None))
print(f"\n=== 按总元素向量分类：{len(cls)} 类 ===")
big = sorted(cls.items(), key=lambda kv: -len(kv[1]))
print("最大的等价类（同一总向量、结果必相同）:")
for v, lst in big[:12]:
    outs = {o for (_, _, o) in lst}
    print(f"  向量{v}: {len(lst)} 对，结果种类={len(outs)} -> {list(outs)[:2]}", end="")
    if len(lst) <= 8:
        print("  对:", [(a, b) for a, b, _ in lst], end="")
    print()

# 单一产物图：A+B->C；找最长增长链
subs = set(vec)
edges = defaultdict(list)   # (a,b) -> c
for t in single:
    a, b, c = t["A"], t["B"], t["products"][0]
    edges[(a, b)].append(c)
    edges[(b, a)].append(c)

best = {"len": 0, "chain": None}


def dfs(chain):
    # chain: list of substances; last two combine -> new
    if len(chain) >= 2:
        a, b = chain[-2], chain[-1]
        for c in edges.get((a, b), []):
            if c in chain:
                continue
            dfs(chain + [c])
    if len(chain) > best["len"]:
        best["len"] = len(chain)
        best["chain"] = list(chain)


for s in sorted(subs):
    dfs([s])

print(f"\n=== 最长单产物增长链（长度={best['len']}）===")
print("  ", best["chain"])

# 每个物质作为单一产物的次数（合成度）
prod_count = Counter(t["products"][0] for t in single)
print("\n合成度最高（最容易被合成）的物质:", prod_count.most_common(10))

# 每个物质参与惰性对的次数
inert_count = Counter()
for t in inert:
    inert_count[t["A"]] += 1
    inert_count[t["B"]] += 1
print("惰性度最高:", inert_count.most_common(10))

# 失败涉及的物质
fcount = Counter()
for t in fail:
    fcount[t["A"]] += 1
    fcount[t["B"]] += 1
print("失败涉及:", dict(fcount))
