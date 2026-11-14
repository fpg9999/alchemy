# -*- coding: utf-8 -*-
"""scan_finite_extended：对"有限但封顶 >16"的类别做扩展全枚举，补齐完整物质清单（到 Nmax）。

类别列表来自 recheck_finite.json 里 max>16 的项 + 3 个平台型三元素。
"""
import itertools
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
EXTRA = ["O/W/A", "X/P/A", "X/W/K"]


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
    failures = {"剩键": 0, "摆不出": 0, "ok": 0}
    for total in range(2, Nmax + 1):
        for comp in gen_compositions(total, len(elems)):
            v = vec_full(comp, elems)
            atoms = P.vec_to_atoms(v, P.ORDER)
            if sum(P.VAL[e] for e in atoms) % 2:
                continue
            mols = P.simulate(atoms)
            if not mols:
                failures["剩键"] += 1
                continue
            ok = True
            for m in mols:
                if P.embed_mol(m["atoms"], m["edges"], max_nodes=40000) is None:
                    ok = False
                    break
            if not ok:
                failures["摆不出"] += 1
                continue
            failures["ok"] += 1
            for m in mols:
                f = P.formula_of(m["atoms"])
                if f not in found:
                    found[f] = {"formula": f, "natoms": len(m["atoms"]),
                                "zh": P.zh_of(m["atoms"]), "feed": list(v),
                                "atoms": list(m["atoms"])}
    return "/".join(elems), Nmax, found, failures


def main():
    rec = json.load(open(BASE + r"\recheck_finite.json", encoding="utf-8"))
    cats = [k for k, v in rec.items() if v["max"] > 16] + EXTRA
    cats = sorted(set(cats), key=lambda s: (len(s.split("/")), s))
    print("扩展类别:", len(cats), cats, flush=True)
    jobs = max(4, (os.cpu_count() or 8) - 6)
    tasks = [(c.split("/"), {3: 24, 4: 22, 5: 20}.get(len(c.split("/")), 18)) for c in cats]
    out = {}
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for key, Nmax, found, failures in pool.map(scan, tasks):
            out[key] = {"Nmax": Nmax, "substances": list(found.values()), "failures": failures}
            n_over = sum(1 for x in found.values() if x["natoms"] > 16)
            maxn = max((x["natoms"] for x in found.values()), default=0)
            print(f"  {key} N≤{Nmax}: 物质 {len(found)} 个, >16 原子 {n_over} 个, 最大 {maxn} 原子", flush=True)
            json.dump(out, open(BASE + r"\extended_finite.json", "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
    print("saved extended_finite.json")


if __name__ == "__main__":
    main()
