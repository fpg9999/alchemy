# -*- coding: utf-8 -*-
"""find_families2：并行版——对每个最小无限类别枚举"纯净一锅一分子"并找参数族。"""
import itertools
import json
import os
import sys
from collections import defaultdict
from math import gcd
from concurrent.futures import ProcessPoolExecutor

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


def scan_pure(args):
    elems, Nmax = args
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
                         "formula": P.formula_of(m["atoms"]), "natoms": total})
    return elems, Nmax, recs


def detect(recs, elems):
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
        "dir": list(dn), "elems": elems,
        "members": [{"vec": list(c), "formula": key2[c]["formula"], "natoms": key2[c]["natoms"]}
                    for c in chain],
    } for dn, chain in best.items()]
    out.sort(key=lambda f: -len(f["members"]))
    return out[:8]


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else BASE + r"\minimal_infinite.json"
    minf = json.load(open(path, encoding="utf-8"))
    minimal = [sorted(s.split("/"), key=lambda e: P.ORDER.index(e)) for s in minf["minimal"]]
    jobs = max(4, (os.cpu_count() or 8) - 4)
    tasks = []
    for elems in minimal:
        n = len(elems)
        Nmax = {3: 24, 4: 20, 5: 18}.get(n, 16)
        tasks.append((elems, Nmax))
    out = {}
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for elems, Nmax, recs in pool.map(scan_pure, tasks):
            key = "/".join(elems)
            fams = detect(recs, elems)
            out[key] = {"elems": elems, "Nmax": Nmax, "pure_onepot": recs, "families": fams}
            print(f"{key}: 纯净一锅 {len(recs)}，族 {len(fams)}", flush=True)
            json.dump(out, open(BASE + r"\families_full.json", "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
    print("saved families_full.json:", len(out))


if __name__ == "__main__":
    main()
