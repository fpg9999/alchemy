# -*- coding: utf-8 -*-
"""t3_validate：对 t3_growth_*.json 里记录的"最大分子候选"做可摆放性校验（整锅）。
输出 *_validated.json：validated max + 是否整锅可摆 + 校验细节。
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def check(task):
    key, T, rec = task
    elems = key.split("/")
    feed = rec.get("feed")
    if not feed:
        return key, T, None
    atoms = P.vec_to_atoms(tuple(feed), elems)
    mols = P.simulate(atoms)
    if not mols:
        return key, T, None
    sizes = sorted((len(m["atoms"]) for m in mols), reverse=True)
    # 先校验最大分子（独立可摆），再校验整锅
    big = [m for m in mols if len(m["atoms"]) == sizes[0]]
    big_ok = any(P.embed_mol(m["atoms"], m["edges"], max_nodes=400000) is not None for m in big)
    all_ok = False
    if big_ok:
        all_ok = True
        for m in mols:
            if P.embed_mol(m["atoms"], m["edges"], max_nodes=400000) is None:
                all_ok = False
                break
    return key, T, {"raw_max": sizes[0], "big_embed": big_ok, "pot_ok": all_ok,
                    "sizes": sizes, "nformulas": [P.formula_of(m["atoms"]) for m in mols]}


def main():
    src = sys.argv[1]
    jobs = int(sys.argv[2]) if len(sys.argv) > 2 else max(2, (os.cpu_count() or 4) - 2)
    data = json.load(open(src, encoding="utf-8"))
    tasks = []
    for key, byT in data.items():
        for T, rec in byT.items():
            if rec.get("max", 0) >= 11:  # 只校验可能接近封顶的
                tasks.append((key, T, rec))
    print(f"校验 {len(tasks)} 个候选（原始 max>=11）", flush=True)
    out = {}
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for key, T, res in ex.map(check, tasks):
            if res is None:
                continue
            out.setdefault(key, {})[T] = res
            print(f"{key:12s} T={T:>2s} raw={res['raw_max']:2d} big_embed={res['big_embed']} pot_ok={res['pot_ok']}", flush=True)
    dst = src.replace(".json", "_validated.json")
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved", dst)


if __name__ == "__main__":
    main()
