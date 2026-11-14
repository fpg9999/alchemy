# -*- coding: utf-8 -*-
"""t12b_analyze.py —— T12B 全物质（natoms<=8）两两反应规律分析（v2，读取增量计算结果）。

输入：
  t12b_S.json            S 物质清单（3931 个）
  t12b_results.json      唯一总向量结果（pot_all 主口径）status: 0成功 1剩键失败 2摆放失败 3未判定
  t12b_vec_v3.json       (可选) pot_v3（正式规则1~9）全量结果
  t12b_failreason.json   (可选) 失败原因细化
  t4_catalog_index.json  产物是否都在 ≤16 完备目录中（验证）
输出：t12b_summary.json
"""
import json
import random
import time
from collections import Counter, defaultdict

import numpy as np

BASE = r"G:\AI work\deepseek\work1\alchemy"
ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]
CAT = {"O": "聚", "X": "聚", "C": "聚", "P": "动", "W": "动", "L": "动",
       "K": "散", "A": "散", "F": "散"}
VAL = {"O": 3, "X": 2, "C": 1, "P": 3, "W": 2, "L": 1, "K": 3, "A": 2, "F": 1}
TRIV_IDX = (0, 3, 6)
MONO_IDX = (2, 5, 8)
BS = [17 ** (8 - i) for i in range(9)]
CAT_ORDER = ["聚", "动", "散"]

import pot_all as P


def vec_of_formula(f):
    return P.parse_formula(f)


def key_of(v):
    return int(sum(int(v[i]) * BS[i] for i in range(9)))


def element_set(v):
    return tuple(ORDER[i] for i in range(9) if v[i] > 0)


def cats_str(v):
    s = set()
    for i in range(9):
        if v[i] > 0:
            s.add(CAT[ORDER[i]])
    return "".join(c for c in CAT_ORDER if c in s)


def pat_of(prods):
    k = len(prods)
    if k == 2:
        return "2×同种" if prods[0] == prods[1] else "2×不同"
    if k == 3:
        return "3产物含同种" if (prods[0] == prods[1] or prods[1] == prods[2]) else "3产物"
    if k >= 4:
        return f"{k}产物"
    return None


def react_direct(va, vb):
    """独立复算一对：pot_all 模拟 + t12b_embed 严格摆放（高上限）。"""
    import t12b_embed as E
    v = tuple(int(va[i]) + int(vb[i]) for i in range(9))
    atoms = [s for s, c in zip(ORDER, v) for _ in range(c)]
    mols = P.simulate(atoms)
    if mols is None:
        return [1, None]
    st, _ = E.embed_all_status(mols, max_nodes=3_000_000)
    if st != "ok":
        return [2, None]
    return [0, sorted(P.formula_of(m["atoms"]) for m in mols)]


def main():
    t0 = time.time()
    S = json.load(open(BASE + r"\t12b_S.json", encoding="utf-8"))
    formulas = [d["formula"] for d in S]
    natoms = np.array([d["natoms"] for d in S], dtype=np.int64)
    V = np.array([d["vec"] for d in S], dtype=np.int64)
    n = len(S)
    data = json.load(open(BASE + r"\t12b_results.json", encoding="utf-8"))
    U = np.array(data["vecs"], dtype=np.int64)
    nv = len(U)
    res = data["res"]
    del data
    keys_sorted = np.array([key_of(v) for v in U], dtype=np.int64)
    assert np.all(np.diff(keys_sorted) > 0)
    print(f"|S|={n}, 向量={nv}, load {time.time()-t0:.1f}s", flush=True)

    keys_i = np.array([key_of(v) for v in V], dtype=np.int64)
    sub_by_key = {int(keys_i[i]): i for i in range(n)}
    total_val_vec = U.dot(np.array([VAL[e] for e in ORDER], dtype=np.int64))
    natoms_vec = U.sum(axis=1)
    triv_vec = U[:, list(TRIV_IDX)].sum(axis=1)
    mono_vec = U[:, list(MONO_IDX)].sum(axis=1)

    catalog = set(d["formula"] for d in json.load(
        open(BASE + r"\t4_catalog_index.json", encoding="utf-8")))

    # ---------------- 预计算 ----------------
    status_a = np.zeros(nv, dtype=np.int8)
    cls_a = np.zeros(nv, dtype=np.int8)   # 0 fail, 1 single, 2 multi, 3 unresolved
    prods_a = [None] * nv
    p0a = np.full(nv, -1, dtype=np.int64)
    p1a = np.full(nv, -1, dtype=np.int64)
    for r in range(nv):
        st, pr = res[r]
        status_a[r] = st
        prods_a[r] = pr
        if st == 0:
            cls_a[r] = 1 if len(pr) == 1 else 2
            if len(pr) == 2:
                for t, f in enumerate(pr):
                    ix = sub_by_key.get(key_of(vec_of_formula(f)))
                    if ix is not None and formulas[ix] == f:
                        if t == 0:
                            p0a[r] = ix
                        else:
                            p1a[r] = ix
        elif st == 3:
            cls_a[r] = 3
        else:
            cls_a[r] = 0
    inert_a = ((p0a >= 0) & (p1a >= 0)).astype(np.int8)
    print(f"prep {time.time()-t0:.1f}s", flush=True)
    # 失败原因细化（若已生成）：用于失败例分层
    fr_detail = None
    _frf = BASE + r"\t12b_failreason.json"
    if __import__("os").path.exists(_frf):
        fr_detail = json.load(open(_frf, encoding="utf-8"))["detail"]

    # ---------------- 每类对数 ----------------
    counts = np.zeros(nv, dtype=np.int64)
    for i in range(n):
        js = np.arange(i, n)
        k = keys_i[i] + keys_i[js]
        idx = np.searchsorted(keys_sorted, k)
        counts += np.bincount(idx, minlength=nv)
    total_pairs = int(counts.sum())
    assert total_pairs == n * (n + 1) // 2
    print(f"counts {time.time()-t0:.1f}s", flush=True)

    fail_pairs = int(counts[cls_a == 0].sum())
    single_pairs = int(counts[cls_a == 1].sum())
    multi_base_pairs = int(counts[cls_a == 2].sum())
    inert_pairs = int(counts[inert_a == 1].sum())
    multi_pairs = multi_base_pairs - inert_pairs
    unresolved_pairs = int(counts[cls_a == 3].sum())
    assert fail_pairs + single_pairs + multi_pairs + inert_pairs + unresolved_pairs == total_pairs
    resolved = total_pairs - unresolved_pairs
    f_sim = int(counts[status_a == 1].sum())
    f_emb = int(counts[status_a == 2].sum())

    # ---------------- 每物质计数 ----------------
    cnts = np.zeros((n, 5), dtype=np.int64)   # fail,inert,single,multi,unresolved
    for i in range(n):
        js = np.arange(i, n)
        k = keys_i[i] + keys_i[js]
        idx = np.searchsorted(keys_sorted, k)
        codes = cls_a[idx]
        pc = np.where(codes == 0, 0, np.where(codes == 1, 2, np.where(codes == 2, 3, 4)))
        m2 = codes == 2
        if m2.any():
            pos2 = np.where(m2)[0]
            ii = idx[pos2]
            jj = js[pos2]
            inert_m = (((i == p0a[ii]) & (jj == p1a[ii])) |
                       ((i == p1a[ii]) & (jj == p0a[ii])))
            if inert_m.any():
                pc[pos2[inert_m]] = 1
        cnts[i] += np.bincount(pc, minlength=5)
        mj = js > i
        if mj.any():
            np.add.at(cnts, (js[mj], pc[mj]), 1)
    assert int(cnts.sum()) == 2 * total_pairs - n
    print(f"per-substance {time.time()-t0:.1f}s", flush=True)

    # ---------------- 工具 ----------------
    def find_pairs(target_key, maxn=8):
        out = []
        tk = int(target_key)
        for i in range(n):
            need = tk - int(keys_i[i])
            j = sub_by_key.get(need)
            if j is not None and j >= i:
                out.append((i, j))
                if len(out) >= maxn:
                    break
        return out

    rng = random.Random(20261113)

    def sample_vec(cands, k, weight=True):
        if len(cands) <= k:
            return [int(x) for x in cands]
        if weight:
            w = counts[cands].astype(float)
            w = w / w.sum()
            pick = rng.choices(range(len(cands)), weights=w, k=k)
            return [int(cands[t]) for t in pick]
        return [int(x) for x in rng.sample(list(cands), k)]

    # 失败例：按"剩键的剩余原子类型 / 摆放失败"分层抽样，保证多样性
    fail_rows = []
    for r in sample_vec(np.where(cls_a == 0)[0], 80):
        pairs = find_pairs(keys_sorted[r], 1)
        if not pairs:
            continue
        i, j = pairs[0]
        e = {
            "A": formulas[i], "B": formulas[j],
            "element_set": "".join(element_set(U[r])),
            "cats": cats_str(U[r]),
            "trivalent": int(triv_vec[r]),
            "total_valence": int(total_val_vec[r]),
            "natoms": int(natoms_vec[r]),
            "reason": "剩键" if status_a[r] == 1 else "摆放失败"}
        if fr_detail is not None and str(r) in fr_detail:
            d = fr_detail[str(r)]
            if d["kind"] == "stuck":
                e["leftover"] = d["left"]
        fail_rows.append(e)
    by_left = {}
    for e in fail_rows:
        if e["reason"] == "剩键" and "leftover" in e:
            by_left.setdefault("+".join(sorted(e["leftover"])), []).append(e)
    picked = []
    for key in sorted(by_left, key=lambda k: -len(by_left[k])):
        picked.extend(by_left[key][:6])
    emb = [e for e in fail_rows if e["reason"] == "摆放失败"][:6]
    examples = {"fail": picked + emb, "inert": [], "single": []}
    for r in sample_vec(np.where(inert_a == 1)[0], 20):
        pairs = find_pairs(keys_sorted[r], 1)
        if not pairs:
            continue
        i, j = pairs[0]
        examples["inert"].append({"A": formulas[i], "B": formulas[j],
                                  "products": prods_a[r]})
    for r in sample_vec(np.where(cls_a == 1)[0], 20):
        pairs = find_pairs(keys_sorted[r], 1)
        if not pairs:
            continue
        i, j = pairs[0]
        examples["single"].append({"A": formulas[i], "B": formulas[j],
                                   "product": prods_a[r][0]})

    # 多产物模式
    pat_cands = defaultdict(list)
    for r in range(nv):
        if cls_a[r] != 2:
            continue
        p = pat_of(prods_a[r])
        if p is not None:
            pat_cands[p].append(r)
    examples["multi"] = {}
    for pat, cands_l in pat_cands.items():
        cands = np.array(cands_l)
        lst = []
        for r in sample_vec(cands, 80):
            if inert_a[r] == 1 and counts[r] == 1:
                continue
            pairs = find_pairs(keys_sorted[r], 8)
            pick = None
            for (i, j) in pairs:
                is_inert = (inert_a[r] == 1 and
                            ((i == p0a[r] and j == p1a[r]) or
                             (i == p1a[r] and j == p0a[r])))
                if not is_inert:
                    pick = (i, j)
                    break
            if pick is None:
                continue
            i, j = pick
            lst.append({"A": formulas[i], "B": formulas[j],
                        "products": prods_a[r]})
            if len(lst) >= 5:
                break
        examples["multi"][pat] = lst
    print(f"examples {time.time()-t0:.1f}s", flush=True)

    # ---------------- 等价类验证 ----------------
    eq_sample = sample_vec(np.where(counts >= 2)[0], 50)
    eq_check = []
    n_checked_pairs = 0
    n_bad = 0
    for r in eq_sample:
        pairs = find_pairs(keys_sorted[r], 8)
        outs = []
        for (i, j) in pairs:
            got = react_direct(V[i], V[j])
            outs.append(json.dumps(got, ensure_ascii=False))
            n_checked_pairs += 1
            cached = [status_a[r], prods_a[r] if status_a[r] == 0 else None]
            if [got[0], got[1]] != cached:
                n_bad += 1
        eq_check.append({"vector": [int(x) for x in U[r]],
                         "class_size": int(counts[r]),
                         "pairs_checked": len(pairs),
                         "n_distinct_outcomes": len(set(outs)),
                         "outcome": [int(status_a[r]), prods_a[r]],
                         "pairs": [[formulas[i], formulas[j]] for (i, j) in pairs]})
    eq_distinct_bad = sum(1 for e in eq_check if e["n_distinct_outcomes"] != 1)

    class_size_hist = Counter(int(x) for x in counts)
    max_class = int(counts.max())
    n_multi_classes = int((counts >= 2).sum())
    pairs_in_multi_classes = int(counts[counts >= 2].sum())
    top_classes = []
    for r in np.argsort(-counts)[:10]:
        rr = int(r)
        pairs = find_pairs(keys_sorted[rr], 2)
        top_classes.append({"vector": [int(x) for x in U[rr]],
                            "size": int(counts[rr]),
                            "pairs": [[formulas[i], formulas[j]] for i, j in pairs],
                            "outcome": [int(status_a[rr]),
                                        prods_a[rr] if status_a[rr] == 0 else None]})
    print(f"eq check {len(eq_check)} classes / {n_checked_pairs} pairs, "
          f"mismatch={n_bad}, multi-outcome={eq_distinct_bad}", flush=True)

    # ---------------- 单产物验证 + 产物分布 ----------------
    single_vecs = np.where(cls_a == 1)[0]
    bad_sum = 0
    bad_examples = []
    prod_counter = Counter()
    prod_natoms_counter = Counter()
    prod_not_in_catalog = Counter()
    for r in single_vecs:
        f = prods_a[r][0]
        pv = vec_of_formula(f)
        if tuple(int(x) for x in pv) != tuple(int(x) for x in U[r]):
            bad_sum += 1
            if len(bad_examples) < 5:
                bad_examples.append((f, [int(x) for x in U[r]]))
        prod_counter[f] += int(counts[r])
        prod_natoms_counter[int(sum(pv))] += int(counts[r])
        if f not in catalog:
            prod_not_in_catalog[f] += int(counts[r])
    # 全部产物中不在目录里的（应为 0）
    all_not_in_catalog = Counter()
    for r in range(nv):
        if status_a[r] != 0:
            continue
        for f in prods_a[r]:
            if f not in catalog:
                all_not_in_catalog[f] += int(counts[r])

    # ---------------- 产物尺寸 / 守恒 ----------------
    size_hist = Counter()
    n_prod_total = 0
    nprod_hist = Counter()
    conservation_bad = 0
    for r in range(nv):
        if status_a[r] != 0:
            continue
        c = int(counts[r])
        tot = 0
        for f in prods_a[r]:
            nn = int(sum(vec_of_formula(f)))
            size_hist[nn] += c
            tot += nn
            n_prod_total += c
        nprod_hist[len(prods_a[r])] += c
        if tot != int(natoms_vec[r]):
            conservation_bad += c

    # ---------------- 集合/大类/尺寸/三价 统计 ----------------
    def new_stats():
        return [0, 0, 0, 0, 0, 0]  # total,fail,inert,single,multi,unresolved

    def add_stat(st, c, cls, inert):
        st[0] += c
        if cls == 0:
            st[1] += c
        elif inert:
            st[2] += c
        elif cls == 1:
            st[3] += c
        elif cls == 2:
            st[4] += c
        else:
            st[5] += c

    set_stats = defaultdict(new_stats)
    cat_stats = defaultdict(new_stats)
    natom_stats = defaultdict(new_stats)
    triv_stats = defaultdict(new_stats)
    elem_stats = defaultdict(new_stats)      # 每个元素：包含该元素的混合对
    noelem_stats = defaultdict(new_stats)    # 每个元素：不含该元素的混合对
    triv_combo = defaultdict(new_stats)      # 三价元素组合（O/P/K 的哪些出现）
    triv_even = defaultdict(lambda: [0, 0, 0])   # total, fail, unresolved
    triv_odd = defaultdict(lambda: [0, 0, 0])
    for r in range(nv):
        c = int(counts[r])
        if c == 0:
            continue
        cls = int(cls_a[r])
        inrt = inert_a[r] == 1
        es = "".join(element_set(U[r]))
        cs = cats_str(U[r])
        t = int(triv_vec[r])
        nat = int(natoms_vec[r])
        for st in (set_stats[es], cat_stats[cs], natom_stats[nat], triv_stats[t]):
            add_stat(st, c, cls, inrt)
        for k, e in enumerate(ORDER):
            if U[r][k] > 0:
                add_stat(elem_stats[e], c, cls, inrt)
            else:
                add_stat(noelem_stats[e], c, cls, inrt)
        tc = "".join(e for k, e in ((0, "O"), (3, "P"), (6, "K")) if U[r][k] > 0) or "无"
        add_stat(triv_combo[tc], c, cls, inrt)
        is_odd = int(total_val_vec[r]) % 2 == 1
        tgt = triv_odd[t] if is_odd else triv_even[t]
        tgt[0] += c
        if cls == 0:
            tgt[1] += c
        elif cls == 3:
            tgt[2] += c

    def fmt_stats(d, sort_key=None):
        out = []
        for k, st in d.items():
            if st[0] == 0:
                continue
            out.append({"key": k, "pairs": st[0], "fail": st[1], "inert": st[2],
                        "single": st[3], "multi": st[4], "unresolved": st[5],
                        "fail_rate": round(st[1] / st[0], 5),
                        "inert_rate": round(st[2] / st[0], 5),
                        "single_rate": round(st[3] / st[0], 5),
                        "multi_rate": round(st[4] / st[0], 5)})
        if sort_key:
            out.sort(key=sort_key)
        return out

    sets_by_size = {}
    for size in range(1, 10):
        items = {k: v for k, v in set_stats.items() if len(k) == size}
        sets_by_size[str(size)] = fmt_stats(items, sort_key=lambda x: -x["fail_rate"])
    cats_stats = fmt_stats(cat_stats, sort_key=lambda x: x["key"])
    elem_present_stats = fmt_stats(elem_stats, sort_key=lambda x: -x["fail_rate"])
    elem_absent_stats = fmt_stats(noelem_stats, sort_key=lambda x: -x["fail_rate"])
    triv_combo_stats = fmt_stats(triv_combo, sort_key=lambda x: -x["fail_rate"])
    natoms_stats = fmt_stats(natom_stats, sort_key=lambda x: int(x["key"]))
    triv_table = []
    for t in sorted(triv_stats):
        st = triv_stats[t]
        ev = triv_even.get(t, [0, 0, 0])
        od = triv_odd.get(t, [0, 0, 0])
        triv_table.append({"trivalent": t, "pairs": st[0], "fail": st[1],
                           "inert": st[2], "single": st[3], "multi": st[4],
                           "fail_rate": round(st[1] / st[0], 5) if st[0] else 0,
                           "even_pairs": ev[0], "even_fail": ev[1],
                           "even_fail_rate": round(ev[1] / ev[0], 5) if ev[0] else 0,
                           "odd_pairs": od[0], "odd_fail": od[1]})

    # ---------------- 自对 A+A ----------------
    self_stats = Counter()
    for i in range(n):
        r = int(np.searchsorted(keys_sorted, int(keys_i[i] * 2)))
        cls = int(cls_a[r])
        if cls == 0:
            self_stats["fail"] += 1
        elif cls == 1:
            self_stats["single"] += 1
        elif cls == 2:
            if inert_a[r] == 1 and p0a[r] == i and p1a[r] == i:
                self_stats["inert"] += 1
            else:
                self_stats["multi"] += 1
        else:
            self_stats["unresolved"] += 1

    # ---------------- 排行 ----------------
    def rank(col, k=15):
        out = []
        for i in np.argsort(-cnts[:, col])[:k]:
            i = int(i)
            out.append({"formula": formulas[i], "natoms": int(natoms[i]),
                        "elements": "".join(element_set(V[i])),
                        "inert": int(cnts[i, 1]), "fail": int(cnts[i, 0]),
                        "single": int(cnts[i, 2]), "multi": int(cnts[i, 3]),
                        "unresolved": int(cnts[i, 4]),
                        "pairs": int(cnts[i].sum())})
        return out

    rankings = {"most_inert": rank(1), "most_fail": rank(0),
                "most_single": rank(2), "most_multi": rank(3)}

    # ---------------- 失败原因细化 ----------------
    fail_reason = {"simfail_pairs": f_sim, "embedfail_pairs": f_emb,
                   "unresolved_pairs": unresolved_pairs}
    fn = BASE + r"\t12b_failreason.json"
    if __import__("os").path.exists(fn):
        fr = json.load(open(fn, encoding="utf-8"))
        detail = fr["detail"]
        kind_w = Counter()
        stuck_left_elem = Counter()
        stuck_left_sig = Counter()
        stuck_triv = Counter()
        stuck_struct = Counter()          # 结构签名 -> 向量数
        stuck_struct_pairs = Counter()    # 结构签名 -> 对数权重
        stuck_examples = []
        for rs, d in detail.items():
            r = int(rs)
            c = int(counts[r])
            k = d["kind"]
            kind_w[k] += c
            if k == "stuck":
                left = d["left"]
                stuck_left_sig["+".join(f"{e}{v}" for e, v in sorted(left.items()))] += c
                stuck_left_elem["+".join(sorted(left))] += c
                tv = sum(v for e, v in left.items() if e in ("O", "P", "K"))
                stuck_triv[tv] += c
                sig = (d.get("n_left"), d.get("max_rem"), len(left))
                stuck_struct[sig] += 1
                stuck_struct_pairs[sig] += c
                if len(stuck_examples) < 10:
                    pairs = find_pairs(keys_sorted[r], 1)
                    if pairs:
                        i, j = pairs[0]
                        stuck_examples.append({
                            "A": formulas[i], "B": formulas[j],
                            "element_set": "".join(element_set(U[r])),
                            "leftover": left,
                            "pairs_in_class": c})
        fail_reason.update({
            "odd_valence_pairs": kind_w.get("odd", 0),
            "stuck_pairs": kind_w.get("stuck", 0),
            "embed_fail_pairs": kind_w.get("embed", 0),
            "n_fail_vectors": len(detail),
            "stuck_by_leftover_elements": [
                {"leftover_elements": k, "pairs": v}
                for k, v in stuck_left_elem.most_common(20)],
            "stuck_by_leftover_signature": [
                {"leftover": k, "pairs": v}
                for k, v in stuck_left_sig.most_common(20)],
            "stuck_by_leftover_trivalent": [
                {"leftover_trivalent_rem": k, "pairs": v}
                for k, v in sorted(stuck_triv.items())],
            "stuck_structure": [
                {"total_left_bonds": k[0], "max_atom_left": k[1], "n_left_elements": k[2],
                 "n_vectors": stuck_struct[k], "pairs": stuck_struct_pairs[k]}
                for k, _ in stuck_struct_pairs.most_common(10)],
            "stuck_uniform_rem2": all(
                (k[0] == 2 and k[1] == 2 and k[2] == 1) for k in stuck_struct),
            "stuck_examples": stuck_examples,
        })

    # ---------------- pot_v3 差异 ----------------
    rule9 = None
    fn_v3 = BASE + r"\t12b_vec_v3.json"
    if __import__("os").path.exists(fn_v3):
        d3 = json.load(open(fn_v3, encoding="utf-8"))
        res3 = d3["res"]
        diff_vec = np.zeros(nv, dtype=bool)
        unknown_vec = np.zeros(nv, dtype=bool)
        n_status_diff = 0
        n_same_ok_diff = 0
        for r in range(nv):
            a, b = res[r], res3[r]
            if a[0] == 3 or b[0] == 3:
                unknown_vec[r] = True
                continue
            if (a[0] == 0) != (b[0] == 0):
                n_status_diff += 1
                diff_vec[r] = True
            elif a[0] != b[0]:
                diff_vec[r] = True
            elif a[0] == 0 and a[1] != b[1]:
                n_same_ok_diff += 1
                diff_vec[r] = True
        n_diff_vec = int(diff_vec.sum())
        n_diff_pairs = int(counts[diff_vec].sum())
        n_unknown_vec = int(unknown_vec.sum())
        n_unknown_pairs = int(counts[unknown_vec].sum())
        diff_examples = []
        for r in sample_vec(np.where(diff_vec)[0], 8):
            pairs = find_pairs(keys_sorted[r], 1)
            diff_examples.append({
                "vector": [int(x) for x in U[r]],
                "pair": [[formulas[i], formulas[j]] for i, j in pairs],
                "pot_all": [int(res[r][0]), res[r][1]],
                "pot_v3": [int(res3[r][0]), res3[r][1]]})
        cls3 = np.zeros(nv, dtype=np.int8)
        for r in range(nv):
            st, pr = res3[r]
            if st == 0:
                cls3[r] = 1 if len(pr) == 1 else 2
            elif st == 3:
                cls3[r] = 3
        inert3 = np.zeros(nv, dtype=np.int8)
        # v3 惰性类：产物等于投料对（这里只按类近似：与 pot_all 惰性标记对比用不到，精确统计需要 p0/p1）
        v3_fail = int(counts[cls3 == 0].sum())
        v3_single = int(counts[cls3 == 1].sum())
        v3_multi_base = int(counts[cls3 == 2].sum())
        v3_unres = int(counts[cls3 == 3].sum())
        rule9 = {"n_diff_vec": n_diff_vec, "n_diff_pairs": n_diff_pairs,
                 "rate_vec": round(n_diff_vec / nv, 6),
                 "rate_pairs": round(n_diff_pairs / total_pairs, 6),
                 "n_unknown_vec": n_unknown_vec,
                 "n_unknown_pairs": n_unknown_pairs,
                 "n_status_diff_vec": n_status_diff,
                 "n_same_ok_diff_vec": n_same_ok_diff,
                 "examples": diff_examples,
                 "pot_v3_counts": {"fail": v3_fail, "single": v3_single,
                                   "multi_base": v3_multi_base,
                                   "unresolved": v3_unres,
                                   "total": total_pairs}}

    # ---------------- 多产物模式统计（扣除惰性对：每个惰性类恰有 1 个惰性对） ----------------
    multi_patterns = {}
    for pat in sorted(pat_cands):
        cands = np.array(pat_cands[pat], dtype=np.int64)
        base = int(counts[cands].sum())
        inerts = int(inert_a[cands].sum())
        multi_patterns[pat] = {
            "classes": len(pat_cands[pat]),
            "pairs": base - inerts,
            "inert_pairs_in_pattern": inerts,
            "examples": examples["multi"].get(pat, []),
        }

    # ---------------- 汇总 ----------------
    summary = {
        "generated_by": "t12b_analyze.py",
        "rule": "主口径 pot_all（规则1~8+tied[0]，与T11/T11B一致）；pot_v3（规则1~9）全量差异见 rule9",
        "n_S": n,
        "natoms_max": 8,
        "natoms_hist": {str(k): v for k, v in sorted(Counter(int(x) for x in natoms).items())},
        "n_pairs": total_pairs,
        "n_uniq_vec": nv,
        "vec_compression": round(total_pairs / nv, 3),
        "classification": {
            "fail": fail_pairs, "inert": inert_pairs, "single": single_pairs,
            "multi": multi_pairs, "unresolved": unresolved_pairs,
            "total": total_pairs, "resolved": resolved,
            "fail_rate": round(fail_pairs / total_pairs, 6),
            "inert_rate": round(inert_pairs / total_pairs, 6),
            "single_rate": round(single_pairs / total_pairs, 6),
            "multi_rate": round(multi_pairs / total_pairs, 6),
            "unresolved_rate": round(unresolved_pairs / total_pairs, 6),
            "success": total_pairs - fail_pairs - unresolved_pairs,
            "success_rate": round((total_pairs - fail_pairs - unresolved_pairs) / total_pairs, 6),
        },
        "examples": examples,
        "fail_analysis": {
            "reason": fail_reason,
            "by_trivalent": triv_table,
            "by_cats": cats_stats,
            "by_natoms": natoms_stats,
        },
        "single_product": {
            "pairs": single_pairs,
            "product_vec_equals_sum_bad": bad_sum,
            "bad_examples": bad_examples,
            "n_distinct_products": len(prod_counter),
            "top_products": [{"product": f, "pairs": c,
                              "natoms": int(sum(vec_of_formula(f)))}
                             for f, c in prod_counter.most_common(40)],
            "product_size_hist": {str(k): v for k, v in sorted(prod_natoms_counter.items())},
            "not_in_catalog_products": dict(all_not_in_catalog),
        },
        "product_size": {
            "size_hist": {str(k): v for k, v in sorted(size_hist.items())},
            "n_products_total": n_prod_total,
            "nprod_hist": {str(k): v for k, v in sorted(nprod_hist.items())},
            "conservation_bad_pairs": conservation_bad,
        },
        "equivalence": {
            "n_classes": nv,
            "n_multi_classes": n_multi_classes,
            "pairs_in_multi_classes": pairs_in_multi_classes,
            "max_class_size": max_class,
            "class_size_hist": {str(k): v for k, v in sorted(class_size_hist.items())},
            "top_classes": top_classes,
            "sample_checks": eq_check,
            "n_sample_classes": len(eq_check),
            "n_pairs_recomputed": n_checked_pairs,
            "n_recompute_mismatch": n_bad,
            "n_multi_outcome": eq_distinct_bad,
        },
        "multi_patterns": multi_patterns,
        "sets": {"by_size": sets_by_size},
        "elem_present": elem_present_stats,
        "elem_absent": elem_absent_stats,
        "triv_combo": triv_combo_stats,
        "cats": cats_stats,
        "self_pairs": dict(self_stats),
        "rankings": rankings,
        "rule9": rule9,
        "runtime_sec": round(time.time() - t0, 1),
    }
    json.dump(summary, open(BASE + r"\t12b_summary.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    c = summary["classification"]
    print(f"\nsaved t12b_summary.json  ({time.time()-t0:.1f}s)")
    print(f"|S|={n} 对数={total_pairs} 唯一向量={nv} 压缩={total_pairs/nv:.2f}x")
    print(f"失败 {c['fail']} ({c['fail_rate']*100:.2f}%) | 惰性 {c['inert']} ({c['inert_rate']*100:.2f}%) | "
          f"单产物 {c['single']} ({c['single_rate']*100:.2f}%) | 多产物 {c['multi']} ({c['multi_rate']*100:.2f}%) | "
          f"未判定 {c['unresolved']}")
    print(f"失败原因: 剩键 {f_sim} / 摆放失败 {f_emb}")
    print(f"等价类 {nv}, 含>=2对 {n_multi_classes}, 最大类 {max_class}, 抽检 mismatch={n_bad}")
    if rule9:
        print(f"pot_v3 差异: 向量 {rule9['n_diff_vec']} / 对 {rule9['n_diff_pairs']} "
              f"({rule9['rate_pairs']*100:.3f}%)")


if __name__ == "__main__":
    main()
