# -*- coding: utf-8 -*-
"""t8_rule9_sample：在 T=10..16 的随机投料上测规则 9 的
   (a) 与 tied[0] 的差异率；(b) 置换不变性；(c) 规则 9 的结果是否落在并列 DFS 的结果集里。"""
import json
import random
import sys
import time
from collections import Counter

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
from t8_canon import simulate_r9

BASE = r"G:\AI work\deepseek\work1\alchemy"


def det_outcome(atoms):
    mols = P.simulate(atoms)
    if mols is None:
        return None
    return tuple(sorted(P.formula_of(m["atoms"]) for m in mols))


def main():
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    rng = random.Random(777)
    ncase = 0
    n_diff = 0
    n_bad = 0
    diffs = []
    t0 = time.time()
    for it in range(N):
        T = rng.randint(10, 16)
        counts = [0] * 9
        for _ in range(T):
            counts[rng.randrange(9)] += 1
        atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        ncase += 1
        base = det_outcome(atoms)
        r9 = simulate_r9(atoms)
        if r9 is None:
            continue
        if r9 != base:
            n_diff += 1
            if len(diffs) < 6:
                diffs.append({"feed": counts, "T": T, "tied0": list(base), "rule9": list(r9)})
        perm = list(atoms)
        rng.shuffle(perm)
        r9b = simulate_r9(perm)
        if r9b != r9:
            n_bad += 1
            if len(diffs) < 6:
                diffs.append({"feed": counts, "T": T, "rule9": list(r9),
                              "permuted": list(r9b) if r9b else None})
        if (it + 1) % 20 == 0:
            print(f"{it+1}/{N} cases={ncase} diff={n_diff} perm_bad={n_bad} {time.time()-t0:.1f}s", flush=True)
    print("RESULT", {"N": N, "cases": ncase, "diff_vs_tied0": n_diff,
                     "perm_invariance_bad": n_bad, "time": round(time.time() - t0, 1)})
    json.dump({"N": N, "cases": ncase, "diff_vs_tied0": n_diff,
               "perm_invariance_bad": n_bad, "examples": diffs},
              open(BASE + r"\t8_rule9_sample.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
