# -*- coding: utf-8 -*-
"""t12c_inspect.py —— T12C 前置：目录分布 / 性能测速（分模式，避免一次跑太久）。
用法：
  python t12c_inspect.py dist          # 分布 + feed/formula 一致性
  python t12c_inspect.py bench O:6 K:9 A:11 ...   # 计时给定 feed
"""
import json, time, sys
from collections import Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v2
import pot_v3

BASE = r"G:\AI work\deepseek\work1\alchemy"
ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]


def atoms_of_feed(feed):
    return [s for s, c in zip(ORDER, feed) for _ in range(c)]


def load():
    t0 = time.time()
    cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
    print(f"load {len(cat)} in {time.time()-t0:.1f}s", flush=True)
    return cat


def dist():
    cat = load()
    na = Counter(d["natoms"] for d in cat)
    print("natoms 分布:", flush=True)
    for k in sorted(na):
        print(f"  {k:3d}: {na[k]}", flush=True)
    layers = [(2, 8), (9, 16), (17, 32), (33, 10**9)]
    for lo, hi in layers:
        n = sum(1 for d in cat if lo <= d["natoms"] <= hi)
        print(f"layer {lo}-{hi if hi < 10**9 else '+':>3}: {n} entries", flush=True)
    # feed vs formula
    mism = []
    for d in cat:
        if P.parse_formula(d["formula"]) != tuple(d["feed"]):
            mism.append(d["formula"])
    print(f"feed/formula 不一致: {len(mism)} / {len(cat)}", mism[:10], flush=True)
    # 源分布
    print("source:", Counter(d.get("source") for d in cat), flush=True)
    # 唯一向量数
    vs = set(tuple(d["feed"]) for d in cat)
    print(f"唯一向量: {len(vs)} / 条目 {len(cat)}", flush=True)


def bench(args):
    feed = [0] * 9
    for a in args:
        e, c = a.split(":")
        feed[ORDER.index(e)] = int(c)
    atoms = atoms_of_feed(feed)
    n = len(atoms)
    total_val = sum(P.VAL[e] for e in atoms)
    print(f"feed={feed} n={n} total_val={total_val}", flush=True)
    t1 = time.time()
    mols = pot_v3.simulate(atoms)
    t2 = time.time()
    print(f"sim: {t2-t1:.2f}s", flush=True)
    if mols is None:
        print("FAIL(rem)", flush=True)
        return
    big = max(len(m["atoms"]) for m in mols)
    print(f"mols={len(mols)} maxmol={big} prods={sorted(P.formula_of(m['atoms']) for m in mols)}", flush=True)
    t3 = time.time()
    ok = pot_v2.embed_all2(mols)
    t4 = time.time()
    print(f"embed: {t4-t3:.2f}s ok={ok}", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "dist":
        dist()
    elif sys.argv[1] == "bench":
        bench(sys.argv[2:])
