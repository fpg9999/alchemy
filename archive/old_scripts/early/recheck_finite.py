# -*- coding: utf-8 -*-
"""recheck_finite：复核当前 207 个"有限"类别——大投料 T=36 随机实测，找是否还能产出 >16 原子物质。

若某有限类别出现 >16 原子且整锅成功，说明分类需修正（可能无限或封顶 >16）。
"""
import json
import os
import random
import sys
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


def task(args):
    elems, T, samples, seed = args
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
        if mx <= 16 or mx <= best:
            continue
        big = [m for m in mols if len(m["atoms"]) == mx][0]
        if P.embed_mol(big["atoms"], big["edges"], max_nodes=40000) is None:
            continue
        ok = True
        for m in mols:
            if len(m["atoms"]) == mx:
                continue
            if P.embed_mol(m["atoms"], m["edges"], max_nodes=8000) is None:
                ok = False
                break
        if not ok:
            continue
        best = mx
        info = {"formula": P.formula_of(big["atoms"]), "feed": list(v), "nmols": len(mols)}
        if best >= 24:
            break
    return "/".join(elems), T, best, info


def main():
    cats = json.load(open(BASE + r"\catalog2_subsets.json", encoding="utf-8"))
    finite = [x["elems"] for x in cats if not x["infinite"]]
    print("有限类别:", len(finite), flush=True)
    jobs = max(4, (os.cpu_count() or 8) - 6)
    out = {}
    tasks = [(x, 36, 800, abs(hash(tuple(x))) & 0xffffffff) for x in finite]
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for key, T, best, info in pool.map(task, tasks):
            out[key] = {"T": T, "max": best, "info": info}
            if best > 16:
                print(f"  !! {key}: max={best} {info}", flush=True)
    json.dump(out, open(BASE + r"\recheck_finite.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    flag = {k: v for k, v in out.items() if v["max"] > 16}
    print(f"完成: {len(out)} 个有限类别，超 16 原子的 {len(flag)} 个")


if __name__ == "__main__":
    main()
