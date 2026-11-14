# -*- coding: utf-8 -*-
"""t12b_prep.py —— T12B 预处理：选 S（natoms<=8）、校验向量、统计总向量等价类、试跑测速。

输出：
  t12b_S.json          S 的物质清单 [{"formula","natoms","vec"}]
  t12b_prep_stats.json 预统计（|S|、对数、唯一总向量数、测速结果）
"""
import json
import sys
import time
from collections import Counter, defaultdict
from itertools import combinations_with_replacement

BASE = r"G:\AI work\deepseek\work1\alchemy"
sys.path.insert(0, BASE)
import pot_all as P
import pot_v2

ORDER = P.ORDER
IDX = {s: i for i, s in enumerate(ORDER)}


def vec_of_formula(f):
    return P.parse_formula(f)


def load_S(max_natoms=8):
    idx = json.load(open(BASE + r"\t4_catalog_index.json", encoding="utf-8"))
    sub = [d for d in idx if d["natoms"] <= max_natoms]
    sub.sort(key=lambda d: (d["natoms"], d["formula"]))
    S = []
    seen = set()
    for d in sub:
        f = d["formula"]
        if f in seen:
            continue
        seen.add(f)
        v = vec_of_formula(f)
        assert sum(v) == d["natoms"], (f, v, d["natoms"])
        S.append({"formula": f, "natoms": d["natoms"], "vec": list(v)})
    return S


def verify_against_catalog(S, max_natoms=8):
    """用 t4_catalog_all_validated.json 校验 formula/vec/natoms 一致。"""
    cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
    print("catalog type/len:", type(cat).__name__, len(cat), flush=True)
    if isinstance(cat, dict):
        recs = list(cat.values())
    else:
        recs = cat
    sample = recs[0]
    if isinstance(sample, str):
        print("catalog sample is str:", sample[:100], flush=True)
        return None
    print("catalog keys:", list(sample.keys())[:12], flush=True)
    # build formula -> atoms map
    fmap = {}
    for r in recs:
        f = r.get("formula")
        if f is not None:
            fmap[f] = r
    miss = [d["formula"] for d in S if d["formula"] not in fmap]
    bad = []
    for d in S:
        r = fmap.get(d["formula"])
        if r is None:
            continue
        atoms = r.get("atoms")
        v = Counter(atoms) if atoms is not None else None
        if v is not None:
            vv = tuple(v.get(e, 0) for e in ORDER)
            if vv != tuple(d["vec"]):
                bad.append((d["formula"], d["vec"], vv))
    return {"n_catalog": len(recs), "missing_in_catalog": len(miss),
            "vec_mismatch": len(bad), "missing_examples": miss[:5],
            "bad_examples": bad[:5]}


def unique_vectors(S):
    vecs = [tuple(d["vec"]) for d in S]
    n = len(vecs)
    tot = n * (n + 1) // 2
    seen = set()
    t = time.time()
    for i in range(n):
        vi = vecs[i]
        seen.add(tuple(vi[k] + vi[k] for k in range(9)))
        for j in range(i + 1, n):
            vj = vecs[j]
            seen.add((vi[0] + vj[0], vi[1] + vj[1], vi[2] + vj[2],
                      vi[3] + vj[3], vi[4] + vj[4], vi[5] + vj[5],
                      vi[6] + vj[6], vi[7] + vj[7], vi[8] + vj[8]))
    return tot, len(seen), time.time() - t


def react_vec(v, sim):
    atoms = [s for s, c in zip(ORDER, v) for _ in range(c)]
    mols = sim(atoms)
    if mols is None:
        return (0, ())  # 失败
    if not pot_v2.embed_all2(mols):
        return (0, ())
    return (1, tuple(sorted(P.formula_of(m["atoms"]) for m in mols)))


def main():
    t0 = time.time()
    S = load_S(8)
    print(f"|S| = {len(S)}（natoms<=8，公式去重）", flush=True)
    json.dump(S, open(BASE + r"\t12b_S.json", "w", encoding="utf-8"), ensure_ascii=False)
    print("natoms 分布:", dict(Counter(d["natoms"] for d in S)), flush=True)

    ver = verify_against_catalog(S)
    print("目录校验:", ver, flush=True)
    print(f"预处理耗时 {time.time()-t0:.1f}s", flush=True)

    tot, nvec, tsum = unique_vectors(S)
    print(f"无序对 {tot}；唯一总向量 {nvec}（压缩率 {tot/nvec:.2f}x），求和耗时 {tsum:.1f}s", flush=True)

    # 测速：对唯一向量抽样（含奇偶价分布），分别测 pot_all / pot_v3
    import random
    rng = random.Random(12345)
    vecs = [tuple(d["vec"]) for d in S]
    sample = set()
    # 从 S 自身及随机对里抽
    for _ in range(4000):
        i = rng.randrange(len(vecs))
        j = rng.randrange(len(vecs))
        vi, vj = vecs[i], vecs[j]
        sample.add(tuple(vi[k] + vj[k] for k in range(9)))
    sample = list(sample)
    rng.shuffle(sample)
    sample = sample[:2000]
    import pot_v3
    for name, sim in (("pot_v3", pot_v3.simulate), ("pot_all", P.simulate)):
        t = time.time()
        res = {}
        for v in sample:
            res[v] = react_vec(v, sim)
        dt = time.time() - t
        ok = sum(1 for r in res.values() if r[0])
        print(f"[测速] {name}: {len(sample)} 向量 {dt:.2f}s => {dt/len(sample)*1000:.3f} ms/向量，"
              f"成功 {ok}，失败 {len(sample)-ok}", flush=True)
        if name == "pot_v3":
            # 全量外推
            print(f"   全量 {nvec} 唯一向量外推：单核 {dt/len(sample)*nvec/60:.1f} 分钟；"
                  f"16 进程 {dt/len(sample)*nvec/60/16:.1f} 分钟", flush=True)

    stats = {"n_S": len(S), "n_pairs": tot, "n_unique_vec": nvec,
             "prep_sec": round(time.time() - t0, 2), "verify": ver,
             "natoms_hist": dict(Counter(d["natoms"] for d in S))}
    json.dump(stats, open(BASE + r"\t12b_prep_stats.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("done", flush=True)


if __name__ == "__main__":
    main()
