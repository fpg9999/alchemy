# -*- coding: utf-8 -*-
"""t3_exact96：对指定的少量子集在较大 T 做全枚举（只模拟），检查最大单分子是否继续增长。

用法: python t3_exact96.py "<S1;S2...>" "<T,T,...>" [jobs]
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def gen_compositions(total, k, prefix=()):
    if k == 1:
        yield prefix + (total,)
        return
    for x in range(total + 1):
        yield from gen_compositions(total - x, k - 1, prefix + (x,))


def work(task):
    elems, T = task
    best = None
    ok = 0
    for counts in gen_compositions(T, len(elems)):
        atoms = P.vec_to_atoms(counts, elems)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        mols = P.simulate(atoms)
        if not mols:
            continue
        ok += 1
        mx = max(len(m["atoms"]) for m in mols)
        if best is None or mx > best[0]:
            m = [x for x in mols if len(x["atoms"]) == mx][0]
            best = (mx, P.formula_of(m["atoms"]), list(counts),
                    [list(m["atoms"]), [list(e) for e in m["edges"]]])
    return "/".join(elems), T, best, ok


def main():
    subsets = [s.split(",") for s in sys.argv[1].split(";")]
    Ts = [int(x) for x in sys.argv[2].split(",")]
    jobs = int(sys.argv[3]) if len(sys.argv) > 3 else max(2, (os.cpu_count() or 4) // 2)
    tasks = [(s, T) for s in subsets for T in Ts]
    out = {}
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for key, T, best, ok in ex.map(work, tasks):
            out.setdefault(key, {})[str(T)] = {"max": best[0], "formula": best[1],
                                               "feed": best[2], "mol": best[3], "ok": ok}
            print(f"{key:10s} T={T:3d} max={best[0]:3d} {best[1]} ok={ok}", flush=True)
            json.dump(out, open(BASE + r"\t3_exact96.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved")


if __name__ == "__main__":
    main()
