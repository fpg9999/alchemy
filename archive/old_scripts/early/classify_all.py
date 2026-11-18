# -*- coding: utf-8 -*-
"""classify_all：对全部 511 个元素类别做"大投料实测"分类（整锅成功口径）。

对每个类别：随机投料 T=24 与 T=32，模拟；若某产物分子 >16 原子，则做完整几何判定
（整锅所有产物都可摆才算成功），记录能得到的最大分子。输出 all511.json。
"""
import itertools
import json
import os
import random
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def rand_vec(total, k, rng):
    cuts = sorted(rng.sample(range(total + k - 1), k - 1)) if k > 1 else []
    out, prev = [], -1
    for c in cuts + [total + k - 1]:
        out.append(c - prev - 1)
        prev = c
    return out


def run_one(elems, T, samples, seed):
    rng = random.Random(seed)
    best = 0
    info = None
    for _ in range(samples):
        comp = rand_vec(T, len(elems), rng)
        v = [0] * 9
        for e, c in zip(elems, comp):
            v[P.ORDER.index(e)] = c
        atoms = P.vec_to_atoms(tuple(v), P.ORDER)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        mols = P.simulate(atoms)
        if not mols:
            continue
        mx = max(len(m["atoms"]) for m in mols)
        if mx > 16 and mx > best:
            ok = True
            for m in mols:
                if P.embed_mol(m["atoms"], m["edges"], max_nodes=60000) is None:
                    ok = False
                    break
            if ok:
                m = [x for x in mols if len(x["atoms"]) == mx][0]
                best = mx
                info = {"formula": P.formula_of(m["atoms"]), "feed": list(v), "nmols": len(mols)}
    return {"elems": elems, "T": T, "max": best, "info": info}


def task(args):
    elems, T, samples, seed = args
    return run_one(elems, T, samples, seed)


def main():
    pools = []
    for r in range(1, 10):
        for c in itertools.combinations(P.ORDER, r):
            pools.append(list(c))
    jobs = max(4, (os.cpu_count() or 8) - 6)
    tasks = []
    for p in pools:
        for T, samples in ((24, 500), (32, 700)):
            tasks.append((p, T, samples, abs(hash((tuple(p), T))) & 0xffffffff))
    res = defaultdict(dict)
    done = 0
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for out in pool.map(task, tasks):
            key = "/".join(out["elems"])
            T = out["T"]
            if T not in res[key] or out["max"] > res[key][T]["max"]:
                res[key][T] = {"max": out["max"], "info": out["info"]}
            done += 1
            if done % 100 == 0:
                print(f"  完成 {done}/{len(tasks)}", flush=True)
                json.dump(res, open(BASE + r"\all511.json", "w", encoding="utf-8"),
                          ensure_ascii=False, indent=1)
    json.dump(res, open(BASE + r"\all511.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved all511.json", len(res))


if __name__ == "__main__":
    main()
