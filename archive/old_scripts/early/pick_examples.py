# -*- coding: utf-8 -*-
"""pick_examples：为指定元素子集，随机搜出一个"整锅一个分子"的成功例子（含结构与投料）。

输出 representatives.json，供 render_cross.py 画图。
"""
import itertools
import json
import random
import sys

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"

# (标签, 元素子集, 目标原子数, 是否三分类)
REQS = [
    # 范围3 无限族代表
    ("范围3 {O,X,K}", ["O", "X", "K"], 28),
    ("范围3 {O,K,A}", ["O", "K", "A"], 28),
    ("范围3 {O,X,K,F}", ["O", "X", "K", "F"], 28),
    # 范围4
    ("范围4 {O,X,P}", ["O", "X", "P"], 28),
    ("范围4 {O,P,W}", ["O", "P", "W"], 28),
    ("范围4 {O,X,P,L}", ["O", "X", "P", "L"], 28),
    # 范围5
    ("范围5 {P,W,K}", ["P", "W", "K"], 28),
    ("范围5 {P,K,A}", ["P", "K", "A"], 28),
    ("范围5 {P,W,K,F}", ["P", "W", "K", "F"], 28),
    # 范围6 三类混合（至少三类）
    ("范围6 三类 {O,X,P,K}", ["O", "X", "P", "K"], 24),
    ("范围6 三类 {O,X,P,A}", ["O", "X", "P", "A"], 24),
    ("范围6 三类 {O,P,W,K}", ["O", "P", "W", "K"], 24),
    ("范围6 三类 {O,X,P,K,A,F}", ["O", "X", "P", "K", "A", "F"], 28),
]


def rand_vec(total, k, rng):
    cuts = sorted(rng.sample(range(total + k - 1), k - 1)) if k > 1 else []
    out, prev = [], -1
    for c in cuts + [total + k - 1]:
        out.append(c - prev - 1)
        prev = c
    return out


def main():
    rng = random.Random(9001)
    out = []
    for label, elems, T in REQS:
        found = None
        for attempt in range(4000):
            v = rand_vec(T, len(elems), rng)
            atoms = P.vec_to_atoms(tuple(v), elems)
            if sum(P.VAL[e] for e in atoms) % 2:
                continue
            mols = P.simulate(atoms)
            if not mols:
                continue
            mx = max(len(m["atoms"]) for m in mols)
            if mx < T:
                continue
            # 只接受整锅一个分子的例子，便于展示
            if len(mols) != 1:
                continue
            if not P.embed_all(mols):
                continue
            m = mols[0]
            place = P.embed_mol(m["atoms"], m["edges"])
            if place is None:
                continue
            cats = sorted({P.CAT[e] for e in m["atoms"]}, key=lambda c: "聚动散".index(c))
            feed9 = [0] * 9
            for e, c in zip(elems, v):
                feed9[P.ORDER.index(e)] = c
            found = {
                "label": label,
                "formula": P.formula_of(m["atoms"]),
                "zh": P.zh_of(m["atoms"]),
                "natoms": len(m["atoms"]),
                "cats": "-".join(cats),
                "feed": feed9,
                "atoms": list(m["atoms"]),
                "edges": [list(e) for e in m["edges"]],
                "place": {str(k): list(p) for k, p in place.items()},
            }
            break
        if found:
            out.append(found)
            print(f"OK {label}: {found['formula']} ({found['natoms']}原子, {found['cats']})", flush=True)
        else:
            print(f"FAIL {label}", flush=True)
    json.dump(out, open(BASE + r"\representatives.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved representatives.json", len(out))


if __name__ == "__main__":
    main()
