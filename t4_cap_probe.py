# -*- coding: utf-8 -*-
"""t4_cap_probe：对若干元素子集搜索"最大可摆放分子"（估算各类别封顶）。

对每个子集、每个固定 T：随机/爬山搜索投料比例，最大化最大分子尺寸；随后用 pot_v2 严格校验
最优候选是否可摆放。输出 t4_cap_probe.json。
"""
import json
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v2

BASE = r"G:\AI work\deepseek\work1\alchemy"


def rand_composition(T, k, rng):
    cuts = sorted(rng.sample(range(T + k - 1), k - 1)) if k > 1 else []
    out, prev = [], -1
    for c in cuts + [T + k - 1]:
        out.append(c - prev - 1)
        prev = c
    return out


def score(elems, feed):
    atoms = P.vec_to_atoms(tuple(feed), elems)
    if sum(P.VAL[e] for e in atoms) % 2:
        return (-1, 999)
    mols = P.simulate(atoms)
    if not mols:
        return (-1, 999)
    sizes = sorted((len(m["atoms"]) for m in mols), reverse=True)
    return (sizes[0], len(sizes))


def task(args):
    elems, T, iters, seed = args
    rng = random.Random(seed)
    k = len(elems)
    best_feed, best_sc = None, (-1, 999)
    for it in range(iters):
        if it % 3 == 0:
            f = rand_composition(T, k, rng)
            if sum(P.VAL[e] * c for e, c in zip(elems, f)) % 2:
                f[rng.randrange(k)] += 1
        else:
            f = list(best_feed) if best_feed else rand_composition(T, k, rng)
            for _ in range(rng.randint(1, 3)):
                i, j = rng.randrange(k), rng.randrange(k)
                if f[i] > 0:
                    f[i] -= 1
                    f[j] += 1
            if sum(P.VAL[e] * c for e, c in zip(elems, f)) % 2:
                continue
        sc = score(elems, f)
        if sc > best_sc:
            best_feed, best_sc = list(f), sc
    # 局部爬山
    cur = list(best_feed)
    cur_sc = best_sc
    for it in range(iters):
        cand = list(cur)
        for _ in range(rng.randint(1, 2)):
            i, j = rng.randrange(k), rng.randrange(k)
            if cand[i] > 0:
                cand[i] -= 1
                cand[j] += 1
        if sum(cand) != sum(cur):
            continue
        sc = score(elems, cand)
        if sc > cur_sc:
            cur, cur_sc = cand, sc
    # 校验最优候选
    atoms = P.vec_to_atoms(tuple(cur), elems)
    mols = P.simulate(atoms)
    rec = {"elems": elems, "T": T, "feed": cur, "raw_max": cur_sc[0],
           "nmols": len(mols) if mols else 0}
    if mols:
        big = max(mols, key=lambda m: len(m["atoms"]))
        t0 = time.time()
        pl = pot_v2.embed_mol2(big["atoms"], big["edges"], max_nodes=2_000_000)
        ok, msg = pot_v2.validate_place(pl, big["atoms"], big["edges"])
        rec.update({"formula": P.formula_of(big["atoms"]), "natoms": len(big["atoms"]),
                    "valid": ok, "msg": msg, "embed_s": round(time.time() - t0, 1)})
    return rec


def main():
    subsets = sys.argv[1].split(";") if len(sys.argv) > 1 else [
        "O/X/K/A", "X/C/K/A", "O/X/W/A", "O/X/P/K", "P/W/K/A",
        "O/X/K/A/P", "O/X/C/K/A", "O/X/C/P/W/K", "O/X/C/P/W/L/K/A/F",
    ]
    Ts = [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [32, 48, 64, 80]
    iters = int(sys.argv[3]) if len(sys.argv) > 3 else 80
    jobs = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    tasks = []
    for i, s in enumerate(subsets):
        elems = s.split("/")
        for T in Ts:
            tasks.append((elems, T, iters, 1000 * i + T))
    out = []
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for rec in ex.map(task, tasks):
            out.append(rec)
            print(f"{'/'.join(rec['elems']):20s} T={rec['T']:3d} raw={rec['raw_max']:3d} "
                  f"valid={rec.get('valid')} n={rec.get('natoms')} {rec.get('formula')}", flush=True)
    json.dump(out, open(BASE + r"\t4_cap_probe.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved t4_cap_probe.json")


if __name__ == "__main__":
    main()
