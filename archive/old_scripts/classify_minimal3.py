# -*- coding: utf-8 -*-
"""classify_minimal3：用"小规模全枚举"判定 3/4/5 元组是否无限。

每个子集：枚举 T=24 与 T=28 的全部计数向量（3 元组 325/435 个），只保留
"整锅只出一个分子且原子数 >= 18" 的候选，再对候选做有预算的几何判定。
"""
import itertools
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def gen_compositions(total, k, prefix=()):
    if k == 1:
        yield prefix + (total,)
        return
    for x in range(total + 1):
        yield from gen_compositions(total - x, k - 1, prefix + (x,))


def vec_full(partial, elems):
    v = [0] * 9
    for e, c in zip(elems, partial):
        v[P.ORDER.index(e)] = c
    return tuple(v)


def is_inf(args):
    elems, T = args
    cands = []
    for comp in gen_compositions(T, len(elems)):
        v = vec_full(comp, elems)
        atoms = P.vec_to_atoms(v, P.ORDER)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        mols = P.simulate(atoms)
        if not mols or len(mols) != 1:
            continue
        m = mols[0]
        if len(m["atoms"]) < 18:
            continue
        cands.append((len(m["atoms"]), P.formula_of(m["atoms"]), m))
    cands.sort(key=lambda t: -t[0])
    for size, f, m in cands[:20]:
        if P.embed_mol(m["atoms"], m["edges"], max_nodes=150000) is not None:
            return list(elems), T, size, f
    return list(elems), T, 0, None


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
    print(f"3 元组待测 {len(todo)}", flush=True)
    jobs = max(4, (os.cpu_count() or 8) - 2)
    inf = set()
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        tasks = [(list(t), 28) for t in todo] + [(list(t), 24) for t in todo]
        for elems, T, size, f in pool.map(is_inf, tasks):
            if size:
                inf.add(tuple(elems))
                print(f"  3元组 {'/'.join(elems)} T={T}: 单分子 {size} {f}", flush=True)
    inf3 = set(k for k, v in known.items() if v) | inf
    print(f"无限 3 元组 {len(inf3)}", flush=True)

    # 4 元组
    fours = [c for c in itertools.combinations(P.ORDER, 4)
             if not any(set(t) <= set(c) for t in inf3)]
    print(f"4 元组待测 {len(fours)}", flush=True)
    inf4 = set()
    tasks4 = [((list(t)), T) for t in fours for T in (24,)]  # 4 元组 T=24 全枚举 2925 个
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for elems, T, size, f in pool.map(is_inf, tasks4):
            if size:
                inf4.add(tuple(elems))
                print(f"  4元组 {'/'.join(elems)}: 单分子 {size} {f}", flush=True)
    print(f"无限 4 元组 {len(inf4)}", flush=True)

    # 5 元组（较少，T=20 全枚举 10626 个/子集）
    fives = [c for c in itertools.combinations(P.ORDER, 5)
             if not any(set(t) <= set(c) for t in inf3)
             and not any(set(t) <= set(c) for t in inf4)]
    print(f"5 元组待测 {len(fives)}", flush=True)
    inf5 = set()
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for elems, T, size, f in pool.map(is_inf, [(list(t), 20) for t in fives]):
            if size:
                inf5.add(tuple(elems))
                print(f"  5元组 {'/'.join(elems)}: 单分子 {size} {f}", flush=True)
    print(f"无限 5 元组 {len(inf5)}", flush=True)

    minimal = [list(t) for t in (inf3 | inf4 | inf5)]
    mins = [m for m in minimal if not any(set(o) < set(m) for o in minimal)]
    out = {
        "inf3": ["/".join(t) for t in sorted(inf3)],
        "inf4": ["/".join(t) for t in sorted(inf4)],
        "inf5": ["/".join(t) for t in sorted(inf5)],
        "minimal": ["/".join(sorted(m, key=lambda e: P.ORDER.index(e))) for m in mins],
    }
    json.dump(out, open(BASE + r"\minimal_infinite.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("最小无限集合:", out["minimal"])
    print("saved minimal_infinite.json")


if __name__ == "__main__":
    main()
