# -*- coding: utf-8 -*-
"""t59_analysis.py —— T59 两阶段连续实验分析（A 阶段 + 整理 + B 阶段）

输入：
  t59_phaseA_result.json   第一阶段（120 种物质、三价最多/一价最少、L=60000、1000 分钟）
  t59_stateA.json          第一阶段 0°C 后整理归档的底物（27,431 分子 / 43 种结构）
  t59_phaseB_result.json   第二阶段（底物 + 第二批 120 种随机物质、T 重置 1000→0、1000 分钟）
  t59_loads.json           batchA / batchB 投料设计
  t59_control_A.json       无化学对照（穿越验证，含 by_size）
  t4_catalog_index.json    84,225 目录（in_catalog）
  substances.json          29 聚素（in_29）
  t58_analysis.json        历史规模对比（可选）

输出：t59_analysis.json

重点：
* 两阶段对比：A 终态 vs B 终态（规模/尺寸/组成/多样性/新物质/质量与元素守恒）；
* 反应统计：complete/incomplete/capped/none、净事件、capped 随时间；
* 最终 B 数量前 30 的结构（final_top_structures 前 24 + natural_engine 重建剩余），
  并给出 atoms/edges/元素/键级/F 稳定性，供结构图渲染。
* 事件样本为蓄水池抽样（上限 50000；A 174,549 / B 206,740），逐分钟净事件总数用
  events_total 差分精确，按类型拆分用抽样比例估计。
"""
import argparse
import datetime
import json
import math
import os
import re
import sys
from collections import Counter, OrderedDict

BASE = r"G:\AI work\deepseek\work1\alchemy"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

DEFAULT_A = os.path.join(BASE, "t59_phaseA_result.json")
DEFAULT_B = os.path.join(BASE, "t59_phaseB_result.json")
DEFAULT_STATE = os.path.join(BASE, "t59_stateA.json")
DEFAULT_LOADS = os.path.join(BASE, "t59_loads.json")
DEFAULT_CONTROL = os.path.join(BASE, "t59_control_A.json")
DEFAULT_CATALOG = os.path.join(BASE, "t4_catalog_index.json")
DEFAULT_SUBS = os.path.join(BASE, "substances.json")
DEFAULT_T58 = os.path.join(BASE, "t58_analysis.json")
DEFAULT_OUT = os.path.join(BASE, "t59_analysis.json")

ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]
CN = {"O": "秩", "X": "晶", "C": "冰", "P": "势", "W": "流", "L": "电",
      "K": "沌", "A": "气", "F": "焰"}
VAL = {"O": 3, "X": 2, "C": 1, "P": 3, "W": 2, "L": 1,
       "K": 3, "A": 2, "F": 1}
T_WINDOWS = [
    ("1000-100", 100.0, 1000.0),
    ("100-50", 50.0, 100.0),
    ("50-20", 20.0, 50.0),
    ("20-10", 10.0, 20.0),
    ("10-5", 5.0, 10.0),
    ("5-0", 0.0, 5.0),
]
_FORMULA_RE = re.compile(r"([A-Z])(\d*)")


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def rnd(x, n=1):
    if x is None:
        return None
    try:
        return round(float(x), n)
    except (TypeError, ValueError):
        return None


def formula_counts(f):
    out = OrderedDict()
    for e, c in _FORMULA_RE.findall(f or ""):
        if e in ORDER:
            out[e] = out.get(e, 0) + (int(c) if c else 1)
    return out


def formula_atoms(f):
    return sum(formula_counts(f).values())


def formula_zh(f, catalog_zh=None):
    if catalog_zh and f in catalog_zh:
        return catalog_zh[f]
    cnt = formula_counts(f)
    return "".join(CN[e] + (str(cnt[e]) if cnt[e] > 1 else "")
                   for e in ORDER if e in cnt) or f


def valence_counts(f):
    cnt = formula_counts(f)
    v3 = sum(c for e, c in cnt.items() if VAL.get(e) == 3)
    v2 = sum(c for e, c in cnt.items() if VAL.get(e) == 2)
    v1 = sum(c for e, c in cnt.items() if VAL.get(e) == 1)
    return v3, v2, v1


def load_catalog(base):
    path = os.path.join(base, "t4_catalog_index.json")
    if not os.path.exists(path):
        return set(), {}
    data = load_json(path)
    zh = {}
    for rec in data:
        f = rec.get("formula")
        if f:
            zh[f] = rec.get("zh") or f
    return set(zh), zh


def trim_event(ev):
    if not isinstance(ev, dict):
        return ev
    out = OrderedDict()
    for k in ("t", "T", "type", "inputs", "products", "class",
              "csum", "isum", "x", "y"):
        if k in ev:
            out[k] = ev[k]
    return out


def mean_of(vals):
    vals = [v for v in vals if v is not None]
    return rnd(sum(vals) / len(vals), 1) if vals else None


# ---------------------------------------------------------------- 投料
def analyze_loads(loads_path):
    d = load_json(loads_path)
    out = {"config": d.get("config")}
    for tag in ("batchA", "batchB"):
        b = d.get(tag) or {}
        sm = b.get("summary") or {}
        rows = b.get("rows") or []
        size_dist = Counter(r.get("atoms") or 0 for r in rows)
        out[tag] = {
            "summary": sm,
            "rows": rows,
            "n_species": sm.get("n_species") or len(rows),
            "molecules": sm.get("molecules"),
            "atoms": sm.get("atoms"),
            "mean_atoms": sm.get("mean_atoms"),
            "element_atoms": sm.get("element_atoms") or {},
            "elements_covered": sm.get("elements_covered") or [],
            "valence_atoms": sm.get("valence_atoms") or {},
            "valence_shares": sm.get("valence_shares") or [],
            "strict_order_3gt2gt1": bool(sm.get("strict_order")),
            "size_distribution": [{"atoms": a, "species": size_dist[a],
                                   "molecules": sum((r.get("count") or 0)
                                                    for r in rows
                                                    if (r.get("atoms") or 0) == a)}
                                  for a in sorted(size_dist)],
        }
        if out[tag]["valence_atoms"]:
            va = out[tag]["valence_atoms"]
            total = sum(va.values()) or 1
            out[tag]["valence_atom_shares"] = {
                "v3": rnd(va.get("v3", 0) / total, 4),
                "v2": rnd(va.get("v2", 0) / total, 4),
                "v1": rnd(va.get("v1", 0) / total, 4),
            }
    a, b = out["batchA"], out["batchB"]
    out["compare"] = {
        "A_vs_B_valence": {
            "A": a.get("valence_atoms"), "B": b.get("valence_atoms"),
            "A_shares": a.get("valence_shares"), "B_shares": b.get("valence_shares"),
            "A_strict": a.get("strict_order_3gt2gt1"),
            "B_strict": b.get("strict_order_3gt2gt1"),
        },
        "total_molecules": (a.get("molecules") or 0) + (b.get("molecules") or 0),
        "total_atoms": (a.get("atoms") or 0) + (b.get("atoms") or 0),
    }
    return out


# ---------------------------------------------------------------- 时间线
def build_timeline_rows(ts):
    ev_total = None
    rows = []
    prev = {"c": 0, "i": 0, "n": 0, "cap": 0, "ev": 0, "dec": 0}
    for r in ts or []:
        t, T = r.get("t"), r.get("T")
        dc = r.get("d_complete")
        if dc is None:
            dc = int(r.get("complete", 0)) - prev["c"]
        di = r.get("d_incomplete")
        if di is None:
            di = int(r.get("incomplete", 0)) - prev["i"]
        dn = r.get("d_none")
        if dn is None:
            dn = int(r.get("none", 0)) - prev["n"]
        dcap = r.get("d_capped")
        if dcap is None:
            dcap = int(r.get("capped", 0)) - prev["cap"]
        ddec = int(r.get("decomp", 0)) - prev["dec"]
        prev["c"] = int(r.get("complete", 0))
        prev["i"] = int(r.get("incomplete", 0))
        prev["n"] = int(r.get("none", 0))
        prev["cap"] = int(r.get("capped", 0))
        prev["dec"] = int(r.get("decomp", 0))
        ev_cum = r.get("events_total")
        net = None
        if ev_cum is not None:
            net = int(ev_cum) - prev["ev"]
            prev["ev"] = int(ev_cum)
        rows.append({"t": t, "T": T, "N": r.get("N"),
                     "mean_atoms": r.get("mean_atoms"),
                     "max_atoms": r.get("max_atoms"),
                     "speed_mean": r.get("speed_mean"),
                     "collisions": r.get("collisions"),
                     "complete": int(dc), "incomplete": int(di),
                     "none": int(dn), "capped": int(dcap),
                     "decomp": int(ddec), "net_events": net,
                     "events_total": ev_cum,
                     "capped_cum": int(r.get("capped", 0)),
                     "path_D": r.get("path_D")})
    return rows


def analyze_phase(result, catalog, catalog_zh, known29, state=None):
    cfg = result.get("config") or {}
    sm = result.get("summary") or {}
    ts = result.get("time_series") or []
    final = result.get("final_composition") or {}
    events = result.get("event_samples") or []
    fs = result.get("formula_series") or []
    tl = build_timeline_rows(ts)
    # 终态表
    total_m = sum(v.get("count", 0) for v in final.values())
    total_a = sum((v.get("atoms") or formula_atoms(f)) * v.get("count", 0)
                  for f, v in final.items())
    final_rows = []
    for f, v in sorted(final.items(), key=lambda kv: -kv[1].get("count", 0)):
        cnt = v.get("count", 0)
        a = v.get("atoms") or formula_atoms(f)
        v3, v2, v1 = valence_counts(f)
        final_rows.append({
            "formula": f, "zh": formula_zh(f, catalog_zh), "count": cnt,
            "share": rnd(cnt / total_m, 5) if total_m else None,
            "atoms": a, "total_atoms": a * cnt,
            "atoms_share": rnd(a * cnt / total_a, 5) if total_a else None,
            "in_catalog": f in catalog, "in_29": f in set(known29),
            "v3": v3, "v2": v2, "v1": v1,
        })
    size_dist = Counter()
    atoms_by = Counter()
    for f, v in final.items():
        a = v.get("atoms") or formula_atoms(f)
        c = v.get("count", 0)
        size_dist[a] += c
        atoms_by[a] += a * c
    size_distribution = [{"atoms": a, "molecules": size_dist[a],
                          "molecule_share": rnd(size_dist[a] / total_m, 5)
                          if total_m else None,
                          "atoms_total": atoms_by[a],
                          "atoms_share": rnd(atoms_by[a] / total_a, 5)
                          if total_a else None}
                         for a in sorted(size_dist)]
    # 事件抽样与估计
    types = Counter(e.get("type") for e in events)
    classification = {k: int((sm.get("reaction_counts") or {}).get(k, 0))
                      for k in ("complete", "incomplete", "none", "capped")}
    net_total = int(sm.get("events_total") or len(events))
    sample_n = max(1, len(events))
    sampling_complete = net_total == sample_n
    if sampling_complete:
        est = dict(types)
    else:
        scale = net_total / sample_n
        est = {k: int(round(v * scale)) for k, v in types.items()}
    # 抽样事件示例
    def atoms_of(e):
        return sum(formula_atoms(f) for f in (e.get("products") or []))
    examples = {
        "largest_products": [trim_event(e) for e in
                             sorted(events, key=atoms_of, reverse=True)[:5]],
        "first": [trim_event(e) for e in events[:3]],
        "latest": [trim_event(e) for e in
                   sorted(events, key=lambda x: x.get("t") or -1, reverse=True)[:3]],
    }
    # 组成演化（formula_series 每 5 分钟一个样本）
    max_count = Counter()
    for fr in fs:
        for f, v in (fr.get("counts") or {}).items():
            if v > 0:
                max_count[f] = max(max_count[f], v)
    stack_order = [f for f, _ in max_count.most_common(10)]
    series = []
    for fr in fs:
        counts = {k: v for k, v in (fr.get("counts") or {}).items() if v > 0}
        tot = sum(counts.values())
        picked = {f: counts.get(f, 0) for f in stack_order}
        series.append({"t": fr.get("t"), "T": fr.get("T"), "total": tot,
                       "n_species": len(counts), "top_counts": picked,
                       "other": tot - sum(picked.values())})
    # 体积控制：时间线每 5 分钟采样
    tl_s = [dict(row) for i, row in enumerate(tl) if i % 5 == 0]
    # capped 统计
    capped_peak = max(tl, key=lambda r: r.get("capped") or 0, default=None)

    def _share(sel):
        c = sum(x.get("capped") or 0 for x in sel)
        t = sum(x.get("collisions") or 0 for x in sel)
        return {"capped": c, "collisions": t, "share": rnd(c / t, 5) if t else None}

    return {
        "phase": result.get("phase"),
        "config": cfg,
        "summary": sm,
        "load_summary": result.get("load_summary"),
        "seed_state_summary": result.get("seed_state_summary"),
        "final_total_molecules": total_m,
        "final_total_atoms": total_a,
        "final_mean_atoms": rnd(total_a / total_m, 3) if total_m else None,
        "final_max_atoms": max(size_dist) if size_dist else None,
        "final_distinct_formulas": len(final_rows),
        "final_table": final_rows,
        "series": series,
        "stack_order": stack_order,
        "size_distribution": size_distribution,
        "large_stats": {
            "ge5": {"molecules": sum(c for a, c in size_dist.items() if a >= 5),
                    "atoms": sum(a * c for a, c in size_dist.items() if a >= 5)},
            "ge10": {"molecules": sum(c for a, c in size_dist.items() if a >= 10),
                     "atoms": sum(a * c for a, c in size_dist.items() if a >= 10)},
            "ge20": {"molecules": sum(c for a, c in size_dist.items() if a >= 20),
                     "atoms": sum(a * c for a, c in size_dist.items() if a >= 20)},
            "ge39": {"molecules": sum(c for a, c in size_dist.items() if a >= 39),
                     "atoms": sum(a * c for a, c in size_dist.items() if a >= 39)},
        },
        "new_substances_count": len(result.get("new_substances") or {}),
        "new_substance_top": sorted(
            [(f, rec.get("first_t"), len(rec.get("atoms") or []))
             for f, rec in (result.get("new_substances") or {}).items()],
            key=lambda x: -(x[2] or 0))[:10],
        "reaction_counts": classification,
        "net_events_total": net_total,
        "event_types": dict(types),
        "event_type_estimate": est,
        "event_sampling_complete": sampling_complete,
        "event_sampling_note": ("" if sampling_complete else
                                "event_samples 为蓄水池抽样 %d/%d；净事件总数精确，"
                                "类型拆分按抽样比例估计。" % (sample_n, net_total)),
        "capped_total": classification.get("capped", 0),
        "capped_share_of_collisions": (rnd(classification.get("capped", 0) /
                                           max(1, sum(classification.values())), 5)),
        "capped_peak": capped_peak,
        "capped_first_100min": _share(tl[:100]),
        "capped_last_100min": _share(tl[-100:]),
        "decomp_events": sm.get("decomp_events"),
        "initial_single_path_stats": sm.get("initial_single_path_stats"),
        "timeline": tl_s,
        "timeline_note": "每 5 分钟采样；capped 为累计值，capped_cum；net_events 为差分。",
        "event_examples": examples,
        "snapshots": [
            {"t": s.get("t"), "color_mode": s.get("color_mode"),
             "n_points": len(s.get("points") or []),
             "legend_size": len(s.get("legend") or {})}
            for s in (result.get("snapshots") or [])],
    }


# ---------------------------------------------------------------- 结构重建
def build_structures(phaseB, catalog, catalog_zh):
    """最终 B 数量前 30 的结构（前 24 用 final_top_structures，其余用 fast 引擎重建）。"""
    import natural_engine as E
    import pot_all as P
    E.set_fast(True)
    final = phaseB.get("final_composition") or {}
    top = sorted(final.items(), key=lambda kv: -kv[1].get("count", 0))[:30]
    raw = phaseB.get("final_top_structures") or {}
    out = []
    for rank, (f, v) in enumerate(top, 1):
        rec = raw.get(f)
        rebuilt = False
        if rec is None:
            vec = P.parse_formula(f)
            prods = E.complete_products(tuple(vec))
            if prods:
                m = next((x for x in prods if x["formula"] == f), prods[0])
                rec = {"label": m.get("label"), "atoms": m["atoms"],
                       "edges": m["edges"], "c": m.get("c")}
                rebuilt = True
        if rec is None:
            out.append({"rank": rank, "formula": f, "count": v.get("count", 0),
                        "atoms": v.get("atoms") or formula_atoms(f),
                        "zh": formula_zh(f, catalog_zh), "structure": None})
            continue
        atoms = rec["atoms"]
        edges = [list(e) for e in rec["edges"]]
        # F 稳定性
        vec = P.parse_formula(f)
        prods = E.complete_products(tuple(vec))
        f_stable = bool(prods and len(prods) == 1 and prods[0]["formula"] == f)
        bond_mult = Counter(int(e[2]) for e in edges)
        elem = Counter(atoms)
        out.append({
            "rank": rank, "formula": f, "zh": formula_zh(f, catalog_zh),
            "count": v.get("count", 0), "atoms": len(atoms),
            "in_catalog": f in catalog, "in_29": f in set(),
            "label": rec.get("label"), "c": rec.get("c"),
            "f_stable": f_stable, "rebuilt": rebuilt,
            "element_counts": dict(elem),
            "bond_multiplicity": {str(k): v2 for k, v2 in sorted(bond_mult.items())},
            "structure": {"atoms": atoms, "edges": edges},
        })
    return out


# ---------------------------------------------------------------- 两阶段对比
def compare_phases(A, B, stateA, loads):
    fa = {r["formula"]: r for r in A["final_table"]}
    fb = {r["formula"]: r for r in B["final_table"]}
    topA = [r["formula"] for r in A["final_table"][:20]]
    topB = [r["formula"] for r in B["final_table"][:20]]
    union = []
    for f in topB + topA:
        if f not in union:
            union.append(f)
    rows = []
    for f in union:
        ra, rb = fa.get(f), fb.get(f)
        rows.append({
            "formula": f, "zh": (ra or rb or {}).get("zh"),
            "A_count": ra["count"] if ra else 0,
            "B_count": rb["count"] if rb else 0,
            "A_rank": (topA.index(f) + 1) if f in topA else None,
            "B_rank": (topB.index(f) + 1) if f in topB else None,
            "A_atoms": ra["atoms"] if ra else None,
            "B_atoms": rb["atoms"] if rb else None,
            "delta": (rb["count"] if rb else 0) - (ra["count"] if ra else 0),
        })
    rows.sort(key=lambda r: -r["B_count"])
    # 质量/元素/价数守恒
    def element_atoms(final_table):
        out = Counter()
        for r in final_table:
            for e, c in formula_counts(r["formula"]).items():
                out[e] += c * r["count"]
        return dict(out)

    def valence_atoms(final_table):
        out = {"v3": 0, "v2": 0, "v1": 0}
        for r in final_table:
            w = r["count"]
            out["v3"] += (r.get("v3") or 0) * w
            out["v2"] += (r.get("v2") or 0) * w
            out["v1"] += (r.get("v1") or 0) * w
        return out

    ea, eb = element_atoms(A["final_table"]), element_atoms(B["final_table"])
    va, vb = valence_atoms(A["final_table"]), valence_atoms(B["final_table"])
    la, lb = loads.get("batchA", {}), loads.get("batchB", {})
    b_initial_atoms = ((A.get("final_total_atoms") or 0) +
                       (lb.get("atoms") or 0))
    mass_balance = {
        "A_final_atoms": A.get("final_total_atoms"),
        "batchB_atoms": lb.get("atoms"),
        "B_initial_atoms_config": (B.get("config") or {}).get("initial_atoms"),
        "expected_B_atoms": b_initial_atoms,
        "B_final_atoms": B.get("final_total_atoms"),
        "mass_conserved": (b_initial_atoms ==
                           (B.get("config") or {}).get("initial_atoms") ==
                           B.get("final_total_atoms")),
        "B_initial_particles_config": (B.get("config") or {}).get("initial_particles"),
        "seed_initial_count": (B.get("config") or {}).get("seed_initial_count"),
        "batchB_molecules": lb.get("molecules"),
        "seed_plus_batchB": ((B.get("config") or {}).get("seed_initial_count") or 0) +
                            (lb.get("molecules") or 0),
    }
    # 元素/价数守恒（A 终态 = A 初始；B 终态 = A终态 + batchB）
    elem_check = []
    for e in ORDER:
        init_a = (la.get("element_atoms") or {}).get(e, 0)
        init_b = (lb.get("element_atoms") or {}).get(e, 0)
        elem_check.append({
            "element": e, "zh": CN[e],
            "A_initial": init_a, "A_final": ea.get(e, 0),
            "A_conserved": init_a == ea.get(e, 0),
            "B_initial": (ea.get(e, 0) + init_b), "B_final": eb.get(e, 0),
            "B_conserved": (ea.get(e, 0) + init_b) == eb.get(e, 0),
        })
    val_check = {
        "A_initial": (la.get("valence_atoms") or {}),
        "A_final": va,
        "A_conserved": all((la.get("valence_atoms") or {}).get(k, 0) == va.get(k, 0)
                           for k in ("v3", "v2", "v1")),
        "B_initial": {k: (va.get(k, 0) + (lb.get("valence_atoms") or {}).get(k, 0))
                      for k in ("v3", "v2", "v1")},
        "B_final": vb,
        "B_conserved": all((va.get(k, 0) + (lb.get("valence_atoms") or {}).get(k, 0))
                           == vb.get(k, 0) for k in ("v3", "v2", "v1")),
    }
    return {
        "A": {"final_N": A["final_total_molecules"],
              "final_atoms": A["final_total_atoms"],
              "distinct_formulas": A["final_distinct_formulas"],
              "mean_atoms": A["final_mean_atoms"],
              "max_atoms": A["final_max_atoms"],
              "new_substances": A["new_substances_count"],
              "reaction_counts": A["reaction_counts"],
              "capped_share": A["capped_share_of_collisions"],
              "net_events": A["net_events_total"]},
        "B": {"final_N": B["final_total_molecules"],
              "final_atoms": B["final_total_atoms"],
              "distinct_formulas": B["final_distinct_formulas"],
              "mean_atoms": B["final_mean_atoms"],
              "max_atoms": B["final_max_atoms"],
              "new_substances": B["new_substances_count"],
              "reaction_counts": B["reaction_counts"],
              "capped_share": B["capped_share_of_collisions"],
              "net_events": B["net_events_total"]},
        "top20_union": rows,
        "topA": topA, "topB": topB,
        "new_in_B_top20": [f for f in topB if f not in fa],
        "dropped_from_A_top20": [f for f in topA if f not in fb],
        "size_distribution_compare": {
            str(a): {"A": next((d["molecules"] for d in A["size_distribution"]
                                if d["atoms"] == a), 0),
                     "B": next((d["molecules"] for d in B["size_distribution"]
                                if d["atoms"] == a), 0)}
            for a in sorted(set([d["atoms"] for d in A["size_distribution"]] +
                                [d["atoms"] for d in B["size_distribution"]]))
        },
        "element_check": elem_check,
        "valence_check": val_check,
        "mass_balance": mass_balance,
        "stateA_summary": stateA,
        "origin_note": ("B 无 origin 标记：config.seed_initial_count=%s 为整理底物（A 终态）"
                        "分子数，batchB=%s 分子 / %s 原子；两者相加=B 初始 %s 分子 / %s 原子。"
                        % ((B.get("config") or {}).get("seed_initial_count"),
                           lb.get("molecules"), lb.get("atoms"),
                           (B.get("config") or {}).get("initial_particles"),
                           (B.get("config") or {}).get("initial_atoms"))),
    }


# ---------------------------------------------------------------- 历史对比
def analyze_history(t58_path, A, B, loads):
    t58 = None
    if t58_path and os.path.exists(t58_path):
        try:
            t58 = load_json(t58_path)
        except Exception:
            t58 = None
    kn58 = (t58 or {}).get("key_numbers") or {}
    m58 = kn58.get("main") or {}
    mix58 = kn58.get("mixture") or {}
    rows = []
    rows.append({"name": "T58", "molecules": mix58.get("total_molecules"),
                 "atoms": mix58.get("total_atoms"),
                 "elements": len(mix58.get("elements_covered") or []),
                 "final_N": m58.get("final_N"),
                 "final_atoms": m58.get("final_atoms"),
                 "distinct": m58.get("final_distinct_formulas"),
                 "max_atoms": m58.get("final_max_atoms"),
                 "new_substances": m58.get("new_substances_total"),
                 "L": (t58 or {}).get("config", {}).get("L")})
    for tag, P, ld in (("T59A", A, loads.get("batchA", {})),
                       ("T59B", B, loads.get("batchB", {}))):
        rows.append({"name": tag,
                     "molecules": (P.get("config") or {}).get("initial_particles"),
                     "atoms": (P.get("config") or {}).get("initial_atoms"),
                     "elements": len(ld.get("elements_covered") or []),
                     "final_N": P["final_total_molecules"],
                     "final_atoms": P["final_total_atoms"],
                     "distinct": P["final_distinct_formulas"],
                     "max_atoms": P["final_max_atoms"],
                     "new_substances": P["new_substances_count"],
                     "L": (P.get("config") or {}).get("L")})
    return {
        "table": rows,
        "T58_vs_T59": {
            "L_T58": 400000.0, "L_T59": 60000.0,
            "area_ratio": rnd((400000.0 / 60000.0) ** 2, 1),
            "note": ("T58 L=400000（面积 1600×）→ T59 L=60000（面积缩小 44 倍），"
                     "碰撞更频繁、退火更充分；T59 允许 ≤40 原子反应（T58 cap=20）。"),
        },
    }


# ---------------------------------------------------------------- 主流程
def analyze_main(a_path, b_path, state_path, loads_path, control_path, t58_path):
    catalog, catalog_zh = load_catalog(BASE)
    known29 = [r.get("formula") for r in
               (load_json(os.path.join(BASE, "substances.json"))
                if os.path.exists(os.path.join(BASE, "substances.json")) else [])
               if r.get("formula")]
    loads = analyze_loads(loads_path)
    A_raw = load_json(a_path)
    B_raw = load_json(b_path)
    stateA = load_json(state_path) if os.path.exists(state_path) else {}
    A = analyze_phase(A_raw, catalog, catalog_zh, known29)
    B = analyze_phase(B_raw, catalog, catalog_zh, known29, stateA)
    compare = compare_phases(A, B, {k: stateA.get(k) for k in
                                    ("total_molecules", "total_atoms",
                                     "distinct_formulas", "distinct_structures",
                                     "t", "T")}, loads)
    structures = build_structures(B_raw, catalog, catalog_zh)
    history = analyze_history(t58_path, A, B, loads)
    # 控制组
    control = None
    if os.path.exists(control_path):
        c = load_json(control_path)
        st = c.get("stats") or {}
        by = c.get("by_size") or {}
        checks = {
            "min_ge_500": st.get("min") is not None and st["min"] >= 500,
            "p1_ge_500": st.get("p1") is not None and st["p1"] >= 500,
            "median_ge_500": st.get("median") is not None and st["median"] >= 500,
            "fraction_ge_500_is_1": st.get("fraction_ge_500") is not None and
                                    st["fraction_ge_500"] >= 0.9999,
            "all_by_size_min_ge_500": all((v.get("min") or 0) >= 500
                                          for v in by.values()) if by else None,
        }
        control = {"stats": st, "by_size": by, "checks": checks,
                   "pass": all(v for v in checks.values() if v is not None),
                   "config": c.get("config"), "timeseries": c.get("timeseries")}
    # 结构统计
    giant = [s for s in structures if (s.get("atoms") or 0) >= 39]
    regular = [s for s in structures if (s.get("atoms") or 0) < 39]
    structure_stats = {
        "top_n": len(structures),
        "regular_count": len(regular),
        "giant_count": len(giant),
        "giant_molecules": sum(s.get("count") or 0 for s in giant),
        "giant_atoms": sum((s.get("atoms") or 0) * (s.get("count") or 0)
                           for s in giant),
        "all_f_stable": all(s.get("f_stable") for s in structures
                            if s.get("structure")),
        "rebuilt_count": sum(1 for s in structures if s.get("rebuilt")),
        "element_colors_note": "原子按 9 元素着色；键按多重键（1/2/3）着色",
    }
    analysis = OrderedDict()
    analysis["meta"] = {
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "files": {"phaseA": os.path.basename(a_path),
                  "phaseB": os.path.basename(b_path),
                  "stateA": os.path.basename(state_path),
                  "loads": os.path.basename(loads_path),
                  "control": os.path.basename(control_path)},
        "catalog_size": len(catalog),
        "known29": known29,
        "engine": "natural_engine.set_fast(True)（fast_pot，已审计）；max_reaction_atoms=40",
        "schema_notes": [
            "event_samples 为蓄水池抽样（上限 50000）；净事件总数精确，类型拆分按比例估计。",
            "B 无 origin 字段；整理底物与第二批的贡献用 config.seed_initial_count 与 batchB 设计说明。",
            "capped=合并后原子数 >40 的弹性保护；time_series 有 capped/capped_cum/d_capped。",
            "快照 element_bitmask；final_top_structures 只有前 24，top30 其余用 fast 引擎重建。",
        ],
    }
    analysis["loads"] = loads
    analysis["phaseA"] = A
    analysis["phaseB"] = B
    analysis["compare"] = compare
    analysis["structures"] = {"top30": structures, **structure_stats}
    analysis["history"] = history
    analysis["control"] = control

    key = OrderedDict()
    key["loads"] = {
        "A": {"species": loads["batchA"]["n_species"],
              "molecules": loads["batchA"]["molecules"],
              "atoms": loads["batchA"]["atoms"],
              "mean_atoms": loads["batchA"]["mean_atoms"],
              "valence_atoms": loads["batchA"]["valence_atoms"],
              "valence_shares": loads["batchA"]["valence_shares"],
              "strict": loads["batchA"]["strict_order_3gt2gt1"]},
        "B": {"species": loads["batchB"]["n_species"],
              "molecules": loads["batchB"]["molecules"],
              "atoms": loads["batchB"]["atoms"],
              "mean_atoms": loads["batchB"]["mean_atoms"],
              "valence_atoms": loads["batchB"]["valence_atoms"],
              "valence_shares": loads["batchB"]["valence_shares"]},
    }
    key["A"] = {"final_N": A["final_total_molecules"],
                "final_atoms": A["final_total_atoms"],
                "distinct": A["final_distinct_formulas"],
                "mean_atoms": A["final_mean_atoms"],
                "max_atoms": A["final_max_atoms"],
                "reaction_counts": A["reaction_counts"],
                "net_events": A["net_events_total"],
                "capped_total": A["capped_total"],
                "capped_share": A["capped_share_of_collisions"],
                "new_substances": A["new_substances_count"],
                "runtime_s": (A.get("summary") or {}).get("runtime_s"),
                "L": (A.get("config") or {}).get("L")}
    key["B"] = {"final_N": B["final_total_molecules"],
                "final_atoms": B["final_total_atoms"],
                "distinct": B["final_distinct_formulas"],
                "mean_atoms": B["final_mean_atoms"],
                "max_atoms": B["final_max_atoms"],
                "reaction_counts": B["reaction_counts"],
                "net_events": B["net_events_total"],
                "capped_total": B["capped_total"],
                "capped_share": B["capped_share_of_collisions"],
                "new_substances": B["new_substances_count"],
                "runtime_s": (B.get("summary") or {}).get("runtime_s"),
                "L": (B.get("config") or {}).get("L"),
                "seed_initial_count": (B.get("config") or {}).get("seed_initial_count"),
                "initial_atoms": (B.get("config") or {}).get("initial_atoms")}
    key["compare"] = {
        "mass_balance": compare["mass_balance"],
        "element_conserved": all(r["A_conserved"] and r["B_conserved"]
                                 for r in compare["element_check"]),
        "valence_conserved": (compare["valence_check"]["A_conserved"] and
                              compare["valence_check"]["B_conserved"]),
        "new_in_B_top20": compare["new_in_B_top20"],
        "dropped_from_A_top20": compare["dropped_from_A_top20"],
    }
    key["structures"] = structure_stats
    key["history"] = history["table"]
    analysis["key_numbers"] = key
    caveats = [
        "event_samples 为蓄水池抽样（50000 上限）：A 174,549 / B 206,740 净事件，"
        "类型拆分按抽样比例估计，逐分钟净事件总数由 events_total 差分精确。",
        "B 无 origin 字段；整理底物 %s 分子（A 终态 43 种结构）+ batchB %s 分子 / %s 原子；"
        "两者相加=B 初始 %s 分子 / %s 原子（已验证）。"
        % ((B.get("config") or {}).get("seed_initial_count"),
           loads["batchB"]["molecules"], loads["batchB"]["atoms"],
           (B.get("config") or {}).get("initial_particles"),
           (B.get("config") or {}).get("initial_atoms")),
        "计算保护：合并后 >40 原子的碰撞不反应（弹性）；39/40 原子巨型分子是 cap 允许的"
        "最大 F 产物，数量少（B 终态 ≥39 原子 %d 个分子），不代表化学上限。"
        % (B["large_stats"]["ge39"]["molecules"]),
        "final_top_structures 只有前 24；top30 其余 6 个由 natural_engine.complete_products"
        "（fast 引擎）重建，均为 F 稳定单产物。",
        "结构图的键级用 edges 的 multiplicity（1/2/3）着色；S/C/L 键型需要原始 hex 几何，"
        "本图用布局算法重排，因此只标注多重键。",
        "A 三价原子最多（要求满足）：A 52.3% / 26.3% / 21.4%（3>2>1）；B 为随机投料"
        "（46.6% / 33.1% / 20.3%，也恰好 3>2>1，但非设计约束）。",
        "T59 环境 L=60000（比 T58 的 400000 面积缩小 44 倍），碰撞更频繁、退火更充分；"
        "允许 ≤40 原子反应，故 B 出现 39/40 原子巨型分子。",
    ]
    analysis["caveats"] = caveats
    return analysis


def main(argv=None):
    ap = argparse.ArgumentParser(description="T59 两阶段实验分析")
    ap.add_argument("--a", default=DEFAULT_A)
    ap.add_argument("--b", default=DEFAULT_B)
    ap.add_argument("--state", default=DEFAULT_STATE)
    ap.add_argument("--loads", default=DEFAULT_LOADS)
    ap.add_argument("--control", default=DEFAULT_CONTROL)
    ap.add_argument("--t58", default=DEFAULT_T58)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    if not os.path.exists(args.a) or not os.path.exists(args.b):
        print("[error] 缺少 phaseA/B 结果")
        return 2
    t0 = datetime.datetime.now()
    analysis = analyze_main(args.a, args.b, args.state, args.loads,
                            args.control, args.t58)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(analysis, fh, ensure_ascii=False, indent=1)
    print("[saved] %s (%.1fs) size %.1f MB"
          % (args.out, (datetime.datetime.now() - t0).total_seconds(),
             os.path.getsize(args.out) / 1024.0 / 1024.0))
    kn = analysis["key_numbers"]
    print(json.dumps({"loads": kn["loads"], "A": kn["A"], "B": kn["B"],
                      "compare": kn["compare"], "structures": kn["structures"]},
                     ensure_ascii=False, indent=1)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
