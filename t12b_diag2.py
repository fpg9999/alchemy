# -*- coding: utf-8 -*-
"""t12b_diag2.py —— 研究 embedding 尾部：抽 5000 唯一向量测耗时/超时；对病态向量试不同 max_nodes。"""
import json
import random
import sys
import time
from collections import Counter

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import t12b_embed as E

BASE = r"G:\AI work\deepseek\work1\alchemy"
ORDER = P.ORDER


def react_diag(v, cap=300000):
    atoms = [s for s, c in zip(ORDER, v) for _ in range(c)]
    t0 = time.perf_counter()
    mols = P.simulate(atoms)
    t1 = time.perf_counter()
    if mols is None:
        return "simfail", t1 - t0, 0.0, 0
    st, bad = E.embed_all_status(mols, max_nodes=cap)
    t2 = time.perf_counter()
    return st, t1 - t0, t2 - t1, max(len(m["atoms"]) for m in mols)


def test_vec(v, caps=(10000, 50000, 100000, 300000, 1000000, 3000000)):
    atoms = [s for s, c in zip(ORDER, v) for _ in range(c)]
    mols = P.simulate(atoms)
    if mols is None:
        print(v, "simfail")
        return
    big = max(mols, key=lambda m: len(m["atoms"]))
    print(f"vec={v} natoms={sum(v)} molecules={[len(m['atoms']) for m in mols]}")
    for cap in caps:
        t0 = time.perf_counter()
        st, _ = E.embed_all_status(mols, max_nodes=cap)
        dt = time.perf_counter() - t0
        print(f"   cap={cap:>8}: {st:8s} {dt*1000:8.1f} ms")
    t0 = time.perf_counter()
    st, _ = E.embed_status(big["atoms"], big["edges"], max_nodes=10**9)
    dt = time.perf_counter() - t0
    print(f"   uncapped big: {st} {dt*1000:.1f}ms" if dt < 60 else
          f"   uncapped big: {st} {dt:.1f}s")


def main():
    S = json.load(open(BASE + r"\t12b_S.json", encoding="utf-8"))
    vecs = [tuple(d["vec"]) for d in S]
    n = len(vecs)
    rng = random.Random(11)
    seen = set()
    vs = []
    while len(vs) < 5000:
        i = rng.randrange(n)
        j = rng.randrange(n)
        v = tuple(vecs[i][k] + vecs[j][k] for k in range(9))
        if v in seen:
            continue
        seen.add(v)
        vs.append(v)

    t_sim = t_emb = 0.0
    status = Counter()
    slow = []
    t0 = time.time()
    for v in vs:
        st, a, b, sz = react_diag(v, cap=300000)
        t_sim += a
        t_emb += b
        status[st] += 1
        if a + b > 0.05:
            slow.append((a + b, v, st, sz))
    dt = time.time() - t0
    slow.sort(reverse=True)
    print(f"\n5000 向量 cap=3e5: {dt:.1f}s => {dt/5000*1000:.2f} ms/向量")
    print(f"sim {t_sim:.1f}s  emb {t_emb:.1f}s  状态 {dict(status)}")
    print(f">50ms 的向量 {len(slow)} 个，最慢 10:")
    for x in slow[:10]:
        print(f"   {x[0]*1000:9.1f}ms {x[2]:8s} sz={x[3]:2d} {x[1]}")
    print(f"\n病态向量专项：")
    for v in [(2, 1, 0, 5, 5, 0, 0, 0, 1), (3, 4, 1, 5, 0, 1, 2, 0, 0),
              (1, 0, 0, 8, 0, 0, 7, 0, 0)]:
        test_vec(v)


if __name__ == "__main__":
    main()
