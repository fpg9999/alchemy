# -*- coding: utf-8 -*-
"""检查投料配方 + 扩展规则开关稳健性"""
import sys
from collections import Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot2 as P


def atoms_of(v):
    return ["O"] * v[0] + ["X"] * v[1] + ["C"] * v[2]


def run(v, opts=None):
    mols = P.simulate(atoms_of(v), opts)
    if mols is None:
        return None
    if not P.embed_all(mols):
        return None
    return mols


V2F = {
    (2, 0, 0): "O2", (0, 2, 0): "X2", (0, 0, 2): "C2", (0, 3, 0): "X3",
    (1, 2, 1): "OX2C", (1, 3, 1): "OX3C", (1, 1, 1): "OXC", (1, 0, 3): "OC3",
    (2, 2, 0): "O2X2", (2, 1, 0): "O2X", (2, 0, 2): "O2C2", (2, 0, 4): "O2C4",
    (0, 2, 2): "X2C2", (0, 1, 2): "XC2", (2, 1, 2): "O2XC2",
    (3, 0, 3): "O3C3", (3, 1, 1): "O3XC", (3, 2, 1): "O3X2C",
}

recipes = [
    ("C2",   [(0, 0, 2)]),
    ("X2",   [(0, 2, 0)]),
    ("O2",   [(2, 0, 0)]),
    ("XC2",  [(0, 0, 2), (0, 0, 2), (0, 2, 0)]),
    ("X2C2", [(0, 2, 0), (0, 0, 2)]),
    ("O2C2", [(2, 0, 0), (0, 0, 2)]),
    ("O2C4", [(2, 0, 0), (0, 0, 2), (0, 0, 2)]),
    ("OXC",  [(2, 0, 0), (0, 2, 0), (0, 0, 2)]),
    ("O2X",  [(2, 0, 0), (2, 0, 0), (0, 2, 0)]),
    ("O2X2", [(2, 0, 0), (0, 2, 0)]),
    ("O2XC2", [(2, 0, 0), (2, 0, 0), (0, 2, 0), (0, 0, 2), (0, 0, 2)]),
    ("OX2C", [(2, 0, 0), (0, 2, 0), (0, 2, 0), (0, 0, 2)]),
    ("OC3",  [(2, 0, 0), (0, 0, 2), (0, 0, 2), (0, 0, 2)]),
    ("OX3C", [(2, 0, 0), (0, 2, 0), (0, 0, 2), (0, 2, 0)]),
    ("O3C3", [(2, 0, 0), (1, 0, 3)]),
    ("O3XC", [(2, 0, 0), (1, 1, 1)]),
    ("O3X2C", [(3, 2, 1)]),
    ("X3",   [(1, 3, 1), (0, 0, 2)]),
]

print("=== 配方验证 ===")
for target, parts in recipes:
    v = tuple(sum(p[i] for p in parts) for i in range(3))
    mols = run(v)
    got = None if mols is None else Counter(P.formula_of(m["atoms"]) for m in mols)
    print(f"  {target:8s} <- 投料{parts} = {v}  ->  {dict(got) if got else '失败'}")

print("\n=== 规则 5/6/7 关掉，总原子<=18 的公式集 ===")


def set_of(opts, N=18):
    s = set()
    for total in range(1, N + 1):
        for a in range(total + 1):
            for b in range(total - a + 1):
                c = total - a - b
                if c < 0 or (a + c) % 2:
                    continue
                mols = run((a, b, c), opts)
                if mols:
                    s |= {P.formula_of(m["atoms"]) for m in mols}
    return s


base = set_of(None)
for name, opts in [("关C5", {"c5": False}), ("关C6", {"c6": False}), ("关C7", {"c7": False}),
                   ("只留1~2", {"c5": False, "c6": False, "c7": False})]:
    s = set_of(opts)
    print(f"  {name}: {len(s)} 种, 多出={sorted(s-base)}, 少了={sorted(base-s)}")
