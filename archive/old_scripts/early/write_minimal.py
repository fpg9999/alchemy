# -*- coding: utf-8 -*-
"""write_minimal：汇总 inf3+inf4+inf5，去掉超集，写 minimal_infinite.json；
并统计剩余（不含任何最小无限集合的）6/7/8/9 元子集，看是否还需补测。"""
import itertools
import json

BASE = r"G:\AI work\deepseek\work1\alchemy"
ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]

INF3 = [{"O", "X", "K"}, {"O", "K", "A"}, {"O", "X", "P"}, {"O", "P", "W"},
        {"P", "W", "K"}, {"P", "K", "A"}, {"O", "P", "A"}, {"O", "W", "K"},
        {"X", "P", "K"}]
partial = json.load(open(BASE + r"\minimal_infinite_partial.json", encoding="utf-8"))
INF4 = [set(s.split("/")) for s in partial["inf4"]]
INF5 = [set(s.split("/")) for s in
        ["O/C/W/L/A", "O/C/W/A/F", "O/W/L/A/F", "X/C/P/L/A", "X/C/P/A/F",
         "X/C/W/L/K", "X/C/W/K/F", "X/P/L/A/F", "X/W/L/K/F"]]

all_sets = INF3 + INF4 + INF5
minimal = [m for m in all_sets if not any(o < m for o in all_sets)]
print("minimal 数量:", len(minimal))


def key(m):
    return "/".join(sorted(m, key=lambda e: ORDER.index(e)))


out = {
    "inf3": [key(m) for m in INF3],
    "inf4": [key(m) for m in INF4],
    "inf5": [key(m) for m in INF5],
    "minimal": sorted(key(m) for m in minimal),
    "minimal_count": len(minimal),
}
json.dump(out, open(BASE + r"\minimal_infinite.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved minimal_infinite.json; 最小集合:")
for k in out["minimal"]:
    print("  ", k)

# 统计不含任何最小无限集合的子集（按大小）
minsets = [set(s.split("/")) for s in out["minimal"]]
for r in range(1, 10):
    rem = [c for c in itertools.combinations(ORDER, r)
           if not any(m <= set(c) for m in minsets)]
    print(f"元素数 {r}: 子集 {len(list(itertools.combinations(ORDER,r)))} 个，"
          f"不含量小无限集合的剩余 {len(rem)} 个")
    if r >= 6 and rem:
        print("   例如:", ["/".join(c) for c in rem[:10]])
