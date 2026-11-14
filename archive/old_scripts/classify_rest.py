# -*- coding: utf-8 -*-
"""classify_rest：在已确认的 16 个无限 3 元组基础上，继续测 4~9 元子集
（只测不含已知无限集合的子集），找是否还有更大的最小无限集合。

输出 all_classified_final.json / all_classified_stats.json（含全部 511 类别分类）。
"""
import itertools
import json
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
INF3 = [
    "O/X/P", "O/X/K", "O/P/W", "O/P/K", "O/P/A", "O/W/K", "O/K/A",
    "X/P/K", "P/W/K", "P/K/A",
    # 来自 medium_test（T=40/44 最大 29~30）
    "O/X/A", "X/P/W", "X/K/A", "P/W/A", "W/K/A", "O/X/W",
]
INF3 = [set(s.split("/")) for s in INF3]


def rand_vec(total, k, rng):
    cuts = sorted(rng.sample(range(total + k - 1), k - 1)) if k > 1 else []
    out, prev = [], -1
    for c in cuts + [total + k - 1]:
        out.append(c - prev - 1)
        prev = c
    return out


def run(args):
    elems, T, samples, seed = args
    try:
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
            big = [m for m in mols if len(m["atoms"]) == mx][0]
            if P.embed_mol(big["atoms"], big["edges"], max_nodes=40000) is None:
                continue
            ok = True
            for m in mols:
                if len(m["atoms"]) == mx:
                    continue
                if P.embed_mol(m["atoms"], m["edges"], max_nodes=8000) is None:
                    ok = False
                    break
            if not ok:
                continue
            best = mx
            info = {"formula": P.formula_of(big["atoms"]), "feed": list(v), "nmols": len(mols)}
            if best >= 24:
                break
        return "/".join(elems), T, best, info
    except Exception as e:
        return "/".join(elems), T, 0, {"error": str(e)}


def main():
    jobs = max(4, (os.cpu_count() or 8) - 6)
    found = [set(s) for s in INF3]
    allsets = {}
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for r in range(4, 10):
            cands = [list(c) for c in itertools.combinations(P.ORDER, r)
                     if not any(m <= set(c) for m in found)]
            if not cands:
                print(f"元素数 {r}: 全被覆盖", flush=True)
                continue
            print(f"元素数 {r}: 待测 {len(cands)}", flush=True)
            tasks = [(s, 32, 500, abs(hash((tuple(s), r))) & 0xffffffff) for s in cands]
            new = 0
            for key, T, best, info in pool.map(run, tasks):
                allsets[key] = {"T": T, "max": best, "info": info}
                if best >= 24:
                    found.append(set(key.split("/")))
                    new += 1
                    print(f"  {key}: max={best} {info}", flush=True)
            print(f"元素数 {r}: 新无限 {new}", flush=True)
            json.dump({"found": ["/".join(sorted(x)) for x in found], "sets": allsets},
                      open(BASE + r"\classify_rest_raw.json", "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
    # 最终分类
    out = {}
    for r in range(1, 10):
        for c in itertools.combinations(P.ORDER, r):
            k = "/".join(c)
            S = set(c)
            cores = [m for m in found if m <= S]
            v = allsets.get(k, {})
            out[k] = {"elems": list(c), "n": r, "infinite": bool(cores),
                      "max": v.get("max", 0), "info": v.get("info"),
                      "cores": ["/".join(sorted(m, key=lambda x: P.ORDER.index(x))) for m in cores]}
    stats = {
        "n_categories": len(out),
        "n_infinite": sum(1 for v in out.values() if v["infinite"]),
        "n_finite": sum(1 for v in out.values() if not v["infinite"]),
        "minimal": ["/".join(sorted(m, key=lambda x: P.ORDER.index(x))) for m in found],
        "infinite_by_size": {r: sum(1 for v in out.values() if v["infinite"] and v["n"] == r) for r in range(1, 10)},
        "finite_by_size": {r: sum(1 for v in out.values() if not v["infinite"] and v["n"] == r) for r in range(1, 10)},
    }
    json.dump(out, open(BASE + r"\all_classified_final.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(stats, open(BASE + r"\all_classified_stats.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(stats, ensure_ascii=False, indent=1)[:1400])
    print("saved all_classified_final.json")


if __name__ == "__main__":
    main()
