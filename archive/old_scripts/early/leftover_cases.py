# -*- coding: utf-8 -*-
"""列出"剩键"失败输入，检查是否与并列选择有关"""
import random
import sys
from collections import Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot2 as P


def atoms_of(v):
    return ["O"] * v[0] + ["X"] * v[1] + ["C"] * v[2]


N = 18
leftover = []
geo = 0
for total in range(1, N + 1):
    for a in range(total + 1):
        for b in range(total - a + 1):
            c = total - a - b
            if c < 0 or (a + c) % 2:
                continue
            v = (a, b, c)
            mols = P.simulate(atoms_of(v))
            if mols is None:
                leftover.append(v)
            elif not P.embed_all(mols):
                geo += 1
print("总原子<=18: 剩键失败 =", len(leftover), leftover)
print("摆不出来 =", geo)

print("\n检查这些输入换原子顺序是否仍失败：")
for v in leftover:
    outs = set()
    for _ in range(12):
        at = atoms_of(v)
        random.shuffle(at)
        m = P.simulate(at)
        outs.add("FAIL" if (m is None or not P.embed_all(m)) else "OK")
    print("  ", v, "slots=", 3 * v[0] + 2 * v[1] + v[2], "->", outs)
