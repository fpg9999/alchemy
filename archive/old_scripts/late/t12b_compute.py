# -*- coding: utf-8 -*-
"""t12b_compute.py —— 对 S 的全部唯一总向量计算反应结果（multiprocessing）。

口径：
  - 主口径 `pot_all.simulate`（规则 1~8 + tied[0]，与 T11/T11B 数据一致）
  - 对照口径 `pot_v3.simulate`（正式规则 1~9），用于量化规则 9 的差异
  - 可摆放性：严格校验 `pot_v2.embed_all2`
输出：t12b_vec_data.json（vecs / all / v3 三个平行数组）
"""
import json
import os
import sys
import time
from multiprocessing import Pool

BASE = r"G:\AI work\deepseek\work1\alchemy"
sys.path.insert(0, BASE)
import pot_all as P
import pot_v2
import pot_v3

ORDER = P.ORDER
NPROC = int(os.environ.get("T12B_PROC", "16"))
CHUNK = int(os.environ.get("T12B_CHUNK", "1000"))


def react_vec(v, sim):
    atoms = [s for s, c in zip(ORDER, v) for _ in range(c)]
    mols = sim(atoms)
    if mols is None:
        return (0, [])
    if not pot_v2.embed_all2(mols):
        return (0, [])
    return (1, sorted(P.formula_of(m["atoms"]) for m in mols))


def work(chunk):
    out = []
    for v in chunk:
        ok_a, pr_a = react_vec(v, P.simulate)
        ok_v, pr_v = react_vec(v, pot_v3.simulate)
        out.append([ok_a, pr_a, ok_v, pr_v])
    return out


def main():
    t0 = time.time()
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
    uniq = sorted(seen)
    nv = len(uniq)
    print(f"|S|={n} 唯一总向量={nv}，进程={NPROC}", flush=True)

    # 分片
    chunks = [uniq[i:i + CHUNK] for i in range(0, nv, CHUNK)]
    print(f"chunks={len(chunks)}", flush=True)
    t = time.time()
    out = []
    with Pool(NPROC) as pool:
        for k, res in enumerate(pool.imap(work, chunks), 1):
            out.extend(res)
            if k % 100 == 0 or k == len(chunks):
                el = time.time() - t
                eta = el / k * (len(chunks) - k)
                print(f"  {k}/{len(chunks)} chunks, {el:.1f}s, ETA {eta:.0f}s", flush=True)
    dt = time.time() - t
    print(f"计算完成 {dt:.1f}s（{dt/nv*1000:.3f} ms/向量，含两口径）", flush=True)

    assert len(out) == nv
    ok_all = [r[0] for r in out]
    prods_all = [r[1] for r in out]
    ok_v3 = [r[2] for r in out]
    prods_v3 = [r[3] for r in out]
    diff_vecs = sum(1 for i in range(nv) if (ok_all[i], prods_all[i]) != (ok_v3[i], prods_v3[i]))
    print(f"pot_all vs pot_v3：向量级差异 {diff_vecs}/{nv} = {diff_vecs/nv*100:.3f}%", flush=True)

    data = {"vecs": [list(v) for v in uniq],
            "all": [[ok_all[i], prods_all[i]] for i in range(nv)],
            "v3": [[ok_v3[i], prods_v3[i]] for i in range(nv)]}
    fn = BASE + r"\t12b_vec_data.json"
    json.dump(data, open(fn, "w", encoding="utf-8"), ensure_ascii=False,
              separators=(",", ":"))
    print(f"saved {fn} ({os.path.getsize(fn)/1e6:.1f} MB)", flush=True)
    stats = {"n_uniq_vec": nv, "sec": round(dt, 1), "nproc": NPROC,
             "diff_all_vs_v3": diff_vecs}
    json.dump(stats, open(BASE + r"\t12b_compute_stats.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("done", flush=True)


if __name__ == "__main__":
    main()
