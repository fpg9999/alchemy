# -*- coding: utf-8 -*-
"""extend6：2 个 6 元有限类补高原子数档（23~24），判断封顶。"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r'G:\AI work\deepseek\work1\alchemy')
import pot_all as P

BASE = r'G:\AI work\deepseek\work1\alchemy'
CATS6 = ["X/C/P/L/A/F", "X/C/W/L/K/F"]
T0, T1 = 24, 24


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


def scan(args):
    elems, t0, t1 = args
    found = {}
    for total in range(t0, t1 + 1):
        for comp in gen_compositions(total, len(elems)):
            v = vec_full(comp, elems)
            atoms = P.vec_to_atoms(v, P.ORDER)
            if sum(P.VAL[e] for e in atoms) % 2:
                continue
            mols = P.simulate(atoms)
            if not mols:
                continue
            ok = True
            for m in mols:
                if P.embed_mol(m["atoms"], m["edges"], max_nodes=40000) is None:
                    ok = False
                    break
            if not ok:
                continue
            for m in mols:
                f = P.formula_of(m["atoms"])
                if f not in found:
                    found[f] = {"formula": f, "natoms": len(m["atoms"]),
                                "zh": P.zh_of(m["atoms"]), "feed": list(v),
                                "atoms": list(m["atoms"])}
    return "/".join(elems), found


if __name__ == "__main__":
    tasks = [(c.split("/"), T0, T1) for c in CATS6]
    out = {}
    with ProcessPoolExecutor(max_workers=2) as pool:
        for key, found in pool.map(scan, tasks):
            mx = max((x["natoms"] for x in found.values()), default=0)
            out[key] = {"t0": T0, "t1": T1, "substances": list(found.values()), "max": mx}
            print(f"{key}: 新物质 {len(found)}, 最大 {mx}", flush=True)
            json.dump(out, open(BASE + r'\extended_finite4b.json', "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
    print("saved extended_finite4b.json")
