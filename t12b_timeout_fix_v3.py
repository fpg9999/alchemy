# -*- coding: utf-8 -*-
"""t12b_timeout_fix_v3.py —— 对 pot_v3 口径下 timeout 的向量用更高上限复核，并回写 t12b_vec_v3.json。"""
import json
import sys
import time
from multiprocessing import Pool

BASE = r"G:\AI work\deepseek\work1\alchemy"
sys.path.insert(0, BASE)
import pot_all as P
import pot_v3
import t12b_embed as E

ORDER = P.ORDER
NPROC = int(__import__("os").environ.get("T12B_PROC", "14"))
CAPS = [3_000_000, 12_000_000]


def work(item):
    ridx, v = item
    atoms = [s for s, c in zip(ORDER, v) for _ in range(c)]
    mols = pot_v3.simulate(atoms)
    if mols is None:
        return ridx, [1, []]
    for cap in CAPS:
        st, _ = E.embed_all_status(mols, max_nodes=cap)
        if st == "ok":
            return ridx, [0, sorted(P.formula_of(m["atoms"]) for m in mols)]
        if st == "fail":
            return ridx, [2, []]
    return ridx, [3, []]


def main():
    t0 = time.time()
    d = json.load(open(BASE + r"\t12b_vec_v3.json", encoding="utf-8"))
    uniq = d["vecs"]
    res = d["res"]
    todo = [(k, tuple(v)) for k, v in enumerate(uniq) if res[k][0] == 3]
    print(f"v3 timeout 向量 {len(todo)}", flush=True)
    with Pool(NPROC) as pool:
        for k, (ridx, r) in enumerate(pool.imap_unordered(work, todo, chunksize=4), 1):
            res[ridx] = r
            if k % 20 == 0 or k == len(todo):
                print(f"  {k}/{len(todo)} {time.time()-t0:.1f}s", flush=True)
    json.dump(d, open(BASE + r"\t12b_vec_v3.json", "w", encoding="utf-8"),
              separators=(",", ":"))
    from collections import Counter
    print("状态分布:", dict(Counter(r[0] for r in res)), flush=True)
    print(f"done {time.time()-t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
