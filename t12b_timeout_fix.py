# -*- coding: utf-8 -*-
"""t12b_timeout_fix.py —— 对 CAP=3e5 下"未判定(timeout)"的向量用更高上限（默认 3e6/1e7）复核。
输出 t12b_timeout_fix.json: {ridx_str: [status, products]}
"""
import json
import os
import sys
import time
from multiprocessing import Pool

BASE = r"G:\AI work\deepseek\work1\alchemy"
sys.path.insert(0, BASE)
import pot_all as P
import t12b_embed as E

ORDER = P.ORDER
NPROC = int(os.environ.get("T12B_PROC", "16"))
CAPS = [3_000_000, 12_000_000]


def work(item):
    ridx, v = item
    atoms = [s for s, c in zip(ORDER, v) for _ in range(c)]
    mols = P.simulate(atoms)
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
    data = json.load(open(BASE + r"\t12b_vec_data2.json", encoding="utf-8"))
    uniq = data["vecs"]
    res = data["res"]
    todo = [(k, tuple(v)) for k, v in enumerate(uniq) if res[k][0] == 3]
    print(f"timeout 向量 {len(todo)} / {len(uniq)}", flush=True)
    if not todo:
        json.dump({}, open(BASE + r"\t12b_timeout_fix.json", "w", encoding="utf-8"))
        return
    out = {}
    with Pool(NPROC) as pool:
        for k, (ridx, r) in enumerate(pool.imap_unordered(work, todo, chunksize=4), 1):
            out[str(ridx)] = r
            if k % 20 == 0 or k == len(todo):
                print(f"  {k}/{len(todo)} {time.time()-t0:.1f}s", flush=True)
    from collections import Counter
    c = Counter(r[0] for r in out.values())
    print("复核结果:", dict(c), flush=True)
    json.dump(out, open(BASE + r"\t12b_timeout_fix.json", "w", encoding="utf-8"),
              separators=(",", ":"))
    print(f"saved {time.time()-t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
