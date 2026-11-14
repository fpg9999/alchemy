# -*- coding: utf-8 -*-
"""t12b_compute2.py —— 全量唯一总向量反应计算（分块增量落盘、可续算、带 embedding 节点上限）。

主口径：pot_all.simulate（规则 1~8 + tied[0]）
可摆放性：t12b_embed.embed_all_status（严格校验 + 节点上限；超过记 timeout 未判定，另附高上限复核）
状态码：0=成功, 1=剩键失败, 2=摆放失败, 3=timeout（未判定）

输出：
  t12b_vecparts/part_%06d.json  每块结果（可续算）
  t12b_vec_data2.json           {vecs, res:[ [status, products], ... ]}
  t12b_compute2.log             进度日志
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
CHUNK = int(os.environ.get("T12B_CHUNK", "400"))
CAP = int(os.environ.get("T12B_CAP", "300000"))
PARTS = BASE + r"\t12b_vecparts"


def work(chunk):
    out = []
    for v in chunk:
        atoms = [s for s, c in zip(ORDER, v) for _ in range(c)]
        mols = P.simulate(atoms)
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


def build_uniq():
    S = json.load(open(BASE + r"\t12b_S.json", encoding="utf-8"))
    vecs = [tuple(d["vec"]) for d in S]
    n = len(vecs)
    seen = set()
    for i in range(n):
        vi = vecs[i]
        seen.add((vi[0] * 2, vi[1] * 2, vi[2] * 2, vi[3] * 2, vi[4] * 2,
                  vi[5] * 2, vi[6] * 2, vi[7] * 2, vi[8] * 2))
        for j in range(i + 1, n):
            vj = vecs[j]
            seen.add((vi[0] + vj[0], vi[1] + vj[1], vi[2] + vj[2],
                      vi[3] + vj[3], vi[4] + vj[4], vi[5] + vj[5],
                      vi[6] + vj[6], vi[7] + vj[7], vi[8] + vj[8]))
    return sorted(seen)


def main():
    t0 = time.time()
    os.makedirs(PARTS, exist_ok=True)
    uniq = build_uniq()
    nv = len(uniq)
    starts = list(range(0, nv, CHUNK))
    print(f"唯一总向量 {nv}，块 {len(starts)}，块大小 {CHUNK}，CAP={CAP}", flush=True)

    have = set()
    for f in os.listdir(PARTS):
        if f.startswith("part_") and f.endswith(".json"):
            have.add(int(f[5:11]))
    todo = [s for s in starts if s not in have]
    print(f"已完成块 {len(have)}，待算块 {len(todo)}", flush=True)

    t = time.time()
    with Pool(NPROC) as pool:
        jobs = [(s, uniq[s:s + CHUNK]) for s in todo]
        done = 0
        for s, res in zip(todo, pool.imap(work, [j[1] for j in jobs])):
            fn = os.path.join(PARTS, "part_%06d.json" % s)
            tmp = fn + ".tmp"
            json.dump(res, open(tmp, "w", encoding="utf-8"), separators=(",", ":"))
            os.replace(tmp, fn)
            done += 1
            if done % 50 == 0 or done == len(todo):
                el = time.time() - t
                eta = el / done * (len(todo) - done)
                print(f"  {done}/{len(todo)} 块 {el:.1f}s ETA {eta:.0f}s", flush=True)
    print(f"计算完成 {time.time()-t:.1f}s", flush=True)

    # 合并
    res = [None] * nv
    for s in starts:
        part = json.load(open(os.path.join(PARTS, "part_%06d.json" % s), encoding="utf-8"))
        for k, r in enumerate(part):
            res[s + k] = r
    assert all(r is not None for r in res), "missing parts"
    fn = BASE + r"\t12b_vec_data2.json"
    json.dump({"vecs": [list(v) for v in uniq], "res": res},
              open(fn, "w", encoding="utf-8"), separators=(",", ":"))
    from collections import Counter
    c = Counter(r[0] for r in res)
    print(f"saved {fn} {os.path.getsize(fn)/1e6:.1f}MB 状态码 {dict(c)}", flush=True)
    print(f"总耗时 {time.time()-t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
