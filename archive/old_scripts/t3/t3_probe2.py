# -*- coding: utf-8 -*-
"""t3_probe2：多进程随机大投料探针（用于找"有限封顶"证据 / 发现无限增长）。

用法: python t3_probe2.py "<elems;elems;...>" "<T,T,...>" <samples> [seed]
输出: t3_probe2.json
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


def work(task):
    key, T, samples, seed = task
    elems = key.split(",")
    rng = random.Random(seed)
    best = (0, None, None)
    seen = {}
    ok = 0
    for _ in range(samples):
        counts = rand_vec(T, len(elems), rng)
        atoms = P.vec_to_atoms(tuple(counts), elems)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        mols = P.simulate(atoms)
        if not mols:
            continue
        mx = max(len(m["atoms"]) for m in mols)
        m = [x for x in mols if len(x["atoms"]) == mx][0]
        if P.embed_mol(m["atoms"], m["edges"], max_nodes=300000) is None:
            continue
        if not P.embed_all(mols):
            continue
        ok += 1
        f = P.formula_of(m["atoms"])
        nm = len(mols)
        seen[f] = seen.get(f, 0) + 1
        if mx > best[0]:
            best = (mx, f, list(counts))
    return key, T, best, ok, seen


def main():
    keys = sys.argv[1].split(";")
    Ts = [int(x) for x in sys.argv[2].split(",")]
    samples = int(sys.argv[3]) if len(sys.argv) > 3 else 500
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 12345
    jobs = max(2, (os.cpu_count() or 4) - 2)
    tasks = []
    for i, k in enumerate(keys):
        for T in Ts:
            tasks.append((k, T, samples, seed + i * 1000 + T))
    out = {}
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for key, T, best, ok, seen in ex.map(work, tasks):
            out.setdefault(key, {})[str(T)] = {"max": best[0], "formula": best[1],
                                               "feed": best[2], "ok": ok, "samples": samples}
            print(f"{key:18s} T={T:2d} max={best[0]:2d} {best[1]} feed={best[2]} ok={ok}", flush=True)
    json.dump(out, open(BASE + r"\t3_probe2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved t3_probe2.json")


if __name__ == "__main__":
    main()
