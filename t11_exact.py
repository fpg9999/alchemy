# -*- coding: utf-8 -*-
"""t11_exact：规则 9d 的精确/加强验证。
  - T=6,7,8：穷举并列 DFS（精确）
  - T=9：随机并列 30 次采样（估计残余）
"""
import itertools
import json
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import t9_variants as V
from t11_rule9d import simulate_rule9d, gen_compositions

BASE = r"G:\AI work\deepseek\work1\alchemy"


def extra_fn(i, j, ci, cj, cats, groups, adj, dists, atom_list):
    cnt_i = [0, 0, 0]
    cnt_j = [0, 0, 0]
    for x in groups[ci]:
        c = P.CAT[atom_list[x]]
        cnt_i[("聚", "散", "动").index(c)] += 1
    for x in groups[cj]:
        c = P.CAT[atom_list[x]]
        cnt_j[("聚", "散", "动").index(c)] += 1
    return (-len(cats[ci] | cats[cj]),
            -(cnt_i[0] + cnt_j[0]), -(cnt_i[1] + cnt_j[1]), -(cnt_i[2] + cnt_j[2]))


def dfs_work(T):
    ncase = 0
    amb = []
    over = []
    for counts in gen_compositions(T, 9):
        atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        ncase += 1
        r = V.run_ties(atoms, extra_fn, max_leaves=4000)
        if r == "over":
            over.append(list(counts))
        elif r is not None and len(r) > 1:
            amb.append({"feed": list(counts), "outcomes": [list(k) for k in r]})
    return T, ncase, amb, len(over)


def rand_work(args):
    T, runs = args
    rng = random.Random(9000 + T)
    ncase = 0
    amb = []
    for counts in gen_compositions(T, 9):
        atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        ncase += 1
        outs = set()
        bad = False
        for _ in range(runs):
            r = simulate_rule9d(atoms, rng)
            if r is None:
                bad = True
                break
            outs.add(r)
        if bad:
            continue
        if len(outs) > 1:
            amb.append({"feed": list(counts), "outcomes": [list(o) for o in list(outs)[:4]]})
    return T, ncase, amb, runs


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "dfs"
    jobs = int(sys.argv[2]) if len(sys.argv) > 2 else max(2, (os.cpu_count() or 4) - 2)
    if what == "dfs":
        results = {}
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            for T, ncase, amb, nover in ex.map(dfs_work, [6, 7, 8]):
                results[str(T)] = {"ncase": ncase, "ambiguous": amb, "over": nover}
                print(f"T={T}: 投料 {ncase}, 精确歧义 {len(amb)}, over {nover}", flush=True)
                for a in amb[:5]:
                    print("   ", a, flush=True)
        json.dump(results, open(BASE + r"\t11_rule9d_exact.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    else:
        results = {}
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            for T, ncase, amb, runs in ex.map(rand_work, [(9, 30)]):
                results[str(T)] = {"ncase": ncase, "runs": runs, "ambiguous": amb}
                print(f"T={T}: 投料 {ncase}, {runs} 次随机采样歧义 {len(amb)}", flush=True)
                for a in amb[:10]:
                    print("   ", a, flush=True)
        json.dump(results, open(BASE + r"\t11_rule9d_t9_rand.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
