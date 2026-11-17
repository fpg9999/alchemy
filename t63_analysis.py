# -*- coding: utf-8 -*-
"""t63_analysis.py —— T63「聚素退火 + F2→A2→K2 三次单质投放」四阶段实验分析

实验设计（见 t63_staged.py / t63_loads.json）：
  stage1：全部 29 种纯聚素（O/X/C，9,002 分子 / 38,532 原子，T57 同款投料），L=30000；
  stage2：stage1 整理底物 + 8,000 个 F2（焰单质，16,000 F 原子），重置 1000°C；
  stage3：stage2 底物 + 8,000 个 A2（气单质，16,000 A 原子）；
  stage4：stage3 底物 + 8,000 个 K2（沌单质，16,000 K 原子）；
  每阶段 1000 分钟、1000→0°C 退火；cap=40；面积模型（A∝原子数，同 T57）。
  一价 F（端帽）→ 二价 A（桥）→ 三价 K（骨架）：聚素熔体被逐级"价数滴定"。

输入：
  t63_loads.json             投料/三次投放设计
  t63_phase1_result.json … t63_phase4_result.json   四阶段完整结果
  t63_state1.json … t63_state4.json                 各阶段 0°C 终态归档
  t63_control_s1.json        第一批无化学对照（可缺失）
  t4_catalog_index.json      84,225 目录（in_catalog）
  substances.json            29 聚素（in_29）

输出：t63_analysis.json

重点：
* 逐阶段：final N/atoms/分子式种数/平均与最大原子数/目录外新物质/reaction_counts/
  净事件/runtime/尺寸分布/top20 终态表/元素原子数与占比/价数原子数与占比；
* 跨阶段（重点）：元素与质量守恒核对（stage k 终态 = stage k-1 终态 + 本阶段 16,000 原子）、
  每阶段新增/保留/消失分子式、top20 四阶段矩阵与首次出现阶段、
  聚素家族（只含 O/X/C）与含 F/含 A/含 K 家族的数量与原子占比、
  价数类占比随阶段变化（每次投放把对应价数类抬高多少）；
* 关键分子结构：每阶段 top 物种 atoms/edges（final_top_structures；不足时 fast 引擎重建）。

缺阶段容忍：任一 t63_phaseK_result.json 缺失时该阶段标 status=PENDING 并跳过，
跨阶段核对自动从已就绪阶段继续（跨缺失阶段的守恒核对标记 skipped）。
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

DEFAULT_P = {k: os.path.join(BASE, "t63_phase%d_result.json" % k)
             for k in (1, 2, 3, 4)}
DEFAULT_STATE = {k: os.path.join(BASE, "t63_state%d.json" % k)
                 for k in (1, 2, 3, 4)}
DEFAULT_LOADS = os.path.join(BASE, "t63_loads.json")
DEFAULT_CONTROL = os.path.join(BASE, "t63_control_s1.json")
DEFAULT_CATALOG = os.path.join(BASE, "t4_catalog_index.json")
DEFAULT_SUBS = os.path.join(BASE, "substances.json")
DEFAULT_OUT = os.path.join(BASE, "t63_analysis.json")

ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]
CN = {"O": "秩", "X": "晶", "C": "冰", "P": "势", "W": "流", "L": "电",
      "K": "沌", "A": "气", "F": "焰"}
# 通用价数口径：O/P/K=3、X/W/A=2、C/L/F=1
VAL = {"O": 3, "X": 2, "C": 1, "P": 3, "W": 2, "L": 1,
       "K": 3, "A": 2, "F": 1}
VAL_LABEL = {3: "三价", 2: "二价", 1: "一价"}
STAGES = [1, 2, 3, 4]
_FORMULA_RE = re.compile(r"([A-Z])(\d*)")
# 三次投放的价数类归属
ADD_VALENCE = {"F": "v1", "A": "v2", "K": "v3"}
FAM_COLORS = {"poly": "#2e86de", "F": "#e74c3c", "A": "#f39c12", "K": "#8e44ad"}


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


def pct(x, n=2):
    if x is None:
        return None
    return round(100.0 * float(x), n)


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


def family_of(f):
    cnt = formula_counts(f)
    if cnt.get("F"):
        return "F"
    if cnt.get("A"):
        return "A"
    if cnt.get("K"):
        return "K"
    return "poly"


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


# ---------------------------------------------------------------- 阶段分析
def _element_atoms_of_table(final_table):
    out = Counter()
    for r in final_table:
        for e, c in formula_counts(r["formula"]).items():
            out[e] += c * (r.get("count") or 0)
    return out


def _valence_atoms_of_table(final_table):
    out = {"v3": 0, "v2": 0, "v1": 0}
    for r in final_table:
        w = r.get("count") or 0
        out["v3"] += (r.get("v3") or 0) * w
        out["v2"] += (r.get("v2") or 0) * w
        out["v1"] += (r.get("v1") or 0) * w
    return out


def build_timeline_rows(ts):
    rows = []
    prev = {"c": 0, "i": 0, "n": 0, "cap": 0, "ev": 0, "dec": 0}
    for r in ts or []:
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
        rows.append({"t": r.get("t"), "T": r.get("T"), "N": r.get("N"),
                     "mean_atoms": r.get("mean_atoms"),
                     "max_atoms": r.get("max_atoms"),
                     "collisions": r.get("collisions"),
                     "complete": int(dc), "incomplete": int(di),
                     "none": int(dn), "capped": int(dcap),
                     "decomp": int(ddec), "net_events": net,
                     "events_total": ev_cum,
                     "capped_cum": int(r.get("capped", 0))})
    return rows


def analyze_stage(result, stage_no, catalog, catalog_zh, known29):
    cfg = result.get("config") or {}
    sm = result.get("summary") or {}
    final = result.get("final_composition") or {}
    events = result.get("event_samples") or []
    ts = result.get("time_series") or []
    fs = result.get("formula_series") or []
    cap = int(cfg.get("max_reaction_atoms") or 40)
    giant_thr = max(1, cap - 1)
    total_m = sum(v.get("count", 0) for v in final.values())
    total_a = sum((v.get("atoms") or formula_atoms(f)) * v.get("count", 0)
                  for f, v in final.items())
    table = []
    for f, v in sorted(final.items(), key=lambda kv: -kv[1].get("count", 0)):
        cnt = v.get("count", 0)
        a = v.get("atoms") or formula_atoms(f)
        v3, v2, v1 = valence_counts(f)
        table.append({
            "formula": f, "zh": v.get("zh") or formula_zh(f, catalog_zh),
            "count": cnt,
            "share": rnd(cnt / total_m, 5) if total_m else None,
            "atoms": a, "total_atoms": a * cnt,
            "atoms_share": rnd(a * cnt / total_a, 5) if total_a else None,
            "in_catalog": f in catalog, "in_29": f in set(known29),
            "family": family_of(f),
            "v3": v3, "v2": v2, "v1": v1,
        })
    size_dist = Counter()
    atoms_by = Counter()
    for f, v in final.items():
        a = v.get("atoms") or formula_atoms(f)
        c = v.get("count", 0)
        size_dist[a] += c
        atoms_by[a] += a * c
    elements = _element_atoms_of_table(table)
    valence = _valence_atoms_of_table(table)
    el_tot = sum(elements.values()) or 1
    va_tot = sum(valence.values()) or 1
    size_distribution = [{"atoms": a, "molecules": size_dist[a],
                          "molecule_share": rnd(size_dist[a] / total_m, 5)
                          if total_m else None,
                          "atoms_total": atoms_by[a]}
                         for a in sorted(size_dist)]
    types = Counter(e.get("type") for e in events)
    reaction_counts = {k: int((sm.get("reaction_counts") or {}).get(k, 0))
                       for k in ("complete", "incomplete", "none", "capped")}
    rc_total = sum(reaction_counts.values()) or 1
    net_total = int(sm.get("events_total") or len(events))
    sample_n = len(events)
    sampling_complete = net_total == sample_n
    if sampling_complete:
        est = dict(types)
    else:
        scale = net_total / max(1, sample_n)
        est = {k: int(round(v * scale)) for k, v in types.items()}
    tl = build_timeline_rows(ts)
    tl_s = [dict(row) for i, row in enumerate(tl) if i % 5 == 0]
    capped_peak = max(tl, key=lambda r: r.get("capped") or 0, default=None)
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
    new_sub = result.get("new_substances") or {}
    new_top = sorted(
        [(f, rec.get("first_t"), len(rec.get("atoms") or []))
         for f, rec in new_sub.items()], key=lambda x: -(x[2] or 0))[:10]

    def _ge(threshold):
        return {"molecules": sum(c for a, c in size_dist.items() if a >= threshold),
                "atoms": sum(a * c for a, c in size_dist.items() if a >= threshold)}

    return {
        "stage": stage_no,
        "status": "ok",
        "config": {k: cfg.get(k) for k in
                   ("L", "T0", "minutes", "max_reaction_atoms",
                    "initial_particles", "initial_atoms",
                    "seed_initial_count", "area_model", "experiment")},
        "load_summary": result.get("load_summary"),
        "final_N": total_m,
        "final_atoms": total_a,
        "final_mean_atoms": rnd(total_a / total_m, 3) if total_m else None,
        "final_max_atoms": max(size_dist) if size_dist else None,
        "distinct_formulas": len(table),
        "new_substances": len(new_sub),
        "new_substance_top": new_top,
        "final_table": table,
        "top20": table[:20],
        "elements": {"atoms": {e: int(elements.get(e, 0)) for e in ORDER},
                     "shares": {e: rnd((elements.get(e, 0) or 0) / el_tot, 5)
                                for e in ORDER}},
        "valence": {"atoms": valence,
                    "shares": {"v3": rnd(valence["v3"] / va_tot, 5),
                               "v2": rnd(valence["v2"] / va_tot, 5),
                               "v1": rnd(valence["v1"] / va_tot, 5)},
                    "percent": {"v3": pct(valence["v3"] / va_tot),
                                "v2": pct(valence["v2"] / va_tot),
                                "v1": pct(valence["v1"] / va_tot)}},
        "size_distribution": size_distribution,
        "large_stats": {"ge5": _ge(5), "ge10": _ge(10), "ge20": _ge(20),
                        "giant": _ge(giant_thr),
                        "giant_threshold": giant_thr},
        "reaction_counts": reaction_counts,
        "reaction_shares": {k: rnd(v / rc_total, 5)
                            for k, v in reaction_counts.items()},
        "capped_total": reaction_counts["capped"],
        "capped_share": rnd(reaction_counts["capped"] / rc_total, 5),
        "net_events": net_total,
        "event_types": dict(types),
        "event_type_estimate": est,
        "event_samples_n": sample_n,
        "event_sampling_complete": sampling_complete,
        "capped_peak": capped_peak,
        "runtime_s": sm.get("runtime_s"),
        "timeline": tl_s,
        "series": series,
        "stack_order": stack_order,
        "snapshots": [{"t": s.get("t"), "n_points": len(s.get("points") or []),
                       "color_mode": s.get("color_mode")}
                      for s in (result.get("snapshots") or [])],
        "event_examples": {
            "first": [trim_event(e) for e in events[:3]],
            "latest": [trim_event(e) for e in
                       sorted(events, key=lambda x: x.get("t") or -1,
                              reverse=True)[:3]],
        },
    }


# ---------------------------------------------------------------- 结构重建
def build_stage_structures(result, catalog, catalog_zh, known29, top_n=10):
    """每阶段 top_n 物种的 atoms/edges：final_top_structures 优先，缺失用 fast 引擎重建。"""
    import natural_engine as E
    import pot_all as P
    E.set_fast(True)
    final = result.get("final_composition") or {}
    top = sorted(final.items(), key=lambda kv: -kv[1].get("count", 0))[:top_n]
    raw = result.get("final_top_structures") or {}
    out = []
    for rank, (f, v) in enumerate(top, 1):
        rec = raw.get(f)
        rebuilt = False
        if rec is None:
            try:
                vec = P.parse_formula(f)
                prods = E.complete_products(tuple(vec))
            except Exception:
                prods = None
            if prods:
                m = next((x for x in prods if x["formula"] == f), prods[0])
                rec = {"label": m.get("label"), "atoms": m["atoms"],
                       "edges": m["edges"], "c": m.get("c")}
                rebuilt = True
        if rec is None:
            out.append({"rank": rank, "formula": f,
                        "zh": v.get("zh") or formula_zh(f, catalog_zh),
                        "count": v.get("count", 0),
                        "atoms": v.get("atoms") or formula_atoms(f),
                        "atoms_list": [], "edges": [], "structure": None,
                        "family": family_of(f), "rebuilt": False})
            continue
        atoms = rec["atoms"]
        edges = [list(e) for e in rec["edges"]]
        f_stable = None
        try:
            vec = P.parse_formula(f)
            prods = E.complete_products(tuple(vec))
            f_stable = bool(prods and len(prods) == 1 and
                            prods[0]["formula"] == f)
        except Exception:
            pass
        elem = Counter(atoms)
        bond_mult = Counter(int(e[2]) for e in edges)
        out.append({
            "rank": rank, "formula": f,
            "zh": v.get("zh") or formula_zh(f, catalog_zh),
            "count": v.get("count", 0), "atoms": len(atoms),
            "atoms_list": atoms, "edges": edges,
            "in_catalog": f in catalog,
            "in_29": f in set(known29 or []),
            "label": rec.get("label"), "family": family_of(f),
            "f_stable": f_stable, "rebuilt": rebuilt,
            "element_counts": dict(elem),
            "bond_multiplicity": {str(k): c for k, c in sorted(bond_mult.items())},
            "structure": {"atoms": atoms, "edges": edges},
        })
    return out


# ---------------------------------------------------------------- 跨阶段
def _stage_of(stages, k):
    return stages.get("phase%d" % k)


def analyze_cross_stage(stages, loads, states):
    additions = {int(a["stage"]): a for a in (loads.get("additions") or [])}
    stage1_meta = (loads.get("stage1") or {}).get("meta") or {}
    # stage1 初始元素原子数（由投料 species 计算）
    init_elems = Counter()
    for r in (loads.get("stage1") or {}).get("species") or []:
        for e, c in formula_counts(r.get("formula")).items():
            init_elems[e] += c * int(r.get("count") or 0)
    present = [k for k in STAGES
               if (_stage_of(stages, k) or {}).get("status") == "ok"]
    cross = {
        "stage_order": STAGES,
        "present": present,
        "missing": [k for k in STAGES if k not in present],
        "additions": [{"stage": a.get("stage"), "element": a.get("element"),
                       "name": a.get("name"), "formula": a.get("formula"),
                       "molecules": a.get("molecules"), "atoms": a.get("atoms"),
                       "valence_class": ADD_VALENCE.get(a.get("element"))}
                      for a in (loads.get("additions") or [])],
        "stage1_initial_elements": {e: int(init_elems.get(e, 0)) for e in ORDER},
        "conservation": [],
        "element_table": [],
        "top_matrix": [],
        "families": [],
        "valence_progression": [],
        "transitions": [],
        "balance_summary": {},
    }
    prev_stage = None
    for k in STAGES:
        S = _stage_of(stages, k)
        if not S or S.get("status") != "ok":
            cross["conservation"].append({"stage": k, "status": "PENDING",
                                          "note": "结果未就绪，跳过"})
            continue
        cfg = S.get("config") or {}
        add = additions.get(k)
        entry = {"stage": k, "status": "ok",
                 "initial_particles_config": cfg.get("initial_particles"),
                 "initial_atoms_config": cfg.get("initial_atoms"),
                 "final_N": S["final_N"], "final_atoms": S["final_atoms"]}
        if k == 1:
            exp_m = stage1_meta.get("total_molecules")
            exp_a = stage1_meta.get("total_atoms")
            entry.update({
                "prev_state_molecules": None, "prev_state_atoms": None,
                "addition_molecules": 0, "addition_atoms": 0,
                "expected_molecules": exp_m, "expected_atoms": exp_a,
                "states_chain_ok": None,
                "molecule_balance": exp_m == cfg.get("initial_particles"),
                "atom_balance": exp_a == cfg.get("initial_atoms"),
                "final_vs_initial_atoms": S["final_atoms"] == exp_a,
                "final_vs_initial_molecules": None,
            })
            prev_elems = {e: int(init_elems.get(e, 0)) for e in ORDER}
            expected_elems = dict(prev_elems)
        else:
            prev = _stage_of(stages, k - 1)
            if not prev or prev.get("status") != "ok":
                cross["conservation"].append({
                    "stage": k, "status": "SKIPPED_PREV_PENDING",
                    "note": "前一阶段（phase%d）未就绪，跳过本阶段守恒核对" % (k - 1)})
                continue
            st = (states.get(k - 1) or {})
            add = add or {}
            exp_m = ((st.get("total_molecules") if st.get("total_molecules")
                      is not None else prev.get("final_N")) or 0) + \
                    int(add.get("molecules") or 0)
            exp_a = ((st.get("total_atoms") if st.get("total_atoms")
                      is not None else prev.get("final_atoms")) or 0) + \
                    int(add.get("atoms") or 0)
            prev_elems = (prev or {}).get("elements", {}).get("atoms") or {}
            expected_elems = dict(prev_elems)
            if add and add.get("element"):
                expected_elems[add["element"]] = \
                    expected_elems.get(add["element"], 0) + int(add.get("atoms") or 0)
            entry.update({
                "prev_state_molecules": st.get("total_molecules"),
                "prev_state_atoms": st.get("total_atoms"),
                "prev_stage_final_N": prev.get("final_N"),
                "states_chain_ok": (st.get("total_molecules") is None or
                                    prev.get("final_N") == st.get("total_molecules")),
                "addition_molecules": int(add.get("molecules") or 0),
                "addition_atoms": int(add.get("atoms") or 0),
                "addition_element": add.get("element"),
                "expected_molecules": exp_m, "expected_atoms": exp_a,
                "molecule_balance": (exp_m == cfg.get("initial_particles")),
                "atom_balance": (exp_a == cfg.get("initial_atoms")),
                "final_vs_initial_atoms": S["final_atoms"] == cfg.get("initial_atoms"),
                "final_vs_initial_molecules": None,
            })
        # 元素核对
        actual = S["elements"]["atoms"]
        elem_rows = []
        for e in ORDER:
            exp = int(expected_elems.get(e, 0) or 0)
            got = int(actual.get(e, 0) or 0)
            elem_rows.append({"element": e, "zh": CN[e], "expected": exp,
                              "actual": got, "delta": got - exp,
                              "conserved": exp == got,
                              "is_added": bool(
                                  add and add.get("element") == e)})
        entry["elements_conserved"] = all(r["conserved"] for r in elem_rows)
        entry["element_delta_rows"] = elem_rows
        entry["added_element_atoms"] = (int(add.get("atoms") or 0)
                                        if add and add.get("element") else 0)
        cross["conservation"].append(entry)
        cross["element_table"].append({"stage": k, "atoms": actual, "row": elem_rows})
        prev_stage = S
    # 元素表（逐元素 × 阶段）
    cross["element_stage_matrix"] = [
        {"element": e, "zh": CN[e],
         "stages": {("stage%d" % k): ((_stage_of(stages, k) or {}).get("elements", {})
                                     .get("atoms", {}) or {}).get(e, 0)
                    for k in STAGES}}
        for e in ORDER]
    # top20 并集矩阵
    union = []
    counts = {}
    for k in STAGES:
        S = _stage_of(stages, k) or {}
        for r in (S.get("top20") or []):
            f = r["formula"]
            if f not in counts:
                counts[f] = {}
                union.append(f)
            counts[f]["stage%d" % k] = r["count"]
    rows = []
    for f in union:
        cts = counts[f]
        first = None
        for k in STAGES:
            if cts.get("stage%d" % k, 0) > 0:
                first = k
                break
        rec = {"formula": f, "zh": (_stage_of(stages, first) or {})
               .get("final_table") and None, "first_stage": first,
               "max_count": max(cts.values()) if cts else 0,
               "counts": {("stage%d" % k): cts.get("stage%d" % k, 0)
                          for k in STAGES},
               "stages_present": sum(1 for k in STAGES
                                     if cts.get("stage%d" % k, 0) > 0),
               "family": family_of(f)}
        # zh 从首个出现阶段的表里取
        for r0 in ((_stage_of(stages, first) or {}).get("final_table") or []):
            if r0["formula"] == f:
                rec["zh"] = r0.get("zh")
                break
        rows.append(rec)
    rows.sort(key=lambda r: (-r["stages_present"], -r["max_count"]))
    cross["top_matrix"] = rows
    # 家族演化
    for k in STAGES:
        S = _stage_of(stages, k)
        if not S or S.get("status") != "ok":
            continue
        fam = {"stage": k,
               "poly": {"molecules": 0, "atoms": 0},
               "F": {"molecules": 0, "atoms": 0},
               "A": {"molecules": 0, "atoms": 0},
               "K": {"molecules": 0, "atoms": 0}}
        total_atoms = S["final_atoms"] or 1
        for r in S["final_table"]:
            famrec = fam[r["family"]]
            famrec["molecules"] += r["count"]
            famrec["atoms"] += r["atoms"] * r["count"]
        for key in ("poly", "F", "A", "K"):
            fam[key]["atoms_share"] = rnd(fam[key]["atoms"] / total_atoms, 4)
            fam[key]["atoms_percent"] = pct(fam[key]["atoms"] / total_atoms)
        cross["families"].append(fam)
    # 价数演化
    prev_val = None
    for k in STAGES:
        S = _stage_of(stages, k)
        if not S or S.get("status") != "ok":
            continue
        val = S["valence"]["atoms"]
        add = additions.get(k)
        rec = {"stage": k, "atoms": val,
               "percent": S["valence"]["percent"],
               "shares": S["valence"]["shares"],
               "delta": ({kk: (val.get(kk, 0) - (prev_val or {}).get(kk, 0))
                          for kk in ("v3", "v2", "v1")}
                         if prev_val is not None else None),
               "added_valence_class": (ADD_VALENCE.get(add.get("element"))
                                       if add else None),
               "added_atoms": (int(add.get("atoms") or 0) if add else 0)}
        cross["valence_progression"].append(rec)
        prev_val = val
    # 阶段间新增/保留/消失（按终态全表）
    prev_set = None
    for k in STAGES:
        S = _stage_of(stages, k)
        if not S or S.get("status") != "ok":
            continue
        cur_map = {r["formula"]: r for r in S["final_table"]}
        cur = set(cur_map)
        if prev_set is None:
            cross["transitions"].append({
                "stage": k, "prev": None, "new": sorted(cur, key=lambda f: -cur_map[f]["count"])[:20],
                "retained": [], "lost": [],
                "new_count": len(cur), "retained_count": 0, "lost_count": 0})
        else:
            new = cur - prev_set
            lost = prev_set - cur
            retained = cur & prev_set
            prev_map = {r["formula"]: r for r in
                        ((_stage_of(stages, k - 1) or {}).get("final_table") or [])}
            cross["transitions"].append({
                "stage": k,
                "prev": k - 1,
                "new": sorted(new, key=lambda f: -cur_map[f]["count"])[:20],
                "retained": sorted(retained, key=lambda f: -cur_map[f]["count"])[:20],
                "lost": sorted(lost, key=lambda f: -(prev_map.get(f, {}).get("count") or 0))[:20],
                "new_count": len(new), "retained_count": len(retained),
                "lost_count": len(lost),
            })
        prev_set = cur
    cons = [c for c in cross["conservation"] if c.get("status") == "ok"]
    cross["balance_summary"] = {
        "all_elements_conserved": all(c.get("elements_conserved") for c in cons) if cons else None,
        "all_molecule_balance": all(c.get("molecule_balance") for c in cons) if cons else None,
        "all_atom_balance": all(c.get("atom_balance") and c.get("final_vs_initial_atoms")
                                for c in cons) if cons else None,
        "all_states_chain_ok": all(c.get("states_chain_ok")
                                   for c in cons if c.get("states_chain_ok") is not None)
        if cons else None,
    }
    return cross


# ---------------------------------------------------------------- 控制组
def analyze_control(control_path):
    if not control_path or not os.path.exists(control_path):
        return None
    try:
        c = load_json(control_path)
    except Exception:
        return None
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
    return {"stats": st, "by_size": by, "checks": checks,
            "pass": all(v for v in checks.values() if v is not None),
            "config": c.get("config")}


# ---------------------------------------------------------------- 主流程
def analyze_main(p_paths, state_paths, loads_path, control_path):
    catalog, catalog_zh = load_catalog(BASE)
    subs_path = os.path.join(BASE, "substances.json")
    known29 = [r.get("formula") for r in
               (load_json(subs_path) if os.path.exists(subs_path) else [])
               if r.get("formula")]
    loads = load_json(loads_path) if os.path.exists(loads_path) else {}
    stages = OrderedDict()
    raw_results = {}
    missing = []
    for k in STAGES:
        p = p_paths.get(k)
        if not p or not os.path.exists(p):
            stages["phase%d" % k] = {"stage": k, "status": "PENDING",
                                     "note": "结果文件未就绪：%s" % (
                                         os.path.basename(p) if p else "-")}
            missing.append(k)
            continue
        try:
            res = load_json(p)
        except Exception as exc:
            stages["phase%d" % k] = {"stage": k, "status": "PENDING",
                                     "note": "读取失败：%s" % exc}
            missing.append(k)
            continue
        raw_results[k] = res
        stages["phase%d" % k] = analyze_stage(res, k, catalog, catalog_zh, known29)
    states = {}
    for k in STAGES:
        sp = state_paths.get(k)
        if sp and os.path.exists(sp):
            try:
                st = load_json(sp)
                states[k] = {kk: st.get(kk) for kk in
                             ("total_molecules", "total_atoms",
                              "distinct_formulas", "distinct_structures",
                              "t", "T")}
            except Exception:
                states[k] = {}
    # 跨阶段
    cross = analyze_cross_stage(stages, loads, states)
    # 结构（每阶段 top10）
    struct = {}
    for k in STAGES:
        res = raw_results.get(k)
        if res is None:
            struct["phase%d" % k] = []
            continue
        struct["phase%d" % k] = build_stage_structures(res, catalog, catalog_zh,
                                                       known29, top_n=10)
    control = analyze_control(control_path)
    # 阶段结构统计
    struct_stats = {}
    for k in STAGES:
        ss = struct["phase%d" % k]
        ok = bool(ss)
        struct_stats["phase%d" % k] = {
            "top_n": len(ss),
            "all_f_stable": (all(s.get("f_stable") for s in ss
                                 if s.get("structure")) if ok else None),
            "rebuilt_count": sum(1 for s in ss if s.get("rebuilt")),
            "status": "ok" if ok else "PENDING",
        }
    analysis = OrderedDict()
    analysis["meta"] = {
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "experiment": "T63 聚素退火 + F2→A2→K2 三次单质投放（价数滴定）",
        "files": {
            "loads": os.path.basename(loads_path) if loads_path else None,
            "control": (os.path.basename(control_path)
                        if control_path and os.path.exists(control_path) else None),
            "phases": {("phase%d" % k): (os.path.basename(p_paths[k])
                                         if p_paths.get(k) else None)
                       for k in STAGES},
            "states": {("state%d" % k): (os.path.basename(state_paths[k])
                                         if state_paths.get(k) else None)
                       for k in STAGES},
        },
        "missing_stages": ["phase%d" % k for k in missing],
        "present_stages": ["phase%d" % k for k in STAGES if k not in missing],
        "catalog_size": len(catalog),
        "known29": known29,
        "engine": ("natural_engine.set_fast(True)（fast_pot，已审计）；"
                   "max_reaction_atoms=%s；L=%s"
                   % ((loads.get("max_reaction_atoms") or 40),
                      loads.get("L") or 30000)),
        "schema_notes": [
            "event_samples 为蓄水池抽样（上限 30000）；净事件总数精确，类型拆分按比例估计。",
            "阶段结果结构同 t55_kinetic_env（config/summary/final_composition/"
            "final_top_structures/new_substances/time_series/formula_series/"
            "snapshots/event_samples）。",
            "stage1 的 reaction_counts 可能没有 capped 键（cap40 下未触发）→ 按 0 处理。",
            "每次投放 8000 个双原子单质 = 16,000 原子（F2 / A2 / K2）。",
            "结构图 atoms/edges 来自 final_top_structures；不足时用 fast 引擎重建。",
        ],
    }
    stage1_species = (loads.get("stage1") or {}).get("species") or []
    stage1_elements = Counter()
    for r in stage1_species:
        for e, c in formula_counts(r.get("formula")).items():
            stage1_elements[e] += c * int(r.get("count") or 0)
    analysis["loads"] = {
        "experiment": loads.get("experiment"),
        "seed": loads.get("seed"), "L": loads.get("L"),
        "minutes": loads.get("minutes"),
        "max_reaction_atoms": loads.get("max_reaction_atoms"),
        "area_model": loads.get("area_model"),
        "stage1": {"name": (loads.get("stage1") or {}).get("name"),
                   "meta": (loads.get("stage1") or {}).get("meta"),
                   "species": stage1_species,
                   "element_atoms": {e: int(stage1_elements.get(e, 0))
                                     for e in ORDER}},
        "additions": loads.get("additions") or [],
        "stage_design": loads.get("stage_design") or [],
    }
    analysis["stages"] = stages
    analysis["cross_stage"] = cross
    analysis["structures"] = {"per_stage": struct, "stats": struct_stats}
    analysis["control"] = control
    # key_numbers
    key = OrderedDict()
    key["stages"] = {}
    for k in STAGES:
        S = stages["phase%d" % k]
        if S.get("status") != "ok":
            key["stages"]["phase%d" % k] = {"status": "PENDING"}
            continue
        key["stages"]["phase%d" % k] = {
            "final_N": S["final_N"], "final_atoms": S["final_atoms"],
            "distinct": S["distinct_formulas"],
            "mean_atoms": S["final_mean_atoms"],
            "max_atoms": S["final_max_atoms"],
            "new_substances": S["new_substances"],
            "reaction_counts": S["reaction_counts"],
            "capped_total": S["capped_total"],
            "capped_share": S["capped_share"],
            "net_events": S["net_events"],
            "runtime_s": S["runtime_s"],
            "initial_particles": S["config"].get("initial_particles"),
            "initial_atoms": S["config"].get("initial_atoms"),
            "elements": S["elements"]["atoms"],
            "element_shares": S["elements"]["shares"],
            "valence": S["valence"]["atoms"],
            "valence_percent": S["valence"]["percent"],
            "top10": [{"formula": r["formula"], "count": r["count"],
                       "atoms": r["atoms"], "family": r["family"],
                       "in_catalog": r["in_catalog"], "in_29": r["in_29"]}
                      for r in S["final_table"][:10]],
        }
    key["cross_stage"] = {
        "present": cross["present"], "missing": cross["missing"],
        "balance_summary": cross["balance_summary"],
        "conservation": [{"stage": c.get("stage"), "status": c.get("status"),
                          "elements_conserved": c.get("elements_conserved"),
                          "molecule_balance": c.get("molecule_balance"),
                          "atom_balance": c.get("atom_balance"),
                          "final_vs_initial_atoms": c.get("final_vs_initial_atoms"),
                          "states_chain_ok": c.get("states_chain_ok"),
                          "expected_molecules": c.get("expected_molecules"),
                          "expected_atoms": c.get("expected_atoms"),
                          "addition_molecules": c.get("addition_molecules"),
                          "addition_atoms": c.get("addition_atoms")}
                         for c in cross["conservation"]],
        "families": cross["families"],
        "valence_progression": cross["valence_progression"],
        "transitions": cross["transitions"],
        "element_stage_matrix": cross["element_stage_matrix"],
    }
    key["structures"] = struct_stats
    key["control"] = ({"pass": control["pass"], "stats": control["stats"]}
                      if control else None)
    analysis["key_numbers"] = key
    # caveats
    caveats = []
    if missing:
        caveats.append("阶段缺失：%s 尚未就绪（标 PENDING，相关跨阶段核对跳过）；"
                       "四阶段齐全后重跑本脚本即可补全。"
                       % "、".join("phase%d" % k for k in missing))
    # capped 动态说明（末期单质投放后巨型堆积增多时自动生成，不硬编码阶段号）
    caps = [stages["phase%d" % k] for k in STAGES
            if (stages.get("phase%d" % k) or {}).get("status") == "ok"
            and (stages["phase%d" % k].get("capped_total") or 0) > 0]
    if caps:
        zeros = [k for k in STAGES
                 if (stages.get("phase%d" % k) or {}).get("status") == "ok"
                 and not ((stages.get("phase%d" % k) or {}).get("capped_total") or 0)]
        seg = "；".join(
            "阶段%d capped %s 次（占判定 %.3f%%，峰值 t=%s 分钟、累计 %s）"
            % (st["stage"], "{:,}".format(int(st["capped_total"])),
               (st.get("capped_share") or 0) * 100,
               (st.get("capped_peak") or {}).get("t", "-"),
               "{:,}".format(int((st.get("capped_peak") or {}).get("capped_cum") or 0)))
            for st in caps)
        prev = ("；前序阶段（%s）capped 均为 0" % "、".join("阶段%d" % k for k in zeros)
                if zeros else "")
        last = caps[-1]
        adds = loads.get("additions") or []
        add_f = (adds[-1].get("formula") if adds else "") or "单质"
        giant = ((last.get("large_stats") or {}).get("giant") or {})
        caveats.append(
            "capped 动态：%s%s；%s 投放后大量悬空价被填满，合并后 >%d 原子的巨型堆积增多"
            "（≥%d 原子巨型分子 %s 个 / %s 原子），部分被 cap 弹性截断——这是 cap=%d 保护的"
            "末期生效，capped 占比仍 <1%%，不改变终态主导产物。"
            % (seg, prev, add_f, int(loads.get("max_reaction_atoms") or 40), 39,
               "{:,}".format(int(giant.get("molecules") or 0)),
               "{:,}".format(int(giant.get("atoms") or 0)),
               int(loads.get("max_reaction_atoms") or 40)))
    caveats.extend([
        "event_samples 为蓄水池抽样（上限 30000）；净事件总数由 events_total 给出，"
        "类型拆分在抽样不完全时按比例估计。",
        "质量/元素守恒：stage k 初始 = stage k-1 终态 + 本阶段投放；"
        "元素核对逐元素 delta（F/A/K 各 +16,000）。",
        "计算保护：合并后 >%d 原子的碰撞不反应（弹性）；≥%d 原子巨型分子是 cap 允许的"
        "最大 F 产物。" % (loads.get("max_reaction_atoms") or 40, 39),
        "价数口径（通用）：O/P/K=3 价、X/W/A=2 价、C/L/F=1 价；"
        "三次投放依次为 F2（一价端帽）、A2（二价桥）、K2（三价骨架）。",
        "家族归类按 F>A>K 优先（含多种投放元素的分子只计入优先级最高的家族，"
        "poly 表示只含 O/X/C）；各类占比用于观察逐级滴定趋势。",
        "目录外新物质 = 不在 84,225 目录 + 29 聚素 + F2/A2/K2 的终态分子式。",
        "stage1 无 capped 键时按 0 处理；cap=40、L=30000、面积模型 A∝原子数（同 T57）。",
    ])
    analysis["caveats"] = caveats
    return analysis


def main(argv=None):
    ap = argparse.ArgumentParser(description="T63 四阶段（聚素 + F2/A2/K2）实验分析")
    for k in STAGES:
        ap.add_argument("--p%d" % k, default=DEFAULT_P[k])
        ap.add_argument("--state%d" % k, default=DEFAULT_STATE[k])
    ap.add_argument("--loads", default=DEFAULT_LOADS)
    ap.add_argument("--control", default=DEFAULT_CONTROL)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    p_paths = {k: getattr(args, "p%d" % k) for k in STAGES}
    state_paths = {k: getattr(args, "state%d" % k) for k in STAGES}
    if not any(os.path.exists(p) for p in p_paths.values()):
        print("[error] 至少需要阶段结果之一（t63_phaseK_result.json）")
        return 2
    t0 = datetime.datetime.now()
    analysis = analyze_main(p_paths, state_paths, args.loads, args.control)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(analysis, fh, ensure_ascii=False, indent=1)
    print("[saved] %s (%.1fs) size %.1f MB"
          % (args.out, (datetime.datetime.now() - t0).total_seconds(),
             os.path.getsize(args.out) / 1024.0 / 1024.0))
    kn = analysis["key_numbers"]
    print(json.dumps({"stages": kn["stages"],
                      "cross_stage": {"present": kn["cross_stage"]["present"],
                                      "missing": kn["cross_stage"]["missing"],
                                      "balance_summary":
                                          kn["cross_stage"]["balance_summary"],
                                      "families": kn["cross_stage"]["families"],
                                      "valence_progression":
                                          kn["cross_stage"]["valence_progression"]},
                      "control": kn["control"]},
                     ensure_ascii=False, indent=1)[:7000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
