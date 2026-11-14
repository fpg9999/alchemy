# -*- coding: utf-8 -*-
"""t9_single_trivalent.py
从权威目录 t4_catalog_all_validated.json 中筛出「三价元素种类 ≤ 1」的物质。
分类：无三价 / 只含秩O / 只含势P / 只含沌K；并做子分类统计。
输出：t9_single_trivalent.json（每类物质清单，含结构数据）+ 控制台计数。
"""
import json
import sys
from collections import Counter, defaultdict

BASE = r"G:\AI work\deepseek\work1\alchemy"
TRI = {"O", "P", "K"}
OTHER = ["X", "C", "P", "W", "L", "K", "A", "F"]


def main():
    data = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
    print("目录总物质数:", len(data), flush=True)
    cats = {"none": [], "O": [], "P": [], "K": []}
    seen = set()
    for rec in data:
        atoms = rec["atoms"]
        triv = set(atoms) & TRI
        if len(triv) >= 2:
            continue
        if len(triv) == 1:
            cat = next(iter(triv))
        else:
            cat = "none"
        f = rec["formula"]
        if f in seen:
            continue
        seen.add(f)
        rec2 = {"formula": f, "natoms": rec["natoms"], "atoms": atoms,
                "edges": rec["edges"], "place": rec["place"], "feed": rec["feed"],
                "source": rec.get("source", "")}
        cats[cat].append(rec2)

    out = {}
    for cat, lst in cats.items():
        lst.sort(key=lambda r: (r["natoms"], r["formula"]))
        out[cat] = lst
        # 子分类：出现的非三价元素集合（按种类数、字母序）
        sub = Counter()
        sub_sets = Counter()
        for r in lst:
            others = frozenset(set(r["atoms"]) - TRI)
            sub_sets["".join(sorted(others)) if others else "(纯三价)"] += 1
        natoms = Counter(r["natoms"] for r in lst)
        print(f"\n类别 {cat}: {len(lst)} 种；原子数范围 {min(natoms)}~{max(natoms)}")
        print("  原子数分布:", dict(sorted(natoms.items())))
        print("  子分类(其它元素组合):", dict(sub_sets))
    json.dump(out, open(BASE + r"\t9_single_trivalent.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    print("\nsaved t9_single_trivalent.json")
    for cat in ["none", "O", "P", "K"]:
        print(f"\n=== {cat} 前 30 个 ===")
        print([r["formula"] for r in cats[cat][:30]])


if __name__ == "__main__":
    main()
