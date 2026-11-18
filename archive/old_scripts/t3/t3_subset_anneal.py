# -*- coding: utf-8 -*-
"""t3_subset_anneal：对给定元素子集，在固定 T 下搜索"最大化最大单分子"的投料比例。
判据：若能在 T 下产出接近 T 的单个分子（或明显超过已知有限封顶 ~40），则该子集可无限增长。

用法: python t3_subset_anneal.py "T1,T2" "<S1;S2;...>" [evals] [seeds]
"""
import json
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def outcome(feed, elems):
    atoms = P.vec_to_atoms(tuple(feed), elems)
    if not atoms or sum(P.VAL[e] for e in atoms) % 2:
        return None
    mols = P.simulate(atoms)
    if not mols:
        return None
    sizes = sorted((len(m["atoms"]) for m in mols), reverse=True)
    return sizes, mols


def score(feed, elems):
    o = outcome(feed, elems)
    if o is None:
        return (-1, 999)
    return (o[0][0], len(o[0]))


def rand_feed(T, k, rng):
    cuts = sorted(rng.sample(range(T + k - 1), k - 1)) if k > 1 else []
    out, prev = [], -1
    for c in cuts + [T + k - 1]:
        out.append(c - prev - 1)
        prev = c
    # 修正价数和为偶数
    if sum(P.VAL[e] * c for e, c in zip(elems_global, out)) % 2:
        out[rng.randrange(k)] += 1
    return out


def task(args):
    elems, T, iters, seed = args
    global elems_global
    elems_global = elems
    rng = random.Random(seed)
    k = len(elems)
    t0 = time.time()
    best_feed, best_sc = None, (-1, 999)
    cur_sc = None
    # 多起点：30% 均匀随机、70% 用"K/A 富集"等偏置模式
    for it in range(iters):
        if it % 5 < 2:
            f = rand_feed(T, k, rng)
        else:
            # 偏置：让最高价/3 价元素与 2 价元素都大量出现
            w = [1.0 if P.VAL[e] == 3 else (1.5 if P.VAL[e] == 2 else 0.6) for e in elems]
            for _ in range(6):
                w[rng.randrange(k)] *= rng.uniform(0.5, 2.0)
            s = sum(w)
            f = [max(0, int(round(T * x / s))) for x in w]
            while sum(f) < T:
                f[rng.randrange(k)] += 1
            while sum(f) > T:
                i = rng.randrange(k)
                if f[i] > 0:
                    f[i] -= 1
            if sum(P.VAL[e] * c for e, c in zip(elems, f)) % 2:
                f[rng.randrange(k)] += 1
        sc = score(f, elems)
        if sc > best_sc:
            best_feed, best_sc = f, sc
    # 局部爬山
    cur = list(best_feed)
    cur_sc = best_sc
    for it in range(iters):
        cand = list(cur)
        if rng.random() < 0.5:
            i, j = rng.randrange(k), rng.randrange(k)
            if cand[i] > 0:
                cand[i] -= 1
                cand[j] += 1
        else:
            for _ in range(rng.randint(1, 3)):
                i, j = rng.randrange(k), rng.randrange(k)
                if cand[i] > 0:
                    cand[i] -= 1
                    cand[j] += 1
        if sum(cand) != sum(cur):
            continue
        sc = score(cand, elems)
        if sc > cur_sc:
            cur, cur_sc = cand, sc
    # 校验最优
    o = outcome(cur, elems)
    rec = {"elems": elems, "T": T, "feed": cur, "score": cur_sc[0], "seconds": round(time.time() - t0, 1)}
    if o:
        sizes, mols = o
        ok = True
        for m in mols:
            if P.embed_mol(m["atoms"], m["edges"], max_nodes=3000000) is None:
                ok = False
                break
        big = [m for m in mols if len(m["atoms"]) == sizes[0]][0]
        rec.update({"max": sizes[0], "sizes": sizes, "pot_ok": ok,
                    "formula": P.formula_of(big["atoms"])})
    print(f"{'/'.join(elems):12s} T={T} max={rec.get('max')} pot_ok={rec.get('pot_ok')} "
          f"formula={rec.get('formula')} feed={cur} ({rec['seconds']}s)", flush=True)
    return rec


def main():
    Ts = [int(x) for x in sys.argv[1].split(",")]
    subsets = [s.split("/") for s in sys.argv[2].split(";")]
    iters = int(sys.argv[3]) if len(sys.argv) > 3 else 150
    seeds = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    jobs = max(2, (os.cpu_count() or 4) // 2 - 2)
    tasks = [(sub, T, iters, seed * 7919 + 13) for T in Ts for sub in subsets for seed in range(seeds)]
    out = []
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for rec in ex.map(task, tasks):
            out.append(rec)
    json.dump(out, open(BASE + r"\t3_subset_anneal.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n== sorted ==")
    for r in sorted(out, key=lambda r: -r.get("max", 0)):
        print(f"{'/'.join(r['elems']):12s} T={r['T']:3d} max={r.get('max')} "
              f"ratio={(r.get('max') or 0)/r['T']:.2f} pot_ok={r.get('pot_ok')}")


elems_global = []

if __name__ == "__main__":
    main()
