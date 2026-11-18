# -*- coding: utf-8 -*-
"""打印 18 种产物的精确结构"""
import sys
from collections import defaultdict, Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot2 as P

TEST = {
    "C2": (0, 0, 2), "XC2": (0, 2, 4), "X2": (0, 2, 0), "X2C2": (0, 2, 2),
    "X3": (1, 3, 3), "OC3": (2, 0, 6), "OXC": (2, 2, 2), "OX2C": (2, 4, 2),
    "OX3C": (1, 3, 1), "O2": (2, 0, 0), "O2C2": (2, 0, 2), "O2C4": (2, 0, 4),
    "O2X": (4, 2, 0), "O2XC2": (4, 2, 4), "O2X2": (2, 2, 0), "O3C3": (3, 0, 3),
    "O3XC": (3, 1, 1), "O3X2C": (3, 2, 1),
}


def atoms_of(v):
    return ["O"] * v[0] + ["X"] * v[1] + ["C"] * v[2]


for f, v in TEST.items():
    mols = P.simulate(atoms_of(v))
    if not P.embed_all(mols):
        print(f, "!! 摆不出来")
        continue
    m = [m for m in mols if P.formula_of(m["atoms"]) == f]
    if not m:
        print(f, "!! 未出现在", v, [P.formula_of(x["atoms"]) for x in mols])
        continue
    m = m[0]
    atoms = m["atoms"]
    deg = Counter()
    for (i, j, k) in m["edges"]:
        deg[i] += k
        deg[j] += k
    parts = []
    for (i, j, k) in sorted(m["edges"], key=lambda t: (-t[2], t[0], t[1])):
        parts.append(f"{i}{atoms[i]}{'-' if k == 1 else '=' * k}{j}{atoms[j]}")
    print(f"{f:8s} 原子={len(atoms)} 度={dict(deg)} 键: " + ", ".join(parts))
