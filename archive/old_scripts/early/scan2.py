# -*- coding: utf-8 -*-
"""修复摆放算法后的全量扫描"""
import sys
from collections import Counter, defaultdict
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot2 as P


def atoms_of(v):
    return ["O"] * v[0] + ["X"] * v[1] + ["C"] * v[2]


def run(v):
    mols = P.simulate(atoms_of(v))
    if mols is None:
        return None, "剩键"
    if not P.embed_all(mols):
        return None, "摆不出来"
    return mols, "ok"


def main(N):
    formulas = {}
    maxsize = 0
    reasons = Counter()
    for total in range(1, N + 1):
        for a in range(total + 1):
            for b in range(total - a + 1):
                c = total - a - b
                if c < 0 or (a + c) % 2:
                    continue
                v = (a, b, c)
                mols, why = run(v)
                reasons[why] += 1
                if mols is None:
                    continue
                for m in mols:
                    f = P.formula_of(m["atoms"])
                    maxsize = max(maxsize, len(m["atoms"]))
                    formulas.setdefault(f, v)
    print(f"N={N}: 公式数={len(formulas)}, 最大分子={maxsize}原子, 失败统计={dict(reasons)}")
    for f in sorted(formulas, key=lambda s: (len(s), s)):
        print(f"  {f:10s} 例:{formulas[f]}")
    return formulas


if __name__ == "__main__":
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    main(N)
