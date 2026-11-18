# -*- coding: utf-8 -*-
"""build_catalog：把 ≤16 原子全量目录按元素组成分类 → 511 类别目录。

依赖：catalog_raw_compact.json（全 9 元素 N≤16 扫描的轻量版）、minimal_infinite.json、families_full.json
输出：catalog_subsets.json / catalog_composition.json / catalog_stats.json
"""
import itertools
import json
import sys
from collections import defaultdict

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
MAXN = 16


def sig(elems):
    return "/".join(sorted(elems, key=lambda e: P.ORDER.index(e)))


def zh_elems(elems):
    return "、".join(f"{e}{P.CN[e]}" for e in sorted(elems, key=lambda x: P.ORDER.index(x)))


def main():
    raw = json.load(open(BASE + r"\catalog_raw_compact.json", encoding="utf-8"))
    print("目录条数:", len(raw), flush=True)
    minf = json.load(open(BASE + r"\minimal_infinite.json", encoding="utf-8"))
    minimal = [set(s.split("/")) for s in minf["minimal"]]
    try:
        fams = json.load(open(BASE + r"\families_full.json", encoding="utf-8"))
    except Exception:
        fams = {}

    groups = defaultdict(list)
    for x in raw:
        groups[frozenset(x["atoms"])].append(x)
    print("组成种类:", len(groups), flush=True)

    def cores_of(S):
        return [sig(m) for m in minimal if m <= set(S)]

    def count_by_N(items):
        ns = [x["natoms"] for x in items]
        return {str(N): sum(1 for n in ns if n <= N) for N in range(2, MAXN + 1)}

    # 精确组成分组
    comp_out = {}
    for E, items in groups.items():
        items.sort(key=lambda x: (x["natoms"], x["formula"]))
        comp_out[sig(E)] = {
            "elems": sorted(E, key=lambda e: P.ORDER.index(e)),
            "zh": zh_elems(E),
            "infinite": bool(cores_of(E)),
            "cores": cores_of(E),
            "count_le16": len(items),
            "count_by_N": count_by_N(items),
            "max_natoms": max(x["natoms"] for x in items),
            "substances": [{"formula": x["formula"], "natoms": x["natoms"],
                            "zh": P.zh_of(x["atoms"])} for x in items],
        }

    # 511 池类别
    sub_out = []
    for r in range(1, 10):
        for c in itertools.combinations(P.ORDER, r):
            S = list(c)
            Sset = set(S)
            items = []
            for E, its in groups.items():
                if E <= Sset:
                    items.extend(its)
            items.sort(key=lambda x: (x["natoms"], x["formula"]))
            cs = cores_of(Sset)
            entry = {
                "elems": S,
                "zh": zh_elems(S),
                "elements_zh": P.zh_of(S),
                "n_elems": len(S),
                "infinite": bool(cs),
                "cores": cs,
                "count_le16": len(items),
                "count_by_N": count_by_N(items),
                "max_natoms": max((x["natoms"] for x in items), default=0),
                "formulas_le16": [x["formula"] for x in items],
                "reps": [{"formula": x["formula"], "zh": P.zh_of(x["atoms"]), "natoms": x["natoms"]}
                         for x in items[:3]],
            }
            if cs:
                entry["growth"] = {
                    "note": "无限：含最小无限集合 " + "、".join(cs) + "；按该核心的链式规律增长",
                    "families": {k: fams.get(k, {}).get("families", [])[:3] for k in cs},
                }
            sub_out.append(entry)
    sub_out.sort(key=lambda e: (e["n_elems"], [P.ORDER.index(x) for x in e["elems"]]))

    # 最小无限集合的 ≤16 计数
    min_sets = []
    for m in minimal:
        items = groups.get(frozenset(m), [])
        allitems = []
        for E, its in groups.items():
            if E <= m:
                allitems.extend(its)
        min_sets.append({
            "elems": sorted(m, key=lambda e: P.ORDER.index(e)),
            "count_le16": len(allitems),
            "count_by_N": count_by_N(allitems),
            "cores": [sig(m)],
            "families": fams.get(sig(m), {}).get("families", []),
            "max_natoms": max((x["natoms"] for x in allitems), default=0),
        })
    min_sets.sort(key=lambda x: (len(x["elems"]), x["elems"]))

    stats = {
        "catalog_size": len(raw),
        "n_composition_groups": len(comp_out),
        "n_pool_categories": len(sub_out),
        "n_finite_categories": sum(1 for x in sub_out if not x["infinite"]),
        "n_infinite_categories": sum(1 for x in sub_out if x["infinite"]),
        "minimal_infinite": minf["minimal"],
        "n_minimal_infinite": len(minimal),
        "infinite_by_size": {r: sum(1 for x in sub_out if x["infinite"] and x["n_elems"] == r)
                             for r in range(1, 10)},
        "finite_by_size": {r: sum(1 for x in sub_out if not x["infinite"] and x["n_elems"] == r)
                           for r in range(1, 10)},
    }
    json.dump(sub_out, open(BASE + r"\catalog_subsets.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(comp_out, open(BASE + r"\catalog_composition.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(min_sets, open(BASE + r"\catalog_minimal.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(stats, open(BASE + r"\catalog_stats.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved catalog_subsets/composition/minimal/stats")
    print(json.dumps(stats, ensure_ascii=False, indent=1)[:1500])


if __name__ == "__main__":
    main()
