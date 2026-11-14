# -*- coding: utf-8 -*-
"""find_families：为每个最小无限类别寻找"参数化无限族"。

方法：枚举该类别内所有"组成 = 投料"且整锅只出一个分子的计数向量（纯净一锅一分子），
再把这些向量按"同一方向"（相邻差向量相同）聚类成长链，输出 m 递增的公式族。
"""
import itertools
import json
import sys
from collections import defaultdict
from math import gcd

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def gen_compositions(total, k, prefix=()):
    if k == 1:
        yield prefix + (total,)
        return
    for x in range(total + 1):
        yield from gen_compositions(total - x, k - 1, prefix + (x,))


def vec_full(partial, elems):
    v = [0] * 9
    for e, c in zip(elems, partial):
        v[P.ORDER.index(e)] = c
    return tuple(v)


def scan_pure(elems, Nmax):
    recs = []
    for total in range(2, Nmax + 1):
        for comp in gen_compositions(total, len(elems)):
            v = vec_full(comp, elems)
            atoms = P.vec_to_atoms(v, P.ORDER)
            if sum(P.VAL[e] for e in atoms) % 2:
                continue
            mols = P.simulate(atoms)
            if not mols or len(mols) != 1:
                continue
            m = mols[0]
            if len(m["atoms"]) != total:
                continue
            recs.append({"vec": [v[P.ORDER.index(e)] for e in elems],
                         "formula": P.formula_of(m["atoms"]),
                         "natoms": total})
    return recs


def detect_families(recs, elems):
    """按"方向"找长度>=3 的等差数列（公式族）。方向取 {-1,0,1}^k 的规范化原向量。"""
    key2 = {tuple(r["vec"]): r for r in recs}
    k = len(elems)
    dirs = set()
    for d in itertools.product((-1, 0, 1), repeat=k):
        if all(x == 0 for x in d):
            continue
        g = gcd(*[abs(x) for x in d if x])
        dn = tuple(x // g for x in d)
        first = next(x for x in dn if x)
        if first < 0:
            dn = tuple(-x for x in dn)
        dirs.add(dn)
    best = {}
    for dn in dirs:
        for v in key2:
            prev = tuple(a - b for a, b in zip(v, dn))
            if prev in key2:
                continue
            chain = []
            c = v
            while c in key2:
                chain.append(c)
                c = tuple(a + b for a, b in zip(c, dn))
            if len(chain) >= 3 and len(chain) > len(best.get(dn, [])):
                best[dn] = chain
    out = [{
        "dir": list(dn),
        "elems": elems,
        "members": [{"vec": list(c), "formula": key2[c]["formula"], "natoms": key2[c]["natoms"]}
                    for c in chain],
    } for dn, chain in best.items()]
    out.sort(key=lambda f: -len(f["members"]))
    return out[:8]


def main():
    minf = json.load(open(sys.argv[1] if len(sys.argv) > 1 else BASE + r"\minimal_infinite.json", encoding="utf-8"))
    minimal = [sorted(s.split("/"), key=lambda e: P.ORDER.index(e)) for s in minf["minimal"]]
    out = {}
    for elems in minimal:
        n = len(elems)
        Nmax = {3: 24, 4: 20, 5: 18}.get(n, 16)
        recs = scan_pure(elems, Nmax)
        fams = detect_families(recs, elems)
        out["/".join(elems)] = {"elems": elems, "Nmax": Nmax,
                                "pure_onepot": recs, "families": fams}
        print(f"{'/'.join(elems)}: 纯净一锅一分子 {len(recs)} 个，族 {len(fams)} 条", flush=True)
        for f in fams[:3]:
            print("   方向", f["dir"], "->", " , ".join(m["formula"] for m in f["members"][:6]), "...")
        json.dump(out, open(BASE + r"\families.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print("saved families.json")


if __name__ == "__main__":
    main()
