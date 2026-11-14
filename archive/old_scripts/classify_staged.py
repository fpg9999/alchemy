# -*- coding: utf-8 -*-
"""classify_staged：分层实测分类（利用"无限向上封闭"的单调性）。

Stage 3: 所有 3 元组，随机大投料，找"整锅成功且最大分子>=24"的强证据；
Stage 4: 不含无限 3 元组的 4 元组，同样测；
Stage 5/6/...: 依次对不含更小无限集合的子集测试，直到没有新的最小无限集合。
输出 all_classified.json（511 类别：无限/有限/证据）。
"""
import itertools
import json
import os
import random
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def rand_vec(total, k, rng):
    cuts = sorted(rng.sample(range(total + k - 1), k - 1)) if k > 1 else []
    out, prev = [], -1
    for c in cuts + [total + k - 1]:
        out.append(c - prev - 1)
        prev = c
    return out


def run_subset(elems, T, samples, seed, strong=24):
    rng = random.Random(seed)
    best = 0
    info = None
    for _ in range(samples):
        comp = rand_vec(T, len(elems), rng)
        v = [0] * 9
        for e, c in zip(elems, comp):
            v[P.ORDER.index(e)] = c
        atoms = P.vec_to_atoms(tuple(v), P.ORDER)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        mols = P.simulate(atoms)
        if not mols:
            continue
        mx = max(len(m["atoms"]) for m in mols)
        if mx <= 16 or mx <= best:
            continue
        # 大分子先判，再快判其他产物
        big = [m for m in mols if len(m["atoms"]) == mx][0]
        if P.embed_mol(big["atoms"], big["edges"], max_nodes=60000) is None:
            continue
        ok = True
        for m in mols:
            if len(m["atoms"]) == mx:
                continue
            if P.embed_mol(m["atoms"], m["edges"], max_nodes=12000) is None:
                ok = False
                break
        if not ok:
            continue
        best = mx
        info = {"formula": P.formula_of(big["atoms"]), "feed": list(v), "nmols": len(mols)}
        if best >= strong:
            break
    return elems, T, best, info


def task(args):
    return run_subset(*args)


def test_level(pool, subsets, T, samples, strong):
    results = {}
    tasks = [(s, T, samples, abs(hash((tuple(s), T, strong))) & 0xffffffff, strong) for s in subsets]
    for elems, T2, best, info in pool.map(task, tasks):
        k = "/".join(elems)
        results[k] = {"T": T2, "max": best, "info": info}
    return results


def main():
    jobs = max(4, (os.cpu_count() or 8) - 6)
    allsets = {}
    found = []  # evidence sets (list of sets)
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for r in range(1, 10):
            cands = [list(c) for c in itertools.combinations(P.ORDER, r)
                     if not any(set(e) <= set(c) for e in found)]
            if not cands:
                print(f"元素数 {r}: 无需测试（都被更小无限集合覆盖）", flush=True)
                continue
            print(f"元素数 {r}: 待测 {len(cands)}", flush=True)
            res = test_level(pool, cands, 32, 900 if r <= 4 else 600,
                             24 if r <= 4 else 20)
            new_inf = 0
            for s in cands:
                k = "/".join(s)
                v = res.get(k, {"max": 0})
                allsets[k] = v
                if v["max"] >= (24 if r <= 4 else 20):
                    found.append(set(s))
                    new_inf += 1
                    print(f"  {k}: max={v['max']} {v['info']}", flush=True)
            print(f"元素数 {r}: 新无限 {new_inf}", flush=True)
            json.dump({"sets": allsets, "found": ["/".join(sorted(e)) for e in found]},
                      open(BASE + r"\all_classified_raw.json", "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
    # 类别判定：含任意 found 集合 → 无限
    out = {}
    for r in range(1, 10):
        for c in itertools.combinations(P.ORDER, r):
            k = "/".join(c)
            S = set(c)
            cores = [e for e in found if e <= S]
            v = allsets.get(k, {})
            out[k] = {
                "elems": list(c), "n": r,
                "infinite": bool(cores),
                "direct": (v.get("max", 0) >= (24 if r <= 4 else 20)),
                "max": v.get("max", 0), "info": v.get("info"),
                "cores": ["/".join(sorted(e, key=lambda x: P.ORDER.index(x))) for e in cores],
            }
    stats = {
        "n_categories": len(out),
        "n_infinite": sum(1 for v in out.values() if v["infinite"]),
        "n_finite": sum(1 for v in out.values() if not v["infinite"]),
        "n_direct": sum(1 for v in out.values() if v["direct"]),
        "minimal": ["/".join(sorted(e, key=lambda x: P.ORDER.index(x))) for e in found],
        "infinite_by_size": {r: sum(1 for v in out.values() if v["infinite"] and v["n"] == r) for r in range(1, 10)},
        "finite_by_size": {r: sum(1 for v in out.values() if not v["infinite"] and v["n"] == r) for r in range(1, 10)},
    }
    json.dump(out, open(BASE + r"\all_classified_final.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(stats, open(BASE + r"\all_classified_stats.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(stats, ensure_ascii=False, indent=1)[:1500])
    print("saved all_classified_final.json / stats")


if __name__ == "__main__":
    main()
