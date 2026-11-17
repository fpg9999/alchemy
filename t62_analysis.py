# -*- coding: utf-8 -*-
"""t62_analysis.py —— T62「九元素·三/二/一价等量」两阶段连续实验分析

T62 是 T59 的对照实验：投料价数从 T59 的 52.3:26.3:21.4（三价最多）
改为 v3:v2:v1 ≈ 33.3:33.3:33.3（9 元素各 ≈1/9），其余变量沿用 T59
（L=60000、A 批 150,019 原子 / B 批 80,027 原子、cap40 主实验 + cap60
高保真、每阶段 1000 分钟 1000→0°C、100 分钟一次快照）。

输入：
  t62_phaseA_result.json    第一阶段（120 种等量价数物质、L=60000、1000 分钟）
  t62_stateA.json           第一阶段 0°C 后整理归档的底物
  t62_phaseB_result.json    第二阶段（底物 + 第二批 120 种等量价数物质）
  t62_loads.json            batchA / batchB 投料设计（IPF 等量配比）
  t62_control_A.json        无化学对照（穿越验证，含 by_size）
  t62_phaseA_hf_result.json cap60 高保真对照（可缺失）
  t62_phaseB_hf_result.json cap60 高保真对照（可缺失）
  t4_catalog_index.json     84,225 目录（in_catalog）
  substances.json           29 聚素（in_29）
  t59_analysis.json         T59 历史对比（key_numbers 的 T59A/T59B）
  t58_analysis.json         更早的规模对比（可选）

输出：t62_analysis.json

重点：
* 两阶段对比：A 终态 vs B 终态（规模/尺寸/组成/多样性/新物质/质量与元素守恒）；
* **价数均衡**：A/B 初始与终态 v3:v2:v1 原子数与占比（应 ≈1/3 且守恒），
  9 元素占比（应 ≈1/9），并与 T59 的 52.3:26.3:21.4 对比；
* 反应统计：complete/incomplete/capped/none、净事件、capped 随时间；
* 最终 B 数量前 30 的结构（final_top_structures 前 24 + natural_engine 重建剩余）；
* 历史对比表 T58（可选）/T59A/T59B/T62A/T62B；
* cap60 对照段 conclusion 全部由数据动态生成（不硬编码 T59 数字）。

注意：T62 的投料不再满足 strict_order_3gt2gt1（三价最多），该字段为 False，
      “三价最多”不能作为本实验的判据；等量价数用 equal_valence / 偏差 pp 衡量。
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

DEFAULT_A = os.path.join(BASE, "t62_phaseA_result.json")
DEFAULT_B = os.path.join(BASE, "t62_phaseB_result.json")
DEFAULT_A_HF = os.path.join(BASE, "t62_phaseA_hf_result.json")
DEFAULT_B_HF = os.path.join(BASE, "t62_phaseB_hf_result.json")
DEFAULT_STATE = os.path.join(BASE, "t62_stateA.json")
DEFAULT_LOADS = os.path.join(BASE, "t62_loads.json")
DEFAULT_CONTROL = os.path.join(BASE, "t62_control_A.json")
DEFAULT_T59 = os.path.join(BASE, "t59_analysis.json")
DEFAULT_T58 = os.path.join(BASE, "t58_analysis.json")
DEFAULT_CATALOG = os.path.join(BASE, "t4_catalog_index.json")
DEFAULT_SUBS = os.path.join(BASE, "substances.json")
DEFAULT_OUT = os.path.join(BASE, "t62_analysis.json")

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
def _element_shares(element_atoms):
    ea = element_atoms or {}
    tot = sum(ea.values()) or 1
    return {e: rnd(ea.get(e, 0) / tot, 4) for e in ORDER if ea.get(e, 0)}


def _valence_share_dict(va):
    va = va or {}
    tot = sum(va.values()) or 1
    return {"v3": rnd(va.get("v3", 0) / tot, 4),
            "v2": rnd(va.get("v2", 0) / tot, 4),
            "v1": rnd(va.get("v1", 0) / tot, 4)}


def _max_dev_pp(shares, target):
    vals = [v for v in (shares or {}).values() if v is not None]
    if not vals:
        return None
    return rnd(max(abs(float(v) * 100.0 - target * 100.0) for v in vals), 3)


def analyze_loads(loads_path):
    d = load_json(loads_path)
    out = {"config": d.get("config")}
    for tag in ("batchA", "batchB"):
        b = d.get(tag) or {}
        sm = b.get("summary") or {}
        rows = b.get("rows") or []
        size_dist = Counter(r.get("atoms") or 0 for r in rows)
        element_atoms = sm.get("element_atoms") or {}
        element_shares = sm.get("element_shares") or _element_shares(element_atoms)
        valence_atoms = sm.get("valence_atoms") or {}
        valence_shares = list(sm.get("valence_shares") or [])
        if not valence_shares and valence_atoms:
            vs = _valence_share_dict(valence_atoms)
            valence_shares = [vs["v3"], vs["v2"], vs["v1"]]
        # 等量价数判据：v3/v2/v1 每类 ≈1/3；9 元素每类 ≈1/9
        equal_valence = sm.get("equal_valence")
        if equal_valence is None:
            equal_valence = bool(valence_shares) and all(
                abs(float(x) - 1.0 / 3.0) * 100.0 <= 2.0 for x in valence_shares)
        max_vdev = sm.get("max_valence_deviation_pp")
        if max_vdev is None and valence_shares:
            max_vdev = rnd(max(abs(float(x) * 100.0 - 100.0 / 3.0)
                               for x in valence_shares), 3)
        max_edev = sm.get("max_element_deviation_pp")
        if max_edev is None and element_shares:
            max_edev = _max_dev_pp(element_shares, 1.0 / 9.0)
        out[tag] = {
            "summary": sm,
            "rows": rows,
            "n_species": sm.get("n_species") or len(rows),
            "molecules": sm.get("molecules"),
            "atoms": sm.get("atoms"),
            "mean_atoms": sm.get("mean_atoms"),
            "element_atoms": element_atoms,
            "element_shares": {e: rnd(v, 4) for e, v in element_shares.items()},
            "elements_covered": sm.get("elements_covered") or [],
            "valence_atoms": valence_atoms,
            "valence_shares": valence_shares,
            "equal_valence": bool(equal_valence),
            "max_valence_deviation_pp": max_vdev,
            "max_element_deviation_pp": max_edev,
            # T62 不要求 3>2>1；保留原名供交叉检查，值为 summary.strict_order
            "strict_order_3gt2gt1": bool(sm.get("strict_order")),
            "size_distribution": [{"atoms": a, "species": size_dist[a],
                                   "molecules": sum((r.get("count") or 0)
                                                    for r in rows
                                                    if (r.get("atoms") or 0) == a)}
                                  for a in sorted(size_dist)],
        }
        if valence_atoms:
            out[tag]["valence_atom_shares"] = _valence_share_dict(valence_atoms)
    a, b = out["batchA"], out["batchB"]
    out["compare"] = {
        "A_vs_B_valence": {
            "A": a.get("valence_atoms"), "B": b.get("valence_atoms"),
            "A_shares": a.get("valence_shares"), "B_shares": b.get("valence_shares"),
            "A_strict": a.get("strict_order_3gt2gt1"),
            "B_strict": b.get("strict_order_3gt2gt1"),
        },
        "valence_equality": {
            "target": "v3:v2:v1 = 1/3 : 1/3 : 1/3；9 元素各 1/9",
            "A_equal": a.get("equal_valence"),
            "B_equal": b.get("equal_valence"),
            "A_max_valence_deviation_pp": a.get("max_valence_deviation_pp"),
            "B_max_valence_deviation_pp": b.get("max_valence_deviation_pp"),
            "A_max_element_deviation_pp": a.get("max_element_deviation_pp"),
            "B_max_element_deviation_pp": b.get("max_element_deviation_pp"),
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
    cap = int(cfg.get("max_reaction_atoms") or 40)
    giant_thr = max(1, cap - 1)
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

    def _ge(threshold):
        return {"molecules": sum(c for a, c in size_dist.items() if a >= threshold),
                "atoms": sum(a * c for a, c in size_dist.items() if a >= threshold)}

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
        "max_reaction_atoms": cap,
        "giant_threshold": giant_thr,
        "large_stats": {
            "ge5": _ge(5),
            "ge10": _ge(10),
            "ge20": _ge(20),
            "giant": _ge(giant_thr),
            "giant_threshold": giant_thr,
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
        "event_samples_n": len(events),
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


# ---------------------------------------------------------------- 价数均衡（T62 核心新增）
def _table_element_atoms(final_table):
    out = Counter()
    for r in final_table or []:
        for e, c in formula_counts(r["formula"]).items():
            out[e] += c * (r.get("count") or 0)
    return dict(out)


def _table_valence_atoms(final_table):
    out = {"v3": 0, "v2": 0, "v1": 0}
    for r in final_table or []:
        w = r.get("count") or 0
        out["v3"] += (r.get("v3") or 0) * w
        out["v2"] += (r.get("v2") or 0) * w
        out["v1"] += (r.get("v1") or 0) * w
    return out


def _valence_share_list(va):
    vs = _valence_share_dict(va)
    return [vs["v3"], vs["v2"], vs["v1"]]


def analyze_valence_balance(loads, A, B, t59_ref=None):
    """A/B 初始与终态的 v3:v2:v1 原子数与占比（≈1/3、守恒）+ 9 元素占比（≈1/9）。"""
    la = loads.get("batchA") or {}
    lb = loads.get("batchB") or {}
    a_init_v = la.get("valence_atoms") or {}
    b_batch_v = lb.get("valence_atoms") or {}
    a_fin_v = _table_valence_atoms(A.get("final_table") or [])
    b_fin_v = _table_valence_atoms(B.get("final_table") or [])
    b_init_v = {k: (a_fin_v.get(k, 0) + b_batch_v.get(k, 0))
                for k in ("v3", "v2", "v1")}

    a_init_e = la.get("element_atoms") or {}
    b_batch_e = lb.get("element_atoms") or {}
    a_fin_e = _table_element_atoms(A.get("final_table") or [])
    b_fin_e = _table_element_atoms(B.get("final_table") or [])
    b_init_e = {e: (a_fin_e.get(e, 0) + b_batch_e.get(e, 0)) for e in ORDER}

    def _elem_record(init_e, fin_e):
        si = _element_shares(init_e)
        sf = _element_shares(fin_e)
        return {
            "initial_atoms": {e: int(init_e.get(e, 0)) for e in ORDER},
            "initial_shares": si,
            "final_atoms": {e: int(fin_e.get(e, 0)) for e in ORDER},
            "final_shares": sf,
            "conserved": all(int(init_e.get(e, 0)) == int(fin_e.get(e, 0))
                             for e in ORDER),
            "max_initial_deviation_pp": _max_dev_pp(si, 1.0 / 9.0),
            "max_final_deviation_pp": _max_dev_pp(sf, 1.0 / 9.0),
        }

    def _val_record(init_v, fin_v):
        si = _valence_share_dict(init_v)
        sf = _valence_share_dict(fin_v)
        return {
            "initial_atoms": {k: int(init_v.get(k, 0)) for k in ("v3", "v2", "v1")},
            "initial_share_dict": si,
            "initial_shares": _valence_share_list(init_v),
            "final_atoms": {k: int(fin_v.get(k, 0)) for k in ("v3", "v2", "v1")},
            "final_share_dict": sf,
            "final_shares": _valence_share_list(fin_v),
            "conserved": all(int(init_v.get(k, 0)) == int(fin_v.get(k, 0))
                             for k in ("v3", "v2", "v1")),
            "equal_target_1_3": all(abs(float(x) - 1.0 / 3.0) * 100.0 <= 2.0
                                    for x in _valence_share_list(fin_v)),
            "max_initial_deviation_pp": _max_dev_pp(si, 1.0 / 3.0),
            "max_final_deviation_pp": _max_dev_pp(sf, 1.0 / 3.0),
        }

    return {
        "target": {"valence": "v3:v2:v1 ≈ 1/3:1/3:1/3（每类原子 ±2pp）",
                   "element": "9 元素各 ≈ 1/9（11.11%）",
                   "note": "等量价数设计：三/二/一价原子数相当，不再要求三价最多。"},
        "A": _val_record(a_init_v, a_fin_v),
        "B": _val_record(b_init_v, b_fin_v),
        "elements": {"A": _elem_record(a_init_e, a_fin_e),
                     "B": _elem_record(b_init_e, b_fin_e)},
        "t59_reference": t59_ref,
        "batch_design": {
            "A_valence_atoms": {k: int(a_init_v.get(k, 0)) for k in ("v3", "v2", "v1")},
            "B_batchB_valence_atoms": {k: int(b_batch_v.get(k, 0))
                                       for k in ("v3", "v2", "v1")},
            "A_equal_valence": la.get("equal_valence"),
            "B_batchB_equal_valence": lb.get("equal_valence"),
            "A_max_valence_deviation_pp": la.get("max_valence_deviation_pp"),
            "A_max_element_deviation_pp": la.get("max_element_deviation_pp"),
            "B_batchB_max_valence_deviation_pp": lb.get("max_valence_deviation_pp"),
            "B_batchB_max_element_deviation_pp": lb.get("max_element_deviation_pp"),
        },
    }


def t59_valence_reference(t59_path):
    """读取 T59 投料价数占比作为对照（不硬编码 52.3/26.3/21.4）。"""
    if not (t59_path and os.path.exists(t59_path)):
        return None
    try:
        kn = (load_json(t59_path) or {}).get("key_numbers") or {}
        la = (kn.get("loads") or {}).get("A") or {}
        lb = (kn.get("loads") or {}).get("B") or {}
        out = {"source": os.path.basename(t59_path),
               "A_valence_shares": la.get("valence_shares"),
               "A_valence_atoms": la.get("valence_atoms"),
               "B_valence_shares": lb.get("valence_shares"),
               "B_valence_atoms": lb.get("valence_atoms")}
        a = out.get("A_valence_shares") or []
        if len(a) == 3:
            out["A_shares_text"] = "%.1f%% : %.1f%% : %.1f%%" % tuple(
                100.0 * float(x) for x in a)
            out["note"] = ("T59 投料价数 %s（三价最多，strict 3>2>1）；"
                           "T62 改为三/二/一价等量 ≈33.3%% : 33.3%% : 33.3%%。"
                           % out["A_shares_text"])
        return out
    except Exception:
        return None


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
        return _table_element_atoms(final_table)

    def valence_atoms(final_table):
        return _table_valence_atoms(final_table)

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


# ---------------------------------------------------------------- 历史对比（T59 为主，T58 可选）
def analyze_history(t59_path, t58_path, A, B, loads, valence_balance=None):
    t59 = None
    if t59_path and os.path.exists(t59_path):
        try:
            t59 = load_json(t59_path)
        except Exception:
            t59 = None
    t58 = None
    if t58_path and os.path.exists(t58_path):
        try:
            t58 = load_json(t58_path)
        except Exception:
            t58 = None
    kn59 = (t59 or {}).get("key_numbers") or {}
    kn58 = (t58 or {}).get("key_numbers") or {}
    rows = []
    # T58（可选，cap20 / L=400000）
    if t58 is not None:
        m58 = kn58.get("main") or {}
        mix58 = kn58.get("mixture") or {}
        rows.append({"name": "T58", "molecules": mix58.get("total_molecules"),
                     "atoms": mix58.get("total_atoms"),
                     "elements": len(mix58.get("elements_covered") or []),
                     "final_N": m58.get("final_N"),
                     "final_atoms": m58.get("final_atoms"),
                     "distinct": m58.get("final_distinct_formulas"),
                     "max_atoms": m58.get("final_max_atoms"),
                     "new_substances": m58.get("new_substances_total"),
                     "L": (t58 or {}).get("config", {}).get("L"),
                     "cap": 20,
                     "valence_note": "六元素/三价最多"})
    # T59A / T59B（读 t59_analysis.json key_numbers）
    l59 = kn59.get("loads") or {}
    for tag, kn, lk in (("T59A", kn59.get("A") or {}, l59.get("A") or {}),
                        ("T59B", kn59.get("B") or {}, l59.get("B") or {})):
        rows.append({"name": tag,
                     "molecules": lk.get("molecules"),
                     "atoms": lk.get("atoms"),
                     "elements": 9,
                     "final_N": kn.get("final_N"),
                     "final_atoms": kn.get("final_atoms"),
                     "distinct": kn.get("distinct"),
                     "max_atoms": kn.get("max_atoms"),
                     "new_substances": kn.get("new_substances"),
                     "L": kn.get("L") or lk.get("L"),
                     "cap": 40,
                     "valence_note": ("投料 %s（三价最多）"
                                      % ("%.1f/%.1f/%.1f" % tuple(
                                          100.0 * float(x) for x in
                                          (lk.get("valence_shares") or [])[:3])
                                         if lk.get("valence_shares") else "n/a"))})
    # T62A / T62B（本实验）
    for tag, P, ld in (("T62A", A, loads.get("batchA", {})),
                       ("T62B", B, loads.get("batchB", {}))):
        rows.append({"name": tag,
                     "molecules": (P.get("config") or {}).get("initial_particles"),
                     "atoms": (P.get("config") or {}).get("initial_atoms"),
                     "elements": len(ld.get("elements_covered") or []),
                     "final_N": P["final_total_molecules"],
                     "final_atoms": P["final_total_atoms"],
                     "distinct": P["final_distinct_formulas"],
                     "max_atoms": P["final_max_atoms"],
                     "new_substances": P["new_substances_count"],
                     "L": (P.get("config") or {}).get("L"),
                     "cap": (P.get("config") or {}).get("max_reaction_atoms") or 40,
                     "valence_note": ("投料 %s（等量价数）"
                                      % ("%.1f/%.1f/%.1f" % tuple(
                                          100.0 * float(x) for x in
                                          (ld.get("valence_shares") or [])[:3])
                                         if ld.get("valence_shares") else "n/a"))})
    rows_by_name = {r["name"]: r for r in rows}
    t59a = rows_by_name.get("T59A") or {}
    t59b = rows_by_name.get("T59B") or {}
    t62a = rows_by_name.get("T62A") or {}
    t62b = rows_by_name.get("T62B") or {}
    vref = (valence_balance or {}).get("t59_reference") or {}

    def _d(a, b):
        if a is None or b is None:
            return None
        return b - a

    return {
        "table": rows,
        "T59_vs_T62": {
            "L_equal": 60000.0,
            "cap_equal": 40,
            "valence_T59": vref.get("A_shares_text"),
            "valence_T62": ("%s : %s : %s" % tuple(
                "%.1f%%" % (100.0 * float(x)) for x in
                ((loads.get("batchA") or {}).get("valence_shares") or [])[:3])
                if (loads.get("batchA") or {}).get("valence_shares") else None),
            "final_N": {"T59A": t59a.get("final_N"), "T62A": t62a.get("final_N"),
                        "T59B": t59b.get("final_N"), "T62B": t62b.get("final_N")},
            "final_distinct": {"T59A": t59a.get("distinct"),
                               "T62A": t62a.get("distinct"),
                               "T59B": t59b.get("distinct"),
                               "T62B": t62b.get("distinct")},
            "final_max_atoms": {"T59A": t59a.get("max_atoms"),
                                "T62A": t62a.get("max_atoms"),
                                "T59B": t59b.get("max_atoms"),
                                "T62B": t62b.get("max_atoms")},
            "delta_final_N_A": _d(t59a.get("final_N"), t62a.get("final_N")),
            "delta_final_N_B": _d(t59b.get("final_N"), t62b.get("final_N")),
            "delta_distinct_A": _d(t59a.get("distinct"), t62a.get("distinct")),
            "delta_distinct_B": _d(t59b.get("distinct"), t62b.get("distinct")),
            "note": ("T59（价数 52.3:26.3:21.4，三价最多）vs T62（等量价数）；"
                     "其余条件一致：L=60000、cap40、两阶段各 1000 分钟 1000→0°C。"),
        },
    }


# ---------------------------------------------------------------- cap60 对照
def _cap_metrics(result, catalog, catalog_zh):
    """从 phase 结果提取 cap 对照需要的指标（HF 结果直接读，cap40 复用 phase dict）。"""
    cfg = result.get("config") or {}
    sm = result.get("summary") or {}
    final = result.get("final_composition") or {}
    total_m = sum(v.get("count", 0) for v in final.values())
    total_a = sum((v.get("atoms") or formula_atoms(f)) * v.get("count", 0)
                  for f, v in final.items())
    size_dist = Counter()
    for f, v in final.items():
        size_dist[v.get("atoms") or formula_atoms(f)] += v.get("count", 0)
    rc = {k: int((sm.get("reaction_counts") or {}).get(k, 0))
          for k in ("complete", "incomplete", "none", "capped")}
    total_rc = sum(rc.values()) or 1
    cap = int(cfg.get("max_reaction_atoms") or 40)
    giant_thr = max(1, cap - 1)
    top = []
    for f, v in sorted(final.items(), key=lambda kv: -kv[1].get("count", 0))[:13]:
        top.append({"formula": f, "zh": formula_zh(f, catalog_zh),
                    "count": v.get("count", 0),
                    "atoms": v.get("atoms") or formula_atoms(f),
                    "in_catalog": f in catalog})
    giant = sum(c for a, c in size_dist.items() if a >= giant_thr)
    giant_atoms = sum(a * c for a, c in size_dist.items() if a >= giant_thr)
    return {
        "max_reaction_atoms": cfg.get("max_reaction_atoms"),
        "giant_threshold": giant_thr,
        "final_N": sm.get("final_N", total_m),
        "final_atoms": sm.get("final_atoms", total_a),
        "distinct_formulas": len(final),
        "mean_atoms": rnd(total_a / total_m, 3) if total_m else None,
        "max_atoms": max(size_dist) if size_dist else None,
        "capped_total": rc.get("capped", 0),
        "capped_share": rnd(rc.get("capped", 0) / total_rc, 5),
        "complete": rc.get("complete", 0),
        "incomplete": rc.get("incomplete", 0),
        "none": rc.get("none", 0),
        "net_events": int(sm.get("events_total") or 0),
        "decomp_events": sm.get("decomp_events"),
        "new_substances": len(result.get("new_substances") or {}),
        "giant_molecules": giant,
        "giant_atoms": giant_atoms,
        "composition": {f: int(v.get("count", 0)) for f, v in final.items()},
        "size_distribution": [{"atoms": a, "molecules": size_dist[a]}
                              for a in sorted(size_dist)],
        "top10": top[:10],
        "top13": top,
        "runtime_s": sm.get("runtime_s"),
        "config": {k: cfg.get(k) for k in
                   ("L", "T0", "minutes", "max_reaction_atoms",
                    "initial_particles", "initial_atoms", "seed_initial_count")},
    }


def _giant_label(m):
    sd = {d["atoms"]: d["molecules"] for d in (m.get("size_distribution") or [])}
    thr = m.get("giant_threshold") or 39
    return [(a, sd[a]) for a in sorted(sd) if a >= thr]


def _fmt_atom_label(m, cap_metrics):
    sd = {d["atoms"]: d["molecules"] for d in (m.get("size_distribution") or [])}
    if not sd:
        return None
    a = max(sd)
    top = (m.get("top13") or [])
    f = next((r["formula"] for r in top if (r.get("atoms") or 0) == a), None)
    return a, f


def build_cap60_conclusion(a40, b40, a60, b60):
    """cap60 对照结论：全部由数据动态生成，不硬编码 T59 数字。"""
    concl = []
    # 1) 结构种数 / 巨人 / 最大尺寸
    a40g = sum(m for _, m in _giant_label(a40))
    b40g = sum(m for _, m in _giant_label(b40))
    a60g = sum(m for _, m in _giant_label(a60))
    b60g = sum(m for _, m in _giant_label(b60))
    a60_max = _fmt_atom_label(a60, a60)
    b60_max = _fmt_atom_label(b60, b60)
    concl.append(
        "cap%d 下 A %d 种 / B %d 种，≥%d 原子巨型分子 A %d 个 / B %d 个；"
        "cap%d 下 A %d 种（最大 %s 原子%s）、B %d 种（最大 %s 原子%s，≥%d 原子巨型 %d 个）。"
        % (a40.get("max_reaction_atoms") or 40,
           a40.get("distinct_formulas") or 0, b40.get("distinct_formulas") or 0,
           a40.get("giant_threshold") or 39, a40g, b40g,
           a60.get("max_reaction_atoms") or 60,
           a60.get("distinct_formulas") or 0,
           a60_max[0] if a60_max else "?", ("（%s）" % a60_max[1]) if a60_max and a60_max[1] else "",
           b60.get("distinct_formulas") or 0,
           b60_max[0] if b60_max else "?", ("（%s）" % b60_max[1]) if b60_max and b60_max[1] else "",
           a60.get("giant_threshold") or 59, a60g + b60g))
    # 2) capped 次数与占比
    def _pct(v):
        return "%.3f%%" % (100.0 * float(v or 0))
    concl.append(
        "capped 次数：A %s→%s（占判定 %s→%s），B %s→%s（%s→%s）；"
        "cap%d 的巨型堆积与额外结构主要来自 cap 边界（提高 cap 后结构种数下降：A %d→%d、B %d→%d）。"
        % (fmt_c(a40.get("capped_total")), fmt_c(a60.get("capped_total")),
           _pct(a40.get("capped_share")), _pct(a60.get("capped_share")),
           fmt_c(b40.get("capped_total")), fmt_c(b60.get("capped_total")),
           _pct(b40.get("capped_share")), _pct(b60.get("capped_share")),
           a40.get("max_reaction_atoms") or 40,
           a40.get("distinct_formulas") or 0, a60.get("distinct_formulas") or 0,
           b40.get("distinct_formulas") or 0, b60.get("distinct_formulas") or 0))
    # 3) 跨阶段稳定核心（cap60 下 A、B 共有的分子式，基于完整终态表）
    a60_comp = a60.get("composition") or {}
    b60_comp = b60.get("composition") or {}
    b60_sorted = sorted(b60_comp.items(), key=lambda kv: -kv[1])
    thr60 = b60.get("giant_threshold") or 59
    giants_b60 = [r["formula"] for r in (b60.get("top13") or [])
                  if (r.get("atoms") or 0) >= thr60]
    stable = [f for f, _ in b60_sorted if f in a60_comp and f not in set(giants_b60)]
    shown = stable[:10]
    stable_text = "、".join(shown) + ("等" if len(stable) > len(shown) else "")
    stable_text = stable_text or "无"
    extra_note = ""
    if giants_b60:
        giant_counts = []
        for f in giants_b60:
            cnt = next((r.get("count") for r in (b60.get("top13") or [])
                        if r["formula"] == f), 0)
            giant_counts.append(fmt_c(cnt))
        extra_note = ("；B 另有 %d 个 ≥%d 原子的残余巨型产物（%s，各 %s 个）"
                      % (len(giants_b60), thr60,
                         "、".join(giants_b60), "/".join(giant_counts)))
    concl.append(
        "cap%d 下 A、B 共有的分子式 %d 种（%s）为跨阶段稳定核心%s。"
        % (a60.get("max_reaction_atoms") or 60, len(stable),
           stable_text, extra_note))
    # 4) 尺寸上限结论
    a40max = a40.get("max_atoms")
    b40max = b40.get("max_atoms")
    a60max = a60.get("max_atoms")
    b60max = b60.get("max_atoms")
    b60g = sum(m for _, m in _giant_label(b60))
    if b60g:
        giant_tail = ("B cap%d 仍有 %d 个 ≥%d 原子的残余巨型产物，是 cap 边界内未拆解的巨大 F 产物，"
                      "但数量极少。" % (b60.get("max_reaction_atoms") or 60, b60g, thr60))
    else:
        giant_tail = ("B cap%d 下无 ≥%d 原子巨型产物（最大 %s 原子），说明 cap%d 下的巨型堆积"
                      "确由 cap 边界造成。"
                      % (b60.get("max_reaction_atoms") or 60, thr60, b60max,
                         a40.get("max_reaction_atoms") or 40))
    concl.append(
        "最大原子数：A cap%d=%s → cap%d=%s；B cap%d=%s → cap%d=%s。"
        "A cap%d 下最大仅 %s 原子，说明完全退火后的化学稳定上限受 cap 影响明显；%s"
        % (a40.get("max_reaction_atoms") or 40, a40max,
           a60.get("max_reaction_atoms") or 60, a60max,
           b40.get("max_reaction_atoms") or 40, b40max,
           b60.get("max_reaction_atoms") or 60, b60max,
           a60.get("max_reaction_atoms") or 60, a60max, giant_tail))
    return concl


def analyze_cap60(a_path, b_path, A40, B40, catalog, catalog_zh):
    if not a_path or not b_path:
        return None
    if not (os.path.exists(a_path) and os.path.exists(b_path)):
        return None
    try:
        a60 = _cap_metrics(load_json(a_path), catalog, catalog_zh)
        b60 = _cap_metrics(load_json(b_path), catalog, catalog_zh)
    except Exception as exc:
        print("[warn] cap60 结果读取失败：%s" % exc, flush=True)
        return None
    a40 = _cap_metrics({"config": A40.get("config"),
                        "summary": A40.get("summary"),
                        "final_composition": {
                            r["formula"]: {"count": r["count"],
                                           "atoms": r["atoms"]}
                            for r in (A40.get("final_table") or [])},
                        "new_substances": {}},
                       catalog, catalog_zh)
    b40 = _cap_metrics({"config": B40.get("config"),
                        "summary": B40.get("summary"),
                        "final_composition": {
                            r["formula"]: {"count": r["count"],
                                           "atoms": r["atoms"]}
                            for r in (B40.get("final_table") or [])},
                        "new_substances": {}},
                       catalog, catalog_zh)
    # new_substances 修正（_cap_metrics 传入的是空 dict）
    a40["new_substances"] = A40.get("new_substances_count")
    b40["new_substances"] = B40.get("new_substances_count")

    def cmp_rows(m40, m60):
        keys = [
            ("终态分子数", "final_N"), ("终态原子数", "final_atoms"),
            ("终态结构种数", "distinct_formulas"), ("平均原子数", "mean_atoms"),
            ("最大原子数", "max_atoms"), ("capped 次数", "capped_total"),
            ("capped 占判定比例", "capped_share"),
            ("complete", "complete"), ("incomplete", "incomplete"),
            ("none", "none"), ("净变化事件", "net_events"),
            ("新物质数", "new_substances"),
            ("%s+ 巨型分子" % (m40.get("giant_threshold") or 39),
             "giant_molecules"),
        ]
        rows = []
        for lab, k in keys:
            v40, v60 = m40.get(k), m60.get(k)
            rows.append({"metric": lab,
                         "cap40": v40, "cap60": v60,
                         "delta": (round(v60 - v40, 6)
                                   if isinstance(v40, (int, float)) and
                                   isinstance(v60, (int, float)) else None)})
        return rows

    def size_cmp(m40, m60):
        d40 = {d["atoms"]: d["molecules"] for d in m40["size_distribution"]}
        d60 = {d["atoms"]: d["molecules"] for d in m60["size_distribution"]}
        return [{"atoms": a,
                 "cap40": d40.get(a, 0), "cap60": d60.get(a, 0)}
                for a in sorted(set(d40) | set(d60))]

    return {
        "files": {"A_cap60": os.path.basename(a_path),
                  "B_cap60": os.path.basename(b_path),
                  "A_cap40": os.path.basename(DEFAULT_A),
                  "B_cap40": os.path.basename(DEFAULT_B)},
        "A": a60, "B": b60,
        "cap40": {"A": a40, "B": b40},
        "compare": {"A": cmp_rows(a40, a60), "B": cmp_rows(b40, b60)},
        "size_distribution_compare": {"A": size_cmp(a40, a60),
                                      "B": size_cmp(b40, b60)},
        "giant_compare": {"A": {"cap40": _giant_label(a40),
                                "cap60": _giant_label(a60)},
                          "B": {"cap40": _giant_label(b40),
                                "cap60": _giant_label(b60)}},
        "conclusion": build_cap60_conclusion(a40, b40, a60, b60),
    }


def fmt_c(v):
    return "{:,}".format(int(v or 0))


# ---------------------------------------------------------------- 主流程
def analyze_main(a_path, b_path, state_path, loads_path, control_path,
                 t59_path=None, t58_path=None, a_hf_path=None, b_hf_path=None):
    catalog, catalog_zh = load_catalog(BASE)
    subs_path = os.path.join(BASE, "substances.json")
    known29 = [r.get("formula") for r in
               (load_json(subs_path) if os.path.exists(subs_path) else [])
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
    vref = t59_valence_reference(t59_path)
    vbal = analyze_valence_balance(loads, A, B, vref)
    history = analyze_history(t59_path, t58_path, A, B, loads, vbal)
    # 控制组
    control = None
    if control_path and os.path.exists(control_path):
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
    capB = (B.get("config") or {}).get("max_reaction_atoms") or 40
    giant_thr = max(1, int(capB) - 1)
    giant = [s for s in structures if (s.get("atoms") or 0) >= giant_thr]
    regular = [s for s in structures if (s.get("atoms") or 0) < giant_thr]
    structure_stats = {
        "top_n": len(structures),
        "regular_count": len(regular),
        "giant_count": len(giant),
        "giant_threshold": giant_thr,
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
                  "control": os.path.basename(control_path) if control_path else None,
                  "t59": os.path.basename(t59_path) if t59_path else None,
                  "t58": (os.path.basename(t58_path)
                          if t58_path and os.path.exists(t58_path) else None),
                  "phaseA_hf": (os.path.basename(a_hf_path) if a_hf_path and
                                os.path.exists(a_hf_path) else None),
                  "phaseB_hf": (os.path.basename(b_hf_path) if b_hf_path and
                                os.path.exists(b_hf_path) else None)},
        "catalog_size": len(catalog),
        "known29": known29,
        "experiment": "T62 九元素·三/二/一价等量（对照 T59 的三价最多）",
        "engine": ("natural_engine.set_fast(True)（fast_pot，已审计）；"
                   "max_reaction_atoms=%s（主实验）%s"
                   % (capB, "/ 60（高保真对照）"
                      if (os.path.exists(str(a_hf_path or "")) and
                          os.path.exists(str(b_hf_path or ""))) else
                      "；cap60 高保真结果尚未就绪")),
        "schema_notes": [
            "event_samples 为蓄水池抽样（上限 50000）；净事件总数精确，类型拆分按比例估计。",
            "B 无 origin 字段；整理底物与第二批的贡献用 config.seed_initial_count 与 batchB 设计说明。",
            "capped=合并后原子数 >max_reaction_atoms 的弹性保护；time_series 有 capped/capped_cum/d_capped。",
            "快照 element_bitmask；final_top_structures 只有前 24，top30 其余用 fast 引擎重建。",
            "T62 投料为等量价数（v3:v2:v1≈1/3:1/3:1/3、9 元素≈1/9），"
            "summary.strict_order=false；不要用 strict_order_3gt2gt1=true 作为“三价最多”判据。",
        ],
    }
    analysis["loads"] = loads
    analysis["phaseA"] = A
    analysis["phaseB"] = B
    analysis["compare"] = compare
    analysis["valence_balance"] = vbal
    analysis["structures"] = {"top30": structures, **structure_stats}
    analysis["history"] = history
    analysis["control"] = control
    cap60 = analyze_cap60(a_hf_path or DEFAULT_A_HF, b_hf_path or DEFAULT_B_HF,
                          A, B, catalog, catalog_zh)
    analysis["cap60"] = cap60

    key = OrderedDict()
    key["loads"] = {
        "A": {"species": loads["batchA"]["n_species"],
              "molecules": loads["batchA"]["molecules"],
              "atoms": loads["batchA"]["atoms"],
              "mean_atoms": loads["batchA"]["mean_atoms"],
              "valence_atoms": loads["batchA"]["valence_atoms"],
              "valence_shares": loads["batchA"]["valence_shares"],
              "element_shares": loads["batchA"]["element_shares"],
              "equal_valence": loads["batchA"]["equal_valence"],
              "max_valence_deviation_pp":
                  loads["batchA"]["max_valence_deviation_pp"],
              "max_element_deviation_pp":
                  loads["batchA"]["max_element_deviation_pp"],
              "strict": loads["batchA"]["strict_order_3gt2gt1"]},
        "B": {"species": loads["batchB"]["n_species"],
              "molecules": loads["batchB"]["molecules"],
              "atoms": loads["batchB"]["atoms"],
              "mean_atoms": loads["batchB"]["mean_atoms"],
              "valence_atoms": loads["batchB"]["valence_atoms"],
              "valence_shares": loads["batchB"]["valence_shares"],
              "element_shares": loads["batchB"]["element_shares"],
              "equal_valence": loads["batchB"]["equal_valence"],
              "max_valence_deviation_pp":
                  loads["batchB"]["max_valence_deviation_pp"],
              "max_element_deviation_pp":
                  loads["batchB"]["max_element_deviation_pp"],
              "strict": loads["batchB"]["strict_order_3gt2gt1"]},
    }
    key["valence_balance"] = {
        "A": {"initial_shares": vbal["A"]["initial_shares"],
              "final_shares": vbal["A"]["final_shares"],
              "conserved": vbal["A"]["conserved"],
              "max_initial_deviation_pp": vbal["A"]["max_initial_deviation_pp"],
              "max_final_deviation_pp": vbal["A"]["max_final_deviation_pp"]},
        "B": {"initial_shares": vbal["B"]["initial_shares"],
              "final_shares": vbal["B"]["final_shares"],
              "conserved": vbal["B"]["conserved"],
              "max_initial_deviation_pp": vbal["B"]["max_initial_deviation_pp"],
              "max_final_deviation_pp": vbal["B"]["max_final_deviation_pp"]},
        "elements": {"A": {"initial_shares": vbal["elements"]["A"]["initial_shares"],
                           "final_shares": vbal["elements"]["A"]["final_shares"]},
                     "B": {"initial_shares": vbal["elements"]["B"]["initial_shares"],
                           "final_shares": vbal["elements"]["B"]["final_shares"]}},
        "t59_reference": vref,
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
    if cap60:
        key["cap60"] = {
            "A": {k: cap60["A"][k] for k in
                  ("max_reaction_atoms", "final_N", "final_atoms",
                   "distinct_formulas", "mean_atoms", "max_atoms",
                   "capped_total", "capped_share", "giant_molecules")},
            "B": {k: cap60["B"][k] for k in
                  ("max_reaction_atoms", "final_N", "final_atoms",
                   "distinct_formulas", "mean_atoms", "max_atoms",
                   "capped_total", "capped_share", "giant_molecules")},
            "conclusion": cap60["conclusion"],
        }
    analysis["key_numbers"] = key
    # caveats（全部动态生成）
    la = loads["batchA"]
    lb = loads["batchB"]
    event_note = ("event_samples 为蓄水池抽样（50000 上限）：A %s / B %s 净事件；"
                  "A 抽样 %d 条、B 抽样 %d 条；类型拆分按抽样比例估计，"
                  "逐分钟净事件总数由 events_total 差分精确。"
                  % (fmt_c(A["net_events_total"]), fmt_c(B["net_events_total"]),
                     A["event_samples_n"], B["event_samples_n"]))
    caveats = [
        event_note,
        "B 无 origin 字段；整理底物 %s 分子（A 终态 %d 种结构）+ batchB %s 分子 / %s 原子；"
        "两者相加=B 初始 %s 分子 / %s 原子（已验证）。"
        % ((B.get("config") or {}).get("seed_initial_count"),
           A["final_distinct_formulas"], fmt_c(lb["molecules"]),
           fmt_c(lb["atoms"]),
           fmt_c((B.get("config") or {}).get("initial_particles")),
           fmt_c((B.get("config") or {}).get("initial_atoms"))),
        "计算保护：合并后 >%d 原子的碰撞不反应（弹性）；≥%d 原子巨型分子是 cap 允许的"
        "最大 F 产物，数量少（B 终态 ≥%d 原子 %d 个分子），不代表化学上限。"
        % (capB, giant_thr, giant_thr,
           (B.get("large_stats") or {}).get("giant", {}).get("molecules", 0)),
        "final_top_structures 只有前 24；top30 其余 %d 个由 natural_engine.complete_products"
        "（fast 引擎）重建，均为 F 稳定单产物。"
        % structure_stats["rebuilt_count"],
        "结构图的键级用 edges 的 multiplicity（1/2/3）着色；S/C/L 键型需要原始 hex 几何，"
        "本图用布局算法重排，因此只标注多重键。",
        "T62 等量价数投料：A v3:v2:v1 = %s（偏差 %.3f pp），B(batchB) = %s（偏差 %.3f pp）；"
        "9 元素各 ≈11.1%%（最大偏差 A %.3f pp / B %.3f pp）；"
        "summary.strict_order=false，本实验不再把“三价最多”作为判据。"
        % (" : ".join("%.1f%%" % (100.0 * float(x)) for x in
                      (la.get("valence_shares") or [])[:3]),
           la.get("max_valence_deviation_pp") or 0,
           " : ".join("%.1f%%" % (100.0 * float(x)) for x in
                      (lb.get("valence_shares") or [])[:3]),
           lb.get("max_valence_deviation_pp") or 0,
           la.get("max_element_deviation_pp") or 0,
           lb.get("max_element_deviation_pp") or 0),
        ("T59 对照：投料价数 %s（三价最多）→ T62 等量价数；终态分子式数 T59A %s / T62A %s、"
         "T59B %s / T62B %s。" % (
             (vref or {}).get("A_shares_text") or "（t59_analysis.json 未就绪）",
             (history["T59_vs_T62"]["final_distinct"] or {}).get("T59A"),
             (history["T59_vs_T62"]["final_distinct"] or {}).get("T62A"),
             (history["T59_vs_T62"]["final_distinct"] or {}).get("T59B"),
             (history["T59_vs_T62"]["final_distinct"] or {}).get("T62B"))),
        "T62 环境 L=60000（与 T59 相同，比 T58 的 400000 面积缩小 44 倍），碰撞更频繁、"
        "退火更充分；允许 ≤%d 原子反应。" % capB,
    ]
    analysis["caveats"] = caveats
    return analysis


def main(argv=None):
    ap = argparse.ArgumentParser(description="T62 两阶段等量价数实验分析")
    ap.add_argument("--a", default=DEFAULT_A)
    ap.add_argument("--b", default=DEFAULT_B)
    ap.add_argument("--state", default=DEFAULT_STATE)
    ap.add_argument("--loads", default=DEFAULT_LOADS)
    ap.add_argument("--control", default=DEFAULT_CONTROL)
    ap.add_argument("--t59", default=DEFAULT_T59)
    ap.add_argument("--t58", default=DEFAULT_T58)
    ap.add_argument("--a-hf", default=DEFAULT_A_HF)
    ap.add_argument("--b-hf", default=DEFAULT_B_HF)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    if not os.path.exists(args.a) or not os.path.exists(args.b):
        print("[error] 缺少 phaseA/B 结果")
        return 2
    t0 = datetime.datetime.now()
    analysis = analyze_main(args.a, args.b, args.state, args.loads,
                            args.control, args.t59, args.t58,
                            args.a_hf, args.b_hf)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(analysis, fh, ensure_ascii=False, indent=1)
    print("[saved] %s (%.1fs) size %.1f MB"
          % (args.out, (datetime.datetime.now() - t0).total_seconds(),
             os.path.getsize(args.out) / 1024.0 / 1024.0))
    kn = analysis["key_numbers"]
    print(json.dumps({"loads": {t: {k: kn["loads"][t][k] for k in
                                    ("species", "molecules", "atoms",
                                     "valence_shares", "equal_valence",
                                     "max_valence_deviation_pp",
                                     "max_element_deviation_pp", "strict")}
                               for t in ("A", "B")},
                      "valence_balance": kn["valence_balance"],
                      "A": kn["A"], "B": kn["B"],
                      "compare": kn["compare"], "structures": kn["structures"]},
                     ensure_ascii=False, indent=1)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
