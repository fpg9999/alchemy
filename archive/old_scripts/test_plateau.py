# -*- coding: utf-8 -*-
"""test_plateau：对 3 个"平台型"三元素（O/W/A、X/P/A、X/W/K）在更大 T 全枚举，
确认它们到底是"有限封顶 ~22" 还是"慢速无限"。"""
import itertools
import json
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
PLATEAU = ["O/W/A", "X/P/A", "X/W/K"]


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


def task(args):
    elems, T = args
    best = 0
    info = None
    for comp in gen_compositions(T, 3):
        v = vec_full(comp, elems)
        atoms = P.vec_to_atoms(v, P.ORDER)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        mols = P.simulate(atoms)
        if not mols:
            continue
        mx = max(len(m["atoms"]) for m in mols)
        if mx <= best:
            continue
        big = [m for m in mols if len(m["atoms"]) == mx][0]
        if P.embed_mol(big["atoms"], big["edges"], max_nodes=40000) is None:
            continue
        ok = all(P.embed_mol(m["atoms"], m["edges"], max_nodes=10000) is not None
                 for m in mols if len(m["atoms"]) < mx)
        if not ok:
            continue
        best = mx
        info = {"formula": P.formula_of(big["atoms"]), "feed": list(v), "nmols": len(mols)}
    return "/".join(elems), T, best, info


if __name__ == "__main__":
    jobs = 6
    tasks = [(k.split("/"), T) for k in PLATEAU for T in (48, 52, 56)]
    out = {}
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for key, T, best, info in pool.map(task, tasks):
            out.setdefault(key, {})[T] = {"max": best, "info": info}
            print(f"{key} T={T}: max={best} {info}", flush=True)
            json.dump(out, open(BASE + r"\plateau_test.json", "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
    print("saved plateau_test.json")
