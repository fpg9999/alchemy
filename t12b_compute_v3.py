# -*- coding: utf-8 -*-
"""t12b_compute_v3.py —— 用正式模拟器 pot_v3（规则 1~9）重算全部唯一总向量（对照口径）。
输出 t12b_v3parts/ + t12b_vec_v3.json {vecs, res}；status 同 t12b_compute2。
"""
import json
import os
import sys
import time
from multiprocessing import Pool

BASE = r"G:\AI work\deepseek\work1\alchemy"
sys.path.insert(0, BASE)
import pot_all as P
import pot_v3
import t12b_embed as E

ORDER = P.ORDER
NPROC = int(os.environ.get("T12B_PROC", "16"))
CHUNK = int(os.environ.get("T12B_CHUNK", "400"))
CAP = int(os.environ.get("T12B_CAP", "300000"))
PARTS = BASE + r"\t12b_v3parts"


def work(chunk):
    out = []
    for v in chunk:
        atoms = [s for s, c in zip(ORDER, v) for _ in range(c)]
        mols = pot_v3.simulate(atoms)
        if mols is None:
            out.append([1, []])
            continue
        st, _ = E.embed_all_status(mols, max_nodes=CAP)
        if st == "ok":
            out.append([0, sorted(P.formula_of(m["atoms"]) for m in mols)])
        elif st == "fail":
            out.append([2, []])
        else:
            out.append([3, []])
    return out


def main():
    t0 = time.time()
    os.makedirs(PARTS, exist_ok=True)
    data = json.load(open(BASE + r"\t12b_results.json", encoding="utf-8"))
    uniq = [tuple(v) for v in data["vecs"]]
    nv = len(uniq)
    starts = list(range(0, nv, CHUNK))
    have = set()
    for f in os.listdir(PARTS):
        if f.startswith("part_") and f.endswith(".json"):
            have.add(int(f[5:11]))
    todo = [s for s in starts if s not in have]
    print(f"pot_v3: 向量 {nv}，块 {len(starts)}，已完成 {len(have)}，待算 {len(todo)}", flush=True)
    t = time.time()
    with Pool(NPROC) as pool:
        jobs = [uniq[s:s + CHUNK] for s in todo]
        done = 0
        for s, res in zip(todo, pool.imap(work, jobs)):
            fn = os.path.join(PARTS, "part_%06d.json" % s)
            tmp = fn + ".tmp"
            json.dump(res, open(tmp, "w", encoding="utf-8"), separators=(",", ":"))
            os.replace(tmp, fn)
            done += 1
            if done % 50 == 0 or done == len(todo):
                el = time.time() - t
                print(f"  {done}/{len(todo)} {el:.1f}s ETA {el/done*(len(todo)-done):.0f}s",
                      flush=True)
    print(f"计算完成 {time.time()-t:.1f}s", flush=True)
    res = [None] * nv
    for s in starts:
        part = json.load(open(os.path.join(PARTS, "part_%06d.json" % s), encoding="utf-8"))
        for k, r in enumerate(part):
            res[s + k] = r
    assert all(r is not None for r in res)
    json.dump({"vecs": [list(v) for v in uniq], "res": res},
              open(BASE + r"\t12b_vec_v3.json", "w", encoding="utf-8"),
              separators=(",", ":"))
    from collections import Counter
    print("状态分布:", dict(Counter(r[0] for r in res)), flush=True)
    print(f"done {time.time()-t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
