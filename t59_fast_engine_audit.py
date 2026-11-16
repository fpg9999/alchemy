# -*- coding: utf-8 -*-
"""t59_fast_engine_audit.py —— fast_pot.py / natural_engine fast 路径独立审计

只读被审文件（fast_pot.py / natural_engine.py），不修改。
运行（alchemy 目录下）：
    python t59_fast_engine_audit.py
产出：
    t59_fast_engine_audit.json

覆盖：
  1. fast_pot.simulate vs pot_v4.simulate（穷举总原子 0~8 全组合 + 随机 8~24 数千条）：
     产物公式多重集 / mol_label 结构多重集 / None 状态 / return_level6 块完全一致；
  2. 固定键：t28 断键 base_edges，fast_pot.simulate(base) vs natural_engine.greedy_bond
     （≥450 对真实分子对 + 200 组合成 base_edges）；level6（含 post-loop fallback）与
     "带 level6 的 slow 参考实现"逐块一致；set_fast(False/True) 的
     complete_products / incomplete_products / resolve / is_stable 一致；
  3. 速度：n=12..60 的 F 单次耗时（fast vs pot_v4，含自然引擎端到端）；
  4. 缺陷排查：并查集增量统计（通过大规模等价 + 结构化用例间接验证）、base_edges 下
     level6/规则10、环标记、并列取序、dt 类型、set_fast 缓存、文档 API 一致性。
"""
import sys
import os
import json
import time
import random
import inspect

BASE = r"G:\AI work\deepseek\work1\alchemy"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import pot_all as P
import pot_v4
import fast_pot
import natural_engine as NE

OUT = os.path.join(BASE, "t59_fast_engine_audit.json")
RNG = random.Random(20261117)
T0 = time.perf_counter()
R = {"meta": {"script": "t59_fast_engine_audit.py",
              "generated": time.strftime("%Y-%m-%d %H:%M:%S")}}


# ---------------------------------------------------------------- 工具
def raw_key(raw):
    """产物结构多重集：[(formula, mol_label)] 排序；None 保持 None。"""
    if raw is None:
        return None
    return tuple(sorted((P.formula_of(m["atoms"]), P.mol_label(m["atoms"], m["edges"]))
                        for m in raw))


def raw_forms(raw):
    if raw is None:
        return None
    return tuple(sorted(P.formula_of(m["atoms"]) for m in raw))


def l6_key(level6):
    """level6 块：[(原子索引集合, mol_label)]，保持顺序；块内 mem 已排序。"""
    if level6 is None:
        return None
    return tuple((tuple(mem), P.mol_label(ats, es)) for ats, es, mem in level6)


def ne_key(mols):
    if mols is None:
        return None
    return tuple(sorted((m["formula"], m["label"]) for m in mols))


def mol_brief(mols):
    if mols is None:
        return None
    return [{"f": m["formula"], "lab": m["label"], "c": m["c"]} for m in mols]


def res_brief(r):
    return {"type": r["type"],
            "products": None if r["products"] is None else [p["formula"] for p in r["products"]],
            "product_labels": None if r["products"] is None else [p["label"] for p in r["products"]],
            "stages": [(s["op"], s["from"], tuple(s["to"])) for s in r["stages"]],
            "class": r["class"], "csum": r["csum"], "isum": r["isum"]}


def gen_compositions(total, k, prefix=()):
    if k == 1:
        yield prefix + (total,)
        return
    for c in range(total + 1):
        yield from gen_compositions(total - c, k - 1, prefix + (c,))


def rand_counts(total):
    bars = sorted(RNG.sample(range(total + 8), 8))
    v = []
    prev = -1
    for b in bars + [total + 8]:
        v.append(b - prev - 1)
        prev = b
    return tuple(v)


def valence_sum(vec):
    return sum(P.VAL[e] * c for e, c in zip(P.ORDER, vec))


def rand_vec(total, allow_odd=False):
    """随机计数向量；默认要求价数和为偶数（F 有意义），少数允许奇数（测 None）。"""
    for _ in range(200):
        v = rand_counts(total)
        if allow_odd or valence_sum(v) % 2 == 0:
            return v
    return v


def rand_atoms(n, seed_rng=None):
    rng = seed_rng or RNG
    return [rng.choice(P.ORDER) for _ in range(n)]


# ---------------------------------------------------------------- slow 参考（带 level6）
def _make_slow_ref():
    """把 natural_engine.greedy_bond 源码复制一份，末端额外返回 (mols, level6, bond)。

    这样"固定键下的 level6/规则 10"答案与 slow 实现逐字一致，可独立对比 fast_pot。
    """
    src = inspect.getsource(NE.greedy_bond)
    assert src.count("    return mols\n") == 1, "源码结构变化，需更新审计脚本"
    src2 = src.replace("    return mols\n", "    return mols, level6, bond\n")
    ns = dict(NE.__dict__)
    exec(src2, ns)
    return ns["greedy_bond"]


_REF_SLOW = _make_slow_ref()


def ref_bond(atoms, base_edges):
    """slow 参考：返回 (mols, level6, bond)；失败返回 (None, None, None)。"""
    r = _REF_SLOW(atoms, base_edges)
    if isinstance(r, tuple):
        return r
    return r, None, None


def components_from_bond(n, bond):
    comp = [-1] * n
    groups = []
    for s in range(n):
        if comp[s] != -1:
            continue
        cid = len(groups)
        comp[s] = cid
        st = [s]
        mem = [s]
        while st:
            u = st.pop()
            for v in range(n):
                if bond[u][v] > 0 and comp[v] == -1:
                    comp[v] = cid
                    st.append(v)
                    mem.append(v)
        groups.append(mem)
    return groups


def expected_post_loop_level6(atoms, bond, n):
    """与 pot_v4 相同的 post-loop fallback：结束前未捕获 level6 时，用最终组件重算块。"""
    out = []
    for g in components_from_bond(n, bond):
        if not any(atoms[v] in fast_pot.TRI for v in g):
            continue
        mem = sorted(g)
        local = {v: k for k, v in enumerate(mem)}
        ats = [atoms[v] for v in mem]
        es = []
        for a in range(len(mem)):
            va = mem[a]
            for b in range(a + 1, len(mem)):
                m = bond[va][mem[b]]
                if m:
                    es.append((local[va], local[mem[b]], m))
        out.append((ats, es, tuple(mem)))
    return out


# ================================================================ 任务 1
def test1_complete():
    t0 = time.perf_counter()
    mismatch = []
    l6_mismatch = []
    checked = 0
    none_both = 0
    section = {}

    def check(vec, tag):
        nonlocal checked, none_both
        checked += 1
        atoms = P.vec_to_atoms(vec, P.ORDER)
        fraw, fl6 = fast_pot.simulate(atoms, return_level6=True)
        sraw, sl6 = pot_v4.simulate(atoms, return_level6=True)
        fk, sk = raw_key(fraw), raw_key(sraw)
        if (fraw is None) != (sraw is None):
            mismatch.append({"tag": tag, "vec": vec, "fast": None if fraw is None else "ok",
                             "slow": None if sraw is None else "ok"})
            return
        if fraw is None:
            none_both += 1
        elif raw_forms(fraw) != raw_forms(sraw) or fk != sk:
            mismatch.append({"tag": tag, "vec": vec,
                             "fast_forms": raw_forms(fraw), "slow_forms": raw_forms(sraw),
                             "fast": fk, "slow": sk})
        if l6_key(fl6) != l6_key(sl6):
            l6_mismatch.append({"tag": tag, "vec": vec,
                                "fast_l6": l6_key(fl6), "slow_l6": l6_key(sl6)})

    # 穷举：总原子 0..7（全部）+ 总原子 8（全部）
    for s in range(0, 8):
        for v in gen_compositions(s, 9, ()):
            check(v, "exhaustive<=7")
    exhaustive_le7 = checked
    for v in gen_compositions(8, 9, ()):
        check(v, "exhaustive=8")
    exhaustive_eq8 = checked - exhaustive_le7

    # 随机：总原子 8..24，共 3000 条（85% 偶数价和，15% 任意）
    rand_n = 0
    for _ in range(3000):
        total = RNG.randint(8, 24)
        allow_odd = RNG.random() < 0.15
        v = rand_vec(total, allow_odd=allow_odd)
        check(v, "random8-24")
        rand_n += 1

    # 边界
    for vec in [(0,) * 9, (1,) + (0,) * 8, (0, 1) + (0,) * 7,
                (0,) * 8 + (1,), (2,) + (0,) * 8]:
        check(vec, "edge")

    R["test1_complete"] = {
        "pass": len(mismatch) == 0 and len(l6_mismatch) == 0,
        "checked": checked,
        "exhaustive_le7": exhaustive_le7,
        "exhaustive_eq8": exhaustive_eq8,
        "random8_24": rand_n,
        "none_both": none_both,
        "mismatch_count": len(mismatch),
        "mismatch_examples": mismatch[:10],
        "level6_mismatch_count": len(l6_mismatch),
        "level6_mismatch_examples": l6_mismatch[:5],
        "seconds": round(time.perf_counter() - t0, 2),
        "note": "逐向量比较 fast_pot.simulate 与 pot_v4.simulate（return_level6=True）："
                "None 状态、产物 (formula, mol_label) 多重集、level6 块 [(原子索引集合, mol_label)] 均要求完全一致。",
    }
    return section


# ================================================================ 任务 2
def make_system(mols):
    atom_list = []
    edges = []
    for m in mols:
        off = len(atom_list)
        atom_list += list(m["atoms"])
        for (a, b, mu) in m["edges"]:
            edges.append((a + off, b + off, mu))
    return atom_list, edges


def t28_break(mols):
    """复刻 natural_engine.incomplete_products 的 t28 断键步骤，返回 (atoms, kept) 或 None。"""
    atom_list, edges = make_system(mols)
    cls = NE.select_class(mols)
    if cls is None:
        return None
    d, mu, v = cls
    kept = []
    broken = 0
    for (a, b, mlt) in edges:
        if (mlt == mu and P.ptable_dist(atom_list[a], atom_list[b]) == d
                and min(P.VAL[atom_list[a]], P.VAL[atom_list[b]]) == v):
            mlt -= 1
            broken += 1
        if mlt > 0:
            kept.append((a, b, mlt))
    if broken == 0:
        return None
    return atom_list, kept


def test2_fixed_base():
    t0 = time.perf_counter()
    out = {}

    # 2a) 真实分子对：t28 断键 -> base_edges，比较 fast_pot.simulate(base) vs greedy_bond
    cat = json.load(open(os.path.join(BASE, "t4_catalog_all_validated.json"), encoding="utf-8"))
    small_recs = [r for r in cat if 2 <= len(r["atoms"]) <= 8]
    subs = [NE.mol_from_record(r) for r in
            json.load(open(os.path.join(BASE, "substances.json"), encoding="utf-8"))]
    pool = subs + [NE.mol_from_record(r) for r in small_recs]
    R["meta"]["catalog_size"] = len(cat)
    R["meta"]["small_catalog_size"] = len(small_recs)

    pairs = []
    tries = 0
    while len(pairs) < 450 and tries < 300000:
        tries += 1
        ma, mb = RNG.sample(pool, 2)
        if len(ma["atoms"]) + len(mb["atoms"]) > 14:
            continue
        pairs.append((ma, mb))

    pair_mismatch = []
    pair_l6_mismatch = []
    pair_stats = {"pairs": 0, "skipped_no_class": 0,
                  "with_base_edges": 0, "base_edge_count": 0, "rearranged": 0}
    pair_examples = []
    for ma, mb in pairs:
        mols = [ma, mb]
        br = t28_break(mols)
        if br is None:
            pair_stats["skipped_no_class"] += 1
            continue
        atom_list, kept = br
        pair_stats["pairs"] += 1
        pair_stats["with_base_edges"] += 1
        pair_stats["base_edge_count"] += len(kept)
        orig = tuple(sorted([ma["formula"], mb["formula"]]))
        ref = NE.greedy_bond(atom_list, kept)
        if raw_forms(ref) != orig:
            pair_stats["rearranged"] += 1
        fraw = fast_pot.simulate(atom_list, base_edges=kept)
        if raw_key(fraw) != raw_key(ref):
            pair_mismatch.append({"A": ma["formula"], "B": mb["formula"],
                                  "base_edges": kept,
                                  "fast": raw_forms(fraw), "slow": raw_forms(ref)})
        # level6 对比（fast vs 带 level6 的 slow 参考）
        f2, fl6 = fast_pot.simulate(atom_list, base_edges=kept, return_level6=True)
        rm, rl6, rbond = ref_bond(atom_list, kept)
        if rl6 is None and rm is not None:
            exp = expected_post_loop_level6(atom_list, rbond, len(atom_list))
            if l6_key(fl6) != l6_key(exp):
                pair_l6_mismatch.append({"A": ma["formula"], "B": mb["formula"],
                                         "kind": "post_loop", "fast": l6_key(fl6),
                                         "expect": l6_key(exp)})
        elif rl6 is not None and l6_key(fl6) != l6_key(rl6):
            pair_l6_mismatch.append({"A": ma["formula"], "B": mb["formula"],
                                     "kind": "in_loop", "fast": l6_key(fl6),
                                     "slow": l6_key(rl6)})
        if len(pair_examples) < 5 and raw_forms(ref) != orig:
            pair_examples.append({"A": ma["formula"], "B": mb["formula"],
                                  "base_edges": len(kept),
                                  "slow_products": raw_forms(ref)})

    out["2a_real_pairs"] = {
        "pass": len(pair_mismatch) == 0 and len(pair_l6_mismatch) == 0,
        "stats": pair_stats,
        "product_mismatch_count": len(pair_mismatch),
        "product_mismatch_examples": pair_mismatch[:5],
        "level6_mismatch_count": len(pair_l6_mismatch),
        "level6_mismatch_examples": pair_l6_mismatch[:5],
        "rearranged_examples": pair_examples,
        "note": "base_edges = t28 选中键类断键后保留的边；slow=natural_engine.greedy_bond。"
                "level6 的 slow 参考 = greedy_bond 源码副本（末端返回 level6+bond），"
                "post-loop fallback 用最终 bond 矩阵独立重算。",
    }

    # 2b) 合成 base_edges（随机固定键，强测固定键 + level6 + 规则 10）
    synth_mismatch = []
    synth_l6_mismatch = []
    synth_stats = {"cases": 0, "with_l6_in_loop": 0, "post_loop_l6": 0}
    for _ in range(200):
        n = RNG.randint(4, 14)
        atoms = [RNG.choice(P.ORDER) for _ in range(n)]
        remm = [P.VAL[e] for e in atoms]
        order = [(i, j) for i in range(n) for j in range(i + 1, n)]
        RNG.shuffle(order)
        base = []
        for (i, j) in order:
            if RNG.random() < 0.45:
                mm = min(3, remm[i], remm[j])
                if mm >= 1:
                    m = RNG.randint(1, mm)
                    base.append((i, j, m))
                    remm[i] -= m
                    remm[j] -= m
        synth_stats["cases"] += 1
        ref_m, ref_l6, ref_bmat = ref_bond(atoms, base)
        fraw, fl6 = fast_pot.simulate(atoms, base_edges=base, return_level6=True)
        if raw_key(fraw) != raw_key(ref_m):
            synth_mismatch.append({"atoms": atoms, "base_edges": base,
                                   "fast": raw_forms(fraw), "slow": raw_forms(ref_m)})
        if ref_l6 is None and ref_m is not None:
            synth_stats["post_loop_l6"] += 1
            exp = expected_post_loop_level6(atoms, ref_bmat, n)
            if l6_key(fl6) != l6_key(exp):
                synth_l6_mismatch.append({"atoms": atoms, "base_edges": base,
                                          "kind": "post_loop",
                                          "fast": l6_key(fl6), "expect": l6_key(exp)})
        elif ref_l6 is not None:
            synth_stats["with_l6_in_loop"] += 1
            if l6_key(fl6) != l6_key(ref_l6):
                synth_l6_mismatch.append({"atoms": atoms, "base_edges": base,
                                          "kind": "in_loop",
                                          "fast": l6_key(fl6), "slow": l6_key(ref_l6)})
    out["2b_synthetic_base"] = {
        "pass": len(synth_mismatch) == 0 and len(synth_l6_mismatch) == 0,
        "stats": synth_stats,
        "product_mismatch_count": len(synth_mismatch),
        "product_mismatch_examples": synth_mismatch[:3],
        "level6_mismatch_count": len(synth_l6_mismatch),
        "level6_mismatch_examples": synth_l6_mismatch[:3],
    }

    # 2c) natural_engine.set_fast(False/True) 端到端一致
    #    注意：set_fast 不自动清缓存；审计时每次切换后 clear_caches()。
    fast_mismatch = []
    # complete_products
    vecs = []
    for s in (2, 3, 4, 5):
        for v in gen_compositions(s, 9, ()):
            vecs.append(v)
    vecs = vecs[::2][:200]
    for _ in range(150):
        vecs.append(rand_vec(RNG.randint(8, 20)))
    comp_cmp = 0
    for v in vecs:
        comp_cmp += 1
        NE.clear_caches()
        NE.set_fast(False)
        slow = NE.complete_products(v)
        NE.clear_caches()
        NE.set_fast(True)
        fast = NE.complete_products(v)
        if ne_key(fast) != ne_key(slow):
            fast_mismatch.append({"op": "complete_products", "vec": v,
                                  "fast": mol_brief(fast), "slow": mol_brief(slow)})
    # incomplete_products
    inc_cmp = 0
    for ma, mb in pairs[:200]:
        mols = [ma, mb]
        NE.clear_caches()
        NE.set_fast(False)
        slow = NE.incomplete_products(mols)
        NE.clear_caches()
        NE.set_fast(True)
        fast = NE.incomplete_products(mols)
        inc_cmp += 1
        if ne_key(fast) != ne_key(slow):
            fast_mismatch.append({"op": "incomplete_products",
                                  "A": ma["formula"], "B": mb["formula"],
                                  "fast": mol_brief(fast), "slow": mol_brief(slow)})
    # resolve
    res_cmp = 0
    for ma, mb in pairs[200:240]:
        mols = [ma, mb]
        csum = ma["c"] + mb["c"]
        for T in (0, 1, 2, csum // 2, max(0, csum - 1), csum, csum + 3):
            NE.clear_caches()
            NE.set_fast(False)
            slow = NE.resolve(mols, T)
            NE.clear_caches()
            NE.set_fast(True)
            fast = NE.resolve(mols, T)
            res_cmp += 1
            if res_brief(fast) != res_brief(slow):
                fast_mismatch.append({"op": "resolve", "A": ma["formula"],
                                      "B": mb["formula"], "T": T,
                                      "fast": res_brief(fast), "slow": res_brief(slow)})
    # is_stable
    stable_cmp = 0
    for m in [NE.mol_from_record(r) for r in RNG.sample(small_recs, 60)]:
        stable_cmp += 1
        NE.clear_caches()
        NE.set_fast(False)
        slow = NE.is_stable(m)
        NE.clear_caches()
        NE.set_fast(True)
        fast = NE.is_stable(m)
        if fast != slow:
            fast_mismatch.append({"op": "is_stable", "formula": m["formula"],
                                  "fast": fast, "slow": slow})
    NE.set_fast(False)
    NE.clear_caches()
    out["2c_natural_fast_path"] = {
        "pass": len(fast_mismatch) == 0,
        "complete_products_compared": comp_cmp,
        "incomplete_products_compared": inc_cmp,
        "resolve_compared": res_cmp,
        "is_stable_compared": stable_cmp,
        "mismatch_count": len(fast_mismatch),
        "mismatch_examples": fast_mismatch[:5],
        "note": "每次 set_fast 切换后都 clear_caches（set_fast 本身不清缓存）。",
    }

    # 2d) 固定键边界：过价 / 重复边 / 零边
    edge_cases = []
    atoms = ["O", "O", "C", "C"]
    for base in ([(0, 1, 3), (2, 3, 1)], [(0, 1, 3), (2, 3, 0)],
                 [(0, 1, 2), (0, 1, 1), (2, 3, 1)], [(0, 1, 3), (1, 2, 3)],
                 [(1, 0, 3), (3, 2, 1)]):
        ref_m = NE.greedy_bond(atoms, base)
        fraw = fast_pot.simulate(atoms, base_edges=base)
        edge_cases.append({"atoms": atoms, "base_edges": base,
                           "fast": raw_forms(fraw), "slow": raw_forms(ref_m),
                           "ok": raw_key(fraw) == raw_key(ref_m)})
    out["2d_base_edge_cases"] = {"pass": all(c["ok"] for c in edge_cases),
                                 "cases": edge_cases}

    out["pass"] = (out["2a_real_pairs"]["pass"] and out["2b_synthetic_base"]["pass"]
                   and out["2c_natural_fast_path"]["pass"] and out["2d_base_edge_cases"]["pass"])
    out["seconds"] = round(time.perf_counter() - t0, 2)
    R["test2_fixed_base"] = out


# ================================================================ 任务 3
def test3_speed():
    out = {}
    rows = []
    sizes = [(12, 5), (16, 5), (20, 5), (24, 5), (30, 4), (40, 3), (60, 2)]

    def timed(atoms, reps):
        ts = []
        for _ in range(reps):
            t = time.perf_counter()
            fast_pot.simulate(atoms)
            ts.append(time.perf_counter() - t)
        tf = sorted(ts)[len(ts) // 2]
        ts = []
        for _ in range(reps):
            t = time.perf_counter()
            pot_v4.simulate(atoms)
            ts.append(time.perf_counter() - t)
        tslow = sorted(ts)[len(ts) // 2]
        return tf, tslow

    for n, reps in sizes:
        vec = rand_vec(n)
        atoms = P.vec_to_atoms(vec, P.ORDER)
        # 先确认一次正确性（同时避免用错误样本测速度）
        ok = raw_key(fast_pot.simulate(atoms)) == raw_key(pot_v4.simulate(atoms))
        tf, tslow = timed(atoms, reps)
        rows.append({"n": n, "atoms": P.formula_of(atoms), "reps": reps,
                     "fast_ms": round(tf * 1000, 2), "slow_ms": round(tslow * 1000, 2),
                     "speedup": round(tslow / tf, 2) if tf > 0 else None,
                     "correct": ok})

    # 小 n：确认 fast 路径没有"小分子反而更慢"的退化（T59 中大量小 F 调用）
    small_rows = []
    for n in (2, 4, 6, 8, 10):
        vec = rand_vec(n)
        atoms = P.vec_to_atoms(vec, P.ORDER)
        tf, tslow = timed(atoms, 300)
        small_rows.append({"n": n, "fast_ms": round(tf * 1000, 3),
                           "slow_ms": round(tslow * 1000, 3),
                           "speedup": round(tslow / tf, 2) if tf > 0 else None,
                           "correct": raw_key(fast_pot.simulate(atoms)) == raw_key(pot_v4.simulate(atoms))})

    # 自然引擎端到端（含 make_mol label 成本）：n=20 / n=24
    e2e = []
    for n in (20, 24):
        vec = rand_vec(n)
        NE.clear_caches()
        NE.set_fast(False)
        t = time.perf_counter()
        NE.complete_products(vec)
        tslow = time.perf_counter() - t
        NE.clear_caches()
        NE.set_fast(True)
        t = time.perf_counter()
        NE.complete_products(vec)
        tfast = time.perf_counter() - t
        NE.set_fast(False)
        NE.clear_caches()
        e2e.append({"n": n, "slow_ms": round(tslow * 1000, 2),
                    "fast_ms": round(tfast * 1000, 2),
                    "speedup": round(tslow / tfast, 2) if tfast > 0 else None})
    le24 = [r for r in rows if r["n"] <= 24]
    out = {
        "pass": all(r["correct"] for r in rows) and all(r["correct"] for r in small_rows),
        "rows": rows,
        "small_n": small_rows,
        "typical_le24": {
            "fast_ms_range": [min(r["fast_ms"] for r in le24), max(r["fast_ms"] for r in le24)],
            "slow_ms_range": [min(r["slow_ms"] for r in le24), max(r["slow_ms"] for r in le24)],
            "speedup_range": [min(r["speedup"] for r in le24), max(r["speedup"] for r in le24)],
        },
        "natural_engine_end_to_end": e2e,
        "note": "F 单次耗时：raw simulate（不含 mol_label）；时间取 reps 次的中位数（perf_counter）。"
                "端到端额外统计 natural_engine.complete_products（含 make_mol/label 与缓存清空）。",
    }
    R["test3_speed"] = out


# ================================================================ 任务 4
def test4_defects():
    t0 = time.perf_counter()
    out = {}
    # 4a) 环标记：fast_pot._ring_flags vs pot_v4.ring_flags
    rng = random.Random(59)
    ring_bad = []
    for _ in range(300):
        n = rng.randint(1, 8)
        adj = [dict() for _ in range(n)]
        for u in range(n):
            for v in range(u + 1, n):
                if rng.random() < 0.42:
                    m = rng.randint(1, 3)
                    adj[u][v] = m
                    adj[v][u] = m
        if fast_pot._ring_flags(n, adj) != pot_v4.ring_flags(n, adj):
            ring_bad.append({"n": n})
    fixed = []
    def graph(edges, n):
        adj = [dict() for _ in range(n)]
        for u, v in edges:
            adj[u][v] = 1
            adj[v][u] = 1
        return adj
    for name, edges, n, expect in [
        ("chain", [(0, 1), (1, 2)], 3, [False, False, False]),
        ("triangle", [(0, 1), (1, 2), (2, 0)], 3, [True, True, True]),
        ("4-ring+tail", [(0, 1), (1, 2), (2, 3), (3, 0), (0, 4)], 5,
         [True, True, True, True, False]),
    ]:
        adj = graph(edges, n)
        fixed.append({"name": name,
                      "fast": fast_pot._ring_flags(n, adj),
                      "slow": pot_v4.ring_flags(n, adj),
                      "expect": expect,
                      "ok": fast_pot._ring_flags(n, adj) == expect})
    out["4a_ring_flags"] = {"pass": len(ring_bad) == 0 and all(f["ok"] for f in fixed),
                            "random_graphs": 300, "mismatch_count": len(ring_bad),
                            "fixed_cases": fixed}

    # 4b) dt 类型：ptable_dist 全为 int（无浮点 key 退化风险）
    vals = set()
    for a in P.ORDER:
        for b in P.ORDER:
            d = P.ptable_dist(a, b)
            vals.add(type(d).__name__)
    family = set(type(P.family_rank(a, b)).__name__ for a in P.ORDER for b in P.ORDER)
    out["4b_dt_types"] = {"pass": vals == {"int"} and family == {"int"},
                          "ptable_dist_types": sorted(vals),
                          "family_rank_types": sorted(family),
                          "note": "dt/fam 均为 int（ptable_dist = |价差| 或 价数和），"
                                  "不存在浮点比较/精度问题。"}

    # 4c) 结构化用例（压力测试并查集增量统计：都是大组件/环/链/混合）
    patterns = []
    for n in (6, 8, 10, 12, 16, 20, 24, 30):
        patterns.append(["O"] * n)
        patterns.append((["O", "X"] * (n // 2 + 1))[:n])
        patterns.append((["P", "K", "A", "F", "W", "L"] * (n // 6 + 1))[:n])
        patterns.append((["O"] * (n // 2) + ["X"] * (n - n // 2)))
    struct_bad = []
    for atoms in patterns:
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        if raw_key(fast_pot.simulate(atoms)) != raw_key(pot_v4.simulate(atoms)):
            struct_bad.append({"atoms": atoms})
    out["4c_structured"] = {"pass": len(struct_bad) == 0,
                            "checked": len(patterns),
                            "mismatch_count": len(struct_bad),
                            "mismatch_examples": struct_bad[:3]}

    # 4d) set_fast 缓存行为（观察项）：切换后不清缓存，旧缓存仍返回（结果正确但可能非 fast 计算）
    vec = (4, 0, 0, 4, 0, 0, 0, 0, 0)  # O4P4, 价数和 24 偶数
    NE.clear_caches()
    NE.set_fast(False)
    slow = NE.complete_products(vec)
    cache_len_after_slow = len(NE._F_CACHE)
    NE.set_fast(True)
    same = NE.complete_products(vec)
    out["4d_set_fast_cache"] = {
        "pass": ne_key(same) == ne_key(slow),
        "cache_not_cleared_by_set_fast": cache_len_after_slow > 0,
        "note": "set_fast 只切开关、不清缓存；切换后同一向量会命中旧缓存（结果仍正确，但不会走 fast 重算）。"
                "建议 T59 在 set_fast(True) 后调用 clear_caches()，确保 fast 路径生效且缓存口径一致。",
    }
    NE.set_fast(False)
    NE.clear_caches()

    # 4e) 文档/API 一致性：docstring 声明但未实现的接口
    api_missing = [name for name in ("simulate_with_base", "simulate_level6")
                   if not hasattr(fast_pot, name)]
    out["4e_api_doc"] = {
        "pass": True,
        "missing_documented_functions": api_missing,
        "note": "fast_pot 模块 docstring 列出 simulate_with_base / simulate_level6，"
                "但模块只实现 simulate(atom_list, base_edges=(), return_level6=False)。"
                "natural_engine 用的是 simulate(..., base_edges=...)，不影响 T59；"
                "若外部按 docstring 调用会 AttributeError，建议补函数或改文档。",
    }

    # 4f) 并列取序/深层 tie：随机大小样本（task1/2 已逐条覆盖），额外构造同元素大样本
    tie_bad = []
    for atoms in (["O"] * 12, ["X"] * 12, ["O"] * 8 + ["P"] * 8,
                  ["K"] * 6 + ["A"] * 6, ["O"] * 16 + ["X"] * 8):
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        if raw_key(fast_pot.simulate(atoms)) != raw_key(pot_v4.simulate(atoms)):
            tie_bad.append({"atoms": atoms})
    out["4f_symmetric_ties"] = {"pass": len(tie_bad) == 0,
                                "checked": 5, "mismatch_count": len(tie_bad),
                                "note": "高对称/大量并列的样本上 fast 与 pot_v4 结构多重集一致，"
                                        "说明分层筛选保持 pot_v4 的并列取序（task1 的 24k 穷举+3k 随机同样覆盖）。"}

    # 4g) 大 n 随机等价（25~60 原子，覆盖 T59 可能的大体系 F）
    large_bad = []
    large_checked = 0
    for _ in range(80):
        n = RNG.randint(25, 60)
        atoms = P.vec_to_atoms(rand_vec(n), P.ORDER)
        large_checked += 1
        if raw_key(fast_pot.simulate(atoms)) != raw_key(pot_v4.simulate(atoms)):
            large_bad.append({"atoms": atoms})
    out["4g_large_n"] = {"pass": len(large_bad) == 0,
                         "checked": large_checked,
                         "mismatch_count": len(large_bad),
                         "note": "随机 25~60 原子（价数和偶数）逐条比较 fast vs pot_v4 结构多重集。"}

    out["pass"] = (out["4a_ring_flags"]["pass"] and out["4b_dt_types"]["pass"]
                   and out["4c_structured"]["pass"] and out["4d_set_fast_cache"]["pass"]
                   and out["4e_api_doc"]["pass"] and out["4f_symmetric_ties"]["pass"]
                   and out["4g_large_n"]["pass"])
    out["seconds"] = round(time.perf_counter() - t0, 2)
    R["test4_defects"] = out


# ================================================================ main
def main():
    print("[1/4] complete equivalence ...", flush=True)
    test1_complete()
    t = R["test1_complete"]
    print("   pass", t["pass"], "checked", t["checked"],
          "mismatch", t["mismatch_count"], "l6", t["level6_mismatch_count"],
          "time", t["seconds"], flush=True)

    print("[2/4] fixed-key / incomplete / set_fast ...", flush=True)
    test2_fixed_base()
    t = R["test2_fixed_base"]
    print("   pass", t["pass"], "| 2a", t["2a_real_pairs"]["stats"],
          "| 2c mismatch", t["2c_natural_fast_path"]["mismatch_count"], flush=True)

    print("[3/4] speed benchmark ...", flush=True)
    test3_speed()
    print("   ", [(r["n"], r["fast_ms"], r["slow_ms"], r["speedup"]) for r in R["test3_speed"]["rows"]],
          flush=True)

    print("[4/4] defect checks ...", flush=True)
    test4_defects()
    print("   pass", R["test4_defects"]["pass"], flush=True)

    R["meta"]["seconds"] = round(time.perf_counter() - T0, 2)
    R["meta"]["all_pass"] = all(R[k]["pass"] for k in R if isinstance(R[k], dict) and "pass" in R[k])
    json.dump(R, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved", OUT, "elapsed", R["meta"]["seconds"], "s")
    print("ALL_PASS =", R["meta"]["all_pass"])
    for k in ("test1_complete", "test2_fixed_base", "test3_speed", "test4_defects"):
        print(" ", k, "PASS" if R[k]["pass"] else "FAIL")


if __name__ == "__main__":
    main()
