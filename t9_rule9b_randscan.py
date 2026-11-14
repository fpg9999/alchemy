# -*- coding: utf-8 -*-
"""t9_rule9b_randscan：用随机并列采样比较
   (基线) 规则 1~8 alone  vs  (用户规则 9) 规则 1~8 + 大类并集数。
对每个投料跑 K 次随机并列，产物分子式多重集若出现 >1 种 → 判为"仍有分歧"。
"""
import json
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
from t9_rule9b_rand import simulate_rule9b

BASE = r"G:\AI work\deepseek\work1\alchemy"


def gen_compositions(total, k, prefix=()):
    if k == 1:
        yield prefix + (total,)
        return
    for x in range(total + 1):
        yield from gen_compositions(total - x, k - 1, prefix + (x,))


def work(args):
    T, runs = args
    rng = random.Random(1000 + T)
    ncase = 0
    base_amb = []
    r9_amb = []
    for counts in gen_compositions(T, 9):
        atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        ncase += 1
        # 基线
        outs = set()
        for _ in range(runs):
            r = P.simulate(atoms, rng=rng)
            if r is None:
                outs = None
                break
            outs.add(tuple(sorted(P.formula_of(m["atoms"]) for m in r)))
        if outs is not None and len(outs) > 1:
            base_amb.append({"feed": list(counts), "outcomes": [list(o) for o in list(outs)[:4]]})
        # 用户规则 9
        outs9 = set()
        for _ in range(runs):
            r = simulate_rule9b(atoms, rng)
            if r is None:
                outs9 = None
                break
            outs9.add(r)
        if outs9 is not None and len(outs9) > 1:
            r9_amb.append({"feed": list(counts), "outcomes": [list(o) for o in list(outs9)[:4]]})
    return T, ncase, base_amb, r9_amb


def main():
    Tmax = int(sys.argv[1]) if len(sys.argv) > 1 else 9
    runs = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    jobs = int(sys.argv[3]) if len(sys.argv) > 3 else max(2, (os.cpu_count() or 4) - 2)
    results = {}
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for T, ncase, base_amb, r9_amb in ex.map(work, [(T, runs) for T in range(3, Tmax + 1)]):
            results[str(T)] = {"ncase": ncase, "runs": runs,
                               "base_ambiguous": len(base_amb),
                               "rule9b_ambiguous": len(r9_amb),
                               "base_examples": base_amb[:5],
                               "rule9b_examples": r9_amb[:8]}
            print(f"T={T}: 投料 {ncase}, 基线歧义 {len(base_amb)}, 规则9b后歧义 {len(r9_amb)}", flush=True)
            for e in r9_amb[:3]:
                print("   ", e["feed"], "->", e["outcomes"], flush=True)
    json.dump(results, open(BASE + r"\t9_rule9b_randscan.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
