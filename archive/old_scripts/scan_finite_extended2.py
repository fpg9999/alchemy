# -*- coding: utf-8 -*-
"""scan_finite_extended2：对边界未定的有限类别继续扩枚举（更大 Nmax），判定封顶并补齐清单。"""
import json
import os
import sys
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


def scan(args):
    elems, Nmax = args
    found = {}
    for total in range(2, Nmax + 1):
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
    return "/".join(elems), Nmax, found


def main():
    bounds = {4: 26, 5: 24, 6: 22}
    rec = json.load(open(BASE + r"\recheck_finite.json", encoding="utf-8"))
    cats = [k for k, v in rec.items() if v["max"] > 16]
    out = {}
    jobs = max(4, (os.cpu_count() or 8) - 6)
    tasks = [(c.split("/"), bounds[len(c.split("/"))]) for c in cats if len(c.split("/")) in bounds]
    print("扩展2 类别:", len(tasks), flush=True)
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for key, Nmax, found in pool.map(scan, tasks):
            mx = max((x["natoms"] for x in found.values()), default=0)
            out[key] = {"Nmax": Nmax, "substances": list(found.values()),
                        "max": mx, "boundary": mx >= Nmax - 1}
            print(f"  {key} N≤{Nmax}: 物质 {len(found)}, 最大 {mx}, 边界={out[key]['boundary']}", flush=True)
            json.dump(out, open(BASE + r"\extended_finite2.json", "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
    print("saved extended_finite2.json")


if __name__ == "__main__":
    main()
