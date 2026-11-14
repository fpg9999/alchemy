# -*- coding: utf-8 -*-
"""classify4：在已知 9 个无限 3 元组的基础上，找最小无限 4 元组 / 5 元组。

- 4 元组（不含无限 3 元组）：T=24 全枚举（2925 个向量/子集），单分子 >=18 且可摆 → 无限
- 5 元组（不含无限 3/4 元组）：T=20 全枚举（10626 个向量/子集）
输出 minimal_infinite.json（inf3/inf4/inf5/minimal）
"""
import itertools
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
INF3 = [
    {"O", "X", "K"}, {"O", "K", "A"}, {"O", "X", "P"}, {"O", "P", "W"},
    {"P", "W", "K"}, {"P", "K", "A"}, {"O", "P", "A"}, {"O", "W", "K"},
    {"X", "P", "K"},
]


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
        if len(m["atoms"]) < T - 4:
            continue
        cands.append((len(m["atoms"]), P.formula_of(m["atoms"]), m, v))
    cands.sort(key=lambda t: -t[0])
    for size, f, m, v in cands[:6]:
        if P.embed_mol(m["atoms"], m["edges"], max_nodes=60000) is not None:
            return list(elems), T, size, f, list(v)
    return list(elems), T, 0, None, None


def main():
    jobs = max(4, (os.cpu_count() or 8) - 5)
    fours = [c for c in itertools.combinations(P.ORDER, 4)
             if not any(t <= set(c) for t in INF3)]
    print(f"4 元组待测 {len(fours)}", flush=True)
    inf4 = set()
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for elems, T, size, f, v in pool.map(is_inf, [(list(t), 24) for t in fours]):
            if size:
                inf4.add(tuple(elems))
                print(f"  4元组 {'/'.join(elems)}: {size} {f} 投料={v}", flush=True)
    print(f"无限 4 元组 {len(inf4)}", flush=True)
    json.dump({"inf3": ["/".join(sorted(t)) for t in INF3],
               "inf4": ["/".join(t) for t in sorted(inf4)]},
              open(BASE + r"\minimal_infinite_partial.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # 4 元组加验：T=28 仍能出 >=24 原子单分子
    verify4 = set()
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for elems, T, size, f, v in pool.map(is_inf, [(list(t), 28) for t in inf4]):
            if size >= 24:
                verify4.add(tuple(elems))
            elif size:
                print(f"  ? 4元组 {'/'.join(elems)} T=28 只有 {size} {f}", flush=True)
    print(f"4 元组 T=28 加验通过 {len(verify4)}/{len(inf4)}", flush=True)
    inf4 = inf4 & verify4

    fives = [c for c in itertools.combinations(P.ORDER, 5)
             if not any(t <= set(c) for t in INF3)
             and not any(set(t) <= set(c) for t in inf4)]
    print(f"5 元组待测 {len(fives)}", flush=True)
    inf5 = set()
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for elems, T, size, f, v in pool.map(is_inf, [(list(t), 20) for t in fives]):
            if size:
                inf5.add(tuple(elems))
                print(f"  5元组 {'/'.join(elems)}: {size} {f}", flush=True)
    print(f"无限 5 元组 {len(inf5)}", flush=True)

    minimal = [list(t) for t in set(INF3) | inf4 | inf5]
    mins = [m for m in minimal if not any(set(o) < set(m) for o in minimal)]
    out = {
        "inf3": ["/".join(t) for t in sorted(INF3)],
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
