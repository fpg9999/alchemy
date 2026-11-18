# -*- coding: utf-8 -*-
"""t3_anneal：以已知大分子投料比例为起点，在固定 T 下做随机扰动/爬山，最大化最大单分子尺寸。
若不同 T 下最大尺寸持续上升则支持"无界增长"；若在 ~70 附近封顶则支持"有限封顶"。
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
BASE_FEED = [3, 9, 10, 7, 2, 0, 30, 17, 2]


def outcome(feed):
    atoms = P.vec_to_atoms(tuple(feed), P.ORDER)
    if not atoms or sum(P.VAL[e] for e in atoms) % 2:
        return None
    mols = P.simulate(atoms)
    if not mols:
        return None
    sizes = sorted((len(m["atoms"]) for m in mols), reverse=True)
    return sizes, mols


def score(feed):
    o = outcome(feed)
    if o is None:
        return (-1, 999)
    return (o[0][0], len(o[0]))


def scale_feed(T, rng, noise=0.35):
    w = [max(0.01, c * (1 + noise * rng.gauss(0, 1))) for c in BASE_FEED]
    s = sum(w)
    counts = [max(0, int(round(T * x / s))) for x in w]
    while sum(counts) < T:
        counts[rng.randrange(9)] += 1
    while sum(counts) > T:
        i = rng.randrange(9)
        if counts[i] > 0:
            counts[i] -= 1
    if sum(P.VAL[e] * c for e, c in zip(P.ORDER, counts)) % 2:
        counts[rng.randrange(9)] += 1
    return counts


def validate(feed):
    o = outcome(feed)
    if o is None:
        return None
    sizes, mols = o
    ok = True
    for m in mols:
        if P.embed_mol(m["atoms"], m["edges"], max_nodes=800000) is None:
            ok = False
            break
    big = [m for m in mols if len(m["atoms"]) == sizes[0]][0]
    return {"max": sizes[0], "sizes": sizes, "pot_ok": ok,
            "formula": P.formula_of(big["atoms"]), "feed": list(feed), "T": sum(feed),
            "elements": sorted(set(big["atoms"]))}


def task(args):
    T, seed = args
    rng = random.Random(seed)
    best_feed, best_sc = None, (-1, 999)
    t0 = time.time()
    for it in range(250):
        f = scale_feed(T, rng, noise=0.5 if it % 2 else 0.2)
        sc = score(f)
        if sc > best_sc:
            best_feed, best_sc = f, sc
    cur = list(best_feed)
    cur_sc = best_sc
    for it in range(250):
        cand = list(cur)
        if rng.random() < 0.5:
            i, j = rng.randrange(9), rng.randrange(9)
            if cand[i] > 0:
                cand[i] -= 1
                cand[j] += 1
        else:
            for _ in range(rng.randint(1, 3)):
                i, j = rng.randrange(9), rng.randrange(9)
                if cand[i] > 0:
                    cand[i] -= 1
                    cand[j] += 1
        if sum(cand) != sum(cur):
            continue
        sc = score(cand)
        if sc > cur_sc:
            cur, cur_sc = cand, sc
    rec = validate(cur)
    rec["seconds"] = round(time.time() - t0, 1)
    print(f"T={T} max={rec['max']} {rec['formula']} pot_ok={rec['pot_ok']} feed={rec['feed']} ({rec['seconds']}s)", flush=True)
    return T, rec


def main():
    Ts = [int(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else [96, 128]
    jobs = min(len(Ts) * 2, max(2, (os.cpu_count() or 4) // 2))
    tasks = [(T, 1000 * i + T) for i in range(2) for T in Ts]
    out = {}
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for T, rec in ex.map(task, tasks):
            if T not in out or rec["max"] > out[T]["max"]:
                out[T] = rec
    json.dump(out, open(BASE + r"\t3_anneal.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n== summary ==")
    for T in sorted(out):
        r = out[T]
        print(f"T={T}: max={r['max']} {r['formula']} pot_ok={r['pot_ok']}")


if __name__ == "__main__":
    main()
