# -*- coding: utf-8 -*-
"""search_family：系统搜"单分子成功反应"（所有产物可摆、其中一个大分子），
收集代表分子式，用于归纳无限族。

用法: python search_family.py <scope_id> <Tmin> <Tmax> <samples_per_T>
对每个 T 随机抽样，找整锅成功且最大分子尽量大的例子；输出分子式 + 投料 + 结构概要。
"""
import json
import random
import sys
import time

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

SCOPES = {
    3: ["O", "X", "C", "K", "A", "F"],
    4: ["O", "X", "C", "P", "W", "L"],
    5: ["P", "W", "L", "K", "A", "F"],
    6: P.ORDER,
}
BASE = r"G:\AI work\deepseek\work1\alchemy"


def rand_vec(total, k, rng):
    cuts = sorted(rng.sample(range(total + k - 1), k - 1)) if k > 1 else []
    out, prev = [], -1
    for c in cuts + [total + k - 1]:
        out.append(c - prev - 1)
        prev = c
    return out


def structure_summary(m, place):
    deg = [0] * len(m["atoms"])
    for (i, j, k) in m["edges"]:
        deg[i] += k
        deg[j] += k
    types = []
    for (i, j, k) in m["edges"]:
        d = (place[j][0] - place[i][0], place[j][1] - place[i][1])
        types.append(P.classify_offset(d) + str(k))
    return " ".join(f"{e}{'' if d == 1 else '^' + str(d)}" for e, d in zip(m["atoms"], deg)), " ".join(types)


def main():
    sid = int(sys.argv[1])
    Tmin, Tmax = int(sys.argv[2]), int(sys.argv[3])
    samples = int(sys.argv[4])
    elems = SCOPES[sid]
    rng = random.Random(4096)
    out = []
    for T in range(Tmin, Tmax + 1):
        t = time.time()
        best = None
        for _ in range(samples):
            v = rand_vec(T, len(elems), rng)
            atoms = P.vec_to_atoms(tuple(v), elems)
            if sum(P.VAL[e] for e in atoms) % 2:
                continue
            mols = P.simulate(atoms)
            if not mols:
                continue
            if not P.embed_all(mols):
                continue
            mx = max(len(m["atoms"]) for m in mols)
            if mx < T - 2:
                continue
            # 找到一个"几乎整锅一个分子"的成功反应
            m = [x for x in mols if len(x["atoms"]) == mx][0]
            place = P.embed_mol(m["atoms"], m["edges"])
            if place is None:
                continue
            f = P.formula_of(m["atoms"])
            best = {"T": T, "feed": v, "formula": f, "natoms": mx,
                    "nmols": len(mols), "sizes": sorted((len(x["atoms"]) for x in mols), reverse=True),
                    "atoms": m["atoms"], "edges": m["edges"],
                    "place": {str(k): list(p) for k, p in place.items()}}
            break
        if best:
            out.append(best)
            print(f"T={T:2d}: {best['formula']} ({best['natoms']}原子, 产物{best['nmols']}个, "
                  f"尺寸{best['sizes']}) 投料={best['feed']} ({time.time()-t:.1f}s)", flush=True)
        else:
            print(f"T={T:2d}: 未找到 ({time.time()-t:.1f}s)", flush=True)
        json.dump(out, open(BASE + rf"\scope{sid}_big_examples.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print("saved", BASE + rf"\scope{sid}_big_examples.json")


if __name__ == "__main__":
    main()
