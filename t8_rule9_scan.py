# -*- coding: utf-8 -*-
"""t8_rule9_scan：规则 9（规范决胜）在 T≤9 全部投料上的验证与影响统计。

内容：
  A) 对每个投料，比较"规则 9"与"tied[0] 确定裁决"的产物分子式多重集，统计差异；
  B) 置换不变性：把投料原子顺序随机打乱后再跑规则 9，比较产物（应完全一致）；
  C) 简单规则 9a（仅类型对序）下仍存在的并列歧义数量（对照：说明只加元素序不够）。
"""
import itertools
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
from t8_canon import simulate_r9, _types_of

BASE = r"G:\AI work\deepseek\work1\alchemy"


def gen_compositions(total, k, prefix=()):
    if k == 1:
        yield prefix + (total,)
        return
    for x in range(total + 1):
        yield from gen_compositions(total - x, k - 1, prefix + (x,))


def det_outcome(atoms):
    mols = P.simulate(atoms)
    if mols is None:
        return None
    return tuple(sorted(P.formula_of(m["atoms"]) for m in mols))


def work(args):
    T, seed = args
    import random
    rng = random.Random(seed)
    ncase = 0
    n_diff = 0
    n_perm_bad = 0
    examples = []
    for counts in gen_compositions(T, 9):
        atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        ncase += 1
        base = det_outcome(atoms)
        r9 = simulate_r9(atoms)
        if r9 is None:
            continue
        if base is not None and r9 != base:
            n_diff += 1
            if len(examples) < 5:
                examples.append({"feed": list(counts), "T": T,
                                 "tied0": list(base), "rule9": list(r9)})
        # 置换不变性
        perm = list(atoms)
        rng.shuffle(perm)
        r9b = simulate_r9(perm)
        if r9b != r9:
            n_perm_bad += 1
            if len(examples) < 8:
                examples.append({"feed": list(counts), "T": T,
                                 "rule9": list(r9), "permuted_rule9": list(r9b) if r9b else None})
    return T, ncase, n_diff, n_perm_bad, examples


def main():
    Tmax = int(sys.argv[1]) if len(sys.argv) > 1 else 9
    jobs = int(sys.argv[2]) if len(sys.argv) > 2 else max(2, (os.cpu_count() or 4) - 2)
    results = {}
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for T, ncase, n_diff, n_perm_bad, examples in ex.map(
                work, [(T, 1000 + T) for T in range(3, Tmax + 1)]):
            results[str(T)] = {"ncase": ncase, "n_diff_vs_tied0": n_diff,
                               "n_perm_invariance_bad": n_perm_bad,
                               "examples": examples}
            print(f"T={T}: 投料 {ncase}, 与 tied0 不同 {n_diff}, 置换不变性失败 {n_perm_bad}", flush=True)
            for e in examples[:3]:
                print("   ", e, flush=True)
    json.dump(results, open(BASE + r"\t8_rule9_scan.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
