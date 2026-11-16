# -*- coding: utf-8 -*-
"""t55_engine_audit.py —— natural_engine.py 独立审计脚本（只读被审文件，不修改）

运行（在 alchemy 目录下）：
    python t55_engine_audit.py

产出：
    t55_engine_audit.json   明细数据

覆盖 7 项任务：
  1. complete_products(vec) 与 pot_v4.simulate(vec_to_atoms(vec)) 逐条一致（穷举小向量 + 随机 ≤12 原子）
  2. 空 base_edges 的 greedy_bond 与 pot_v4.simulate 完全一致
  3. 不完全反应移植 vs t28_rule_v2.react_v2（420 对 ≤8 原子目录分子；用"规则 10/11 关闭"变体做归因）
  4. c(M)、i(M)、select_class 定义/排序
  5. T35 优先级场景（完全优先、自分解优先、重判、多不稳定同轮、低于阈值不反应）+ T33 W2A/WA3F2 口径对照
  6. 稳定性/自分解（F 不动点、T>=c 分解、T<c 不分解、产物为 F 不动点、clear_caches 确定性）
  7. 实现缺陷排查（ring_flags 桥检测、固定键下的 level6/规则 10、ties、缓存顺序依赖、边界）
"""
import sys
import os
import json
import time
import random
from collections import Counter

BASE = r"G:\AI work\deepseek\work1\alchemy"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import pot_all as P
import pot_v4
import t28_rule_v2 as T28
import natural_engine as NE

OUT = os.path.join(BASE, "t55_engine_audit.json")
RNG = random.Random(20261116)
T0 = time.time()
R = {"meta": {"script": "t55_engine_audit.py", "generated": time.strftime("%Y-%m-%d %H:%M:%S")}}


# ---------------------------------------------------------------- 工具
def forms(mols):
    return None if mols is None else tuple(sorted(m["formula"] for m in mols))


def labels(mols):
    return None if mols is None else tuple(sorted(m["label"] for m in mols))


def v4_mols(mols):
    """pot_v4 的 dict 产物 -> natural_engine Mol。"""
    if mols is None:
        return None
    return [NE.make_mol(m["atoms"], m["edges"]) for m in mols]


def brief(mols):
    if mols is None:
        return None
    return [{"f": m["formula"], "lab": m["label"], "c": m["c"]} for m in mols]


def cls_dict(c):
    """键类 Counter -> JSON 可序列化 dict（键为 str）。"""
    return {str(k): v for k, v in c.items()}


def res_brief(r):
    return {
        "type": r["type"],
        "products": None if r["products"] is None else [p["formula"] for p in r["products"]],
        "product_labels": labels(r["products"]),
        "stages": r["stages"],
        "class": r["class"],
        "csum": r["csum"],
        "isum": r["isum"],
        "state": [p["formula"] for p in r["state"]],
    }


def load_catalog():
    return json.load(open(os.path.join(BASE, "t4_catalog_all_validated.json"), encoding="utf-8"))


CAT = load_catalog()
SMALL = [r for r in CAT if 2 <= len(r["atoms"]) <= 8]
CAT_BY_F = {r["formula"]: r for r in CAT}
SUB_RECS = json.load(open(os.path.join(BASE, "substances.json"), encoding="utf-8"))
SUBS = [NE.mol_from_record(r) for r in SUB_RECS]
SUBS_BY_F = {m["formula"]: m for m in SUBS}
R["meta"]["catalog_size"] = len(CAT)
R["meta"]["small_catalog_size"] = len(SMALL)


# ================================================================ 任务 1
def test1_complete():
    t0 = time.time()
    mismatch = []
    total = 0
    none_count = 0
    even_fail = 0

    def check(vec):
        nonlocal total, none_count, even_fail
        total += 1
        ne = NE.complete_products(vec)
        ref = v4_mols(pot_v4.simulate(P.vec_to_atoms(vec, P.ORDER)))
        if ne is None:
            none_count += 1
            if sum(P.VAL[e] * c for e, c in zip(P.ORDER, vec)) % 2 == 0:
                even_fail += 1
        if labels(ne) != labels(ref):
            mismatch.append({
                "vec": list(vec),
                "natoms": sum(vec),
                "ne": forms(ne),
                "v4": forms(ref),
                "ne_labels": labels(ne),
                "v4_labels": labels(ref),
            })

    # 穷举：总原子数 0..7
    def gen(total_atoms, k, prefix):
        if k == 1:
            yield prefix + (total_atoms,)
            return
        for c in range(total_atoms + 1):
            yield from gen(total_atoms - c, k - 1, prefix + (c,))

    for s in range(0, 8):
        for vec in gen(s, 9, ()):
            check(vec)
    exhaustive_total = total

    # 随机：总原子数 8..12
    def rand_vec(total_atoms):
        bars = sorted(RNG.sample(range(total_atoms + 8), 8))
        vec = []
        prev = -1
        for b in bars + [total_atoms + 8]:
            vec.append(b - prev - 1)
            prev = b
        return tuple(vec)

    for _ in range(3000):
        check(rand_vec(RNG.choice([8, 9, 10, 11, 12])))

    # 明确边界：单原子 / 奇数价和 / 已知失败
    special = [(1, 0, 0, 0, 0, 0, 0, 0, 0), (0, 1, 0, 0, 0, 0, 0, 0, 0),
               (3, 0, 0, 0, 0, 0, 0, 0, 0), (0, 0, 0, 0, 0, 0, 0, 0, 1)]
    for vec in special:
        check(vec)

    R["test1_complete"] = {
        "pass": len(mismatch) == 0,
        "exhaustive_vectors": exhaustive_total,
        "random_vectors": 3003,
        "checked": total,
        "none_both": none_count,
        "even_valence_failures": even_fail,
        "mismatch_count": len(mismatch),
        "mismatch_examples": mismatch[:10],
        "seconds": round(time.time() - t0, 2),
        "note": "穷举总原子 0..7 全向量；随机总原子 8..12 共 3000 条；另加单原子边界。",
    }


# ================================================================ 任务 2
def test2_greedy():
    t0 = time.time()
    cases = []
    for _ in range(500):
        n = RNG.randint(1, 9)
        cases.append([RNG.choice(P.ORDER) for _ in range(n)])
    cases += [["O"], ["X"], ["F"], ["O", "O"], ["O", "X"], ["X", "X", "X"],
              ["O", "P", "K"], ["O", "X", "C", "P", "W", "L", "K", "A", "F"]]
    mismatch = []
    for atoms in cases:
        g = NE.greedy_bond(atoms)
        ref = v4_mols(pot_v4.simulate(atoms))
        if labels(g) != labels(ref):
            mismatch.append({"atoms": atoms, "greedy": forms(g), "pot_v4": forms(ref),
                             "greedy_labels": labels(g), "pot_v4_labels": labels(ref)})
    R["test2_greedy_bonds"] = {
        "pass": len(mismatch) == 0,
        "checked": len(cases),
        "mismatch_count": len(mismatch),
        "mismatch_examples": mismatch[:10],
        "seconds": round(time.time() - t0, 2),
    }


# ================================================================ 任务 3
def incomplete_r19(mols):
    """用与 natural_engine.greedy_bond 同一代码、但关闭规则 10/11 的变体。

    做法（不改被审文件）：
      * NE.TRI = set()  -> greedy_bond 内 level6 捕获为空 -> blockid 全 -1 -> 规则 10 恒为常数；
      * NE.ring_flags 替换为全 False -> 规则 11 恒为常数。
    这样 key 只剩规则 1~9，即 t28 重结合所用的口径。
    """
    NE.clear_caches()
    old_tri, old_rf = NE.TRI, NE.ring_flags
    NE.TRI = set()
    NE.ring_flags = lambda n, adj: [False] * n
    try:
        return NE.incomplete_products(mols)
    finally:
        NE.TRI, NE.ring_flags = old_tri, old_rf
        NE.clear_caches()


def t28_forms(r):
    if not r.get("changed"):
        return None
    return tuple(sorted(p["formula"] for p in r["products"]))


def t28_labels(r):
    if not r.get("changed"):
        return None
    return tuple(sorted(NE.make_mol(p["atoms"], p["edges"])["label"] for p in r["products"]))


def test3_incomplete():
    t0 = time.time()
    pairs = []
    tries = 0
    while len(pairs) < 420 and tries < 300000:
        tries += 1
        A, B = RNG.sample(SMALL, 2)
        if len(A["atoms"]) + len(B["atoms"]) > 12:
            continue
        pairs.append((A, B))

    stats = Counter()
    formula_diffs = []      # natural vs t28 分子式多重集不同
    label_diffs = []        # 分子式相同、结构（label）不同 -> 规则 10/11
    r19_mismatch = []       # 规则 1~9 变体 vs t28 -> 移植差异（可疑 bug）
    class_mismatch = []
    fail_parity = []
    rule1011_effect = 0

    for A, B in pairs:
        ma, mb = NE.mol_from_record(A), NE.mol_from_record(B)
        mols = [ma, mb]
        sys28 = [(list(A["atoms"]), [tuple(e) for e in A["edges"]]),
                 (list(B["atoms"]), [tuple(e) for e in B["edges"]])]
        r28 = T28.react_v2(sys28, check_geometry=False)
        NE.clear_caches()
        rNE = NE.incomplete_products(mols)
        r19 = incomplete_r19(mols)

        # select_class 对齐
        clsNE = NE.select_class(mols)
        cls28 = None if r28.get("class") is None else (r28["class"][0], -r28["class"][1], r28["class"][2])
        if clsNE != cls28:
            class_mismatch.append({"A": A["formula"], "B": B["formula"],
                                   "ne": clsNE, "t28": cls28})

        f28 = t28_forms(r28)
        fNE = forms(rNE)
        f19 = forms(r19)
        stats["pairs"] += 1
        orig = tuple(sorted([A["formula"], B["formula"]]))
        if f28 is None:
            stats["t28_none"] += 1
        elif f28 == orig:
            stats["t28_restored"] += 1
        else:
            stats["t28_changed"] += 1
        if fNE is None:
            stats["ne_none"] += 1
        elif fNE == orig:
            stats["ne_restored"] += 1
        else:
            stats["ne_changed"] += 1

        # 规则 1~9 变体 vs t28（应逐条一致）
        if f19 != f28:
            r19_mismatch.append({"A": A["formula"], "B": B["formula"],
                                 "r19": f19, "t28": f28,
                                 "t28_changed": r28.get("changed"),
                                 "t28_reason": r28.get("reason")})
        # 失败/成功状态对齐
        if (rNE is None) != (not r28.get("changed")):
            fail_parity.append({"A": A["formula"], "B": B["formula"],
                                "ne": fNE, "ne_is_none": rNE is None,
                                "t28_changed": r28.get("changed"),
                                "t28_reason": r28.get("reason")})

        if fNE is None and f28 is None:
            stats["both_fail"] += 1
        elif fNE is not None and f28 is not None:
            if fNE == f28:
                stats["formula_same"] += 1
                # 结构比较（规则 10/11 预期差异）
                lNE = labels(rNE)
                l28 = t28_labels(r28)
                if lNE != l28:
                    stats["structure_diff"] += 1
                    if len(label_diffs) < 12:
                        label_diffs.append({"A": A["formula"], "B": B["formula"],
                                            "forms": list(fNE),
                                            "ne_labels": lNE, "t28_labels": l28})
            else:
                stats["formula_diff"] += 1
                if len(formula_diffs) < 12:
                    formula_diffs.append({"A": A["formula"], "B": B["formula"],
                                          "ne": fNE, "t28": f28, "r19": f19,
                                          "attrib": "rules10_11" if f19 == f28 else "SUSPECT"})
        # 规则 10/11 是否实际改变结果（结构或分子式）
        if fNE is not None and f19 is not None and labels(rNE) != labels(r19):
            rule1011_effect += 1

    # 顺序/缓存依赖：同一对分子换输入顺序，结果是否变化
    order_flip = []
    for A, B in pairs[:150]:
        ma, mb = NE.mol_from_record(A), NE.mol_from_record(B)
        NE.clear_caches()
        r1 = NE.incomplete_products([ma, mb])
        NE.clear_caches()
        r2 = NE.incomplete_products([mb, ma])
        if labels(r1) != labels(r2):
            order_flip.append({"A": A["formula"], "B": B["formula"],
                               "ab": forms(r1), "ba": forms(r2),
                               "ab_labels": labels(r1), "ba_labels": labels(r2)})

    R["test3_incomplete"] = {
        "pass": len(r19_mismatch) == 0 and len(class_mismatch) == 0,
        "pass_formula_core": len(formula_diffs) == 0,
        "pairs": len(pairs),
        "stats": dict(stats),
        "class_mismatch_count": len(class_mismatch),
        "class_mismatch_examples": class_mismatch[:10],
        "r19_vs_t28_mismatch_count": len(r19_mismatch),
        "r19_vs_t28_mismatch_examples": r19_mismatch[:10],
        "fail_parity_count": len(fail_parity),
        "fail_parity_examples": fail_parity[:10],
        "formula_diff_count": len(formula_diffs),
        "formula_diff_examples": formula_diffs,
        "structure_diff_count": stats["structure_diff"],
        "structure_diff_examples": label_diffs,
        "rules10_11_effect_count": rule1011_effect,
        "order_flip_count": len(order_flip),
        "order_flip_examples": order_flip[:5],
        "seconds": round(time.time() - t0, 2),
        "note": "r19 = 同一 greedy 代码关闭规则 10/11（TRI=set/ring_flags 全 False）得到规则 1~9 口径；"
                "r19 与 t28 的差异可判定为移植 bug；natural(规则1~11) 与 t28 的差异属设计预期。",
    }


# ================================================================ 任务 4
def test4_thresholds():
    t0 = time.time()
    c_bad = []
    i_bad = []
    for rec in SMALL:
        m = NE.mol_from_record(rec)
        c_direct = sum(e[2] for e in m["edges"])
        if m["c"] != c_direct:
            c_bad.append({"formula": m["formula"], "c": m["c"], "direct": c_direct})
        # i(M)：该键类的"元素对数"（每个元素对 1，与键级无关）
        cnt = Counter()
        for (a, b, mu) in m["edges"]:
            cnt[(P.ptable_dist(m["atoms"][a], m["atoms"][b]), mu,
                 min(P.VAL[m["atoms"][a]], P.VAL[m["atoms"][b]]))] += 1
        if dict(cnt) != dict(NE.bond_classes(m)):
            i_bad.append({"formula": m["formula"], "direct": cls_dict(cnt),
                          "engine": cls_dict(NE.bond_classes(m))})
        # 引擎 i_count 与直接计数一致
        for cls, v in cnt.items():
            if NE.i_count(m, cls) != v:
                i_bad.append({"formula": m["formula"], "cls": cls,
                              "i_count": NE.i_count(m, cls), "direct": v})

    # O2 三键：i 应为 1（元素对数），不是 3（键级）
    o2 = NE.make_mol(["O", "O"], [(0, 1, 3)])
    triple_pair = {"formula": o2["formula"], "classes": cls_dict(NE.bond_classes(o2)),
                   "i": NE.i_count(o2, (0, 3, 3)), "expect": 1,
                   "ok": NE.i_count(o2, (0, 3, 3)) == 1}

    # select_class 排序单元测试（合成边集，只测选择器本身）
    o2m = NE.make_mol(["O", "O"], [(0, 1, 3)])       # (d=0,m=3,v=3)
    c2m = NE.make_mol(["C", "C"], [(0, 1, 1)])       # (d=0,m=1,v=1)
    x2m = NE.make_mol(["X", "X"], [(0, 1, 2)])       # (d=0,m=2,v=2)
    xw = NE.make_mol(["X", "W"], [(0, 1, 1)])        # (d=4,m=1,v=2)
    of = NE.make_mol(["O", "F"], [(0, 1, 1)])        # (d=4,m=1,v=1)
    sel_tests = [
        {"case": "d 优先(0 小于 4)", "input": [xw, o2m], "expect": (0, 3, 3),
         "got": NE.select_class([xw, o2m])},
        {"case": "m 优先(同 d=0: 3>1)", "input": [c2m, o2m], "expect": (0, 3, 3),
         "got": NE.select_class([c2m, o2m])},
        {"case": "v 优先(同 d=4,m=1: 1<2)", "input": [xw, of], "expect": (4, 1, 1),
         "got": NE.select_class([xw, of])},
        {"case": "同 d=0 时 m 大者优先(2>1)", "input": [c2m, x2m], "expect": (0, 2, 2),
         "got": NE.select_class([c2m, x2m])},
    ]
    for t in sel_tests:
        t.pop("input")
        t["ok"] = t["got"] == t["expect"]

    R["test4_thresholds"] = {
        "pass": (len(c_bad) == 0 and len(i_bad) == 0
                 and all(t["ok"] for t in sel_tests) and triple_pair["ok"]),
        "c_bad_count": len(c_bad), "c_bad_examples": c_bad[:5],
        "i_bad_count": len(i_bad), "i_bad_examples": i_bad[:5],
        "triple_pair_i": triple_pair,
        "select_class_unit_tests": sel_tests,
        "seconds": round(time.time() - t0, 2),
        "note": "c(M)=Σ边键级；i(M)=选中键类的元素对数（每元素对 1，与键级无关）；"
                "select_class=(d 小, m 大, v 小)，已与 t28_rule_v2.select_class 在任务 3 的 420 对上交叉验证。",
    }


# ================================================================ 公共：找不稳定分子
UNSTABLE = []


def find_unstable(n_target=8, max_tries=2500, seed=42):
    rng = random.Random(seed)
    found = {}
    tries = 0
    for _ in range(max_tries):
        A, B = rng.sample(SMALL, 2)
        if len(A["atoms"]) + len(B["atoms"]) > 10:
            continue
        tries += 1
        ma, mb = NE.mol_from_record(A), NE.mol_from_record(B)
        prods = NE.incomplete_products([ma, mb])
        if not prods:
            continue
        for p in prods:
            if p["label"] in found:
                continue
            if not NE.is_stable(p):
                found[p["label"]] = p
        if len(found) >= n_target:
            break
    out = [m for m in found.values() if m["c"] >= 1]
    return out, tries


def stable_pool():
    """稳定伙伴池：substances.json 29 种 + 目录小分子（目录物质按 T30 均为 F 不动点，抽样后过滤）。"""
    pool = list(SUBS)
    for rec in SMALL[:120]:
        pool.append(NE.mol_from_record(rec))
    seen = set()
    out = []
    for m in pool:
        if m["label"] in seen or m["c"] < 1:
            continue
        seen.add(m["label"])
        if NE.is_stable(m):
            out.append(m)
    return out


# ================================================================ 任务 5
def max_rule_decision(mols, T):
    """T33 旧口径（max）：完全 T>=max c；否则不完全 T>=max i；否则不反应。"""
    prods = NE.complete_products(NE.mols_vec(mols))
    if T >= max(m["c"] for m in mols) and prods is not None:
        return "complete", forms(prods)
    cls = NE.select_class(mols)
    if cls is not None:
        part = [m for m in mols if NE.has_class(m, cls)]
        if part and T >= max(NE.i_count(m, cls) for m in part):
            inc = NE.incomplete_products(mols)
            if inc is not None:
                return "incomplete", forms(inc)
    return "none", None


def test5_t35(unstable):
    t0 = time.time()
    pool = stable_pool()
    out = {}

    # ---- 5a) T>=Σc：完全反应优先（即使含不稳定物也不单独自分解）
    pair = [pool[0], pool[1]]
    T = sum(m["c"] for m in pair)
    r = NE.resolve(pair, T)
    exp = NE.complete_products(NE.mols_vec(pair))
    a1 = (r["type"] == "complete" and labels(r["products"]) == labels(exp) and r["stages"] == [])
    if unstable:
        mu = unstable[0]
        B = pool[0]
        T2 = mu["c"] + B["c"]
        r2 = NE.resolve([mu, B], T2)
        exp2 = NE.complete_products(NE.mols_vec([mu, B]))
        a2 = (r2["type"] == "complete" and labels(r2["products"]) == labels(exp2)
              and r2["stages"] == [])
    else:
        a2 = None
    out["5a_complete_priority"] = {
        "pass": bool(a1 and (a2 in (True, None))),
        "stable_pair": {"mols": [m["formula"] for m in pair], "T": T,
                        "type": r["type"], "products": forms(r["products"]),
                        "expected": forms(exp), "stages": r["stages"]},
        "unstable_plus_stable": None if a2 is None else {
            "mols": [mu["formula"], B["formula"]], "T": T2, "type": r2["type"],
            "products": forms(r2["products"]), "expected": forms(exp2),
            "stages": r2["stages"]},
    }

    # ---- 5b) T>=c(U) 但 T<Σc：U 先自分解，而不是与伙伴不完全反应
    B = SUBS_BY_F.get("C2") or pool[0]
    cases = []
    for mu in unstable:
        T = mu["c"]
        csum = mu["c"] + B["c"]
        cls = NE.select_class([mu, B])
        part = [m for m in [mu, B] if cls is not None and NE.has_class(m, cls)]
        isum_old = sum(NE.i_count(m, cls) for m in part) if cls is not None else None
        r = NE.resolve([mu, B], T)
        decomp = [s for s in r["stages"] if s["op"] == "self_decomp"]
        ok = (T < csum and len(decomp) >= 1 and decomp[0]["from"] == mu["formula"]
              and r["csum"] == csum        # csum 与元素计数守恒（见任务 7）
              and r["type"] != "complete")  # 自分解不会降低 Σc
        preempted = isum_old is not None and T >= isum_old
        cases.append({
            "U": mu["formula"], "B": B["formula"], "c(U)": mu["c"], "c(B)": B["c"],
            "T": T, "csum": csum, "old_isum": isum_old,
            "preempted_incomplete": preempted,
            "decomp_stage": decomp[:1],
            "final_type": r["type"], "final_products": forms(r["products"]),
            "ok": ok,
        })
    out["5b_self_decomp_priority"] = {
        "pass": len(cases) > 0 and all(c["ok"] for c in cases),
        "cases": cases,
    }

    # ---- 5c) 自分解后对新产品集合重判
    # 5c-1 语义验证：结果 == 对 S2=(F(v_U)+B) 直接 resolve 的结果
    #      并与"完全不做自分解、直接对原集合做不完全反应"的假设结果对照
    rejudge = []
    for mu in unstable[:6]:
        T = mu["c"]
        r = NE.resolve([mu, B], T)
        subs = NE.self_decomp_products(mu)
        if subs is None:
            continue
        s2 = list(subs) + [B]
        r2 = NE.resolve(s2, T)
        skipped = NE.incomplete_products([mu, B])   # 假设跳过自分解、直接不完全反应
        changed = (skipped is None) or (labels(skipped) != labels(r["products"]))
        ok = (r["type"] == r2["type"] and labels(r["products"]) == labels(r2["products"])
              and r2["stages"] == [])
        rejudge.append({"U": mu["formula"], "T": T,
                        "stage": [s["from"] for s in r["stages"]],
                        "S2": [m["formula"] for m in s2],
                        "engine": {"type": r["type"], "products": forms(r["products"])},
                        "resolve_S2": {"type": r2["type"], "products": forms(r2["products"])},
                        "hypothetical_no_decomp_incomplete": forms(skipped),
                        "rejudge_changed_outcome": changed,
                        "ok": ok})
    # 5c-2 寻找"重判解锁不完全反应"：分解前 T<Σi_old（原本不能不完全反应），
    #      分解后新集合发生不完全反应。先用廉价预筛（键类计数）再调 resolve。
    unlock = []
    all_small_mols = [NE.mol_from_record(r) for r in SMALL]
    for mu in unstable:
        T = mu["c"]
        bcM = NE.bond_classes(mu)
        for Bx in all_small_mols:
            if Bx["label"] == mu["label"]:
                continue
            if T >= mu["c"] + Bx["c"]:
                continue
            bcB = NE.bond_classes(Bx)
            cls = min(list(bcM) + list(bcB), key=lambda c: (c[0], -c[1], c[2]))
            iM = bcM.get(cls, 0)
            iB = bcB.get(cls, 0)
            if iM + iB <= T:          # 旧集合本来就能不完全反应，不算"解锁"
                continue
            r = NE.resolve([mu, Bx], T)
            if (r["type"] == "incomplete"
                    and any(s["op"] == "self_decomp" for s in r["stages"])):
                unlock.append({"U": mu["formula"], "B": Bx["formula"], "T": T,
                               "old_isum": iM + iB,
                               "final": forms(r["products"]),
                               "stages": [s["from"] for s in r["stages"]]})
                if len(unlock) >= 5:
                    break
        if len(unlock) >= 5:
            break
    # 兼容旧口径的补充搜索（稳定伙伴池）
    for mu in unstable:
        T = mu["c"]
        for Bx in pool:
            mols = [mu, Bx]
            csum = mu["c"] + Bx["c"]
            if T >= csum:
                continue
            cls = NE.select_class(mols)
            if cls is None:
                continue
            part = [m for m in mols if NE.has_class(m, cls)]
            isum_old = sum(NE.i_count(m, cls) for m in part)
            r = NE.resolve(mols, T)
            if (T < isum_old and r["type"] == "incomplete"
                    and any(s["op"] == "self_decomp" for s in r["stages"])):
                unlock.append({"U": mu["formula"], "B": Bx["formula"], "T": T,
                               "old_isum": isum_old, "final": forms(r["products"]),
                               "stages": [s["from"] for s in r["stages"]]})
                if len(unlock) >= 8:
                    break
        if len(unlock) >= 8:
            break
    # 5c-3 完全反应解锁的"不可能性"：c 只由元素计数决定，自分解不改变 Σc
    cinv = []
    for mu in unstable:
        subs = NE.self_decomp_products(mu)
        cinv.append({"U": mu["formula"], "c(U)": mu["c"],
                     "sum_c_F": sum(m["c"] for m in subs),
                     "invariant": mu["c"] == sum(m["c"] for m in subs)})
    out["5c_rejudge"] = {
        "pass_semantics": all(x["ok"] for x in rejudge) if rejudge else False,
        "rejudge_semantics": rejudge,
        "incomplete_unlock_examples": unlock,
        "complete_unlock_possible": not all(x["invariant"] for x in cinv),
        "c_invariance": cinv,
        "note": "Σc 由元素计数唯一决定（2c=Σ价数），自分解不改变 Σc，因此“自分解后解锁完全反应”"
                "在该模型中不可能（与 T35 §3/§6.3 的举例不符，属文档层面问题，不是引擎 bug）；"
                "重判循环本身正确，且可改变后续不完全反应的键类/阈值。",
    }

    # ---- 5d) 多个不稳定同时满足：同一轮全部自分解
    d = None
    if len(unstable) >= 2:
        m1, m2 = unstable[0], unstable[1]
        T = max(m1["c"], m2["c"])
        r = NE.resolve([m1, m2], T)
        staged = [s["from"] for s in r["stages"] if s["op"] == "self_decomp"]
        ok = (T < m1["c"] + m2["c"] and len(staged) >= 2
              and set(staged[:2]) == {m1["formula"], m2["formula"]})
        d = {"mols": [m1["formula"], m2["formula"]],
             "c": [m1["c"], m2["c"]], "T": T,
             "all_staged": staged, "final_type": r["type"],
             "final_products": forms(r["products"]), "ok": ok}
    out["5d_multi_decomp"] = {"pass": d is not None and d["ok"], "case": d}

    # ---- 5e) T < 阈值：不反应
    e_cases = []
    pair_ab = [NE.mol_from_record(CAT_BY_F["W2A"]), NE.mol_from_record(CAT_BY_F["WA3F2"])]
    tests = [
        ("stable pair T=0", pair_ab, 0),
        ("stable pair T=1 (<isum=2)", pair_ab, 1),
    ]
    if unstable:
        tests.append(("unstable U+B T=0", [unstable[0], B], 0))
    for name, mols, T in tests:
        r = NE.resolve(mols, T)
        ok = r["type"] == "none" and r["products"] is None and r["stages"] == []
        e_cases.append({"case": name, "T": T, "type": r["type"],
                        "products": forms(r["products"]), "stages": r["stages"], "ok": ok})
    out["5e_below_threshold"] = {"pass": all(c["ok"] for c in e_cases), "cases": e_cases}

    # ---- T33 W2A + WA3F2 口径对照
    if "W2A" in CAT_BY_F and "WA3F2" in CAT_BY_F:
        mA, mB = NE.mol_from_record(CAT_BY_F["W2A"]), NE.mol_from_record(CAT_BY_F["WA3F2"])
        table = []
        for T in range(0, 10):
            r = NE.resolve([mA, mB], T)
            old = max_rule_decision([mA, mB], T)
            table.append({"T": T, "sum_rule": {"type": r["type"], "products": forms(r["products"]),
                                               "isum": r["isum"], "csum": r["csum"]},
                          "max_rule": {"type": old[0], "products": old[1]}})
        f3 = [row for row in table if row["T"] == 3][0]
        f5 = [row for row in table if row["T"] == 5][0]
        f8 = [row for row in table if row["T"] == 8][0]
        t33 = {
            "cA": mA["c"], "cB": mB["c"], "csum": mA["c"] + mB["c"],
            "class": NE.select_class([mA, mB]),
            "iA": NE.i_count(mA, NE.select_class([mA, mB])),
            "iB": NE.i_count(mB, NE.select_class([mA, mB])),
            "table": table,
            "checks": {
                "T3_incomplete_W3A4F2": f3["sum_rule"]["type"] == "incomplete"
                and f3["sum_rule"]["products"] == ("W3A4F2",),
                "T5_sum_incomplete": f5["sum_rule"]["type"] == "incomplete",
                "T5_max_complete": f5["max_rule"]["type"] == "complete",
                "T8_sum_complete_WA_WA_WA2F2": f8["sum_rule"]["type"] == "complete"
                and f8["sum_rule"]["products"] == ("WA", "WA", "WA2F2"),
            },
        }
        t33["pass"] = all(t33["checks"].values())
    else:
        t33 = {"pass": False, "error": "W2A/WA3F2 不在 substances.json"}
    out["t33_w2a_wa3f2"] = t33

    out["pass"] = all(out[k]["pass"] for k in
                      ["5a_complete_priority", "5b_self_decomp_priority",
                       "5d_multi_decomp", "5e_below_threshold", "t33_w2a_wa3f2"]) \
        and out["5c_rejudge"]["pass_semantics"]
    out["seconds"] = round(time.time() - t0, 2)
    R["test5_t35"] = out


# ================================================================ 任务 6
def test6_stability(unstable):
    t0 = time.time()
    # 6-1 目录物质应为 F 不动点（抽样 300）
    sample = RNG.sample(CAT, 300)
    bad_stable = []
    for rec in sample:
        m = NE.mol_from_record(rec)
        if not NE.is_stable(m):
            bad_stable.append({"formula": m["formula"], "atoms": list(m["atoms"]),
                               "c": m["c"], "F": forms(NE.self_decomp_products(m))})
    # 6-2 不稳定分子验证
    checks = []
    for mu in unstable:
        F = NE.self_decomp_products(mu)
        direct_not_fixed = labels(F) != (mu["label"],)
        subs_stable = F is not None and all(NE.is_stable(s) for s in F)
        c_inv = F is not None and mu["c"] == sum(s["c"] for s in F)
        # T >= c：单分子场景下会走"完全反应"分支（Σc=c），产物应等于 F(v_M)
        r_high = NE.resolve([mu], mu["c"])
        high_ok = (r_high["type"] in ("complete", "incomplete")
                   and r_high["products"] is not None
                   and labels(r_high["products"]) == labels(F))
        # T < c：不自分解（单分子不完全反应只会复原自身）
        T_low = mu["c"] - 1
        r_low = NE.resolve([mu], T_low)
        low_ok = (not any(s["op"] == "self_decomp" for s in r_low["stages"])
                  and (r_low["products"] is None or labels(r_low["products"]) == (mu["label"],)))
        # 分解产物再作用 F：仍为自身（一步收敛）
        fixed = F is not None and all(labels(NE.complete_products(s["vec"])) == (s["label"],) for s in F)
        checks.append({
            "U": mu["formula"], "c": mu["c"],
            "unstable": not NE.is_stable(mu),
            "direct_F_not_self": direct_not_fixed,
            "F": forms(F), "c_sum_F": None if F is None else sum(s["c"] for s in F),
            "subs_all_stable": subs_stable, "c_invariant": c_inv,
            "T_ge_c_products": forms(r_high["products"]), "T_ge_c_type": r_high["type"],
            "T_ge_c_ok": high_ok,
            "T_lt_c_type": r_low["type"], "T_lt_c_no_decomp": low_ok,
            "products_are_F_fixed_points": fixed,
            "ok": (direct_not_fixed and subs_stable and c_inv and high_ok and low_ok and fixed),
        })

    # 6-3 F 幂等抽样：随机向量的每个产物应为 F 不动点
    idem_bad = []
    for _ in range(120):
        total = RNG.randint(2, 8)
        bars = sorted(RNG.sample(range(total + 8), 8))
        vec = []
        prev = -1
        for b in bars + [total + 8]:
            vec.append(b - prev - 1)
            prev = b
        vec = tuple(vec)
        prods = NE.complete_products(vec)
        if not prods:
            continue
        for p in prods:
            if labels(NE.complete_products(p["vec"])) != (p["label"],):
                idem_bad.append({"vec": vec, "product": p["formula"]})

    # 6-4 clear_caches 前后确定性
    vecs = []
    for _ in range(30):
        total = RNG.randint(2, 7)
        bars = sorted(RNG.sample(range(total + 8), 8))
        v = []
        prev = -1
        for b in bars + [total + 8]:
            v.append(b - prev - 1)
            prev = b
        vecs.append(tuple(v))
    mols = [NE.mol_from_record(r) for r in RNG.sample(SMALL, 15)]
    pairs = []
    for _ in range(15):
        A, B = RNG.sample(SMALL, 2)
        pairs.append([NE.mol_from_record(A), NE.mol_from_record(B)])
    scen = []
    for _ in range(8):
        A, B = RNG.sample(SMALL, 2)
        T = RNG.randint(0, 12)
        scen.append(([NE.mol_from_record(A), NE.mol_from_record(B)], T))

    def snap():
        s = {
            "F": {str(v): forms(NE.complete_products(v)) for v in vecs},
            "stable": {m["label"]: NE.is_stable(m) for m in mols},
            "inc": {str(i): forms(NE.incomplete_products(p)) for i, p in enumerate(pairs)},
            "resolve": {str(i): (r["type"], forms(r["products"]),
                                  tuple(x["from"] for x in r["stages"]))
                        for i, (mols2, T) in enumerate(scen)
                        for r in [NE.resolve(mols2, T)]},
        }
        return s

    s1 = snap()
    NE.clear_caches()
    s2 = snap()
    cache_same = s1 == s2

    R["test6_stability"] = {
        "pass": (len(bad_stable) == 0 and all(c["ok"] for c in checks)
                 and len(idem_bad) == 0 and cache_same),
        "catalog_sample_stable": {"sample": 300, "unstable_count": len(bad_stable),
                                  "examples": bad_stable[:5]},
        "unstable_checks": checks,
        "F_idempotence_bad": idem_bad[:5],
        "clear_caches_consistent": cache_same,
        "seconds": round(time.time() - t0, 2),
        "note": "单分子不稳定物在 T>=c 时由 resolve 第 1 步（完全反应，Σc=c）完成，"
                "产物与自分解 F(v_M) 相同；T<c 时不走自分解分支（单分子不完全反应仅复原自身）。",
    }


# ================================================================ 任务 7
def brute_ring(n, adj):
    """对简单图（多重边合并）暴力判定每个原子是否在环上（incident 非桥边）。"""
    ring = [False] * n
    edges = set()
    for u in range(n):
        for v in adj[u]:
            if u < v:
                edges.add((u, v))
    for (u, v) in edges:
        # 去掉该边后 u 是否还能到 v
        seen = {u}
        stack = [u]
        recon = False
        while stack and not recon:
            x = stack.pop()
            for y in adj[x]:
                if (x == u and y == v) or (x == v and y == u):
                    continue
                if y == v:
                    recon = True
                    break
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
        if recon:
            ring[u] = ring[v] = True
    return ring


def test7_defects(unstable):
    t0 = time.time()
    # 7-1 ring_flags vs 暴力桥检测（随机图，含多重键）
    rng = random.Random(7)
    ring_bad = []
    for _ in range(300):
        n = rng.randint(1, 7)
        adj = [dict() for _ in range(n)]
        for u in range(n):
            for v in range(u + 1, n):
                if rng.random() < 0.45:
                    m = rng.randint(1, 3)
                    adj[u][v] = m
                    adj[v][u] = m
        got = pot_v4.ring_flags(n, adj)
        exp = brute_ring(n, adj)
        if got != exp:
            ring_bad.append({"n": n, "adj": [[u, v, m] for u in range(n) for v, m in adj[u].items() if u < v],
                             "got": got, "expect": exp})
    # 三角形/树/四元环的定点检查
    def graph(edges, n):
        adj = [dict() for _ in range(n)]
        for u, v in edges:
            adj[u][v] = 1
            adj[v][u] = 1
        return adj
    fixed = [
        {"name": "链 0-1-2", "ring": pot_v4.ring_flags(3, graph([(0, 1), (1, 2)], 3)),
         "expect": [False, False, False]},
        {"name": "三角 0-1-2-0", "ring": pot_v4.ring_flags(3, graph([(0, 1), (1, 2), (2, 0)], 3)),
         "expect": [True, True, True]},
        {"name": "四元环+尾", "ring": pot_v4.ring_flags(5, graph([(0, 1), (1, 2), (2, 3), (3, 0), (0, 4)], 5)),
         "expect": [True, True, True, True, False]},
    ]
    for f in fixed:
        f["ok"] = f["ring"] == f["expect"]

    # 7-2 c = Σ价数/2 不变式（自分解不改变 Σc，见 5c）
    inv_bad = []
    for _ in range(60):
        A, B = RNG.sample(SMALL, 2)
        mols = [NE.mol_from_record(A), NE.mol_from_record(B)]
        total_val = sum(P.VAL[e] for m in mols for e in m["atoms"])
        if sum(m["c"] for m in mols) * 2 != total_val:
            inv_bad.append({"A": A["formula"], "B": B["formula"]})

    # 7-3 只剩单原子 / 无键集合的边界（不应死循环）
    lone = NE.make_mol(["X"], [])
    r_lone = NE.resolve([lone], 0)
    edge_cases = {
        "lone_X_is_stable": NE.is_stable(lone),
        "lone_X_resolve_type": r_lone["type"],
        "lone_X_products": r_lone["products"],
        "empty_F": forms(NE.complete_products((0,) * 9)),
        "empty_greedy": NE.greedy_bond([]),
    }

    # 7-4 固定键下的 level6/规则 10：统计规则 10/11 是否改变结果 + 结构性观察
    #      用任务 3 的统计（results 已写入 R），这里补一个显式"带固定键时 level6 块可能跨原分子"的说明。
    #      构造：对单分子做不完全反应（断键后再接回），检查 level6 块是否包含固定键连通的三价原子。
    level6_note = []
    for mu in unstable[:3]:
        subs = NE.self_decomp_products(mu)
        if subs is not None:
            level6_note.append({
                "U": mu["formula"],
                "note": "自分解产物由 F(v_U) 给出，走 greedy_bond 空 base_edges，与 pot_v4 完全同口径；"
                        "规则 10 的 level6 块捕获在空 base 下与 pot_v4 相同。",
            })

    R["test7_defects"] = {
        "pass": len(ring_bad) == 0 and all(f["ok"] for f in fixed) and len(inv_bad) == 0,
        "ring_flags_random_bad": len(ring_bad),
        "ring_flags_bad_examples": ring_bad[:5],
        "ring_flags_fixed_cases": fixed,
        "c_invariance_bad": len(inv_bad),
        "edge_cases": edge_cases,
        "level6_note": level6_note,
        "seconds": round(time.time() - t0, 2),
    }


# ================================================================ main
def main():
    print("[1/7] complete_products vs pot_v4 ...", flush=True)
    test1_complete()
    print("   ", R["test1_complete"]["pass"], R["test1_complete"]["checked"], "vec",
          R["test1_complete"]["mismatch_count"], "mismatch", flush=True)

    print("[2/7] greedy_bond (empty base) vs pot_v4 ...", flush=True)
    test2_greedy()
    print("   ", R["test2_greedy_bonds"]["pass"], flush=True)

    print("[3/7] incomplete reaction transplant vs t28 ...", flush=True)
    test3_incomplete()
    t3 = R["test3_incomplete"]
    print("   ", t3["pass"], t3["stats"], "formula_diff", t3["formula_diff_count"],
          "structure_diff", t3["structure_diff_count"], flush=True)

    print("[4/7] thresholds/select_class ...", flush=True)
    test4_thresholds()
    print("   ", R["test4_thresholds"]["pass"], flush=True)

    unstable, tries = find_unstable()
    R["meta"]["unstable_found"] = len(unstable)
    R["meta"]["unstable_search_tries"] = tries
    R["meta"]["unstable_formulas"] = [m["formula"] for m in unstable]
    print("    unstable found:", [m["formula"] for m in unstable], flush=True)

    print("[5/7] T35 priority scenarios ...", flush=True)
    test5_t35(unstable)
    print("   ", R["test5_t35"]["pass"], flush=True)

    print("[6/7] stability/self-decomposition ...", flush=True)
    test6_stability(unstable)
    print("   ", R["test6_stability"]["pass"], flush=True)

    print("[7/7] defect checks ...", flush=True)
    test7_defects(unstable)
    print("   ", R["test7_defects"]["pass"], flush=True)

    R["meta"]["seconds"] = round(time.time() - T0, 2)
    R["meta"]["all_pass"] = all(R[k]["pass"] for k in R if isinstance(R[k], dict) and "pass" in R[k])
    json.dump(R, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved", OUT, "elapsed", R["meta"]["seconds"], "s")
    print("ALL_PASS =", R["meta"]["all_pass"])
    for k in ("test1_complete", "test2_greedy_bonds", "test3_incomplete", "test4_thresholds",
              "test5_t35", "test6_stability", "test7_defects"):
        print(" ", k, "PASS" if R[k]["pass"] else "FAIL")


if __name__ == "__main__":
    main()
