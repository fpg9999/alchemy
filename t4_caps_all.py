# -*- coding: utf-8 -*-
"""t4_caps_all：对全部 511 个元素子集搜索"已知最大合法分子"（封顶下界）。

策略：对每个子集、每个 T∈{32,48,64,96}，随机+爬山搜索投料比例，最大化最大分子尺寸；
收集若干个高分候选，按尺寸降序用 pot_v2 严格校验（预算 300k），记录最大合法分子。
≤3 元素的子集已有完备枚举，以完备枚举为准。
输出 t4_caps_all.json
"""
import itertools
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
THREE = set("OPK")
TWO = set("XWA")


def rand_comp(T, k, rng, bias=False):
    if bias:
        w = [1.0 if P.VAL[e] == 3 else (1.5 if P.VAL[e] == 2 else 0.6) for e in range(1)]
    cuts = sorted(rng.sample(range(T + k - 1), k - 1)) if k > 1 else []
    out, prev = [], -1
    for c in cuts + [T + k - 1]:
        out.append(c - prev - 1)
        prev = c
    return out


def outcome(elems, feed):
    atoms = P.vec_to_atoms(tuple(feed), elems)
    if sum(P.VAL[e] for e in atoms) % 2:
        return None
    mols = P.simulate(atoms)
    if not mols:
        return None
    sizes = sorted((len(m["atoms"]) for m in mols), reverse=True)
    return sizes, mols


def score(elems, feed):
    o = outcome(elems, feed)
    if o is None:
        return (-1, 999)
    return (o[0][0], len(o[0]))


def search(elems, T, iters, rng):
    k = len(elems)
    best = [(0, None)]
    cur = rand_comp(T, k, rng)
    if sum(P.VAL[e] * c for e, c in zip(elems, cur)) % 2:
        cur[rng.randrange(k)] += 1
    cur_sc = score(elems, cur)
    for it in range(iters):
        cand = list(cur)
        for _ in range(rng.randint(1, 3)):
            i, j = rng.randrange(k), rng.randrange(k)
            if cand[i] > 0:
                cand[i] -= 1
                cand[j] += 1
        if sum(cand) != T:
            continue
        sc = score(elems, cand)
        if sc > cur_sc:
            cur, cur_sc = cand, sc
            best.append((sc[0], list(cand)))
        elif rng.random() < 0.05:
            cur, cur_sc = cand, sc
    best.sort(key=lambda x: -x[0])
    # 去重
    seen = set()
    out = []
    for s, f in best:
        if f is None:
            continue
        key = (s, tuple(f))
        if key in seen:
            continue
        seen.add(key)
        out.append((s, f))
    return out[:4]


def task(args):
    elems, T, iters, seed = args
    rng = random.Random(seed)
    cands = search(elems, T, iters, rng)
    for s, f in cands:
        if s <= 0:
            continue
        o = outcome(elems, f)
        if o is None:
            continue
        sizes, mols = o
        # 只校验最大分子
        big = [m for m in mols if len(m["atoms"]) == sizes[0]][0]
        pl = pot_v2.embed_mol2(big["atoms"], big["edges"], max_nodes=300000)
        ok, msg = pot_v2.validate_place(pl, big["atoms"], big["edges"])
        if ok:
            return {"elems": elems, "T": T, "feed": f, "natoms": sizes[0],
                    "valid": True, "formula": P.formula_of(big["atoms"]),
                    "pot_ok": True}
    return {"elems": elems, "T": T, "feed": cands[0][1] if cands else None,
            "natoms": cands[0][0] if cands else 0, "valid": False, "formula": None}


def main():
    jobs = int(sys.argv[1]) if len(sys.argv) > 1 else max(2, (os.cpu_count() or 4) - 2)
    iter_per_T = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    subsets = [list(c) for n in range(1, 10) for c in itertools.combinations(P.ORDER, n)]
    tasks = []
    for i, sub in enumerate(subsets):
        if len(sub) <= 3:
            continue  # 完备枚举已覆盖
        k = len(sub)
        if k <= 5:
            Ts = [32, 48, 64, 96]
        elif k <= 7:
            Ts = [64, 96, 128]
        else:
            Ts = [96, 160, 192]
        for T in Ts:
            # 每个 T 给 3 个随机起点
            for r in range(3):
                tasks.append((sub, T, iter_per_T, i * 10000 + T * 10 + r))
    print(f"subsets>=4: {len(subsets)-129}, tasks {len(tasks)}, jobs {jobs}", flush=True)
    results = {}
    t0 = time.time()
    done = 0
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for rec in ex.map(task, tasks):
            key = "/".join(rec["elems"])
            d = results.setdefault(key, {"elems": rec["elems"], "best_valid": None, "best_any": 0})
            if rec["valid"] and (d["best_valid"] is None or rec["natoms"] > d["best_valid"]["natoms"]):
                d["best_valid"] = {"natoms": rec["natoms"], "formula": rec["formula"],
                                   "T": rec["T"], "feed": rec["feed"]}
            if rec["natoms"] > d["best_any"]:
                d["best_any"] = rec["natoms"]
            done += 1
            if done % 200 == 0:
                print(f"  {done}/{len(tasks)} {time.time()-t0:.0f}s", flush=True)
    json.dump(results, open(BASE + r"\t4_caps_all.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"saved t4_caps_all.json, {len(results)} subsets, {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
