# -*- coding: utf-8 -*-
"""t16b_decompose.py：用 WL 不变式检验「终态新骨架 = 45 库骨架的直接并集」
库：7 单类型模块（单元素归一）+ T8 35 形态（带元素标签）。
对每个终态新形态，求最大覆盖的库骨架块（不相交），剩余顶点为未覆盖（单原子）。
"""
import itertools
import json
import sys
from functools import lru_cache
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from t15_forms_examples import wl_key

BASE = r"G:\AI work\deepseek\work1\alchemy"

# 库
lib = {}
mod = {
    "单原子": (["A"], []),
    "单键二聚体": (["A", "A"], [(0, 1, 1)]),
    "双键二聚体": (["A", "A"], [(0, 1, 2)]),
    "三键二聚体": (["A", "A"], [(0, 1, 3)]),
    "三元链": (["A", "A", "A"], [(0, 1, 1), (1, 2, 1)]),
    "三元环(全单键)": (["A", "A", "A"], [(0, 1, 1), (1, 2, 1), (0, 2, 1)]),
    "三元环(含双键)": (["A", "A", "A"], [(0, 1, 1), (0, 2, 2), (1, 2, 1)]),
}
for name, (atoms, edges) in mod.items():
    lib[wl_key(atoms, edges)] = name
t8 = json.load(open(BASE + r"\t8_forms.json", encoding="utf-8"))
for f in t8:
    if len(f["atoms"]) == 1:
        continue
    lib[wl_key(f["atoms"], [tuple(e) for e in f["edges"]])] = "T8:" + f["formula"]
print("库形态数:", len(lib), flush=True)


def decompose(n, atoms, edges, max_exact=10):
    inc = [[] for _ in range(n)]
    for (i, j, m) in edges:
        inc[i].append((j, m))
        inc[j].append((i, m))
    if n <= max_exact:
        good = []
        for mask in range(1, 1 << n):
            vs = [i for i in range(n) if mask >> i & 1]
            if len(vs) < 2:
                continue
            idx = {v: k for k, v in enumerate(vs)}
            ats = [atoms[v] for v in vs]
            es = [(idx[i], idx[j], m) for (i, j, m) in edges if i in idx and j in idx]
            if wl_key(ats, es) in lib:
                good.append((mask, len(vs)))
        states = {}

        def f(rem):
            if rem == 0:
                return (0, 0, ())
            if rem in states:
                return states[rem]
            low = rem & -rem
            c, p, seq = f(rem & ~low)   # 不覆盖这个顶点
            best = (c, -p, seq)
            for mask, sz in good:
                if mask & low and (mask & ~rem) == 0:
                    c2, p2, seq2 = f(rem & ~mask)
                    cand = (c2 + sz, -(p2 + 1), seq2 + (mask,))
                    if cand[:2] > best[:2]:
                        best = cand
            states[rem] = best
            return best
        c, negp, seq = f((1 << n) - 1)
        masks = list(seq)
        parts = [tuple(i for i in range(n) if (m >> i) & 1) for m in masks]
        return c, -negp, parts
    # n>10：贪心
    covered = set()
    parts = []
    for size in (5, 4, 3, 2):
        for comb in itertools.combinations(range(n), size):
            if any(v in covered for v in comb):
                continue
            idx = {v: k for k, v in enumerate(comb)}
            ats = [atoms[v] for v in comb]
            es = [(idx[i], idx[j], m) for (i, j, m) in edges if i in idx and j in idx]
            if wl_key(ats, es) in lib:
                parts.append(comb)
                covered.update(comb)
    return len(covered), len(parts), [tuple(p) for p in parts]


def main():
    d = json.load(open(BASE + r"\t15_forms.json", encoding="utf-8"))
    print("新形态数:", len(d), flush=True)
    full = 0
    results = []
    for k, x in enumerate(d):
        atoms = x["atoms"]
        edges = [tuple(e) for e in x["edges"]]
        n = len(atoms)
        c, p, seq = decompose(n, atoms, edges)
        results.append({"example": x["example"], "n": n, "covered": c, "parts": p,
                        "frac": round(c / n, 3),
                        "parts_desc": ["".join(atoms[i] for i in part) for part in seq]})
        if c == n:
            full += 1
        if (k + 1) % 100 == 0:
            print("processed", k + 1, flush=True)
    print(f"完全覆盖（全部顶点都能被库骨架块覆盖）: {full}/{len(d)}")
    from collections import Counter
    fr = Counter(r["frac"] for r in results)
    print("覆盖率分布:", dict(sorted(fr.items())))
    # 示例
    for target in ["O3P", "O2CK", "O3KA2", "CP2K3", "O2K4", "O2K6", "O2P6", "O5P5K2"]:
        r = next((q for q in results if q["example"] == target), None)
        if r:
            print(f"\n{target}: n={r['n']} 覆盖={r['covered']}/{r['n']} 块数={r['parts']}")
            print("   ", r["parts_desc"])
    json.dump(results, open(BASE + r"\t16_decompose.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    print("saved t16_decompose.json")


if __name__ == "__main__":
    main()
