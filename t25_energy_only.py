# -*- coding: utf-8 -*-
"""t25_energy_only.py：只保留能量限制（去掉端帽/单对交换限制）时会发生什么
键能 S=3,C=2,L=1；每根断开重连键需释放 2 ⇒ 只有 S→L 允许；C、L 键冻结。
统计：≤8 原子物质中，哪些分子含"可自然发生的 聚-散 S 键"（可 S→L 弛豫）。
"""
import json
import sys
from collections import Counter

BASE = r"G:\AI work\deepseek\work1\alchemy"
VAL = {"O": 3, "X": 2, "C": 1, "P": 3, "W": 2, "L": 1, "K": 3, "A": 2, "F": 1}
CAT = {e: ("聚" if e in "OXC" else ("动" if e in "PWL" else "散")) for e in "OXCPWLKAF"}
EDGE = {(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)}
CORN = {(1, 1), (2, -1), (1, -2), (-1, -1), (-2, 1), (-1, 2)}
LONG = {(2 * a, 2 * b) for (a, b) in EDGE}
W = {"S": 3, "C": 2, "L": 1}


def rel(d):
    if d in EDGE:
        return "S"
    if d in CORN:
        return "C"
    if d in LONG:
        return "L"
    return None


def main():
    cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
    small = [r for r in cat if len(r["atoms"]) <= 8 and r.get("place")]
    stats = Counter()
    examples = []
    for rec in small:
        atoms = rec["atoms"]
        place = {int(k): (int(v[0]), int(v[1])) for k, v in rec["place"].items()}
        S_bonds = C_bonds = L_bonds = 0
        convertible = 0      # 聚-散 S 键（可 S→L）
        frozen_S = 0         # 不是聚-散的 S 键（不能直接 S→L）
        for e in rec["edges"]:
            i, j, m = e[0], e[1], (e[2] if len(e) > 2 else 1)
            d = (place[j][0] - place[i][0], place[j][1] - place[i][1])
            t = rel(d)
            if t is None:
                continue
            n = m
            if t == "S":
                S_bonds += n
                if {CAT[atoms[i]], CAT[atoms[j]]} == {"聚", "散"}:
                    convertible += n
                else:
                    frozen_S += n
            elif t == "C":
                C_bonds += n
            else:
                L_bonds += n
        stats["分子数"] += 1
        stats["总S"] += S_bonds
        stats["可转换S(聚-散)"] += convertible
        stats["冻结S"] += frozen_S
        stats["C"] += C_bonds
        stats["L"] += L_bonds
        if convertible > 0:
            stats["会发生自然弛豫的分子"] += 1
            if len(examples) < 15:
                examples.append({"formula": rec["formula"], "convertible_S": convertible,
                                 "frozen_S": frozen_S, "C": C_bonds, "L": L_bonds,
                                 "release": 2 * convertible})
        elif frozen_S > 0:
            stats["含冻结S(无聚-散S)的分子"] += 1
        else:
            stats["无S键的稳定分子"] += 1
    print("小物质:", stats["分子数"])
    print("键统计: 总S", stats["总S"], "可转换S(聚-散)", stats["可转换S(聚-散)"],
          f"({stats['可转换S(聚-散)'] / max(stats['总S'], 1) * 100:.1f}%)",
          "冻结S", stats["冻结S"], "C", stats["C"], "L", stats["L"])
    print("会发生自然弛豫的分子:", stats["会发生自然弛豫的分子"],
          f"({stats['会发生自然弛豫的分子'] / stats['分子数'] * 100:.1f}%)")
    print("含冻结S(无聚-散S)的分子:", stats["含冻结S(无聚-散S)的分子"],
          f"({stats['含冻结S(无聚-散S)的分子'] / stats['分子数'] * 100:.1f}%)")
    print("无S键的稳定分子:", stats["无S键的稳定分子"],
          f"({stats['无S键的稳定分子'] / stats['分子数'] * 100:.1f}%)")
    print("\n会弛豫的例子（可转换S键数、冻结S、释放能量）:")
    for e in examples:
        print(" ", e)
    json.dump({"stats": dict(stats), "examples": examples},
              open(BASE + r"\t25_energy_only.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t25_energy_only.json")


if __name__ == "__main__":
    main()
