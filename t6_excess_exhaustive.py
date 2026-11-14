# -*- coding: utf-8 -*-
"""t6_excess_exhaustive：对全 9 元素计数各 <=N 穷举，统计单组件 Σ(rem-1) 的最大值。"""
import itertools
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
from t6_excess import max_excess

BASE = r"G:\AI work\deepseek\work1\alchemy"


def work(args):
    n0, NMAX = args
    best = 0
    bestcounts = None
    ncase = 0
    for rest in itertools.product(range(NMAX + 1), repeat=8):
        counts = (n0,) + rest
        if sum(counts) == 0:
            continue
        atoms = []
        for e, c in zip(P.ORDER, counts):
            atoms += [e] * c
        m = max_excess(atoms)
        if m is None:
            continue
        ncase += 1
        if m > best:
            best, bestcounts = m, counts
    return n0, best, bestcounts, ncase


def main():
    NMAX = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    jobs = int(sys.argv[2]) if len(sys.argv) > 2 else max(2, (os.cpu_count() or 4) - 2)
    overall = 0
    case = None
    ncase = 0
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for n0, best, bc, nc in ex.map(work, [(n0, NMAX) for n0 in range(NMAX + 1)]):
            ncase += nc
            if best > overall:
                overall, case = best, bc
            print(f"nO={n0}: max excess so far {overall} case {case}", flush=True)
    print("NMAX", NMAX, "cases", ncase, "overall max excess", overall, "case", case)
    json.dump({"NMAX": NMAX, "cases": ncase, "max_excess": overall, "case": case},
              open(BASE + rf"\t6_excess_exhaustive_{NMAX}.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
