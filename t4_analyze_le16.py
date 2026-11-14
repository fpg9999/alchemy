# -*- coding: utf-8 -*-
"""t4_analyze_le16：分析修正版 ≤16 全目录：按精确元素集合分组、统计、自组成一锅复现检验，
并与旧目录（substances_league_s6.json 等）比较。"""
import itertools
import json
import sys
from collections import defaultdict

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
THREE = set("OPK")
TWO = set("XWA")


def main():
    data = json.load(open(BASE + r"\t4_catalog_le16.json", encoding="utf-8"))
    print("corrected <=16 substances:", len(data), flush=True)

    # 自组成复现检验
    bad = []
    for x in data:
        vec = tuple(x["vec"])
        mols = P.simulate(P.vec_to_atoms(vec, P.ORDER))
        if not mols or len(mols) != 1 or P.formula_of(mols[0]["atoms"]) != x["formula"]:
            bad.append(x["formula"])
    print(f"self-composition one-pot check: {len(data)-len(bad)}/{len(data)} ok; bad={len(bad)}", flush=True)

    # 按元素集合分组
    def eset(x):
        return frozenset(e for e, c in zip(P.ORDER, x["vec"]) if c > 0)

    groups = defaultdict(list)
    for x in data:
        groups[eset(x)].append(x)
    print("distinct element sets:", len(groups), flush=True)

    stats = {}
    for n in range(1, 10):
        for c in itertools.combinations(P.ORDER, n):
            S = frozenset(c)
            items = groups.get(S, [])
            keys = set(S & THREE), set(S & TWO)
            a, b = len(S & THREE), len(S & TWO)
            stats["/".join(c)] = {
                "n": n, "count_le16": len(items),
                "max_le16": max((x["natoms"] for x in items), default=0),
                "a": a, "b": b,
            }
    json.dump({"n_total": len(data), "selfcomposition_bad": bad, "stats": stats},
              open(BASE + r"\t4_le16_stats.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved t4_le16_stats.json", flush=True)

    # 旧目录对比
    try:
        old = json.load(open(BASE + r"\catalog_raw_compact.json", encoding="utf-8"))
        oldf = {x["formula"] for x in old}
        newf = {x["formula"] for x in data}
        print(f"old {len(oldf)}, new {len(newf)}, common {len(oldf & newf)}, "
              f"new-only {len(newf - oldf)}, old-only {len(oldf - newf)}")
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    main()
