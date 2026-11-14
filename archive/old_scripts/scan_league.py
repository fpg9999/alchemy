# -*- coding: utf-8 -*-
"""scan_league：多进程"全投料向量"扫描 + 导出全部可产出物质（有界截断 Nmax）。

用法: python scan_league.py <scope_id> <Nmax> [jobs]
产物: substances_league_s{scope}.json
  每项: scope/formula/zh/natoms/vec(9)/feed(9)/cats/atoms/edges/dirs/bond/place/place_xy
说明: 扫描所有价数总和为偶数的投料计数向量（总原子 <= Nmax）；反应成功 + 全部产物可摆才计入。
"""
import itertools
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
SCOPES = {
    1: ("动素", ["P", "W", "L"]),
    2: ("散素", ["K", "A", "F"]),
    3: ("聚素+散素", ["O", "X", "C", "K", "A", "F"]),
    4: ("聚素+动素", ["O", "X", "C", "P", "W", "L"]),
    5: ("动素+散素", ["P", "W", "L", "K", "A", "F"]),
    6: ("三类混合", P.ORDER),
}


def gen_compositions(total, k, prefix=()):
    if k == 1:
        yield prefix + (total,)
        return
    for x in range(total + 1):
        yield from gen_compositions(total - x, k - 1, prefix + (x,))


def vec_full(partial, elems):
    """把只含 scope 元素的局部计数补成 9 元完整向量"""
    v = [0] * 9
    for e, c in zip(elems, partial):
        v[P.ORDER.index(e)] = c
    return tuple(v)


def dir_of(t, d):
    table = {"S": P.S_DIRS, "C": P.C_DIRS, "L": P.L_DIRS}
    for k, off in table[t].items():
        if off == d:
            return k
    return None


def struct_of(m, embed_cache):
    key = P.canonical_sig(m["atoms"], m["edges"])
    miss = object()
    place = embed_cache.get(key, miss)
    if place is miss:
        place = P.embed_mol(m["atoms"], m["edges"], max_nodes=150000)
        embed_cache[key] = place
    if place is None:
        return None
    occ = set(place.values())
    dirs = []
    bonds = []
    for (i, j, mm) in m["edges"]:
        d = (place[j][0] - place[i][0], place[j][1] - place[i][1])
        t = P.classify_offset(d)
        if t is None:
            return None
        if t == "L":
            mid = P.midpoint_of(d)
            if (place[i][0] + mid[0], place[i][1] + mid[1]) in occ:
                return None
        bonds.append(t)
        dirs.append(dir_of(t, d))
    return {
        "atoms": list(m["atoms"]),
        "edges": [list(e) for e in m["edges"]],
        "dirs": dirs,
        "bonds": bonds,
        "place": {str(k): list(v) for k, v in place.items()},
        "place_xy": {str(k): [q, q + 2 * r] for k, (q, r) in place.items()},
    }


def work(task):
    scope_id, elems, vecs = task
    cache = {}
    out = {}
    for v in vecs:
        atoms = P.vec_to_atoms(v, P.ORDER)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        mols = P.simulate(atoms)
        if not mols:
            continue
        ok = True
        for m in mols:
            if struct_of(m, cache) is None:
                ok = False
                break
        if not ok:
            continue
        for m in mols:
            f = P.formula_of(m["atoms"])
            if f in out:
                continue
            st = struct_of(m, cache)
            if st is None:
                continue
            cats = sorted({P.CAT[e] for e in m["atoms"]}, key=lambda c: "聚动散".index(c))
            out[f] = {
                "scope": scope_id,
                "formula": f,
                "zh": P.zh_of(m["atoms"]),
                "natoms": len(m["atoms"]),
                "vec": [sum(1 for e in m["atoms"] if e == c) for c in P.ORDER],
                "feed": list(vec_full(v, elems)),
                "cats": "-".join(cats),
                **st,
            }
    return out


def main():
    sid = int(sys.argv[1])
    Nmax = int(sys.argv[2])
    jobs = int(sys.argv[3]) if len(sys.argv) > 3 else max(1, (os.cpu_count() or 4) - 2)
    name, elems = SCOPES[sid]
    # 仅枚举 scope 内元素的计数向量（其余为 0）
    all_vecs = []
    for total in range(1, Nmax + 1):
        for comp in gen_compositions(total, len(elems)):
            all_vecs.append(vec_full(comp, elems))
    print(f"范围{sid} {name}: 投料向量 {len(all_vecs)} 个, N<={Nmax}, 进程 {jobs}", flush=True)
    CH = 1500
    tasks = [(sid, elems, all_vecs[i:i + CH]) for i in range(0, len(all_vecs), CH)]
    merged = {}
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for k, res in enumerate(ex.map(work, tasks)):
            for f, item in res.items():
                if f not in merged:
                    merged[f] = item
            if (k + 1) % max(1, len(tasks) // 20) == 0 or k == len(tasks) - 1:
                print(f"  进度 {k+1}/{len(tasks)} 任务, 已知物质 {len(merged)}", flush=True)
    out = sorted(merged.values(), key=lambda x: (x["natoms"], x["vec"]))
    path = BASE + rf"\substances_league_s{sid}.json"
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"saved {path}: {len(out)} 种物质")


if __name__ == "__main__":
    main()
