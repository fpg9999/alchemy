# -*- coding: utf-8 -*-
"""t26_ground_state.py：能量门槛 e=1 + 结构性限制（分子内键型弛豫，不换原子对/不改连接图）
统计：每根键的"基态键型"、可降级键数、能量释放潜力。
键能 S=3,C=2,L=1；允许 S→C、S→L、C→L（每根释放 ≥1）。
"""
import json
from collections import Counter

BASE = r"G:\AI work\deepseek\work1\alchemy"
VAL = {"O": 3, "X": 2, "C": 1, "P": 3, "W": 2, "L": 1, "K": 3, "A": 2, "F": 1}
CAT = {e: ("聚" if e in "OXC" else ("动" if e in "PWL" else "散")) for e in "OXCPWLKAF"}
EDGE = {(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)}
CORN = {(1, 1), (2, -1), (1, -2), (-1, -1), (-2, 1), (-1, 2)}
LONG = {(2 * a, 2 * b) for (a, b) in EDGE}
W = {"S": 3, "C": 2, "L": 1}
ALLOWED = {("聚", "聚"): {"S"}, ("动", "动"): {"C"}, ("散", "散"): {"L"},
           ("聚", "动"): {"S", "C"}, ("动", "聚"): {"S", "C"},
           ("聚", "散"): {"S", "L"}, ("散", "聚"): {"S", "L"},
           ("动", "散"): {"C", "L"}, ("散", "动"): {"C", "L"}}


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
        reactive_bonds = 0
        release = 0
        bonds = 0
        detail = []
        for e in rec["edges"]:
            i, j, m = e[0], e[1], (e[2] if len(e) > 2 else 1)
            d = (place[j][0] - place[i][0], place[j][1] - place[i][1])
            t = rel(d)
            if t is None:
                continue
            allowed = ALLOWED.get((CAT[atoms[i]], CAT[atoms[j]]))
            if not allowed:
                continue
            ground = min(allowed, key=lambda z: W[z])
            bonds += m
            if t != ground:
                # 当前键型是否可降至 ground（每根释放 >=1）
                if W[t] - W[ground] >= 1:
                    reactive_bonds += m
                    release += (W[t] - W[ground]) * m
                    if len(detail) < 4:
                        detail.append((atoms[i] + atoms[j], t, ground))
        stats["分子"] += 1
        stats["总键"] += bonds
        stats["可降级键"] += reactive_bonds
        stats["能量潜力"] += release
        if reactive_bonds > 0:
            stats["可弛豫分子"] += 1
            if len(examples) < 12:
                examples.append({"formula": rec["formula"], "bonds": bonds,
                                 "reactive_bonds": reactive_bonds, "release": release,
                                 "detail": detail})
    print("分子:", stats["分子"])
    print("总键:", stats["总键"], "可降级键:", stats["可降级键"],
          f"({stats['可降级键'] / stats['总键'] * 100:.1f}%)")
    print("可弛豫分子:", stats["可弛豫分子"],
          f"({stats['可弛豫分子'] / stats['分子'] * 100:.1f}%)")
    print("已处基态的分子:", stats["分子"] - stats["可弛豫分子"],
          f"({(stats['分子'] - stats['可弛豫分子']) / stats['分子'] * 100:.1f}%)")
    print("总能量释放潜力:", stats["能量潜力"])
    print("\n例子:")
    for e in examples:
        print(" ", e)
    json.dump({"stats": dict(stats), "examples": examples},
              open(BASE + r"\t26_ground_state.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t26_ground_state.json")


if __name__ == "__main__":
    main()
