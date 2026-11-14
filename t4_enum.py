# -*- coding: utf-8 -*-
"""t4_enum：正确的全枚举（修复后的可摆放校验 + 精确缓存），统计某元素池的真实物质集合。

用法: python t4_enum.py "<E1,E2,...>" <Tmax> [jobs]
- 枚举该元素池内总原子 <= Tmax 的所有投料向量；
- 规则 1~8 模拟；要求反应成功且**所有产物都能被严格校验的可摆放性接受**；
- 收集分子式（去重）、每条的合法摆放样例；输出 t4_enum_<name>.json
"""
import json
import os
import sys
from collections import defaultdict
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
    elems, Ts, budget = task
    found = {}
    cache = {}
    best = 0
    bestf = None
    nfeed = 0
    for T in Ts:
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
                    found[f] = {"formula": f, "natoms": len(m["atoms"]),
                                "zh": P.zh_of(m["atoms"]),
                                "atoms": list(m["atoms"]),
                                "edges": [list(e) for e in m["edges"]],
                                "place": {str(k): list(v) for k, v in cache[key].items()},
                                "feed": list(counts)}
                    if len(m["atoms"]) > best:
                        best = len(m["atoms"])
                        bestf = f
    return list(elems), best, bestf, found, nfeed


def main():
    elems = sys.argv[1].split(",")
    Tmax = int(sys.argv[2])
    Tmin = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    jobs = int(sys.argv[4]) if len(sys.argv) > 4 else max(2, (os.cpu_count() or 4) - 2)
    budget = 3_000_000
    tasks = [(elems, [T], budget) for T in range(Tmin, Tmax + 1)]
    allfound = {}
    best = 0
    bestf = None
    nfeed = 0
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for e, b, bf, found, nf in ex.map(work, tasks):
            nfeed += nf
            for f, item in found.items():
                if f not in allfound:
                    allfound[f] = item
            if b > best:
                best, bestf = b, bf
            print(f"T done, total formulas={len(allfound)}, max={best}({bestf}), feeds={nfeed}", flush=True)
    name = "_".join(elems)
    out = {"elems": elems, "Tmax": Tmax, "n_formulas": len(allfound),
           "max_atoms": best, "max_formula": bestf,
           "by_natoms": dict(sorted((n, sum(1 for x in allfound.values() if x["natoms"] == n))
                                    for n in {x["natoms"] for x in allfound.values()})),
           "substances": sorted(allfound.values(), key=lambda x: (x["natoms"], x["formula"]))}
    json.dump(out, open(BASE + rf"\t4_enum_{name}.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"saved t4_enum_{name}.json: {len(allfound)} formulas, max {best} ({bestf}), feeds {nfeed}")


if __name__ == "__main__":
    main()
