# -*- coding: utf-8 -*-
"""t4_batch_triples：对全部 84 个三元组，枚举总原子 Tmin..Tmax 的支撑内全部投料（只含该三元素），
严格校验可摆放性，收集每种元素的"完备物质清单"（在 T<=Tmax 范围内）。

用法: python t4_batch_triples.py <Tmin> <Tmax> [jobs]
输出: t4_triples_complete.json
"""
import itertools
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v2

BASE = r"G:\AI work\deepseek\work1\alchemy"


def gen_compositions(total, k, prefix=()):
    if k == 1:
        yield prefix + (total,)
        return
    for x in range(total + 1):
        yield from gen_compositions(total - x, k - 1, prefix + (x,))


def work(task):
    elems, T, budget = task
    found = {}
    cache = {}
    best = 0
    bestf = None
    nfeed = 0
    for counts in gen_compositions(T, len(elems)):
        atoms = P.vec_to_atoms(counts, elems)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        nfeed += 1
        mols = P.simulate(atoms)
        if not mols:
            continue
        ok = True
        for m in mols:
            key = (tuple(m["atoms"]), tuple(sorted(tuple(e) for e in m["edges"])))
            if key not in cache:
                pl = pot_v2.embed_mol2(m["atoms"], m["edges"], max_nodes=budget)
                if pl is not None:
                    good, _ = pot_v2.validate_place(pl, m["atoms"], m["edges"])
                    pl = pl if good else None
                cache[key] = pl
            if cache[key] is None:
                ok = False
                break
        if not ok:
            continue
        for m in mols:
            f = P.formula_of(m["atoms"])
            if f not in found:
                key = (tuple(m["atoms"]), tuple(sorted(tuple(e) for e in m["edges"])))
                found[f] = {"formula": f, "natoms": len(m["atoms"]), "zh": P.zh_of(m["atoms"]),
                            "atoms": list(m["atoms"]),
                            "edges": [list(e) for e in m["edges"]],
                            "place": {str(k): list(p) for k, p in cache[key].items()},
                            "feed": list(counts)}
                if len(m["atoms"]) > best:
                    best = len(m["atoms"])
                    bestf = f
    return "/".join(elems), T, best, bestf, found, nfeed


def main():
    Tmin = int(sys.argv[1]) if len(sys.argv) > 1 else 17
    Tmax = int(sys.argv[2]) if len(sys.argv) > 2 else 48
    jobs = int(sys.argv[3]) if len(sys.argv) > 3 else max(2, (os.cpu_count() or 4) - 2)
    triples = [list(t) for t in itertools.combinations(P.ORDER, 3)]
    tasks = [(t, T, 800000) for t in triples for T in range(Tmin, Tmax + 1)]
    print(f"triples={len(triples)}, T={Tmin}..{Tmax}, tasks={len(tasks)}, jobs={jobs}", flush=True)
    data = {}
    t0 = time.time()
    done = 0
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for key, T, best, bestf, found, nfeed in ex.map(work, tasks):
            d = data.setdefault(key, {"elems": key.split("/"), "Tmax": Tmax, "substances": {},
                                      "max": 0, "max_formula": None})
            for f, item in found.items():
                d["substances"].setdefault(f, item)
            if best > d["max"]:
                d["max"], d["max_formula"] = best, bestf
            done += 1
            if done % 200 == 0 or done == len(tasks):
                print(f"  {done}/{len(tasks)} tasks, {time.time()-t0:.0f}s", flush=True)
    for d in data.values():
        d["n"] = len(d["substances"])
        d["substances"] = sorted(d["substances"].values(), key=lambda x: (x["natoms"], x["formula"]))
    json.dump(data, open(BASE + r"\t4_triples_complete.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"saved t4_triples_complete.json: {len(data)} triples, 用时 {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
