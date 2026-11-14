# -*- coding: utf-8 -*-
"""growth_cores：对每个"最小无限集合"精确枚举 ≤Nmax 的投料，统计
① 该类物质数（按原子数累计）；② 各 N 的最大分子；③ 代表公式序列（用于归纳参数族）。

产出 cores_growth.json
"""
import json
import os
import sys
from collections import defaultdict

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


def scan_core(elems, Nmax):
    formulas = {}          # formula -> (natoms, atoms, edges, feed)
    by_n = defaultdict(int)
    for total in range(2, Nmax + 1):
        for comp in gen_compositions(total, len(elems)):
            v = vec_full(comp, elems)
            atoms = P.vec_to_atoms(v, P.ORDER)
            if sum(P.VAL[e] for e in atoms) % 2:
                continue
            mols = P.simulate(atoms)
            if not mols:
                continue
            ok = all(P.embed_mol(m["atoms"], m["edges"], max_nodes=80000) is not None
                     for m in mols)
            if not ok:
                continue
            for m in mols:
                f = P.formula_of(m["atoms"])
                if f not in formulas:
                    formulas[f] = {"natoms": len(m["atoms"]), "atoms": list(m["atoms"]),
                                   "edges": [list(e) for e in m["edges"]], "feed": list(v)}
        # 累计到 total 的公式数（按分子的原子数 <= total 等价，这里直接统计当前已知）
        by_n[total] = len(formulas)
    return formulas, by_n


def main():
    minf = json.load(open(sys.argv[1] if len(sys.argv) > 1 else BASE + r"\minimal_infinite.json", encoding="utf-8"))
    minimal = [s.split("/") for s in minf["minimal"]]
    # 去掉含更小集合的超集
    mins = []
    for m in minimal:
        if not any(set(o) < set(m) for o in minimal):
            mins.append(m)
    print("最小无限集合:", ["/".join(m) for m in mins], flush=True)
    out = {}
    for m in mins:
        elems = sorted(m, key=lambda e: P.ORDER.index(e))
        n = len(elems)
        Nmax = {3: 20, 4: 18, 5: 16, 6: 14}.get(n, 12)
        formulas, by_n = scan_core(elems, Nmax)
        # 最大分子代表（每 N 取一个最大）
        reps = []
        for N in range(2, Nmax + 1):
            cand = [(f, x) for f, x in formulas.items() if x["natoms"] <= N]
            if not cand:
                continue
            f, x = max(cand, key=lambda t: t[1]["natoms"])
            reps.append({"N": N, "formula": f, "natoms": x["natoms"], "feed": x["feed"]})
        # 按原子数统计（完整类别：组成 ⊆ 该集合）
        by_size = defaultdict(list)
        for f, x in formulas.items():
            by_size[x["natoms"]].append(f)
        out["/".join(elems)] = {
            "elems": elems,
            "Nmax": Nmax,
            "count_by_N": by_n,
            "total": len(formulas),
            "reps": reps,
            "by_size": {str(k): sorted(v) for k, v in sorted(by_size.items())},
        }
        print(f"  {('/'.join(elems))}: ≤{Nmax} 共 {len(formulas)} 种；"
              f"最大代表的原子数={reps[-1]['natoms'] if reps else 0}", flush=True)
        json.dump(out, open(BASE + r"\cores_growth.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print("saved cores_growth.json")


if __name__ == "__main__":
    main()
