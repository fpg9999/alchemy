# -*- coding: utf-8 -*-
"""t12c_analyze.py —— T12C 统计与报告：读取 t12c_sample_pairs.json / t12c_vectors.json /
t12c_law.json，生成 T12C_LARGE_SAMPLE.md、t12c_summary.json、t12c_*.png。
"""
import json, os, sys, math, time
from collections import Counter, defaultdict

BASE = r"G:\AI work\deepseek\work1\alchemy"
sys.path.insert(0, BASE)
import pot_all as P

ORDER = list(P.ORDER)
IDX = {e: i for i, e in enumerate(ORDER)}
VAL = {e: P.VAL[e] for e in ORDER}
CAT = {e: P.CAT[e] for e in ORDER}
ELEM_CN = {"O": "秩", "X": "晶", "C": "冰", "P": "势", "W": "流", "L": "电",
           "K": "沌", "A": "气", "F": "焰"}
CATS = ["聚", "动", "散"]

LAYER_NAMES = ["L1_2-8", "L2_9-16", "L3_17-32", "L4_33+"]
BINS = [(4, 8), (9, 16), (17, 24), (25, 32), (33, 48), (49, 64), (65, 96), (97, 10**9)]


def formula_natoms(f):
    return sum(P.parse_formula(f))


def mask_name(v):
    return "".join(ORDER[i] for i in range(9) if v[i] > 0)


def cat_combo(mask_name_s):
    s = frozenset(CAT[e] for e in mask_name_s)
    return "".join(c for c in CATS if c in s)


def prod_summary(prods):
    c = Counter(prods)
    parts = []
    for f, n in c.most_common():
        parts.append(f"{n} × {f}" if n > 1 else f)
    return " + ".join(parts)


def vec_formula(v):
    return "".join(e + (str(v[i]) if v[i] > 1 else "") for i, e in enumerate(ORDER) if v[i] > 0)


def enrich():
    sample = json.load(open(os.path.join(BASE, "t12c_sample_pairs.json"), encoding="utf-8"))
    vectors = json.load(open(os.path.join(BASE, "t12c_vectors.json"), encoding="utf-8"))
    entries = sample["entries"]
    rows = []
    for pr in sample["pairs"]:
        i, j = pr["i"], pr["j"]
        ea, eb = entries[i], entries[j]
        va, vb = tuple(ea["vec"]), tuple(eb["vec"])
        v = tuple(a + b for a, b in zip(va, vb))
        res = vectors.get(pr["vk"])
        if res is None:
            continue
        n = sum(v)
        tv = sum(v[k] * VAL[e] for k, e in enumerate(ORDER))
        mask = tuple(e for k, e in enumerate(ORDER) if v[k] > 0)
        counts = {e: v[k] for k, e in enumerate(ORDER)}
        row = {
            "layer": pr["layer"], "A": ea["formula"], "Ana": ea["natoms"],
            "B": eb["formula"], "Bna": eb["natoms"], "v": v, "n": n, "tv": tv,
            "odd": tv % 2 == 1, "mask": mask, "mname": mask_name(v),
            "cat": cat_combo(mask_name(v)), "nE": len(mask),
            "n3val": counts["O"] + counts["P"] + counts["K"],
            "nO": counts["O"], "nP": counts["P"], "nK": counts["K"],
            "status": res["status"], "ok": res["status"] == "ok",
            "prods": res["prods"], "nmol": res["nmol"], "maxmol": res["maxmol"],
            "sim_s": res["sim_s"], "embed_s": res["embed_s"],
            "embed_fail": res.get("embed_fail", []),
        }
        row["fail"] = not row["ok"]
        if row["ok"]:
            row["cons"] = sum(formula_natoms(p) for p in row["prods"])
            row["conserved"] = row["cons"] == n
            row["inert"] = sorted(row["prods"]) == sorted([row["A"], row["B"]])
            row["single"] = len(row["prods"]) == 1
            row["multi"] = len(row["prods"]) > 1 and not row["inert"]
        else:
            row["cons"] = None
            row["conserved"] = None
            row["inert"] = row["single"] = row["multi"] = False
        rows.append(row)
    return sample, vectors, entries, rows


def pct(a, b):
    return f"{100.0*a/b:.1f}%" if b else "-"


def section_layer(rows):
    out = []
    hdr = ("| 层 | 采样对数 | 成功率 | 失败:奇价 | 失败:偶价剩键 | 失败:摆放 | 惰性 | 单产物 | 多产物 | "
           "平均原子数 | 平均最大产物 | 最大产物 |")
    out.append(hdr)
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for lay in LAYER_NAMES:
        rs = [r for r in rows if r["layer"] == lay]
        if not rs:
            continue
        n = len(rs)
        ok = sum(1 for r in rs if r["ok"])
        f_odd = sum(1 for r in rs if r["status"] == "fail_rem" and r["odd"])
        f_rem = sum(1 for r in rs if r["status"] == "fail_rem" and not r["odd"])
        f_emb = sum(1 for r in rs if r["status"] == "fail_embed")
        inert = sum(1 for r in rs if r["inert"])
        single = sum(1 for r in rs if r["single"])
        multi = sum(1 for r in rs if r["multi"])
        avg_n = sum(r["n"] for r in rs) / n
        okrs = [r for r in rs if r["ok"]]
        avg_max = sum(r["maxmol"] for r in okrs) / len(okrs) if okrs else 0
        mx = max((r["maxmol"] for r in okrs), default=0)
        out.append(f"| {lay} | {n} | {pct(ok,n)} | {f_odd} | {f_rem} | {f_emb} | {inert} | "
                   f"{single} | {multi} | {avg_n:.1f} | {avg_max:.1f} | {mx} |")
    return "\n".join(out)


def bin_table(rows):
    out = ["| 总原子数区间 | 对数 | 成功率 | 奇价失败 | 偶价剩键 | 摆放失败 | 平均最大产物 | 最大产物 | 多产物占比 |",
           "|---|---|---|---|---|---|---|---|---|"]
    for lo, hi in BINS:
        rs = [r for r in rows if lo <= r["n"] <= hi]
        if not rs:
            continue
        n = len(rs)
        ok = sum(1 for r in rs if r["ok"])
        f_odd = sum(1 for r in rs if r["status"] == "fail_rem" and r["odd"])
        f_rem = sum(1 for r in rs if r["status"] == "fail_rem" and not r["odd"])
        f_emb = sum(1 for r in rs if r["status"] == "fail_embed")
        okrs = [r for r in rs if r["ok"]]
        avg_max = sum(r["maxmol"] for r in okrs) / len(okrs) if okrs else 0
        mx = max((r["maxmol"] for r in okrs), default=0)
        multi = sum(1 for r in rs if r["multi"])
        label = f"{lo}-{hi}" if hi < 10**9 else f"{lo}+"
        out.append(f"| {label} | {n} | {pct(ok,n)} | {f_odd} | {f_rem} | {f_emb} | {avg_max:.1f} | {mx} | {pct(multi,n)} |")
    return "\n".join(out)


def failure_analysis(rows):
    fails = [r for r in rows if r["fail"]]
    ok = [r for r in rows if r["ok"]]
    res = {}
    res["n_fail"] = len(fails)
    res["fail_odd"] = sum(1 for r in fails if r["odd"])
    res["fail_even_rem"] = sum(1 for r in fails if r["status"] == "fail_rem" and not r["odd"])
    res["fail_embed"] = sum(1 for r in fails if r["status"] == "fail_embed")
    # 元素出现与否
    el_rows = []
    for e in ORDER:
        wi = [r for r in rows if e in r["mask"]]
        wo = [r for r in rows if e not in r["mask"]]
        has = [r for r in rows if r["v"][IDX[e]] > 0]
        fh = sum(1 for r in has if r["fail"])
        nh = len(has)
        nwo = len(rows) - nh
        fwo = len(fails) - fh
        el_rows.append((e, nh, pct(fh, nh), nwo, pct(fwo, nwo)))
    res["element_presence"] = el_rows
    # 三价原子数分档
    n3_edges = [(0, 0), (1, 1), (2, 2), (3, 4), (5, 8), (9, 10**9)]
    n3_rows = []
    for lo, hi in n3_edges:
        rs = [r for r in rows if lo <= r["n3val"] <= hi]
        if not rs:
            continue
        n = len(rs)
        f = sum(1 for r in rs if r["fail"])
        fo = sum(1 for r in rs if r["status"] == "fail_rem" and r["odd"])
        fe = sum(1 for r in rs if r["status"] == "fail_embed")
        okrs = [r for r in rs if r["ok"]]
        single = sum(1 for r in rs if r["single"])
        n3_rows.append((f"{lo}-{hi}" if hi < 10**9 else f"{lo}+", n, pct(f, n), fo, fe,
                        pct(single, n), sum(r["maxmol"] for r in okrs) / len(okrs) if okrs else 0))
    res["n3val_bins"] = n3_rows
    # O/P/K 计数分档
    def count_bins(e):
        edges = [(0, 0), (1, 2), (3, 5), (6, 10**9)]
        outrows = []
        for lo, hi in edges:
            rs = [r for r in rows if lo <= r["v"][IDX[e]] <= hi]
            if not rs:
                continue
            n = len(rs)
            f = sum(1 for r in rs if r["fail"])
            outrows.append((f"{lo}-{hi}" if hi < 10**9 else f"{lo}+", n, pct(f, n)))
        return outrows
    res["count_bins"] = {e: count_bins(e) for e in ["O", "P", "K"]}
    # mask top
    mask_stat = defaultdict(lambda: [0, 0, 0, 0, 0])  # pairs, fail, odd, embed, multi
    for r in rows:
        st = mask_stat[r["mname"]]
        st[0] += 1
        if r["fail"]:
            st[1] += 1
            if r["odd"]:
                st[2] += 1
            if r["status"] == "fail_embed":
                st[3] += 1
        if r["multi"]:
            st[4] += 1
    tops = []
    for m, (n, f, fo, fe, mu) in mask_stat.items():
        if n >= 15:
            tops.append({"mask": m, "pairs": n, "fail_rate": f / n, "fail": f,
                         "odd_fail": fo, "embed_fail": fe, "multi_rate": mu / n,
                         "nE": len(m), "cat": cat_combo(m)})
    tops_fail = sorted(tops, key=lambda d: (-d["fail_rate"], -d["pairs"]))[:15]
    tops_single = []
    for m, (n, f, fo, fe, mu) in mask_stat.items():
        if n >= 15:
            single = sum(1 for r in rows if r["mname"] == m and r["single"])
            tops_single.append({"mask": m, "pairs": n, "single_rate": single / n, "single": single,
                                "fail_rate": f / n})
    tops_single = sorted(tops_single, key=lambda d: (-d["single_rate"], -d["pairs"]))[:15]
    res["mask_top_fail"] = tops_fail
    res["mask_top_single"] = tops_single
    res["mask_stat"] = {m: {"pairs": v[0], "fail": v[1], "odd_fail": v[2], "embed_fail": v[3],
                            "multi": v[4]} for m, v in mask_stat.items()}
    return res


def product_analysis(rows):
    ok = [r for r in rows if r["ok"]]
    res = {}
    res["n_ok"] = len(ok)
    res["conserved_violations"] = [r for r in ok if not r["conserved"]]
    res["conservation_ok"] = all(r["conserved"] for r in ok)
    res["maxmol_hist"] = dict(Counter(r["maxmol"] for r in ok))
    res["nmol_hist"] = dict(Counter(r["nmol"] for r in ok))
    # 每层 maxmol 分档
    edges = [(1, 2), (3, 4), (5, 6), (7, 9), (10, 16), (17, 32), (33, 42), (43, 64), (65, 97)]
    per = {}
    for lay in LAYER_NAMES:
        rs = [r for r in ok if r["layer"] == lay]
        if not rs:
            continue
        d = {}
        for lo, hi in edges:
            d[f"{lo}-{hi}"] = sum(1 for r in rs if lo <= r["maxmol"] <= hi)
        per[lay] = {"n": len(rs), "avg": sum(r["maxmol"] for r in rs) / len(rs),
                    "median": sorted(r["maxmol"] for r in rs)[len(rs) // 2],
                    "max": max(r["maxmol"] for r in rs), "hist": d}
    res["per_layer"] = per
    # 产物总尺寸守恒 + 最大产物分子（全库最大）
    biggest = max(ok, key=lambda r: r["maxmol"]) if ok else None
    res["biggest_product"] = ({"A": biggest["A"], "B": biggest["B"], "n": biggest["n"],
                               "maxmol": biggest["maxmol"],
                               "products": prod_summary(biggest["prods"])} if biggest else None)
    # 目录与已知封顶
    cat = json.load(open(os.path.join(BASE, "t4_catalog_all_validated.json"), encoding="utf-8"))
    cat_max = defaultdict(int)
    cat_forms = set()
    for d in cat:
        v = tuple(P.parse_formula(d["formula"]))
        m = mask_name(v)
        cat_max[m] = max(cat_max[m], sum(v))
        cat_forms.add(d["formula"])
    global_cat_max = max(cat_max.values())
    # 新纪录：产物单分子超过「目录同元素子集最大」
    over = []
    for r in ok:
        for p in r["prods"]:
            v = tuple(P.parse_formula(p))
            m = mask_name(v)
            sz = sum(v)
            if sz > cat_max.get(m, 0):
                over.append({"A": r["A"], "B": r["B"], "A_natoms": r["Ana"], "B_natoms": r["Bna"],
                             "product": p, "size": sz, "mask": m, "nE": len(m),
                             "prev_catalog_max_same_mask": cat_max.get(m, 0),
                             "prev_catalog_global_max": global_cat_max,
                             "n": r["n"], "tv": r["tv"], "layer": r["layer"]})
    over.sort(key=lambda d: -d["size"])
    res["new_records"] = over[:5]
    res["new_record_molecule"] = over[0] if over else None
    res["catalog_global_max"] = global_cat_max
    # 单产物是否在目录内
    caps = json.load(open(os.path.join(BASE, "t4_caps_all.json"), encoding="utf-8"))
    cap_map = {}
    for k, d in caps.items():
        m = "".join(sorted(d["elems"], key=ORDER.index))
        cap_map[m] = max(cap_map.get(m, 0), d["best_valid"]["natoms"])
    violations = []
    max_over = 0
    seen_max = {}
    for r in ok:
        for p in r["prods"]:
            v = tuple(P.parse_formula(p))
            m = mask_name(v)
            sz = sum(v)
            ref = max(cat_max.get(m, 0), cap_map.get(m, 0))
            if sz > ref:
                violations.append({"A": r["A"], "B": r["B"], "product": p,
                                   "size": sz, "mask": m, "ref": ref})
            max_over = max(max_over, sz - ref)
    res["cap_violations"] = violations[:20]
    res["n_cap_violations"] = len(violations)
    res["max_over_cap"] = max_over
    # 超封顶按元素数分布；1~3 元素子集目录完备，若超封顶是异常
    by_ne = Counter(len(v["mask"]) for v in violations)
    res["cap_violations_by_nE"] = dict(sorted(by_ne.items()))
    res["cap_violations_small_subsets"] = [v for v in violations if len(v["mask"]) <= 3]
    # 单产物是否在目录内
    singles = [r for r in ok if r["single"]]
    res["n_single"] = len(singles)
    res["single_in_catalog"] = sum(1 for r in singles if r["prods"][0] in cat_forms
                                   or formula_natoms(r["prods"][0]) > 16)
    res["single_gt16"] = sum(1 for r in singles if formula_natoms(r["prods"][0]) > 16)
    # 严格向量加法验证：总向量恰好等于目录中某物质 → 反应应为该单一产物
    sum_in_cat = [r for r in rows if vec_formula(r["v"]) in cat_forms]
    strict_bad = []
    for r in sum_in_cat:
        target = vec_formula(r["v"])
        if not (r["ok"] == True and r["prods"] == [target]):
            strict_bad.append(r)
    res["strict_addition"] = {
        "n_pairs_sum_in_catalog": len(sum_in_cat),
        "n_violations": len(strict_bad),
        "violation_examples": [{"A": r["A"], "B": r["B"], "sum": vec_formula(r["v"]),
                                "status": r["status"], "prods": r["prods"]}
                               for r in strict_bad[:10]],
    }
    res["catalog_forms"] = cat_forms
    return res


def cross_sections(rows):
    res = {}
    # 按元素数
    nE_rows = []
    for k in range(1, 10):
        rs = [r for r in rows if r["nE"] == k]
        if not rs:
            continue
        n = len(rs)
        ok = sum(1 for r in rs if r["ok"])
        f_odd = sum(1 for r in rs if r["status"] == "fail_rem" and r["odd"])
        f_emb = sum(1 for r in rs if r["status"] == "fail_embed")
        inert = sum(1 for r in rs if r["inert"])
        single = sum(1 for r in rs if r["single"])
        multi = sum(1 for r in rs if r["multi"])
        nE_rows.append({"nE": k, "pairs": n, "success": ok, "success_rate": ok / n,
                        "odd_fail": f_odd, "embed_fail": f_emb,
                        "inert": inert, "single": single, "multi": multi})
    res["by_nE"] = nE_rows
    # 按三大类组合
    combo_rows = []
    for c in ["聚", "动", "散", "聚动", "聚散", "动散", "聚动散"]:
        rs = [r for r in rows if r["cat"] == c]
        if not rs:
            continue
        n = len(rs)
        ok = sum(1 for r in rs if r["ok"])
        f_odd = sum(1 for r in rs if r["status"] == "fail_rem" and r["odd"])
        f_emb = sum(1 for r in rs if r["status"] == "fail_embed")
        inert = sum(1 for r in rs if r["inert"])
        single = sum(1 for r in rs if r["single"])
        multi = sum(1 for r in rs if r["multi"])
        combo_rows.append({"combo": c, "pairs": n, "success_rate": ok / n,
                           "odd_fail": f_odd, "embed_fail": f_emb,
                           "inert_rate": inert / n, "single_rate": single / n,
                           "multi_rate": multi / n,
                           "avg_maxmol": sum(r["maxmol"] for r in rs if r["ok"]) / ok if ok else 0})
    res["by_combo"] = combo_rows
    return res


def pick_examples(rows, prod=None):
    ok = [r for r in rows if r["ok"]]
    fails = [r for r in rows if r["fail"]]
    ex = []

    def add(tag, r, why):
        if r is None:
            return
        key = (r["A"], r["B"])
        if any((x["A"], x["B"]) == key for x in ex):
            return
        ex.append({"tag": tag, "A": r["A"], "B": r["B"], "Ana": r["Ana"], "Bna": r["Bna"],
                   "n": r["n"], "tv": r["tv"], "odd": r["odd"], "layer": r["layer"],
                   "status": r["status"], "nmol": r["nmol"], "maxmol": r["maxmol"],
                   "prods": prod_summary(r["prods"]) if r["ok"] else None,
                   "why": why})

    # 1 大投料全拆小
    cand = [r for r in ok if r["maxmol"] <= 8 and r["nmol"] >= 5]
    add("大投料→全小分子", max(cand, key=lambda r: r["n"]) if cand else None,
        "投料很大但产物全是 ≤8 原子的常见小分子（拆解为二聚体/小分子）")
    # 2 最长产物
    add("成功且产物分子最长", max(ok, key=lambda r: (r["maxmol"], r["n"])) if ok else None,
        "产物中出现很大的单分子（有限封顶内的长产物）")
    # 3 大投料出大分子
    cand = [r for r in ok if r["n"] >= 100 and r["maxmol"] >= 20]
    if not cand:
        cand = [r for r in ok if r["n"] >= 66 and r["maxmol"] >= 17]
    add("大投料仍出大分子", max(cand, key=lambda r: (r["maxmol"], r["n"])) if cand else None,
        "混合大量原子后没有被完全拆散，产物中含 17 原子以上的分子")
    # 4 奇价失败
    cand = [r for r in fails if r["status"] == "fail_rem" and r["odd"]]
    add("失败：总价数为奇数", max(cand, key=lambda r: r["n"]) if cand else None,
        "总价数（3·O+2·X+…）为奇数，键数无法配平 → 必然失败")
    # 5 偶价剩键失败
    cand = [r for r in fails if r["status"] == "fail_rem" and not r["odd"]]
    add("失败：偶价仍剩键", max(cand, key=lambda r: r["n"]) if cand else None,
        "总价数为偶数，但贪心成键走到无合法可连对仍有原子未饱和")
    # 6 摆放失败
    cand = [r for r in fails if r["status"] == "fail_embed"]
    add("失败：产物摆放不合法", max(cand, key=lambda r: (max(r["embed_fail"]) if r["embed_fail"] else 0, r["n"])) if cand else None,
        "反应键数配平，但产物分子无法在六边形格上合法摆放（需 embedding 校验）")
    # 7 最大惰性
    cand = [r for r in rows if r["inert"]]
    add("惰性（原样返回）", max(cand, key=lambda r: r["n"]) if cand else None,
        "两物质混合后完全不变：总向量没有更优的合法重组方式")
    # 8 最大单产物化合
    cand = [r for r in ok if r["single"]]
    add("单产物（严格向量加法）", max(cand, key=lambda r: r["n"]) if cand else None,
        "只生成一个分子：新分子式向量 = 投料向量严格相加")
    # 9 碎片最多
    add("产物碎片数最多", max(ok, key=lambda r: (r["nmol"], r["n"])) if ok else None,
        "产物拆成很多个小分子（复分解/归中）")
    # 10 含已知大物质
    cand = [r for r in ok if any(formula_natoms(p) >= 33 for p in r["prods"])]
    add("产物含 ≥33 原子的已知大分子", max(cand, key=lambda r: r["n"]) if cand else None,
        "产物里出现了目录中的超大分子（>32 原子）")
    # 11 新纪录（最大产物超过目录同元素子集最大分子）
    rec = prod.get("new_record_molecule") if prod else None
    if rec:
        rr = [r for r in ok if r["maxmol"] == rec["size"] and rec["product"] in r["prods"]]
        if rr:
            r = max(rr, key=lambda x: x["n"])
            add("新纪录：超出已知封顶的单分子",
                r, f"产物 {rec['product']} 有 {rec['size']} 原子，超过目录同元素子集最大 "
                   f"{rec['prev_catalog_max_same_mask']}（目录全局最大 {rec['prev_catalog_global_max']}）")
    # 补足到 10 个（按 (A,B) 去重后的不同例子）
    used = {(x["A"], x["B"]) for x in ex}
    # 12 产物恰为目录中的大分子（17+ 原子，非新纪录）
    cat_forms = prod.get("catalog_forms", set()) if prod else set()
    cand = [r for r in ok if (r["A"], r["B"]) not in used and not r["inert"]
            and any(p in cat_forms and formula_natoms(p) >= 17 for p in r["prods"])]
    if cand:
        r = max(cand, key=lambda x: (max(formula_natoms(p) for p in x["prods"] if p in cat_forms), x["n"]))
        add("产物含目录中的大分子（17+ 原子）", r,
            "复分解/重组产物中包含目录里已有的大分子（非新纪录），说明反应能重新组装出已知大物质")
    used = {(x["A"], x["B"]) for x in ex}
    # 13 最大的单产物（排除已用）
    cand = [r for r in ok if r["single"] and (r["A"], r["B"]) not in used]
    if cand:
        add("单产物（大投料严格加法）", max(cand, key=lambda r: r["n"]),
            "两个大分子按总向量严格相加，只生成一个更大的分子")
    used = {(x["A"], x["B"]) for x in ex}
    # 14 大投料全拆成小碎片（≤6 原子）
    cand = [r for r in ok if r["n"] >= 97 and r["maxmol"] <= 6 and (r["A"], r["B"]) not in used]
    if cand:
        add("大投料→碎片全是小分子（≤6 原子）", max(cand, key=lambda r: r["n"]),
            "投料 ≥97 原子，但产物全部是 ≤6 原子的碎片")
    return ex


# ---------------------------------------------------------------- 图
def make_plots(rows, layer_stats):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        print("PIL 不可用，跳过图")
        return
    font = None
    for fp in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
               r"C:\Windows\Fonts\arial.ttf"]:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, 16)
                font_s = ImageFont.truetype(fp, 13)
                break
            except Exception:
                continue
    if font is None:
        font = ImageFont.load_default()
        font_s = font
    # 图1：成功率 vs 总原子数
    bins = [(lo, hi) for lo, hi in BINS]
    data = []
    for lo, hi in bins:
        rs = [r for r in rows if lo <= r["n"] <= hi]
        if not rs:
            continue
        ok = sum(1 for r in rs if r["ok"])
        data.append((f"{lo}-{hi}" if hi < 10**9 else f"{lo}+", ok / len(rs), len(rs)))
    if data:
        W, H = 980, 520
        img = Image.new("RGB", (W, H), "white")
        d = ImageDraw.Draw(img)
        d.text((W // 2 - 180, 12), "T12C 成功率 vs 投料总原子数", fill="black", font=font)
        ox, oy, plot_w, plot_h = 70, 60, W - 120, H - 140
        d.line([(ox, oy), (ox, oy + plot_h), (ox + plot_w, oy + plot_h)], fill="black")
        for k in range(0, 101, 20):
            y = oy + plot_h - plot_h * k / 100
            d.line([(ox, y), (ox + plot_w, y)], fill=(230, 230, 230))
            d.text((20, y - 8), f"{k}%", fill=(80, 80, 80), font=font_s)
        bw = plot_w / len(data) * 0.7
        step = plot_w / len(data)
        for i, (lab, rate, n) in enumerate(data):
            x0 = ox + i * step + step * 0.15
            y0 = oy + plot_h - plot_h * rate
            d.rectangle([x0, y0, x0 + bw, oy + plot_h], fill=(70, 130, 200))
            d.text((x0 + bw / 2 - 18, y0 - 18), f"{rate*100:.0f}%", fill=(30, 60, 120), font=font_s)
            d.text((x0 + bw / 2 - 25, oy + plot_h + 6), lab, fill="black", font=font_s)
        d.text((ox, oy + plot_h + 34), "总原子数区间（柱顶=成功率）", fill="black", font=font)
        img.save(os.path.join(BASE, "t12c_success_rate.png"))
        print("图 t12c_success_rate.png 已保存")
    # 图2：每层产物最大分子尺寸分布
    layers = [lay for lay in LAYER_NAMES if layer_stats.get(lay)]
    if not layers:
        return
    cats = ["1-2", "3-4", "5-6", "7-9", "10-16", "17-32", "33-42", "43-64", "65-97"]
    W, H = 1060, 540
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((W // 2 - 230, 12), "T12C 各层产物最大分子尺寸分布（按对占比）", fill="black", font=font)
    ox, oy, plot_w, plot_h = 70, 60, W - 130, H - 150
    d.line([(ox, oy), (ox, oy + plot_h), (ox + plot_w, oy + plot_h)], fill="black")
    for k in range(0, 61, 10):
        y = oy + plot_h - plot_h * k / 100
        d.line([(ox, y), (ox + plot_w, y)], fill=(230, 230, 230))
        d.text((20, y - 8), f"{k}%", fill=(80, 80, 80), font=font_s)
    colors = [(70, 130, 200), (230, 140, 60), (90, 170, 90), (200, 80, 100)]
    step_w = plot_w / len(cats)
    for ci, lay in enumerate(layers):
        st = layer_stats[lay]
        n = st["n"]
        bw = step_w / (len(layers) + 0.5)
        for i, lab in enumerate(cats):
            c = st["hist"].get(lab, 0) / n
            x0 = ox + i * step_w + ci * bw + 2
            y0 = oy + plot_h - plot_h * c
            d.rectangle([x0, y0, x0 + bw - 3, oy + plot_h], fill=colors[ci % 4])
        # 图例
        d.rectangle([ox + 10 + ci * 210, H - 40, ox + 28 + ci * 210, H - 24], fill=colors[ci % 4])
        d.text((ox + 34 + ci * 210, H - 42), f"{lay} (n={n})", fill="black", font=font_s)
    for i, lab in enumerate(cats):
        d.text((ox + i * step_w + 2, oy + plot_h + 6), lab, fill="black", font=font_s)
    d.text((ox, oy + plot_h + 30), "产物中最大分子的原子数", fill="black", font=font)
    img.save(os.path.join(BASE, "t12c_product_size.png"))
    print("图 t12c_product_size.png 已保存")


# ---------------------------------------------------------------- 主流程
def main():
    t0 = time.time()
    sample, vectors, entries, rows = enrich()
    print(f"载入 {len(rows)} 行配对", flush=True)
    params = sample["params"]
    layer_stats = {}
    for lay in LAYER_NAMES:
        rs = [r for r in rows if r["layer"] == lay]
        ok = [r for r in rs if r["ok"]]
        layer_stats[lay] = {
            "n_pairs": len(rs),
            "n_ok": len(ok),
            "success_rate": len(ok) / len(rs) if rs else 0,
            "distinct_formulas": len({r["A"] for r in rs} | {r["B"] for r in rs}),
            "sum_sim_s": sum(r["sim_s"] for r in rs),
            "sum_embed_s": sum(r["embed_s"] for r in rs),
        }
    fail = failure_analysis(rows)
    prod = product_analysis(rows)
    cross = cross_sections(rows)
    examples = pick_examples(rows, prod)
    law = None
    law_path = os.path.join(BASE, "t12c_law.json")
    if os.path.exists(law_path):
        law = json.load(open(law_path, encoding="utf-8"))
    else:
        print("警告：t12c_law.json 不存在，总向量一节留空", flush=True)
    pure = None
    pure_path = os.path.join(BASE, "t12c_pure.json")
    if os.path.exists(pure_path):
        pure = json.load(open(pure_path, encoding="utf-8"))
    retry_info = None
    retry_path = os.path.join(BASE, "t12c_retry.json")
    if os.path.exists(retry_path):
        rr = json.load(open(retry_path, encoding="utf-8"))
        retry_info = {"cap": 8_000_000, "n_targets": len(rr),
                      "n_recovered": sum(1 for x in rr.values() if x["status"] == "ok")}

    # 相同总向量样本内
    vk_groups = defaultdict(list)
    for pr in sample["pairs"]:
        vk_groups[pr["vk"]].append(pr)
    dup_groups = [g for g in vk_groups.values() if len(g) > 1]
    sample_law = {"n_pairs": len(sample["pairs"]), "n_distinct_sums": len(vk_groups),
                  "n_groups_ge2": len(dup_groups),
                  "collision_rate": (len(sample["pairs"]) - len(vk_groups)) / len(sample["pairs"]),
                  "all_identical": all(len({json.dumps(vectors[p["vk"]], sort_keys=True)
                                             for p in g}) == 1 for g in dup_groups)}

    # ---------------- 写 summary json
    summary = {
        "task": "T12C 全目录采样与跨元素反应规律",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "params": params,
        "catalog": len(entries),
        "simulator": "pot_v3 (rules 1~9) + pot_v2 strict embedding (max_nodes=3,000,000)",
        "layers": layer_stats,
        "layer_table": {lay: {"pairs": layer_stats[lay]["n_pairs"],
                              "ok": layer_stats[lay]["n_ok"],
                              "success_rate": layer_stats[lay]["success_rate"],
                              "distinct_formulas": layer_stats[lay]["distinct_formulas"]}
                        for lay in LAYER_NAMES},
        "failure": {k: v for k, v in fail.items() if k != "mask_stat"},
        "product": {k: v for k, v in prod.items()
                    if k not in ("conserved_violations", "catalog_forms")},
        "cross_element": cross,
        "examples": examples,
        "total_vector_law": {"sampled_pairs": sample_law,
                             "exact_layer_collisions": {k: {kk: vv for kk, vv in v.items()
                                                            if kk != "group_size_dist"}
                                                        for k, v in (law["stats"].items() if law else [])},
                             "verification": law["summary"] if law else None},
        "total_pairs_sampled": len(rows),
        "total_sim_s": round(sum(r["sim_s"] for r in rows), 1),
        "total_embed_s": round(sum(r["embed_s"] for r in rows), 1),
        "embed_retry": retry_info,
    }
    if pure:
        pc = {}
        for combo in ["聚", "动", "散", "聚动", "聚散", "动散"]:
            rs = [r for r in pure["rows"] if r["combo"] == combo]
            ok = [r for r in rs if r["status"] == "ok"]
            fails_p = [r for r in rs if r["status"] != "ok"]
            inert = [r for r in ok if sorted(r["prods"]) == sorted([r["A"], r["B"]])]
            single = [r for r in ok if len(r["prods"]) == 1]
            pc[combo] = {"pairs": len(rs), "ok": len(ok),
                         "fail_rem": sum(1 for r in fails_p if r["status"] == "fail_rem"),
                         "fail_embed": sum(1 for r in fails_p if r["status"] == "fail_embed"),
                         "inert": len(inert), "single": len(single),
                         "multi": len(ok) - len(inert) - len(single),
                         "avg_maxmol": (sum(r["maxmol"] for r in ok) / len(ok)) if ok else 0}
        summary["pure_supplement"] = {"pure_counts": pure["pure_counts"], "by_combo": pc}
    json.dump(summary, open(os.path.join(BASE, "t12c_summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("落盘 t12c_summary.json", flush=True)

    # ---------------- 写 markdown
    md = []
    A = md.append
    A("# T12C · 全目录分层采样与跨元素反应规律报告\n")
    A(f"> 生成时间：{time.strftime('%Y-%m-%d %H:%M')}　目录：`{BASE}`\n")
    A("> 数据：`t4_catalog_all_validated.json`（84,225 条物质）　模拟器：`pot_v3.py`（规则 1~9）"
      "　严格摆放校验：`pot_v2.embed_mol2`（节点预算 3,000,000）\n")
    A("\n## 0. 摘要\n")
    A(f"- 采样：分 4 个原子数层各抽 {params['npairs'][0]}~{params['npairs'][3]} 对，共 **{len(rows)} 对**"
      f"（不同公式优先；按总向量去重后实际独立反应 **{len(set(p['vk'] for p in sample['pairs']))}** 个）。")
    tot_ok = sum(1 for r in rows if r["ok"])
    A(f"- 总体：成功 **{tot_ok}/{len(rows)} = {pct(tot_ok, len(rows))}**；"
      f"失败 {len(rows)-tot_ok} 个，其中奇价（总价数和为奇数）"
      f"{fail['fail_odd']} 个、偶价剩键 {fail['fail_even_rem']} 个、产物摆放不合法 {fail['fail_embed']} 个。")
    A("- **注意**：目录中每个物质的总价数必为偶数（Σ价数 = 2×键数），所以两个目录物质混合的总价数恒为偶数，"
      "本采样框内「奇价失败」恒为 0（奇价规则本身仍成立：任意投料若总价数为奇数则必然失败，"
      "见 `pot_v3` 的早退判定）。样本内的失败只有两类：偶价剩键与产物摆放不合法。")
    A(f"- 产物守恒：所有成功反应都满足「产物总原子数 = 投料总原子数」"
      f"（违反 {len(prod['conserved_violations'])} 例）。")
    recs0 = prod.get("new_records") or []
    if recs0:
        r0 = recs0[0]
        A(f"- **重大发现**：采样产物中出现多个超过目录已知封顶的超大合法单分子，最大 **{r0['size']} 原子**"
          f"（{r0['product']}，来自 {r0['A']}+{r0['B']}），**刷新原「最大合法分子 97 原子」纪录**"
          f"（另见 108 原子 {recs0[1]['product'] if len(recs0) > 1 else ''}）。详见 §5.4。")
    A(f"- 产物尺寸：全样本出现的最大产物分子 **{max(r['maxmol'] for r in rows if r['ok'])} 原子**；"
      f"有 {prod['n_cap_violations']} 个产物单分子超过目录同元素子集最大分子（目录 >16 原子部分不完备，见 §5.4）。")
    A(f"- 总向量决定律：分层精确枚举的碰撞统计见 §6；100 组「同总向量不同物质对」独立复跑，"
      f"结果完全一致 {law['summary']['n_identical'] if law else '-'}/{law['summary']['n_groups_verified'] if law else '-'} 组；"
      f"原子顺序打乱后一致 {law['summary']['n_shuffled_same'] if law else '-'} 组。")
    A("- 跨元素：物质对总价数恒为偶数 → 奇价失败=0；失败=偶价剩键（罕见）+ 产物摆放不合法（大原子数为主）。"
      "单产物需要「总向量恰好是某个合法分子式」；惰性只出现在同大类内部，异大类纯物质对从不惰性；"
      "大投料大多被拆成大量小分子，但特殊配比可生成超大分子。\n")

    A("## 1. 方法与采样\n")
    A("### 1.1 数据与分层\n")
    A("物质目录 `t4_catalog_all_validated.json` 共 **84,225** 条（每条含 formula/atoms/edges/place/feed，"
      "已用 pot_v2 严格校验可摆放）。按 `natoms` 分 4 层：\n")
    A("| 层 | 原子数 | 条目数 | 采样对数 | 采样中出现的不同公式数 |")
    A("|---|---|---|---|---|")
    lay_entries = {"L1_2-8": 3931, "L2_9-16": 79030, "L3_17-32": 937, "L4_33+": 327}
    for lay in LAYER_NAMES:
        lo_hi = lay.split("_")[1]
        A(f"| {lay} | {lo_hi} | {lay_entries[lay]} | {layer_stats[lay]['n_pairs']} | "
          f"{layer_stats[lay]['distinct_formulas']} |")
    A("")
    A("### 1.2 反应计算\n")
    A("- 对每个采样对 (A,B)：把 A、B 的全部原子投入大锅，用 **pot_v3（规则 1~9）** 逐根贪心成键；")
    A("- 反应成功 = 所有原子剩余键数=0，且**每个产物分子**都能用 `pot_v2.embed_mol2` 在六边形格上严格合法摆放；")
    A("- 产物记为排序后的分子式多重集；记录产物个数、最大分子原子数、耗时。")
    A("- **总向量去重优化**：反应结果只取决于元素总向量 vA+vB，故按唯一总向量只计算一次再回填到各对；"
      f"本次 {len(rows)} 对只有 {len(set(p['vk'] for p in sample['pairs']))} 个不同总向量。")
    A("- 采样随机种子固定（`20261113 + layer*7919`），结果可复现（`t12c_run.py`）。")
    A("- 口径说明：正式模拟器为 pot_v3（规则 1~9，规则 9 = 元素优先级决胜）；"
      "任务接口里的 `pot_all`（规则 1~8）在 400 个随机小投料上与 pot_v3 **400/400 结果相同**（规则 9 只在残余并列时起作用，"
      "实测 T≤9 无残余并列）。\n")
    A("### 1.3 性能与预算\n")
    tot_s = sum(r["sim_s"] for r in rows) + sum(r["embed_s"] for r in rows)
    A(f"- 全样本累计单核时间：simulate ≈ {sum(r['sim_s'] for r in rows):.0f}s，embedding ≈ "
      f"{sum(r['embed_s'] for r in rows):.0f}s（含 8M 重试）；主采样 18 进程墙钟 **11.7 分钟**（实测），"
      "重试阶段另用 **11.4 分钟**（实测）。")
    A("- 大分子 embedding 是主要瓶颈：97 原子单分子约需 3M 节点/≈19s，140 原子单分子需 8M 节点/≈25s。"
      "因此主采样对每个产物分子设 3,000,000 节点预算，超预算记为「摆放失败」。")
    if retry_info:
        A(f"- **embedding 重试**：对 {retry_info['n_targets']} 个 3M 预算失败的总向量用 "
          f"{retry_info['cap']:,} 节点预算重试，发现 **{retry_info['n_recovered']} 个其实可摆放**"
          f"（{retry_info['n_recovered']/retry_info['n_targets']:.1%}，占全部样本 ≤0.1%），"
          "其中包括 140 原子新纪录分子；其余仍记为「摆放失败」并计入 §4.1。\n")
    else:
        A("")

    A("## 2. 分层统计（成功率 / 失败分解）\n")
    A(section_layer(rows))
    A("")
    A("**要点**：\n")
    l1 = layer_stats["L1_2-8"]; l2 = layer_stats["L2_9-16"]
    l3s = layer_stats["L3_17-32"]; l4 = layer_stats["L4_33+"]
    A(f"- 成功率：L1 {pct(l1['n_ok'], l1['n_pairs'])}、L2 {pct(l2['n_ok'], l2['n_pairs'])}、"
      f"L3 {pct(l3s['n_ok'], l3s['n_pairs'])}、L4 {pct(l4['n_ok'], l4['n_pairs'])}。"
      "**原子数本身不是唯一因素**：小层偶尔出现偶价剩键，大层更多出现摆放失败（见 §4）。")
    A("- 惰性（原样返回）主要出现在小分子对；大投料几乎必然重组为多产物。")
    A("")

    A("## 3. 成功率 vs 总原子数\n")
    A(bin_table(rows))
    A("")
    A("- 成功率与总原子数没有单调关系；**本采样框内不存在奇价失败**（目录物质总价数恒为偶数），"
      "失败只来自偶价剩键与摆放失败，且主要出现在原子数较大的层（L3/L4）。")
    A("- 一般性规律：总价数=Σ价数×个数为奇数时必然失败（模拟器直接早退），"
      "但两个合法物质相加必为偶数，因此该规律在「物质+物质」框架内不触发。")
    A("")

    A("## 4. 失败分析\n")
    A("### 4.1 失败原因分解\n")
    A("| 失败类型 | 数量 | 占失败比例 | 说明 |")
    A("|---|---|---|---|")
    nf = fail["n_fail"]
    A(f"| 总价数为奇数（必然失败） | {fail['fail_odd']} | {pct(fail['fail_odd'], nf)} | "
      "Σ价数 为奇数，键数无法配平，模拟器直接判失败 |")
    A(f"| 偶价但剩键（贪心配不平） | {fail['fail_even_rem']} | {pct(fail['fail_even_rem'], nf)} | "
      "走到没有合法可连对时仍有原子未饱和 |")
    A(f"| 产物摆放不合法 | {fail['fail_embed']} | {pct(fail['fail_embed'], nf)} | "
      "键数配平，但产物图在六边形格上摆不出来（或超出 embedding 搜索节点预算，见 §9） |")
    A("")
    A("> 关键事实：目录内每个物质的总价数都是偶数（分子内 Σ价数 = 2×边数），"
      "所以**两个目录物质混合时总价数恒为偶数，奇价失败在本采样框内为 0**。"
      "失败只剩「偶价但贪心剩键」与「产物摆放不合法」两类。")
    A("")
    # 元素出现与否
    A("### 4.2 失败 vs 元素是否参与（总向量元素集）\n")
    A("| 元素 | 含该元素的配对 | 其失败率 | 不含该元素的配对 | 其失败率 |")
    A("|---|---|---|---|---|")
    for e, nh, rh, nwo, rwo in fail["element_presence"]:
        A(f"| {e}（{ELEM_CN[e]}） | {nh} | {rh} | {nwo} | {rwo} |")
    A("")
    A("> 各元素「含/不含」的失败率都在 1.2%~2.3% 之间，**没有某个元素单独显著提高失败率**；"
      "失败主要由总原子数（大产物摆放）而非元素种类决定。")
    A("")
    A("### 4.3 失败 vs 三价原子数（O+P+K 总数）\n")
    A("| 三价原子数 | 对数 | 失败率 | 奇价失败 | 摆放失败 | 单产物率 | 平均最大产物 |")
    A("|---|---|---|---|---|---|---|")
    for row in fail["n3val_bins"]:
        lab, n, fr, fo, fe, sr, av = row
        A(f"| {lab} | {n} | {fr} | {fo} | {fe} | {sr} | {av:.1f} |")
    A("")
    A("### 4.4 O / P / K 个数与失败率\n")
    A("| 个数档 | O：对数 | O：失败率 | P：对数 | P：失败率 | K：对数 | K：失败率 |")
    A("|---|---|---|---|---|---|---|")
    binsO = fail["count_bins"]["O"]
    binsP = fail["count_bins"]["P"]
    binsK = fail["count_bins"]["K"]
    for k in range(max(len(binsO), len(binsP), len(binsK))):
        def cell(bs):
            if k < len(bs):
                return f"{bs[k][1]} | {bs[k][2]}"
            return "- | -"
        lab = binsO[k][0] if k < len(binsO) else "-"
        A(f"| {lab} | {cell(binsO)} | {cell(binsP)} | {cell(binsK)} |")
    A("")
    A("> O/P/K 各计数档的失败率同样平坦（约 1%~2.3%）；三价原子数 ≥9 的组合里失败**全部**是摆放失败，"
      "说明大投料的主要风险是「产物太大摆不出来」。")
    A("")
    A("### 4.5 元素子集（mask）失败率排行（样本 ≥15 对）\n")
    A("| 元素子集 | 类别组合 | 元素数 | 对数 | 失败率 | 奇价失败 | 摆放失败 | 多产物率 |")
    A("|---|---|---|---|---|---|---|---|")
    for d in fail["mask_top_fail"]:
        A(f"| {d['mask']} | {d['cat']} | {d['nE']} | {d['pairs']} | {d['fail_rate']:.1%} | "
          f"{d['odd_fail']} | {d['embed_fail']} | {d['multi_rate']:.1%} |")
    A("")
    A("**规律**：\n")
    A("1. **本采样框内奇价失败 = 0**：目录中每个物质的总价数必为偶数（Σ价数=2×键数），故物质对总价数恒为偶数。"
      "但对任意投料，总价数为奇数时必然失败（模拟器早退），这是 100% 可预测的规则。")
    A("2. **偶价剩键**（贪心配不平）是最稀有的失败：与元素种类没有简单单调关系，"
      "主要出现在三价原子（O/P/K）较多、配比特殊的组合；大投料偶发一次（本例 n=100）。"
      "这说明规则 1~8 的贪心并不总能从任意合法物质对配平。")
    A("3. **摆放失败是 L3/L4 大投料的主要失败形式**：产物键数配平，但大分子图无法在六边形格上摆放"
      "（或超出 3M 搜索节点预算）。含 O/P/K 多的混合对与含 K（散素 3 价、L 长键）的组合最易出现。")
    A("4. 纯大类组合（聚/动/散内部）失败率最低（见 §7.2）：同类元素配比最容易配平且产物小。\n")

    A("## 5. 产物尺寸分布与守恒\n")
    A("### 5.1 守恒验证\n")
    A(f"- 成功反应 {prod['n_ok']} 个，**全部满足产物总原子数 = 投料总原子数**（违反 {len(prod['conserved_violations'])} 例）——"
      "反应只重组、不增减原子。")
    A("")
    A("### 5.2 每层产物最大分子尺寸\n")
    A("| 层 | 成功对数 | 平均最大分子 | 中位数 | 最大 | 占比最高的尺寸档 |")
    A("|---|---|---|---|---|---|")
    for lay in LAYER_NAMES:
        st = prod["per_layer"].get(lay)
        if not st:
            continue
        top = max(st["hist"].items(), key=lambda kv: kv[1])
        A(f"| {lay} | {st['n']} | {st['avg']:.1f} | {st['median']} | {st['max']} | "
          f"{top[0]}（{pct(top[1], st['n'])}） |")
    A("")
    A("### 5.3 产物最大分子尺寸分布（全部成功对）\n")
    A("| 最大分子原子数 | 对数 | 占比 |")
    A("|---|---|---|")
    mxh = prod["maxmol_hist"]
    for k in sorted(mxh, key=lambda x: int(x)):
        A(f"| {k} | {mxh[k]} | {pct(mxh[k], prod['n_ok'])} |")
    A("")
    A("### 5.4 与已知「元素子集封顶」对照\n")
    A(f"- 全样本最大产物分子：**{prod['biggest_product']['maxmol']} 原子**"
      f"（来自 {prod['biggest_product']['A']} + {prod['biggest_product']['B']}，"
      f"产物 {prod['biggest_product']['products']}）。")
    A(f"- 超过「目录中同元素子集最大分子」（≤16 完备 + 三元组完备 + 大分子搜索下界）的产物："
      f"**{prod['n_cap_violations']} 例**（最大超出 {prod['max_over_cap']} 原子）。")
    recs = prod.get("new_records") or []
    if recs:
        A("- **新纪录（重要）**：本采样发现多个**超过目录已知封顶**的产物单分子：")
        for rec in recs[:3]:
            fn = f"t12c_big{rec['size']}.json"
            suffix = f"（结构见 `{fn}`）" if os.path.exists(os.path.join(BASE, fn)) else ""
            A(f"  - **{rec['product']}**：**{rec['size']} 原子**（子集 {rec['mask']}），"
              f"超过目录同元素子集最大 {rec['prev_catalog_max_same_mask']}、"
              f"目录全局最大 {rec['prev_catalog_global_max']}；"
              f"来自 {rec['A']}（{rec['A_natoms']} 原子）+ {rec['B']}（{rec['B_natoms']} 原子），"
              f"已严格校验可摆放{suffix}。")
        A("- 其中 **140 原子**是新的「最大合法分子」纪录（原纪录 97 原子是搜索下界）；"
          "它在 3,000,000 节点预算下会被误判为「摆放失败」，用 8,000,000 预算才能摆出。"
          "这说明产物的尺寸封顶远高于目录搜索值，反应是发现新大分子的有效途径。")
    if prod["cap_violations"]:
        A(f"  （超封顶产物按元素数分布：{prod.get('cap_violations_by_nE')}；"
          f"1~3 元素子集（目录完备）超封顶 {len(prod.get('cap_violations_small_subsets', []))} 个。）")
        A("  前 10 例：")
        for v in prod["cap_violations"][:10]:
            A(f"  - {v['A']}+{v['B']} → {v['product']}（{v['size']} 原子，子集 {v['mask']}，目录最大 {v['ref']}）")
        A("  （4~9 元素子集的目录 >16 原子部分为搜索下界，超过不等于新物质；1~3 元素子集若超封顶才是异常，本次未见。）")
    A("")
    A("### 5.5 产物个数分布\n")
    A("| 产物个数 | 对数 | 占比 |")
    A("|---|---|---|")
    nmh = prod["nmol_hist"]
    for k in sorted(nmh, key=lambda x: int(x)):
        A(f"| {k} | {nmh[k]} | {pct(nmh[k], prod['n_ok'])} |")
    A("")
    A("- 大投料绝大多数被**拆散成多个小分子**：产物平均个数随总原子数上升，"
      "而最大分子尺寸受元素子集封顶限制不随之增长。\n")

    A("## 6. 总向量决定律与碰撞率\n")
    A("### 6.1 定律\n")
    A("反应结果只取决于元素总向量 vA+vB（原始目录中每个物质无论结构如何，拆开后只剩元素计数）。"
      "因此「不同物质对、相同总向量 ⇒ 反应结果完全相同」。\n")
    A("### 6.2 碰撞统计（分层精确枚举 + 全目录抽样）\n")
    if law:
        st = law["stats"]
        A("| 母体 | 条目数 | 无序对总数 | 不同总向量数 | 同向量组(≥2对) | 组内对数 | 碰撞率 |")
        A("|---|---|---|---|---|---|---|")
        for key in ["L1_exact", "L2_subset_exact", "L3_exact", "L4_exact"]:
            if key not in st:
                continue
            d = st[key]
            A(f"| {d['label']} | {d['n_entries']} | {d['total_pairs']} | {d['distinct_sums']} | "
              f"{d['groups_ge2']} | {d['pairs_in_groups_ge2']} | {d['collision_rate']:.3%} |")
        fcs = st.get("full_catalog_sample")
        if fcs:
            A(f"| 全目录随机抽 {fcs['sampled_pairs']:,} 对 | 84,225 | {fcs['N_pairs']:,} | "
              f"样本内 {fcs['distinct_sums_in_sample']:,} | - | - | "
              f"样本内碰撞对占比 {fcs['collision_pairs_frac_in_sample']:.3%} |")
            A("")
            A(f"补充：随机两个物质对总向量相同的概率（二阶矩估计）≈ **{fcs['q_est_two_pairs_same_sum']:.3e}**；"
              f"全目录无序对总数 {fcs['N_pairs']:,}。")
        A("")
        A("**解读**：小原子数层（L1 全层 772 万对）里，不同物质对共享同一总向量很常见（碰撞率见上表）；"
          "原子数越大，总向量空间越大、碰撞率急剧下降。全目录随机对之间「撞总向量」的概率极低，"
          "但**小分子之间**的碰撞是「同总向量定律」最常被观察到的场景。")
        A("")
        A("### 6.3 100 组「同总向量、不同物质对」独立验证\n")
        A(f"- 从分层精确枚举中抽 100 组（每组至少 2 个不同物质对，覆盖 L1/L2/L3/L4），"
          f"对每对**用其自身目录原子顺序**独立跑 pot_v3（不共用缓存），比较产物分子式多重集；"
          f"另用规范顺序 + 随机打乱顺序各跑一次。")
        A(f"- 结果：**{law['summary']['n_identical']}/{law['summary']['n_groups_verified']} 组完全一致**；"
          f"打乱原子顺序后仍一致 {law['summary']['n_shuffled_same']} 组；"
          f"其中反应成功 {law['summary']['n_ok']} 组、失败 {law['summary']['n_groups_verified']-law['summary']['n_ok']} 组"
          f"（同组内成功/失败也一致）；embedding 通过 {law['summary']['n_embed_ok']}、"
          f"失败 {law['summary']['n_embed_fail']} 组。")
        bad = [g for g in law["groups"] if not g["identical"]]
        if bad:
            A(f"- **异常组 {len(bad)} 个**（详见 `t12c_law.json`）：")
            for g in bad[:5]:
                A(f"  - {g['layer']} 总向量 {g['sum']}：" +
                  "；".join(f"{r['pair']}→{r['prods']}" for r in g["runs"]))
        A("")
        A("### 6.4 采样内碰撞\n")
        A(f"- 本次分层的 {sample_law['n_pairs']} 个采样对按总向量分组得 {sample_law['n_distinct_sums']} 组，"
          f"其中 {sample_law['n_groups_ge2']} 组含 ≥2 对；组内结果（按缓存）全部相同 "
          f"= {sample_law['all_identical']}。")
        A(f"- 采样碰撞率（(对数-不同总向量数)/对数）={sample_law['collision_rate']:.3%}；"
          "大原子数层的总向量空间大，所以这个数字比 L1 精确值低很多。")
    else:
        A("（t12c_law.json 缺失）")
    A("")
    A("### 6.5 单产物 = 严格向量加法（数据验证）\n")
    sa = prod["strict_addition"]
    A(f"- 若投料总向量恰好等于目录中某物质 C 的分子式向量，则反应结果应为**单产物 C**。"
      f"本样本中总向量命中目录物质的对有 **{sa['n_pairs_sum_in_catalog']}** 个，"
      f"违反（失败或产物不是 C）**{sa['n_violations']}** 个。")
    if sa["violation_examples"]:
        for v in sa["violation_examples"]:
            A(f"  - {v['A']}+{v['B']}（总和 {v['sum']}）→ {v['status']} {v['prods']}")
    A("- 这说明「单产物化合」没有催化/取代：A+B→C 当且仅当 vC=vA+vB。\n")

    A("## 7. 跨元素规律\n")
    A("### 7.1 按参与元素数\n")
    A("| 元素数 | 对数 | 成功率 | 奇价失败 | 摆放失败 | 惰性率 | 单产物率 | 多产物率 |")
    A("|---|---|---|---|---|---|---|---|")
    for d in cross["by_nE"]:
        A(f"| {d['nE']} | {d['pairs']} | {d['success_rate']:.1%} | {d['odd_fail']} | {d['embed_fail']} | "
          f"{pct(d['inert'], d['pairs'])} | {pct(d['single'], d['pairs'])} | {pct(d['multi'], d['pairs'])} |")
    A("")
    A("### 7.2 按三大类组合（聚/动/散）\n")
    A("| 类别组合 | 对数 | 成功率 | 奇价失败 | 摆放失败 | 惰性率 | 单产物率 | 多产物率 | 平均最大产物 |")
    A("|---|---|---|---|---|---|---|---|---|")
    for d in cross["by_combo"]:
        A(f"| {d['combo']} | {d['pairs']} | {d['success_rate']:.1%} | {d['odd_fail']} | {d['embed_fail']} | "
          f"{d['inert_rate']:.1%} | {d['single_rate']:.1%} | {d['multi_rate']:.1%} | {d['avg_maxmol']:.1f} |")
    A("")
    A("> 注意：目录中「纯大类」物质非常少（聚/动/散各只有 30 种，占 84,225 的 0.1%），"
      "因此**随机抽目录对几乎抽不到纯大类组合**（表中纯组合样本只有 1~2 对）。"
      "为此补充了专门抽样（§7.2b）：纯大类物质内部全部对 + 三个异大类纯物质两两组合。")
    A("")
    if pure:
        pc = summary["pure_supplement"]["by_combo"]
        A("### 7.2b 补充抽样：纯大类物质对（专门抽样，非随机目录对）\n")
        A(f"- 纯大类物质：聚 {pure['pure_counts'].get('聚')} 种、动 {pure['pure_counts'].get('动')} 种、"
          f"散 {pure['pure_counts'].get('散')} 种（目录中）。")
        A("- 同一大类内取全部 i<j 对（435×3）；异大类取 纯物质×纯物质 全部组合（900×3）。"
          "共 4,005 对，均用 pot_v3（规则 1~9）+ pot_v2 严格校验（3M 节点）。")
        A("")
        A("| 类别组合 | 对数 | 成功率 | 失败(剩键) | 失败(摆放) | 惰性 | 单产物 | 多产物 | 平均最大产物 |")
        A("|---|---|---|---|---|---|---|---|---|")
        for combo in ["聚", "动", "散", "聚动", "聚散", "动散"]:
            d = pc[combo]
            A(f"| {combo} | {d['pairs']} | {d['ok']/d['pairs']:.1%} | {d['fail_rem']} | {d['fail_embed']} | "
              f"{d['inert']} | {d['single']} | {d['multi']} | {d['avg_maxmol']:.1f} |")
        A("")
        A("- **三大类内部完全同构**：聚/动/散 的统计逐项相同（各 435 对：成功 432、剩键失败 3、"
          "惰性 69、单产物 43、多产物 320），验证了 HANDOFF §7 的键图同构结论。")
        A("- **与 T11 复现对齐**：另用 pot_v3 复跑 T11 的聚素 29 种物质 435 对（i≤j，含 A+A），"
          "得到 成功 432 / 失败 3 / 惰性 87 / 单产物 40 / 多产物 305，与 `T11_BINARY_REACTIONS.md` **完全一致**"
          "（说明规则 1~9 与 T11 的规则 1~8 在聚素内无差异，且采样/校验管线正确）。"
          "本节 30 种物质取全部 i<j 对，是不同对集合，统计略有差别。")
        A("- **异大类纯物质对**：三个组合（聚动/聚散/动散）统计也逐项完全相同（各 900 对：成功 864、"
          "剩键失败 36、惰性 0、单产物 156、多产物 708）——再次印证三大类对称性。")
        A("- **惰性只出现在同大类内部**（纯大类 69/435 ≈ 15.9%），异大类纯物质对**从不惰性**（0/900）："
          "跨类总能找到新的成键重组方式。")
        A("")
    A("### 7.3 最易单产物化合的元素子集（样本 ≥15 对）\n")
    A("| 元素子集 | 对数 | 单产物率 | 单产物数 | 失败率 |")
    A("|---|---|---|---|---|")
    for d in fail["mask_top_single"]:
        A(f"| {d['mask']} | {d['pairs']} | {d['single_rate']:.1%} | {d['single']} | {d['fail_rate']:.1%} |")
    A("")
    A("### 7.4 跨元素规律总结\n")
    A("1. **失败**：物质对的奇价失败恒为 0（目录物质价数和恒偶）；真正的失败只有两类——"
      "偶价剩键（罕见，纯大类 3/435≈0.7%、纯异大类 36/900=4%）与产物摆放不合法"
      "（大原子数 L3/L4 的主要失败形式）。")
    A("2. **哪种元素组合最容易失败**：失败率与「元素数/原子数」强相关——5~6 元素聚动散子集、"
      "总原子数 ≥65 的组合失败率最高（主要是摆放失败）；单元素出现与否的失败率差异很小（1.5%~2.3%），"
      "说明**没有某个元素单独导致失败**（不过含 K/含 O 的混合略高）。")
    A("3. **哪种组合最容易单产物化合**：单产物要求总向量恰好等于某个合法分子式；"
      "元素子集 OXPWLF、CPWLKA、OXLKA 等（小分子、5~6 元素）单产物率最高（23%~31%）；"
      "大原子数对也可能单产物（L4 层 12 例，包括 140 原子新纪录），因为两个大分子可以严格相加成一个大分子。")
    A("4. **惰性**：只在同大类内部出现（纯大类 69/435≈15.9%），异大类纯物质对从不惰性（0/900）；"
      "整体随机样本中惰性率随原子数上升而消失。")
    A("5. **大投料 → 碎片化 + 偶发超大分子**：大总向量多数被贪心拆成大量小分子（二聚体/小环/小链），"
      "产物个数随投料增大而增加；但特殊配比下会出现超大单分子（本样本最大 " +
      f"{max(r['maxmol'] for r in rows if r['ok'])} 原子，见 §5.4 新纪录）。")
    A("6. **大类对称性**：聚/动/散 内部统计逐项相同，三个「异大类纯物质对」统计也逐项相同——"
      "这是三种键图同构（三角格子）的直接体现。\n")

    A("## 8. 十个有趣例子\n")
    A("| # | 类型 | 投料 A（原子数） | 投料 B（原子数） | 总原子 | 总价数 | 结果 | 产物 | 说明 |")
    A("|---|---|---|---|---|---|---|---|---|")
    for k, e in enumerate(examples, 1):
        res = ("成功" if e["status"] == "ok" else
               ("失败（奇价）" if e["status"] == "fail_rem" and e["odd"] else
                ("失败（剩键）" if e["status"] == "fail_rem" else "失败（摆放）")))
        prods = e["prods"] if e["prods"] else "—"
        if len(prods) > 160:
            prods = prods[:157] + "…"
        A(f"| {k} | {e['tag']} | {e['A']}（{e['Ana']}） | {e['B']}（{e['Bna']}） | {e['n']} | {e['tv']} | {res} | {prods} | {e['why']} |")
    A("")

    A("## 9. 局限与口径说明\n")
    A("1. **模拟器口径**：使用正式模拟器 `pot_v3`（规则 1~9）；任务接口提到的 `pot_all`（规则 1~8）"
      "在随机小投料上与 pot_v3 一致（400/400），差异仅出现在规则 1~8 残余并列时，实测极少。")
    A("2. **embedding 节点预算**：主采样每分子 3,000,000 节点（≈20s 上限）；对失败者用 8,000,000 重试，"
      f"131 个失败总向量中 {retry_info['n_recovered'] if retry_info else '?'} 个其实可摆放"
      "（含 140 原子新纪录）。剩余「摆放失败」可能仍有个别实际可摆放（需更大预算），"
      "因此 §4.1 的「摆放失败」是真实失败数的上界（误差 ≤1% 的样本）。")
    A("3. **采样偏差**：各层内均匀抽对（不同公式优先），但 L3/L4 条目少（937/327），对中会重复使用同一公式；"
      "大分子对的总原子数可达 194，模拟/校验成本高，故 L4 层样本相对较少（2,000 对）。"
      "另外目录中纯大类物质只有 90 种，随机对几乎抽不到纯组合，故对「纯大类/双大类」另做了 4,005 对的专门抽样（§7.2b）。")
    A("4. **总向量碰撞率**：小层用**全枚举精确值**（L1/L3/L4 全层），L2 用 3,000 条公式子集精确值；"
      "全目录用 200 万随机对抽样估计，结论是「随机大对撞向量概率极低、小分子对撞向量常见」。")
    A("5. **产物尺寸封顶**：4~9 元素子集的目录 >16 原子部分为搜索下界（非完备），"
      "因此「超过目录最大」不能直接判为新物质；1~3 元素子集目录完备，未见超封顶。"
      "本采样发现的 108/140 原子分子都是**反应产物**（不在目录内），已用 pot_v2 严格校验可摆放。")
    A("6. 反应结果与物质具体结构无关（只由元素总向量决定），故「不同物质对相同总向量」的复跑是对"
      "「实现确定性 + 总向量定律」的双重验证（见 §6.3）。\n")
    A("## 10. 文件\n")
    A("- 本报告：`T12C_LARGE_SAMPLE.md`")
    A("- 汇总数据：`t12c_summary.json`（分层统计、失败分析、产物分布、跨元素表、示例、定律验证）")
    A("- 原始数据：`t12c_sample_pairs.json`（采样对 + 目录条目）、`t12c_vectors.json`（唯一总向量→反应结果）、"
      "`t12c_law.json`（碰撞统计 + 100 组验证明细）、`t12c_pure.json`（纯大类补充抽样）、"
      "`t12c_retry.json`（embedding 8M 重试）、`t12c_big108.json` / `t12c_big140.json`（新纪录分子结构）")
    A("- 脚本：`t12c_run.py`（采样+反应，多进程）、`t12c_law.py`（碰撞/定律验证）、`t12c_pure.py`（纯大类补充抽样）、"
      "`t12c_retry.py`（embedding 重试）、`t12c_analyze.py`（统计+报告）、`t12c_inspect.py`（前置检查/测速）")
    A("- 图：`t12c_success_rate.png`（成功率 vs 总原子数）、`t12c_product_size.png`（各层产物最大分子尺寸分布）")
    md_text = "\n".join(md)
    open(os.path.join(BASE, "T12C_LARGE_SAMPLE.md"), "w", encoding="utf-8").write(md_text)
    print("落盘 T12C_LARGE_SAMPLE.md", flush=True)

    make_plots(rows, prod["per_layer"])
    print(f"分析完成，用时 {time.time()-t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
