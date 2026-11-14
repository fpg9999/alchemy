# -*- coding: utf-8 -*-
"""t4_scan_le16：修正版全 9 元素、总原子 <=16 全投料扫描（严格可摆放校验 + 精确缓存）。

与旧 scan_league 的区别：
- 用 pot_v2.embed_mol2（修复 L 中间格 bug）并逐条 validate_place；
- 缓存键用"精确表示"(atoms, edges)，避免 canonical_sig 碰撞导致复用错误摆放；
- 只收录"整锅成功 + 所有产物严格可摆"的物质。
输出 t4_catalog_le16.json（按分子式去重，含一个合法摆放与投料例）。
"""
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v2

BASE = r"G:\AI work\deepseek\work1\alchemy"


def gen_compositions(total, k, prefix=()):
    if k == 1:
        yield prefix + (total,)
        return
    for x in range(total + 1):
        yield from gen_compositions(total - x, k - 1, prefix + (x,))


def all_vecs(Nmax):
    out = []
    for T in range(1, Nmax + 1):
        for comp in gen_compositions(T, 9):
            v = tuple(comp)
            if sum(P.VAL[e] * c for e, c in zip(P.ORDER, v)) % 2:
                continue
            out.append(v)
    return out


def work(task):
    vecs, budget = task
    found = {}
    cache = {}
    for v in vecs:
        atoms = P.vec_to_atoms(v, P.ORDER)
        mols = P.simulate(atoms)
        if not mols:
            continue
        ok = True
        for m in mols:
            key = (tuple(m["atoms"]), tuple(sorted(tuple(e) for e in m["edges"])))
            if key not in cache:
                pl = pot_v2.embed_mol2(m["atoms"], m["edges"], max_nodes=budget)
                if pl is not None:
                    good, _ = pot_v2.validate_place(pl, m["atoms"], m["edges"])
                    pl = pl if good else None
                cache[key] = pl
            if cache[key] is None:
                ok = False
                break
        if not ok:
            continue
        for m in mols:
            f = P.formula_of(m["atoms"])
            if f in found:
                continue
            key = (tuple(m["atoms"]), tuple(sorted(tuple(e) for e in m["edges"])))
            found[f] = {"formula": f, "natoms": len(m["atoms"]), "zh": P.zh_of(m["atoms"]),
                        "vec": [sum(1 for e in m["atoms"] if e == c) for c in P.ORDER],
                        "feed": list(v),
                        "atoms": list(m["atoms"]),
                        "edges": [list(e) for e in m["edges"]],
                        "place": {str(k): list(p) for k, p in cache[key].items()}}
    return found


def main():
    Nmax = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    jobs = int(sys.argv[2]) if len(sys.argv) > 2 else max(2, (os.cpu_count() or 4) - 2)
    t0 = time.time()
    vecs = all_vecs(Nmax)
    print(f"N<={Nmax}: 偶数价数向量 {len(vecs)} 个, workers {jobs}", flush=True)
    CH = 400
    tasks = [(vecs[i:i + CH], 400000) for i in range(0, len(vecs), CH)]
    merged = {}
    done = 0
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for res in ex.map(work, tasks):
            for f, item in res.items():
                if f not in merged:
                    merged[f] = item
            done += 1
            if done % max(1, len(tasks) // 40) == 0 or done == len(tasks):
                print(f"  进度 {done}/{len(tasks)}, 物质 {len(merged)}, {time.time()-t0:.0f}s", flush=True)
    out = sorted(merged.values(), key=lambda x: (x["natoms"], x["vec"]))
    json.dump(out, open(BASE + rf"\t4_catalog_le{Nmax}.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"saved t4_catalog_le{Nmax}.json: {len(out)} 条物质, 用时 {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
