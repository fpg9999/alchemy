# -*- coding: utf-8 -*-
"""t12b_diag.py —— 诊断：不同 natoms 的向量反应耗时（simulate / embed 分别计时）。
用于决定全量计算的分块与 max_nodes 上限。
"""
import json
import random
import sys
import time
from collections import Counter, defaultdict

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v2

BASE = r"G:\AI work\deepseek\work1\alchemy"
ORDER = P.ORDER


def time_vec(v, sim, max_nodes=None):
    atoms = [s for s, c in zip(ORDER, v) for _ in range(c)]
    t0 = time.perf_counter()
    mols = sim(atoms)
    t1 = time.perf_counter()
    if mols is None:
        return t1 - t0, 0.0, "sim_fail", 0
    t2 = time.perf_counter()
    ok = pot_v2.embed_all2(mols, max_nodes=max_nodes)
    t3 = time.perf_counter()
    if not ok:
        return t1 - t0, t3 - t2, "embed_fail", max(len(m["atoms"]) for m in mols)
    return t1 - t0, t3 - t2, "ok", max(len(m["atoms"]) for m in mols)


def main():
    S = json.load(open(BASE + r"\t12b_S.json", encoding="utf-8"))
    vecs = [tuple(d["vec"]) for d in S]
    n = len(vecs)
    rng = random.Random(7)
    # 统一按唯一向量空间抽样：随机 i,j
    samples = defaultdict(list)  # natoms -> list of vecs
    seen = set()
    while len(seen) < 3000:
        i = rng.randrange(n)
        j = rng.randrange(n)
        v = tuple(vecs[i][k] + vecs[j][k] for k in range(9))
        if v in seen:
            continue
        seen.add(v)
        samples[sum(v)].append(v)

    stats = {}
    for nat in sorted(samples):
        vs = samples[nat]
        if len(vs) < 20:
            continue
        t_sim = t_emb = 0.0
        reasons = Counter()
        sizes = Counter()
        worst = []
        for v in vs:
            a, b, why, sz = time_vec(v, P.simulate)
            t_sim += a
            t_emb += b
            reasons[why] += 1
            sizes[sz] += 1
            worst.append((a + b, v, why))
        worst.sort(reverse=True)
        stats[nat] = {"n": len(vs), "sim_ms": round(t_sim / len(vs) * 1000, 2),
                      "emb_ms": round(t_emb / len(vs) * 1000, 2),
                      "reasons": dict(reasons), "worst_ms": round(worst[0][0] * 1000, 1),
                      "worst": [str(w[1]) for w in worst[:3]]}
        print(nat, stats[nat], flush=True)

    # 针对最慢的做 max_nodes 测试
    allv = [v for nat in samples for v in samples[nat]]
    allv.sort(key=lambda v: sum(v))
    rng.shuffle(allv)
    t0 = time.time()
    tot_cap = 0.0
    for v in allv[:300]:
        a, b, why, sz = time_vec(v, P.simulate, max_nodes=2_000_000)
        tot_cap += a + b
    print(f"cap=2e6: 300 向量 {time.time()-t0:.2f}s => {tot_cap/300*1000:.2f}ms/向量(CPU)", flush=True)


if __name__ == "__main__":
    main()
