# -*- coding: utf-8 -*-
"""t3_exact_growth：对给定元素子集，按"总原子恰好=T"做全枚举，得到最大单分子尺寸随 T 的变化。
用于严格判定该子集是"无限"（max 随 T 增长不封顶）还是"有限"（封顶）。

用法:
  python t3_exact_growth.py X,C,K,A 20,24,28,32,36,40,48,56,64 [jobs] [max_nodes]
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
EMBED_BUDGET = 200000


def gen_compositions(total, k, prefix=()):
    if k == 1:
        yield prefix + (total,)
        return
    for x in range(total + 1):
        yield from gen_compositions(total - x, k - 1, prefix + (x,))


def work(task):
    elems, T, vecs, budget = task
    best = (0, None, None)
    ok_feeds = 0
    hist = {}
    for counts in vecs:
        atoms = P.vec_to_atoms(counts, elems)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        mols = P.simulate(atoms)
        if not mols:
            continue
        mx = max(len(m["atoms"]) for m in mols)
        m = [x for x in mols if len(x["atoms"]) == mx][0]
        if P.embed_mol(m["atoms"], m["edges"], max_nodes=budget) is None:
            continue
        if not P.embed_all(mols):
            continue
        ok_feeds += 1
        hist[mx] = hist.get(mx, 0) + 1
        if mx > best[0]:
            best = (mx, P.formula_of(m["atoms"]), list(counts))
    return elems, T, best, ok_feeds, hist


def main():
    elems = sys.argv[1].split(",")
    Ts = [int(x) for x in sys.argv[2].split(",")]
    jobs = int(sys.argv[3]) if len(sys.argv) > 3 else max(2, (os.cpu_count() or 4) - 2)
    budget = int(sys.argv[4]) if len(sys.argv) > 4 else EMBED_BUDGET
    result = {"elems": elems, "budget": budget, "T": {}}
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for T in Ts:
            vecs = list(gen_compositions(T, len(elems)))
            CH = 800
            tasks = [(elems, T, vecs[i:i + CH], budget) for i in range(0, len(vecs), CH)]
            best = (0, None, None)
            ok = 0
            hist = {}
            for _, _, b, o, h in ex.map(work, tasks):
                ok += o
                for k, v in h.items():
                    hist[k] = hist.get(k, 0) + v
                if b[0] > best[0]:
                    best = b
            result["T"][str(T)] = {"max": best[0], "formula": best[1], "feed": best[2],
                                   "ok_feeds": ok, "nvec": len(vecs), "hist": hist}
            print(f"T={T:2d}: max={best[0]:2d} {best[1]} feed={best[2]} "
                  f"ok_feeds={ok}/{len(vecs)} top_hist={sorted(hist.items())[-6:]}", flush=True)
            json.dump(result, open(BASE + rf"\t3_exact_{'_'.join(elems)}.json", "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
    print("saved", BASE + rf"\t3_exact_{'_'.join(elems)}.json")


if __name__ == "__main__":
    main()
