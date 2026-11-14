# -*- coding: utf-8 -*-
"""t3_growth_scan：对候选子集做"恰好 T 原子"的全枚举增长扫描（只模拟，不逐投料 embed）。

- 任务粒度 (subset, T)：枚举该子集内总原子=T 的全部投料向量，规则 1~8 模拟；
- 记录反应成功（无剩余键）的投料中"最大分子"的尺寸与其结构；记录原始 max（未校验可摆放）。
- 输出 t3_growth_scan.json，后续再用 embed 校验 top 候选。

用法:
  python t3_growth_scan.py <groups> [jobs]
groups: triples / fours / fives / sixes / sevens / all
"""
import itertools
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
THREE = set("OPK")
TWO = set("XWA")


def gen_compositions(total, k, prefix=()):
    if k == 1:
        yield prefix + (total,)
        return
    for x in range(total + 1):
        yield from gen_compositions(total - x, k - 1, prefix + (x,))


def work(task):
    elems, T = task
    best = None  # (natoms, formula, counts, mol_structure)
    ok = 0
    hist = Counter()
    for counts in gen_compositions(T, len(elems)):
        atoms = P.vec_to_atoms(counts, elems)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        mols = P.simulate(atoms)
        if not mols:
            continue
        ok += 1
        mx = max(len(m["atoms"]) for m in mols)
        hist[mx] += 1
        if best is None or mx > best[0]:
            m = [x for x in mols if len(x["atoms"]) == mx][0]
            best = (mx, P.formula_of(m["atoms"]), list(counts),
                    [[list(m["atoms"]), [list(e) for e in m["edges"]]]])
    return tuple(elems), T, best, ok, dict(hist)


def groups_spec(which):
    spec = {}
    if which in ("triples", "all"):
        spec["triples"] = ([list(t) for t in itertools.combinations(P.ORDER, 3)], [20, 24, 28, 32, 40, 48])
    if which in ("fours", "all"):
        fours = []
        for c in itertools.combinations(P.ORDER, 4):
            inf = any(len(set(c) & THREE) >= 2 and len(set(c) & TWO) >= 1 for _ in [0])
            if inf:
                continue
            fours.append(list(c))
        spec["fours"] = (fours, [20, 24, 28, 32, 36, 40])
    if which in ("fives", "all"):
        fives = []
        for c in itertools.combinations(P.ORDER, 5):
            if len(set(c) & THREE) >= 2 and len(set(c) & TWO) >= 1:
                continue
            fives.append(list(c))
        spec["fives"] = (fives, [16, 20, 24, 28])
    if which in ("sixes", "all"):
        sixes = []
        for c in itertools.combinations(P.ORDER, 6):
            if len(set(c) & THREE) >= 2 and len(set(c) & TWO) >= 1:
                continue
            sixes.append(list(c))
        spec["sixes"] = (sixes, [16, 20, 24])
    if which in ("sevens", "all"):
        sevens = []
        for c in itertools.combinations(P.ORDER, 7):
            if len(set(c) & THREE) >= 2 and len(set(c) & TWO) >= 1:
                continue
            sevens.append(list(c))
        spec["sevens"] = (sevens, [16, 20])
    if which == "inf3":
        # 9 个无限核心三元组，扫更大 T 看增长
        cores = [list(c) for c in itertools.combinations(sorted(THREE), 2)]
        spec["inf3"] = ([c + [x] for c in cores for x in sorted(TWO)], [32, 40, 48, 56, 64])
    return spec


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    jobs = int(sys.argv[2]) if len(sys.argv) > 2 else max(2, (os.cpu_count() or 4) - 2)
    spec = groups_spec(which)
    out = {}
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for gname, (subsets, Ts) in spec.items():
            tasks = [(s, T) for s in subsets for T in Ts]
            print(f"[{gname}] {len(subsets)} subsets x {Ts}", flush=True)
            for elems, T, best, ok, hist in ex.map(work, tasks):
                key = "/".join(elems)
                out.setdefault(key, {})[str(T)] = {"max": best[0] if best else 0,
                                                   "formula": best[1] if best else None,
                                                   "feed": best[2] if best else None,
                                                   "mol": best[3] if best else None,
                                                   "ok": ok, "hist": hist}
            print(f"[{gname}] done", flush=True)
            json.dump(out, open(BASE + rf"\t3_growth_{which}.json", "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
    print("saved", BASE + rf"\t3_growth_{which}.json")


if __name__ == "__main__":
    main()
