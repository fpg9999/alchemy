# -*- coding: utf-8 -*-
"""t12c_law.py —— T12C 任务3：总向量决定律 / 同总向量分组 / 碰撞率。

三部分：
A. 碰撞统计（分层"精确"枚举）：
   - L1(2-8) 全层 3,931 条 → 全部无序对 7.72M，精确；
   - L2(9-16) 抽 4,000 条公式 → 全部无序对 8.0M，精确（样本层）；
   - L3(17-32) 全层 937 条 → 全部无序对 438,516，精确；
   - L4(33+) 全层 327 条 → 全部无序对 53,451，精确；
   - 全目录：随机抽 2,000,000 对，估计不同总向量数与碰撞率（二阶矩估计）。
B. 从上述精确分组中分层抽 100 组「同总向量、不同物质对」，每组取 2~3 对，
   分别用**各对自身的原子顺序**独立跑 pot_v3，比较产物分子式多重集是否完全相同
   （并额外用规范顺序与随机打乱顺序各跑一次，检验实现是否依赖原子顺序）。
C. 每组对规范结果做一次严格 embedding 校验（节点预算 3M），记录成功/失败。

输出: t12c_law.json
"""
import json, sys, os, time, random, itertools
from collections import Counter, defaultdict

BASE = r"G:\AI work\deepseek\work1\alchemy"
sys.path.insert(0, BASE)
import numpy as np
import pot_all as P
import pot_v2
import pot_v3

ORDER = list(P.ORDER)
EMBED_CAP = 3_000_000
N_VERIFY = 100


def atoms_of(v):
    return [e for e, c in zip(ORDER, v) for _ in range(c)]


def load_entries():
    cat = json.load(open(os.path.join(BASE, "t4_catalog_all_validated.json"), encoding="utf-8"))
    ents = []
    for d in cat:
        v = tuple(P.parse_formula(d["formula"]))
        ents.append({"formula": d["formula"], "vec": v, "natoms": sum(v), "atoms": d["atoms"]})
    return ents


def encode(codes, base):
    """返回 int64 编码向量（按 base 混合进制）。"""
    return codes @ (base ** np.arange(9, dtype=np.int64))


def collision_stats_codes(codes, base, label):
    """codes: np.int64 array (已编码)。枚举所有 i<j 对之和的精确统计。"""
    n = len(codes)
    total = n * (n - 1) // 2
    t0 = time.time()
    sums = codes[:, None] + codes[None, :]
    iu = np.triu_indices(n, 1)
    flat = sums[iu]
    del sums
    vals, counts = np.unique(flat, return_counts=True)
    del flat
    D = len(vals)
    multi_mask = counts >= 2
    n_multi_groups = int(multi_mask.sum())
    pairs_in_multi = int(counts[multi_mask].sum())
    coll_rate = pairs_in_multi / total if total else 0.0
    print(f"[{label}] n={n} pairs={total} distinct_sums={D} "
          f"groups>=2={n_multi_groups} pairs_in_groups>=2={pairs_in_multi} "
          f"collision_rate={coll_rate:.4%} ({time.time()-t0:.1f}s)", flush=True)
    return {"label": label, "n_entries": int(n), "total_pairs": int(total),
            "distinct_sums": int(D), "groups_ge2": n_multi_groups,
            "pairs_in_groups_ge2": pairs_in_multi, "collision_rate": coll_rate,
            "group_size_dist": {int(k): int(v) for k, v in
                                zip(*np.unique(counts, return_counts=True))},
            "values": vals, "counts": counts, "codes": codes, "base": base}


def find_pairs_for_sum(codes, base, target, nmax=3):
    """给定编码和，找 i<j 使 code[i]+code[j]==target。"""
    pos = {int(c): i for i, c in enumerate(codes)}
    out = []
    n = len(codes)
    for i in range(n):
        need = target - int(codes[i])
        j = pos.get(need)
        if j is not None and j > i:
            out.append((i, j))
            if len(out) >= nmax:
                break
    return out


def pick_groups(stats, quota, rng):
    """从某层精确统计中随机选 quota 个（sum 值）含 >=2 对的组。"""
    vals, counts = stats["values"], stats["counts"]
    idx = np.where(counts >= 2)[0]
    if len(idx) == 0:
        return []
    pick = rng.sample(list(idx), min(quota, len(idx)))
    return [(int(vals[k]), int(counts[k])) for k in pick]


# ---------------------------------------------------------------- 验证 worker
def verify_group(args):
    """args: (layer, sum_vec, pairs_atoms, group_size)
    pairs_atoms: list of (formulaA, atomsA, formulaB, atomsB)
    返回该组的验证记录。"""
    layer, svec, pairs_atoms, group_size = args
    runs = []
    for fa, aa, fb, ab in pairs_atoms:
        seq = list(aa) + list(ab)
        mols = pot_v3.simulate(seq)
        sig = None if mols is None else tuple(sorted(P.formula_of(m["atoms"]) for m in mols))
        runs.append({"pair": [fa, fb], "status": "ok" if mols is not None else "fail",
                     "sig": sig, "prods": list(sig) if sig else None})
    # 规范顺序
    cv = atoms_of(svec)
    mols_c = pot_v3.simulate(cv)
    sig_c = None if mols_c is None else tuple(sorted(P.formula_of(m["atoms"]) for m in mols_c))
    # 随机打乱顺序
    seq_r = cv[:]
    random.Random(12345).shuffle(seq_r)
    mols_r = pot_v3.simulate(seq_r)
    sig_r = None if mols_r is None else tuple(sorted(P.formula_of(m["atoms"]) for m in mols_r))
    # embedding 校验（规范结果）
    embed_ok = None
    if mols_c is not None:
        embed_ok = True
        for m in mols_c:
            if pot_v2.embed_mol2(m["atoms"], m["edges"], max_nodes=EMBED_CAP) is None:
                embed_ok = False
                break
    sigs = [r["sig"] for r in runs] + [sig_c, sig_r]
    identical = all(s == sigs[0] for s in sigs)
    return {"layer": layer, "sum": list(svec), "sum_atoms": int(sum(svec)),
            "group_size_seen": group_size,
            "runs": runs, "canonical": list(sig_c) if sig_c else None,
            "shuffled_check": bool(sig_r == sig_c),
            "identical": bool(identical), "embed_ok": embed_ok,
            "status": "ok" if sig_c is not None else "fail"}


def main():
    t_start = time.time()
    ents = load_entries()
    rng = random.Random(20261113)
    stats_out = {}
    groups_pool = []  # (layer, sum_vec, [(i,j),...])

    # ---- L1 全层精确
    i1 = [k for k, e in enumerate(ents) if 2 <= e["natoms"] <= 8]
    codes1 = encode(np.array([ents[k]["vec"] for k in i1], dtype=np.int64), 17)
    st1 = collision_stats_codes(codes1, 17, "L1(2-8) 全层")
    stats_out["L1_exact"] = {k: v for k, v in st1.items() if k not in ("values", "counts", "codes")}
    for sval, cnt in pick_groups(st1, 30, rng):
        idxs = find_pairs_for_sum(codes1, 17, sval, nmax=3)
        pairs = [(i1[a], i1[b]) for a, b in idxs]
        rem = sval
        vec = []
        for _ in range(9):
            vec.append(rem % 17)
            rem //= 17
        groups_pool.append(("L1_2-8", tuple(vec), pairs, cnt))

    # ---- L2 子集精确（4000 条）
    i2 = [k for k, e in enumerate(ents) if 9 <= e["natoms"] <= 16]
    sub2 = rng.sample(i2, 3000)
    codes2 = encode(np.array([ents[k]["vec"] for k in sub2], dtype=np.int64), 33)
    st2 = collision_stats_codes(codes2, 33, "L2(9-16) 子集3000")
    stats_out["L2_subset_exact"] = {k: v for k, v in st2.items() if k not in ("values", "counts", "codes")}
    for sval, cnt in pick_groups(st2, 25, rng):
        idxs = find_pairs_for_sum(codes2, 33, sval, nmax=3)
        pairs = [(sub2[a], sub2[b]) for a, b in idxs]
        rem = sval
        vec = []
        for _ in range(9):
            vec.append(rem % 33)
            rem //= 33
        groups_pool.append(("L2_9-16", tuple(vec), pairs, cnt))

    # ---- L3 全层精确（Python 元组）
    i3 = [k for k, e in enumerate(ents) if 17 <= e["natoms"] <= 32]
    d3 = defaultdict(list)
    for a in range(len(i3)):
        va = ents[i3[a]]["vec"]
        for b in range(a + 1, len(i3)):
            s = tuple(x + y for x, y in zip(va, ents[i3[b]]["vec"]))
            d3[s].append((i3[a], i3[b]))
    total3 = len(i3) * (len(i3) - 1) // 2
    multi3 = {k: v for k, v in d3.items() if len(v) >= 2}
    print(f"[L3(17-32) 全层] pairs={total3} distinct={len(d3)} groups>=2={len(multi3)} "
          f"pairs_in={sum(len(v) for v in multi3.values())} "
          f"rate={sum(len(v) for v in multi3.values())/total3:.4%}", flush=True)
    stats_out["L3_exact"] = {"label": "L3(17-32) 全层", "n_entries": len(i3),
                             "total_pairs": total3, "distinct_sums": len(d3),
                             "groups_ge2": len(multi3),
                             "pairs_in_groups_ge2": sum(len(v) for v in multi3.values()),
                             "collision_rate": sum(len(v) for v in multi3.values()) / total3}
    keys3 = rng.sample(list(multi3), min(25, len(multi3)))
    for k in keys3:
        groups_pool.append(("L3_17-32", k, multi3[k][:3], len(multi3[k])))

    # ---- L4 全层精确
    i4 = [k for k, e in enumerate(ents) if e["natoms"] >= 33]
    d4 = defaultdict(list)
    for a in range(len(i4)):
        va = ents[i4[a]]["vec"]
        for b in range(a + 1, len(i4)):
            s = tuple(x + y for x, y in zip(va, ents[i4[b]]["vec"]))
            d4[s].append((i4[a], i4[b]))
    total4 = len(i4) * (len(i4) - 1) // 2
    multi4 = {k: v for k, v in d4.items() if len(v) >= 2}
    print(f"[L4(33+) 全层] pairs={total4} distinct={len(d4)} groups>=2={len(multi4)} "
          f"pairs_in={sum(len(v) for v in multi4.values())} "
          f"rate={sum(len(v) for v in multi4.values())/total4:.4%}", flush=True)
    stats_out["L4_exact"] = {"label": "L4(33+) 全层", "n_entries": len(i4),
                             "total_pairs": total4, "distinct_sums": len(d4),
                             "groups_ge2": len(multi4),
                             "pairs_in_groups_ge2": sum(len(v) for v in multi4.values()),
                             "collision_rate": sum(len(v) for v in multi4.values()) / total4}
    keys4 = rng.sample(list(multi4), min(20, len(multi4)))
    for k in keys4:
        groups_pool.append(("L4_33+", k, multi4[k][:3], len(multi4[k])))

    # ---- 全目录：随机 200 万对抽样估计
    n_all = len(ents)
    N_pairs = n_all * (n_all - 1) // 2
    m = 2_000_000
    code_all = np.array([e["vec"] for e in ents], dtype=np.int64)
    # 分量最大 97，对和最大 194 < 256：用 256 进制拆成两块 int64 编码（避免 256^9 溢出）
    pw = (256 ** np.arange(5, dtype=np.int64))
    ca_lo = code_all[:, :5] @ pw
    ca_hi = code_all[:, 5:] @ (256 ** np.arange(4, dtype=np.int64))
    rr = np.random.default_rng(20261113)
    ai = rr.integers(0, n_all, m)
    bi = rr.integers(0, n_all, m)
    keep = ai != bi
    ai, bi = ai[keep], bi[keep]
    lo = ca_lo[ai] + ca_lo[bi]
    hi = ca_hi[ai] + ca_hi[bi]
    enc = np.stack([lo, hi], axis=1)
    uniq_enc, counts_s = np.unique(enc, axis=0, return_counts=True)
    dist_samp = len(uniq_enc)
    # q = 两个随机对同 sum 的概率估计（有序对样本的二阶矩无偏估计）
    q_est = float(np.sum(counts_s * (counts_s - 1)) / (len(lo) * (len(lo) - 1)))
    coll_samp = float(np.sum(counts_s[counts_s >= 2] - 1) / len(lo))
    print(f"[全目录抽样 {len(lo)} 对] distinct_in_sample={dist_samp} "
          f"collision_pairs_frac_in_sample={coll_samp:.4%} "
          f"q_est(two random pairs share sum)={q_est:.3e} N_pairs={N_pairs}", flush=True)
    stats_out["full_catalog_sample"] = {"label": "全目录随机对抽样", "sampled_pairs": int(len(lo)),
                                        "distinct_sums_in_sample": int(dist_samp),
                                        "collision_pairs_frac_in_sample": coll_samp,
                                        "q_est_two_pairs_same_sum": q_est,
                                        "N_pairs": int(N_pairs),
                                        "note": "q_est=两个随机物质对的总向量相同的概率（样本二阶矩估计）"}

    # ---- 100 组验证（补足到 100，按层配额不足时从别的层补）
    print(f"候选组 {len(groups_pool)}", flush=True)
    rng.shuffle(groups_pool)
    # 尽量按层均衡：每层最多 30，总数 100
    by_layer = defaultdict(list)
    for g in groups_pool:
        by_layer[g[0]].append(g)
    selected = []
    order = ["L1_2-8", "L2_9-16", "L3_17-32", "L4_33+"]
    targets = {"L1_2-8": 30, "L2_9-16": 25, "L3_17-32": 25, "L4_33+": 20}
    for lay in order:
        selected.extend(by_layer[lay][:targets[lay]])
    if len(selected) < N_VERIFY:
        for g in groups_pool:
            if g not in selected:
                selected.append(g)
                if len(selected) >= N_VERIFY:
                    break
    selected = selected[:N_VERIFY]
    print(f"选中验证组 {len(selected)}", flush=True)

    tasks = []
    for lay, svec, pairs, gsize in selected:
        pa = []
        seen_pair = set()
        for (i, j) in pairs:
            fa, fb = ents[i]["formula"], ents[j]["formula"]
            if (fa, fb) in seen_pair:
                continue
            seen_pair.add((fa, fb))
            pa.append((fa, ents[i]["atoms"], fb, ents[j]["atoms"]))
        if len(pa) >= 2:
            tasks.append((lay, svec, pa, int(gsize)))

    from multiprocessing import Pool
    t0 = time.time()
    with Pool(12) as pool:
        ver = pool.map(verify_group, tasks, chunksize=1)
    print(f"验证完成 {len(ver)} 组，用时 {time.time()-t0:.1f}s", flush=True)

    n_ident = sum(1 for v in ver if v["identical"])
    n_ok = sum(1 for v in ver if v["status"] == "ok")
    n_embed = sum(1 for v in ver if v["embed_ok"] is True)
    n_embed_fail = sum(1 for v in ver if v["embed_ok"] is False)
    print(f"同总向量验证: {n_ident}/{len(ver)} 组结果完全一致；反应成功 {n_ok}；"
          f"embedding ok {n_embed} / fail {n_embed_fail}", flush=True)
    for v in ver:
        if not v["identical"]:
            print("  ! 不一致组:", v["layer"], v["sum"], [r["pair"] for r in v["runs"]],
                  [r["sig"] for r in v["runs"]], flush=True)

    out = {"stats": stats_out, "groups": ver,
           "summary": {"n_groups_verified": len(ver), "n_identical": n_ident,
                       "n_ok": n_ok, "n_embed_ok": n_embed, "n_embed_fail": n_embed_fail,
                       "n_shuffled_same": sum(1 for v in ver if v["shuffled_check"])}}
    json.dump(out, open(os.path.join(BASE, "t12c_law.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    print(f"落盘 t12c_law.json；总用时 {(time.time()-t_start)/60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
