# -*- coding: utf-8 -*-
"""classify_minimal2：快速判定"最小无限元素集合"。

思路：无限 ⇔ 存在任意大的"整锅只出一个分子"的投料（实测验证过这个等价在本题里成立；
      有限块封顶 16 原子，所以 T=28 时单分子 >=17 即可判无限）。
- 2 大类内的 3 元组：直接用 scope{3,4,5}_subset_growth.json 的结论（已实测）。
- 三类混合的 3 元组（27 个）：随机大投料 + 单分子产物 + 可摆判定。
- 4 元组（不含已知无限 3 元组）：随机大投料测试。
"""
import itertools
import json
import os
import random
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def vec_full(partial, elems):
    v = [0] * 9
    for e, c in zip(elems, partial):
        v[P.ORDER.index(e)] = c
    return tuple(v)


def rand_vec(total, k, rng):
    cuts = sorted(rng.sample(range(total + k - 1), k - 1)) if k > 1 else []
    out, prev = [], -1
    for c in cuts + [total + k - 1]:
        out.append(c - prev - 1)
        prev = c
    return out


def test_subset(args):
    elems, T, samples, seed = args
    rng = random.Random(seed)
    for _ in range(samples):
        comp = rand_vec(T, len(elems), rng)
        v = vec_full(comp, elems)
        atoms = P.vec_to_atoms(v, P.ORDER)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        mols = P.simulate(atoms)
        if not mols or len(mols) != 1:
            continue
        m = mols[0]
        if len(m["atoms"]) < T - 1:
            continue
        if P.embed_mol(m["atoms"], m["edges"], max_nodes=200000) is None:
            continue
        return (list(elems), T, len(m["atoms"]), P.formula_of(m["atoms"]), comp)
    return (list(elems), T, 0, None, None)


def load_known_triples():
    known = {}
    for sid in (3, 4, 5):
        try:
            rows = json.load(open(BASE + rf"\scope{sid}_subset_growth.json", encoding="utf-8"))
        except Exception:
            continue
        for r in rows:
            sub = tuple(r["subset"])
            if len(sub) == 3:
                known[sub] = r["infinite"]
    return known


def main():
    known = load_known_triples()
    all_triples = [tuple(c) for c in itertools.combinations(P.ORDER, 3)]
    todo = [t for t in all_triples if t not in known]
    print(f"3 元组: 全部 {len(all_triples)}，已有结论 {len(known)}，待测 {len(todo)}", flush=True)
    jobs = max(4, (os.cpu_count() or 8) - 2)
    inf = []
    tasks = [(list(t), 28, 4000, abs(hash(t)) & 0xffffffff) for t in todo]
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for res in pool.map(test_subset, tasks):
            elems, T, size, formula, feed = res
            if size:
                inf.append(tuple(elems))
                print(f"  3元组 {'/'.join(elems)}: 单分子 {size} {formula} 投料={feed}", flush=True)
    # 合并已有结论
    inf3 = set(k for k, v in known.items() if v) | set(inf)
    print(f"无限 3 元组共 {len(inf3)}: {sorted('/'.join(t) for t in inf3)}", flush=True)

    # 4 元组：不含无限 3 元组
    fours = [c for c in itertools.combinations(P.ORDER, 4)
             if not any(set(t) <= set(c) for t in inf3)]
    print(f"4 元组待测 {len(fours)}", flush=True)
    inf4 = []
    tasks = [(list(t), 28, 2500, abs(hash(t)) & 0xffffffff) for t in fours]
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for res in pool.map(test_subset, tasks):
            elems, T, size, formula, feed = res
            if size:
                inf4.append(tuple(elems))
                print(f"  4元组 {'/'.join(elems)}: 单分子 {size} {formula} 投料={feed}", flush=True)
    inf4 = set(inf4)
    print(f"无限 4 元组共 {len(inf4)}", flush=True)

    # 5 元组：不含无限 3/4 元组
    fives = [c for c in itertools.combinations(P.ORDER, 5)
             if not any(set(t) <= set(c) for t in inf3)
             and not any(set(t) <= set(c) for t in inf4)]
    print(f"5 元组待测 {len(fives)}", flush=True)
    inf5 = set()
    tasks = [(list(t), 26, 2000, abs(hash(t)) & 0xffffffff) for t in fives]
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for res in pool.map(test_subset, tasks):
            elems, T, size, formula, feed = res
            if size:
                inf5.add(tuple(elems))
                print(f"  5元组 {'/'.join(elems)}: 单分子 {size} {formula}", flush=True)
    print(f"无限 5 元组共 {len(inf5)}", flush=True)

    minimal = [list(t) for t in (inf3 | inf4 | inf5)]
    mins = [m for m in minimal if not any(set(o) < set(m) for o in minimal)]
    out = {
        "inf3": ["/".join(t) for t in sorted(inf3)],
        "inf4": ["/".join(t) for t in sorted(inf4)],
        "inf5": ["/".join(t) for t in sorted(inf5)],
        "minimal": ["/".join(sorted(m, key=lambda e: P.ORDER.index(e))) for m in mins],
        "known_from_subset_growth": {"/".join(k): v for k, v in known.items()},
    }
    json.dump(out, open(BASE + r"\minimal_infinite.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("最小无限集合:", out["minimal"])
    print("saved minimal_infinite.json")


if __name__ == "__main__":
    main()
