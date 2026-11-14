# -*- coding: utf-8 -*-
"""TASK3 分析现有数据：按"分子含有的元素集合"分组，看 511 类别的覆盖与截断情况。"""
import json
import sys
from collections import defaultdict

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def elem_set(f):
    out = set()
    i = 0
    while i < len(f):
        out.add(f[i])
        i += 1
        while i < len(f) and f[i].isdigit():
            i += 1
    return out


def main():
    data = json.load(open(BASE + r"\substances_all.json", encoding="utf-8"))
    print("total substances:", len(data))
    # 按元素集合分组
    groups = defaultdict(list)
    for x in data:
        groups[frozenset(elem_set(x["formula"]))].append(x)
    print("distinct element sets:", len(groups))

    INF = []  # 满足 a>=2, b>=1
    THREE = set("OPK")
    TWO = set("XWA")
    all_subsets = []
    for r in range(1, 10):
        import itertools
        for sub in itertools.combinations(P.ORDER, r):
            s = frozenset(sub)
            all_subsets.append(s)
    print("all subsets:", len(all_subsets))
    finite, infinite = set(), set()
    for s in all_subsets:
        a = len(s & THREE)
        b = len(s & TWO)
        (infinite if (a >= 2 and b >= 1) else finite).add(s)
    print("infinite subsets:", len(infinite), " finite:", len(finite))

    missing = [s for s in all_subsets if s not in groups]
    print("subsets with no substances in data:", len(missing))
    # 每个 scope 的最大原子
    for sid in (1, 2, 3, 4, 5, 6):
        mx = max((x["natoms"] for x in data if x["scope"] == sid), default=0)
        n = sum(1 for x in data if x["scope"] == sid)
        print(f"  scope{sid}: {n} 种, 最大 {mx} 原子")

    # 有限类别的最大原子数 / 是否触边界
    boundary2 = {16}
    rows = []
    for s in sorted(finite, key=lambda z: (-len(z), sorted(z))):
        items = groups.get(s, [])
        if not items:
            rows.append((s, 0, 0, "空"))
            continue
        mx = max(x["natoms"] for x in items)
        cats = len({P.CAT[e] for e in s})
        bound = 16 if cats <= 2 else 12
        flag = "触边界" if mx >= bound else ""
        rows.append((s, len(items), mx, flag))
    # 统计
    from collections import Counter
    print("\n有限类别 max atoms 分布:", Counter(r[2] for r in rows))
    print("有限类别按元素数分组:")
    byk = defaultdict(list)
    for s, n, mx, flag in rows:
        byk[len(s)].append((n, mx, flag))
    for k in sorted(byk):
        vals = byk[k]
        print(f"  size {k}: {len(vals)} 类, 物质数合计 {sum(v[0] for v in vals)}, max原子 {max(v[1] for v in vals)}, 触边界 {sum(1 for v in vals if v[2])}")

    print("\n== 触边界的有限类别（需补扫） ==")
    cnt = 0
    for s, n, mx, flag in rows:
        if flag:
            cnt += 1
            if cnt <= 60:
                print("  ", "/".join(sorted(s)), f"n={n} max={mx}", flag)
    print("  共", cnt, "个")

    print("\n== 有限类别中物质数最多的 20 个 ==")
    for s, n, mx, flag in sorted(rows, key=lambda r: -r[1])[:20]:
        print("  ", "/".join(sorted(s)), f"n={n} max={mx}", flag)

    # 无限类别的现有物质数
    print("\n无限类别 (224) 现有数据统计: 总数", sum(len(groups.get(s, [])) for s in infinite))
    print("  最大原子:", max((x["natoms"] for s in infinite for x in groups.get(s, [])), default=0))

    # 检查：是否存在元素集合不在 511 内的物质（不该有）
    extra = [g for g in groups if g not in set(all_subsets)]
    print("\n非法元素集合:", len(extra))

    # 纯大类核对
    for cat, syms in (("聚", set("OXC")), ("动", set("PWL")), ("散", set("KAF"))):
        for s in [syms]:
            print(f"纯{cat}: {len(groups.get(frozenset(s),[]))} 种", end="; ")
    print()


if __name__ == "__main__":
    main()
