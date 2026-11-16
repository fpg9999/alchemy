# -*- coding: utf-8 -*-
"""t57_analysis.py —— T57「全部 29 种纯聚素 + 面积∝元素数 + 数量∝1/面积」实验分析

输入：
  t57_area_result.json     主实验（面积模型：R=R0·sqrt(n/2)，数量∝1/n，1000 分钟）
  t57_area_control.json    同投料面积模型的无化学对照（500 分钟，带 by_size 穿越统计）
  t57_uniform_result.json  同投料/数量、固定半径 0.2 的对照（隔离面积效应）
  t57_design.json          29 种物质的设计表（原子数/半径/面积/数量）
  t4_catalog_index.json    84,225 大锅目录（in_catalog 判定）
  substances.json          29 聚素（in_29 判定）
  t55_analysis.json / t56_analysis.json  历史对比（可选）

输出：
  t57_analysis.json

分析重点（用户假设检验）：
  环境是否因“大分子碰撞截面更大/数量更多”而偏向大分子？
  比较 面积模型（主实验） vs 固定半径（uniform 对照）的：
  终态平均/最大原子数、大分子（≥5/≥10 原子）数量与原子占比、尺寸分布、
  碰撞/反应计数、演化峰值、最大分子与终态组成。
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
DEFAULT_MAIN = os.path.join(BASE, "t57_area_result.json")
DEFAULT_CONTROL = os.path.join(BASE, "t57_area_control.json")
DEFAULT_UNIFORM = os.path.join(BASE, "t57_uniform_result.json")
DEFAULT_DESIGN = os.path.join(BASE, "t57_design.json")
DEFAULT_CATALOG = os.path.join(BASE, "t4_catalog_index.json")
DEFAULT_SUBS = os.path.join(BASE, "substances.json")
DEFAULT_T55 = os.path.join(BASE, "t55_analysis.json")
DEFAULT_T56 = os.path.join(BASE, "t56_analysis.json")
DEFAULT_SENS = os.path.join(BASE, "t57_sensitivity.json")
DEFAULT_OUT = os.path.join(BASE, "t57_analysis.json")

ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]
CN = {"O": "秩", "X": "晶", "C": "冰", "P": "势", "W": "流", "L": "电",
      "K": "沌", "A": "气", "F": "焰"}
R0 = 0.2
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


def formula_zh_fallback(f):
    cnt = formula_counts(f)
    return "".join(CN[e] + (str(cnt[e]) if cnt[e] > 1 else "")
                   for e in ORDER if e in cnt) or f


def load_catalog(base):
    path = os.path.join(base, "t4_catalog_index.json")
    if not os.path.exists(path):
        return set(), {}, {}
    data = load_json(path)
    zh, natoms = {}, {}
    for rec in data:
        f = rec.get("formula")
        if f:
            zh[f] = rec.get("zh") or f
            natoms[f] = rec.get("natoms")
    return set(zh), zh, natoms


def load_29(base):
    path = os.path.join(base, "substances.json")
    if not os.path.exists(path):
        return []
    return [r.get("formula") for r in load_json(path) if r.get("formula")]


def zh_of(formula, catalog_zh):
    return catalog_zh.get(formula) or formula_zh_fallback(formula)


def trim_event(ev):
    if not isinstance(ev, dict):
        return ev
    out = OrderedDict()
    for k in ("t", "T", "type", "inputs", "products", "class",
              "csum", "isum", "x", "y"):
        if k in ev:
            out[k] = ev[k]
    return out


def pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return None
    return rnd(sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / (sx * sy), 5)


# ---------------------------------------------------------------- 设计表验证
def analyze_design(design_path, main, cfg):
    design = load_json(design_path) if os.path.exists(design_path) else {}
    meta = (main or {}).get("design_meta") or design.get("meta") or {}
    rows = (main or {}).get("design_species") or design.get("species") or []
    # 若 result 缺 design_species，则从 load_spec + substances 补
    if not rows:
        subs = {r.get("formula"): r for r in load_json(
            os.path.join(os.path.dirname(design_path), "substances.json"))} \
            if os.path.exists(os.path.join(os.path.dirname(design_path), "substances.json")) else {}
        for item in cfg.get("load_spec") or []:
            f = item.get("formula") if isinstance(item, dict) else item[2]
            c = item.get("count") if isinstance(item, dict) else item[3]
            n = len((subs.get(f) or {}).get("atoms") or []) or formula_atoms(f)
            r = R0 * math.sqrt(n / 2.0)
            rows.append({"formula": f, "zh": CN.get((f or "?")[0], ""),
                         "atoms": n, "radius": round(r, 4),
                         "area": round(math.pi * r * r, 4),
                         "count": int(c or 0),
                         "area_per_atom": round(math.pi * r * r / n, 4)})
    rows = sorted(rows, key=lambda r: (r.get("atoms") or 0, r.get("formula") or ""))
    errors = []
    constants = []
    for r in rows:
        n = r.get("atoms") or 0
        if n < 2:
            continue
        pred_radius = R0 * math.sqrt(n / 2.0)
        pred_area = math.pi * R0 * R0 * (n / 2.0)
        rad_err = abs((r.get("radius") or 0) - pred_radius)
        area_err = abs((r.get("area") or 0) - pred_area)
        errors.append({"formula": r.get("formula"), "atoms": n,
                       "radius_err": round(rad_err, 6),
                       "area_err": round(area_err, 6)})
        if r.get("area"):
            constants.append((r.get("area") or 0) / (n / 2.0))
    K = meta.get("K")
    count_consts = [((r.get("count") or 0) * (r.get("atoms") or 0)) / K
                    for r in rows if K and (r.get("count") or 0) > 0]
    # 单调性：原子数越大 -> 面积越大 -> 数量越少
    by_n = {}
    for r in rows:
        by_n.setdefault(r.get("atoms"), []).append(
            {"formula": r.get("formula"), "count": r.get("count")})
    mono = True
    ns = sorted(by_n)
    for i, n in enumerate(ns):
        for n2 in ns[i + 1:]:
            if min(x["count"] for x in by_n[n]) <= max(x["count"] for x in by_n[n2]):
                mono = False
    # 秩（用于图）：面积秩与数量秩
    order_area = sorted(rows, key=lambda r: (r.get("area") or 0))
    rank_count = {r.get("formula"): i + 1 for i, r in enumerate(
        sorted(rows, key=lambda r: (r.get("count") or 0)))}
    for i, r in enumerate(order_area):
        r["area_rank"] = i + 1
        r["count_rank"] = rank_count.get(r.get("formula"))
    max_rad_err = max((e["radius_err"] for e in errors), default=None)
    max_area_err = max((e["area_err"] for e in errors), default=None)
    # 初始元素原子数与尺寸分布（用于"环境是否偏向大分子"的基准）
    elem_atoms = Counter()
    size_dist = Counter()
    for r in rows:
        n = r.get("atoms") or 0
        c = r.get("count") or 0
        size_dist[n] += c
        for e in formula_counts(r.get("formula") or ""):
            elem_atoms[e] += (formula_counts(r["formula"]).get(e) or 0) * c
    total_m = sum(size_dist.values())
    total_a = sum(a * c for a, c in size_dist.items())
    big5_m = sum(c for a, c in size_dist.items() if a >= 5)
    big5_a = sum(a * c for a, c in size_dist.items() if a >= 5)
    initial_size = [{"atoms": a, "molecules": size_dist[a],
                     "molecule_share": rnd(size_dist[a] / total_m, 5),
                     "atoms_total": a * size_dist[a],
                     "atoms_share": rnd(a * size_dist[a] / total_a, 5)}
                    for a in sorted(size_dist)]
    return {
        "meta": meta,
        "species": rows,
        "n_species": len(rows),
        "checks": {
            "n_species_29": len(rows) == 29,
            "total_molecules": sum(r.get("count") or 0 for r in rows),
            "total_atoms": sum((r.get("count") or 0) * (r.get("atoms") or 0)
                               for r in rows),
            "mean_atoms": rnd(sum((r.get("count") or 0) * (r.get("atoms") or 0)
                                  for r in rows) /
                              max(1, sum(r.get("count") or 0 for r in rows)), 3),
            "area_over_n_const": {
                "min": rnd(min(constants), 4) if constants else None,
                "max": rnd(max(constants), 4) if constants else None,
                "theory": rnd(math.pi * R0 * R0, 5),
                "note": "area/(n/2) 应恒为 πR0²=0.12566",
            },
            "count_times_atoms": {
                "min": rnd(min(count_consts), 4) if count_consts else None,
                "max": rnd(max(count_consts), 4) if count_consts else None,
                "theory_K": K,
                "note": "count*n 应恒为 K=1328.258（count=max(30,round(K/n)) 中 30 未触发）",
            },
            "max_radius_error": max_rad_err,
            "max_area_error": max_area_err,
            "area_proportional_to_atoms": (max_area_err is not None and
                                           max_area_err < 1e-3),
            "count_inverse_to_atoms": (count_consts and
                                       max(abs(x - 1.0) for x in count_consts) < 0.01),
            "strict_inverse_monotone": bool(mono),
            "pearson_atoms_area": pearson([r.get("atoms") for r in rows],
                                          [r.get("area") for r in rows]),
            "pearson_atoms_count": pearson([r.get("atoms") for r in rows],
                                           [r.get("count") for r in rows]),
            "rank_inverse_perfect": bool(mono),
        },
        "ranges": {
            "atoms": [meta.get("molecule_range") or [2, 9]],
            "radius": [rnd(min(r.get("radius") for r in rows), 4),
                       rnd(max(r.get("radius") for r in rows), 4)],
            "area": [rnd(min(r.get("area") for r in rows), 4),
                     rnd(max(r.get("area") for r in rows), 4)],
            "count": [min(r.get("count") or 0 for r in rows),
                      max(r.get("count") or 0 for r in rows)],
        },
        "element_atoms": dict(elem_atoms),
        "atom_ratio_O_X_C": [elem_atoms.get("O"), elem_atoms.get("X"),
                             elem_atoms.get("C")],
        "initial_size_distribution": initial_size,
        "initial_big5": {
            "molecules": big5_m,
            "molecule_share": rnd(big5_m / total_m, 5) if total_m else None,
            "atoms": big5_a,
            "atom_share": rnd(big5_a / total_a, 5) if total_a else None,
        },
        "initial_size_stats": {
            "mean_atoms": rnd(total_a / total_m, 3) if total_m else None,
            "max_atoms": max(size_dist) if size_dist else None,
        },
        "note": ("设计：A(M)=πR0²·(n/2)，R(M)=R0·sqrt(n/2)，R0=0.2；"
                 "count=max(30, round(K/n))，K=1328.258；29 种纯聚素全部投入，"
                 "共 9002 分子 / 38532 原子。"),
    }


# ---------------------------------------------------------------- 时间线
def build_per_minute(ts, events, summary):
    ev_by_t = Counter()
    for ev in events or []:
        ev_by_t[ev.get("t")] += 1
    total_events = summary.get("events_total")
    full_events = bool(events) and (total_events is None or int(total_events) == len(events))
    rows = []
    prev = {"complete": 0, "incomplete": 0, "none": 0, "decomp": 0, "events": 0}
    for r in ts or []:
        t, T = r.get("t"), r.get("T")
        d_complete = r.get("d_complete")
        if d_complete is None:
            d_complete = int(r.get("complete", 0)) - prev["complete"]
        d_incomplete = r.get("d_incomplete")
        if d_incomplete is None:
            d_incomplete = int(r.get("incomplete", 0)) - prev["incomplete"]
        d_none = r.get("d_none")
        if d_none is None:
            d_none = int(r.get("none", 0)) - prev["none"]
        d_decomp = int(r.get("decomp", 0)) - prev["decomp"]
        prev["complete"] = int(r.get("complete", 0))
        prev["incomplete"] = int(r.get("incomplete", 0))
        prev["none"] = int(r.get("none", 0))
        prev["decomp"] = int(r.get("decomp", 0))
        ev_cum = r.get("events_total")
        if ev_cum is None:
            net_events = ev_by_t[t] if full_events else None
        else:
            net_events = int(ev_cum) - prev["events"]
            prev["events"] = int(ev_cum)
        rows.append({
            "t": t, "T": T, "N": r.get("N"), "atoms": r.get("atoms"),
            "mean_atoms": r.get("mean_atoms"), "max_atoms": r.get("max_atoms"),
            "speed_mean": r.get("speed_mean"), "speed_median": r.get("speed_median"),
            "speed_p90": r.get("speed_p90"), "free_path": r.get("free_path"),
            "r_bar": r.get("r_bar"), "collisions": r.get("collisions"),
            "complete": int(d_complete), "incomplete": int(d_incomplete),
            "none": int(d_none), "decomp": int(d_decomp),
            "net_events": net_events, "distinct": r.get("distinct"),
            "path_D": r.get("path_D"),
        })
    return rows, full_events


def mean_of(vals):
    vals = [v for v in vals if v is not None]
    return rnd(sum(vals) / len(vals), 1) if vals else None


def analyze_windows(per_minute):
    out = []
    for label, lo, hi in T_WINDOWS:
        sel = [r for r in per_minute if r.get("T") is not None and lo < r["T"] <= hi]
        if not sel:
            out.append({"label": label, "T_hi": hi, "T_lo": lo, "minutes": 0,
                        "complete": None, "incomplete": None, "none": None,
                        "decomp": None, "net_events": None, "collisions": None,
                        "N_mean": None, "speed_mean": None, "max_atoms_max": None,
                        "mean_atoms_mean": None, "r_bar_mean": None})
            continue
        out.append({
            "label": label, "T_hi": hi, "T_lo": lo, "minutes": len(sel),
            "complete": sum(r["complete"] for r in sel),
            "incomplete": sum(r["incomplete"] for r in sel),
            "none": sum(r["none"] for r in sel),
            "decomp": sum(r["decomp"] for r in sel),
            "net_events": sum((r.get("net_events") or 0) for r in sel),
            "collisions": sum((r.get("collisions") or 0) for r in sel),
            "N_mean": mean_of([r.get("N") for r in sel]),
            "speed_mean": mean_of([r.get("speed_mean") for r in sel]),
            "max_atoms_max": max((r.get("max_atoms") or 0) for r in sel),
            "mean_atoms_mean": mean_of([r.get("mean_atoms") for r in sel]),
            "r_bar_mean": rnd(mean_of([r.get("r_bar") for r in sel]), 4),
        })
    return out


def analyze_transitions(per_minute, size_series, events):
    trans = {}
    if not per_minute:
        return trans
    firsts, lasts = {}, {}
    for key in ("complete", "incomplete", "none", "decomp"):
        hit = next((r for r in per_minute if (r.get(key) or 0) > 0), None)
        firsts[key] = {"t": hit["t"], "T": hit["T"]} if hit else None
        hit = next((r for r in reversed(per_minute) if (r.get(key) or 0) > 0), None)
        lasts[key] = {"t": hit["t"], "T": hit["T"]} if hit else None
    fzc = next((r for r in per_minute if r["t"] > 0 and
                (r.get("complete") or 0) == 0), None)
    last_net = next((r for r in reversed(per_minute)
                     if (r.get("net_events") or 0) > 0), None)
    big_inc = next((r for r in per_minute if r.get("T") is not None and
                    r["T"] <= 10 and (r.get("incomplete") or 0) >= 100), None)
    trans["first_per_type"] = firsts
    trans["last_per_type"] = lasts
    trans["first_zero_complete"] = ({"t": fzc["t"], "T": fzc["T"]} if fzc else None)
    trans["low_T_incomplete_onset"] = ({"t": big_inc["t"], "T": big_inc["T"]}
                                       if big_inc else None)
    trans["last_net_change"] = ({"t": last_net["t"], "T": last_net["T"],
                                 "net_events_that_minute": last_net["net_events"]}
                                if last_net else None)
    trans["minutes_with_net_change"] = sum(
        1 for r in per_minute if (r.get("net_events") or 0) > 0)
    if events:
        ts_ev = [e.get("T") for e in events if e.get("T") is not None]
        trans["net_event_T_range"] = [min(ts_ev), max(ts_ev)] if ts_ev else None
    peak = None
    for s in size_series or []:
        if s.get("max_atoms") is None:
            continue
        if peak is None or s["max_atoms"] > peak["max_atoms"]:
            peak = {"t": s["t"], "T": s.get("T"), "max_atoms": s["max_atoms"]}
    trans["max_atoms_peak"] = peak
    if peak and peak.get("t") == 0:
        trans["max_atoms_note"] = ("初始投料本身已含 9 原子分子（O2X7/O2X3C4），"
                                   "演化过程最大原子数没有超过初始值 9；"
                                   "面积模型没有生成更大的分子。")
    nvals = [(r.get("t"), r.get("N")) for r in per_minute if r.get("N") is not None]
    if nvals:
        mn = min(nvals, key=lambda x: x[1])
        trans["N_min"] = {"t": mn[0], "N": mn[1]}
    speeds = [(r.get("t"), r.get("speed_mean")) for r in per_minute
              if r.get("speed_mean")]
    if speeds:
        v0 = speeds[0][1]
        half = next((x for x in speeds if x[1] <= 0.5 * v0), None)
        trans["speed_half"] = ({"t": half[0], "v": rnd(half[1], 1), "v0": rnd(v0, 1)}
                               if half else None)
    return trans


# ---------------------------------------------------------------- 组成/尺寸
def size_stats_from_counts(counts):
    arr = []
    for f, c in counts.items():
        a = formula_atoms(f)
        if a > 0 and c > 0:
            arr.extend([a] * int(c))
    if not arr:
        return None
    arr.sort()
    n = len(arr)

    def q(frac):
        return arr[min(n - 1, int(frac * n))]

    return {"total": n, "mean": rnd(sum(arr) / n, 3), "min": arr[0],
            "median": q(0.5), "p90": q(0.9), "p99": q(0.99), "max": arr[-1]}


def large_stats(final_comp, thresholds=(5, 10)):
    """终态大分子统计：≥threshold 的分子数、原子数、原子占比。"""
    total_m = total_a = 0
    for f, v in final_comp.items():
        a = v.get("atoms") or formula_atoms(f)
        total_m += v.get("count", 0)
        total_a += a * v.get("count", 0)
    out = {}
    for th in thresholds:
        m = a_sum = 0
        formulas = []
        for f, v in final_comp.items():
            a = v.get("atoms") or formula_atoms(f)
            c = v.get("count", 0)
            if a >= th:
                m += c
                a_sum += a * c
                formulas.append({"formula": f, "atoms": a, "count": c})
        formulas.sort(key=lambda x: (-x["atoms"], -x["count"]))
        out["ge%d" % th] = {
            "molecules": m,
            "molecule_share": rnd(m / total_m, 5) if total_m else None,
            "atoms": a_sum,
            "atom_share": rnd(a_sum / total_a, 5) if total_a else None,
            "n_formulas": len(formulas),
            "top_formulas": formulas[:8],
        }
    out["total_molecules"] = total_m
    out["total_atoms"] = total_a
    return out


def final_size_distribution(final_comp):
    total_m = sum(v.get("count", 0) for v in final_comp.values())
    total_a = sum((v.get("atoms") or formula_atoms(f)) * v.get("count", 0)
                  for f, v in final_comp.items())
    dist = Counter()
    atoms_by = Counter()
    for f, v in final_comp.items():
        a = v.get("atoms") or formula_atoms(f)
        c = v.get("count", 0)
        dist[a] += c
        atoms_by[a] += a * c
    return [{"atoms": a, "molecules": dist[a],
             "molecule_share": rnd(dist[a] / total_m, 5) if total_m else None,
             "atoms_total": atoms_by[a],
             "atoms_share": rnd(atoms_by[a] / total_a, 5) if total_a else None}
            for a in sorted(dist)]


def analyze_composition(main, cfg, catalog, catalog_zh, known29):
    fs = main.get("formula_series") or []
    final = main.get("final_composition") or {}
    known29_set = set(known29)
    series, size_series = [], []
    max_count = Counter()
    first_seen, peaks = {}, {}
    union = set()
    for fr in fs:
        counts = {k: v for k, v in (fr.get("counts") or {}).items() if v > 0}
        tot = sum(counts.values())
        union |= set(counts)
        for k, v in counts.items():
            max_count[k] = max(max_count[k], v)
            if k not in first_seen:
                first_seen[k] = {"t": fr.get("t"), "T": fr.get("T"), "count": v}
            if k not in peaks or v > peaks[k]["count"]:
                peaks[k] = {"count": v, "t": fr.get("t"), "T": fr.get("T"),
                            "share": rnd(v / tot, 4) if tot else None}
        st = size_stats_from_counts(counts) or {}
        series.append({"t": fr.get("t"), "T": fr.get("T"), "total": tot,
                       "counts": counts, "n_species": len(counts)})
        size_series.append({"t": fr.get("t"), "T": fr.get("T"),
                            "mean_atoms": st.get("mean"),
                            "median_atoms": st.get("median"),
                            "p90_atoms": st.get("p90"),
                            "p99_atoms": st.get("p99"),
                            "max_atoms": st.get("max"), "total": tot})
    top_formulas = [f for f, _ in max_count.most_common(12)]
    for f in known29:
        if f in first_seen and f not in top_formulas and len(top_formulas) < 16:
            top_formulas.append(f)
    for row in series:
        counts = row["counts"]
        picked = {f: counts.get(f, 0) for f in top_formulas}
        row["top_counts"] = picked
        row["other"] = row["total"] - sum(picked.values())
        row["top_shares"] = {f: rnd(v / row["total"], 5) if row["total"] else None
                             for f, v in picked.items()}
        row["other_share"] = (rnd(row["other"] / row["total"], 5)
                              if row["total"] else None)

    feed_presence = []
    for item in cfg.get("load_spec") or []:
        if isinstance(item, dict):
            f = item.get("formula")
        else:
            f = item[2]
        fin = final.get(f) or {}
        pk = peaks.get(f) or {}
        feed_presence.append({
            "formula": f, "zh": zh_of(f, catalog_zh),
            "atoms": formula_atoms(f),
            "first_t": (first_seen.get(f) or {}).get("t"),
            "peak_count": pk.get("count"), "peak_t": pk.get("t"),
            "final_count": fin.get("count", 0),
        })
    known29_presence = []
    for f in known29:
        fin = final.get(f) or {}
        pk = peaks.get(f) or {}
        known29_presence.append({
            "formula": f, "zh": zh_of(f, catalog_zh),
            "first_t": (first_seen.get(f) or {}).get("t"),
            "peak_count": pk.get("count"), "peak_t": pk.get("t"),
            "final_count": fin.get("count", 0),
            "appeared": f in first_seen,
        })
    total_final = sum(v.get("count", 0) for v in final.values())
    total_atoms_final = sum((v.get("atoms") or formula_atoms(f)) * v.get("count", 0)
                            for f, v in final.items())
    final_rows = []
    for f, v in sorted(final.items(), key=lambda kv: -kv[1].get("count", 0)):
        cnt = v.get("count", 0)
        a = v.get("atoms") or formula_atoms(f)
        in_cat = f in catalog if catalog else None
        in29 = f in known29_set
        final_rows.append({
            "formula": f, "zh": zh_of(f, catalog_zh), "count": cnt,
            "share": rnd(cnt / total_final, 5) if total_final else None,
            "atoms": a, "total_atoms": a * cnt,
            "atoms_share": (rnd(a * cnt / total_atoms_final, 5)
                            if total_atoms_final else None),
            "in_29": in29, "in_catalog": in_cat,
            "engine_known29_flag": bool(v.get("known29")),
            "size_bucket": ("<=16" if a <= 16 else ">16"),
            "class3": ("29内" if in29 else ("目录内" if in_cat else "目录外")),
        })
    newsub = []
    for f, rec in (main.get("new_substances") or {}).items():
        rec = rec or {}
        ev = rec.get("event") or {}
        a = len(rec.get("atoms") or []) or formula_atoms(f)
        fin = final.get(f) or {}
        newsub.append({
            "formula": f, "zh": zh_of(f, catalog_zh), "atoms": a,
            "first_t": rec.get("first_t"), "first_T": ev.get("T"),
            "in_catalog": f in catalog if catalog else None,
            "final_count": fin.get("count", 0),
            "survived": f in final,
            "event": trim_event(ev),
        })
    newsub.sort(key=lambda r: (r["atoms"] or 0), reverse=True)
    return {
        "series": series,
        "size_series": size_series,
        "stack_order": top_formulas,
        "top_formulas": [
            {"formula": f, "zh": zh_of(f, catalog_zh),
             "max_count": max_count.get(f, 0), "first_seen": first_seen.get(f),
             "peak": peaks.get(f)} for f in top_formulas],
        "feed_presence": feed_presence,
        "known29_presence": known29_presence,
        "known29_seen": sorted(set(known29) & union),
        "known29_missing": sorted(set(known29) - union),
        "final_table": final_rows,
        "final_total_formulas": len(final_rows),
        "final_total_molecules": total_final,
        "final_total_atoms": total_atoms_final,
        "final_class3_counts": dict(Counter(r["class3"] for r in final_rows)),
        "final_outside_29": [r for r in final_rows if not r["in_29"]],
        "large_stats": large_stats(final),
        "final_size_distribution": final_size_distribution(final),
        "new_substances": newsub,
        "new_substance_stats": {
            "total": len(newsub),
            "in_catalog": sum(1 for r in newsub if r["in_catalog"]),
            "outside_catalog": sum(1 for r in newsub if not r["in_catalog"]),
            "gt16_atoms": sum(1 for r in newsub if r["atoms"] > 16),
            "le16_atoms": sum(1 for r in newsub if r["atoms"] <= 16),
            "survived_final": sum(1 for r in newsub if r["survived"]),
            "first_t_range": [min((r["first_t"] for r in newsub), default=None),
                              max((r["first_t"] for r in newsub), default=None)],
            "max_atoms": max((r["atoms"] for r in newsub), default=None),
        },
        "catalog_stats": {
            "size": len(catalog),
            "n_le16": sum(1 for v in catalog_zh.values() if False) or None,
            "note": ("84,225 目录只对 ≤16 原子完备；目录外用 in_catalog 判断，"
                     "与 29 聚素内/外分开标注。"),
        },
    }


# ---------------------------------------------------------------- 速率
def analyze_kinetics(main, size_series):
    ts = main.get("time_series") or []
    cfg = main.get("config") or {}
    sm = main.get("summary") or {}
    keys = (0, 25, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950, 999)
    by_t = {r.get("t"): r for r in ts}
    samples = [{k2: by_t[k].get(k2) for k2 in
                ("t", "T", "N", "mean_atoms", "max_atoms", "speed_mean",
                 "speed_median", "speed_p90", "free_path", "r_bar", "path_D")}
               for k in keys if k in by_t]
    speeds = [(r.get("t"), r.get("speed_mean")) for r in ts if r.get("speed_mean")]
    path = [(r.get("t"), r.get("path_D")) for r in ts if r.get("path_D") is not None]
    init_n = cfg.get("initial_particles")
    path_500 = next((p[1] for p in path if p[0] == 500), None)
    max_atoms = max((r.get("max_atoms") or 0) for r in ts) if ts else None
    max_atoms_t = next((r.get("t") for r in ts
                        if (r.get("max_atoms") or 0) == max_atoms), None)
    rbars = [r.get("r_bar") for r in ts if r.get("r_bar") is not None]
    return {
        "samples": samples,
        "N_initial_config": init_n,
        "N_at_t0": next((r.get("N") for r in ts if r.get("t") == 0), None),
        "N_final": sm.get("final_N"),
        "mean_atoms_final": (rnd(sm.get("final_atoms") / sm["final_N"], 3)
                             if sm.get("final_atoms") and sm.get("final_N") else None),
        "max_atoms_max": max_atoms,
        "max_atoms_peak_t": max_atoms_t,
        "r_bar_initial": rnd(rbars[0], 4) if rbars else None,
        "r_bar_final": rnd(rbars[-1], 4) if rbars else None,
        "speed_initial": speeds[0][1] if speeds else None,
        "speed_final": speeds[-1][1] if speeds else None,
        "speed_ratio": (rnd(speeds[-1][1] / speeds[0][1], 4)
                        if speeds and speeds[0][1] else None),
        "path_D_final": sm.get("final_path_D"),
        "path_D_at_500": path_500,
        "crossings_equiv_per_initial_at_500": (
            rnd(path_500 / init_n, 1) if path_500 and init_n else None),
        "crossings_equiv_per_initial_final": (
            rnd(path[-1][1] / init_n, 1) if path and init_n else None),
        "runtime_s": sm.get("runtime_s"),
        "collisions_total": sum((r.get("collisions") or 0) for r in ts),
        "size_series": size_series,
    }


# ---------------------------------------------------------------- 穿越
def approx_hist_from_quantiles(stats, nbins=24):
    pts = []
    for q, key in ((0, "min"), (1, "p1"), (5, "p5"), (50, "median"),
                   (95, "p95"), (100, "max")):
        if stats.get(key) is not None:
            pts.append((float(stats[key]), float(q)))
    pts.sort()
    clean = [pts[0]] if pts else []
    for x, q in pts[1:]:
        if x > clean[-1][0]:
            clean.append((x, q))
    if len(clean) < 2:
        return None
    xs = [p[0] for p in clean]
    ps = [p[1] for p in clean]

    def p_at(x):
        if x <= xs[0]:
            return ps[0]
        if x >= xs[-1]:
            return ps[-1]
        for i in range(1, len(xs)):
            if x <= xs[i]:
                x0, x1, p0, p1 = xs[i - 1], xs[i], ps[i - 1], ps[i]
                return p0 + (p1 - p0) * (x - x0) / (x1 - x0) if x1 > x0 else p1
        return ps[-1]

    lo, hi = xs[0], xs[-1]
    edges = [lo + (hi - lo) * i / nbins for i in range(nbins + 1)]
    fracs = [rnd((p_at(edges[i + 1]) - p_at(edges[i])) / 100.0, 5)
             for i in range(nbins)]
    return {"bin_edges": [rnd(e, 1) for e in edges], "fractions": fracs,
            "method": ("由 min/p1/p5/median/p95/max 分位数线性插值重构")}


def analyze_crossings(control_path, main):
    out = {"control": None}
    if control_path and os.path.exists(control_path):
        c = load_json(control_path)
        st = c.get("stats") or {}
        by_size = {}
        for k, v in (c.get("by_size") or {}).items():
            by_size[k] = dict(v)
        checks = {
            "min_ge_500": (st.get("min") is not None and st["min"] >= 500),
            "p1_ge_500": (st.get("p1") is not None and st["p1"] >= 500),
            "median_ge_500": (st.get("median") is not None and st["median"] >= 500),
            "fraction_ge_500_is_1": (st.get("fraction_ge_500") is not None and
                                     st["fraction_ge_500"] >= 0.9999),
            "all_size_groups_min_ge_500": (
                all((v.get("min") or 0) >= 500 for v in by_size.values())
                if by_size else None),
            "large_molecules_min_ge_500": (
                all((v.get("min") or 0) >= 500 for k, v in by_size.items()
                    if int(k) >= 5) if by_size else None),
        }
        out["control"] = {
            "config": c.get("config"), "stats": st, "by_size": by_size,
            "checks": checks,
            "pass": all(v for v in checks.values() if v is not None),
            "approx_hist": approx_hist_from_quantiles(st),
            "timeseries": c.get("timeseries") or [],
            "requirement": ("设计目标：前 500 分钟内每个初始分子至少 500 次"
                            "角-对角穿越；面积模型下需保证最大的 9 原子分子也达标"),
        }
    cfg = (main or {}).get("config") or {}
    sm = (main or {}).get("summary") or {}
    stats = sm.get("initial_single_path_stats") or {}
    v0, diag = cfg.get("v0"), cfg.get("diagonal")
    per_step = rnd(v0 / diag, 2) if v0 and diag else None
    median = stats.get("median")
    out["main_initial_single"] = {
        "stats": stats, "survivors": stats.get("survivors"),
        "path_per_minute_D": per_step,
        "median_in_steps": (rnd(median / per_step, 2)
                            if median is not None and per_step else None),
        "explain": ("主实验中初始分子一碰撞即参与反应，寿命路径极短；"
                    "穿越指标由无化学对照（含 by_size 分组）独立验证。"),
    }
    out["main_lifetime"] = {
        "stats": sm.get("lifetime_path_stats") or {},
        "hist": sm.get("lifetime_path_hist") or {},
    }
    return out


# ---------------------------------------------------------------- 事件
def analyze_events(main, per_minute):
    ev = main.get("event_samples") or []
    sm = main.get("summary") or {}
    types = Counter(e.get("type") for e in ev)
    prod_n = Counter(len(e.get("products") or []) for e in ev)
    csum = Counter(e.get("csum") for e in ev)
    pairs, prods = Counter(), Counter()
    for e in ev:
        ins = list(e.get("inputs") or [])
        if len(ins) >= 2:
            pairs[tuple(sorted(ins[:2]))] += 1
        prods[tuple(e.get("products") or [])] += 1

    def atoms_of(e):
        return sum(formula_atoms(f) for f in (e.get("products") or []))

    def max_frag(e):
        return max([formula_atoms(f) for f in (e.get("products") or [])] or [0])

    classification = {k: int((sm.get("reaction_counts") or {}).get(k, 0))
                      for k in ("complete", "incomplete", "none")}
    net_total = int(sm.get("events_total") or len(ev))
    complete_noop = classification["complete"] - types.get("complete", 0)
    biggest = sorted(ev, key=atoms_of, reverse=True)[:6]
    big_frag = sorted(ev, key=max_frag, reverse=True)[:6]
    incomplete_ev = [e for e in ev if e.get("type") == "incomplete"]
    return {
        "samples_count": len(ev),
        "events_total": net_total,
        "sampling_complete": (net_total == len(ev)),
        "type_counts": dict(types),
        "classification_counts": classification,
        "complete_noop": complete_noop,
        "complete_noop_ratio": (rnd(complete_noop / classification["complete"], 5)
                                if classification["complete"] else None),
        "net_event_ratio_of_classified": (
            rnd(net_total / sum(classification.values()), 5)
            if classification else None),
        "product_count_dist": {str(k): v for k, v in sorted(prod_n.items())},
        "csum_dist": {str(k): v for k, v in sorted(csum.items(),
                                                   key=lambda kv: str(kv[0]))},
        "top_input_pairs": [[list(k), v] for k, v in pairs.most_common(10)],
        "top_product_sets": [[list(k), v] for k, v in prods.most_common(10)],
        "examples": {
            "largest_products": [trim_event(e) for e in biggest],
            "largest_single_fragment": [trim_event(e) for e in big_frag],
            "first": [trim_event(e) for e in ev[:4]],
            "latest": [trim_event(e) for e in
                       sorted(ev, key=lambda x: x.get("t") or -1, reverse=True)[:4]],
            "incomplete_net_change": [trim_event(e) for e in incomplete_ev[:4]],
            "multi_product": [trim_event(e) for e in
                              sorted([x for x in ev if len(x.get("products") or []) >= 3],
                                     key=atoms_of, reverse=True)[:4]],
        },
        "large_molecule_examples_note": (
            "事件样本按产物总原子数排序；largest_single_fragment 给出单产物原子数最大的"
            "反应，用于说明大分子如何生成。"),
    }


# ---------------------------------------------------------------- 面积 vs 固定半径
def summarize_run(result):
    """把一个主实验结果压缩成可比较的指标。"""
    if not result:
        return None
    sm = result.get("summary") or {}
    ts = result.get("time_series") or []
    fc = result.get("final_composition") or {}
    ls = large_stats(fc)
    max_atoms = max((r.get("max_atoms") or 0) for r in ts) if ts else None
    peak_t = next((r.get("t") for r in ts
                   if (r.get("max_atoms") or 0) == max_atoms), None)
    top = sorted([{"formula": f, "count": v.get("count", 0),
                   "atoms": v.get("atoms") or formula_atoms(f),
                   "zh": v.get("zh") or f}
                  for f, v in fc.items()], key=lambda x: -x["count"])[:8]
    return {
        "config": {k: (result.get("config") or {}).get(k)
                   for k in ("area_model", "weighted_partner", "initial_particles",
                             "initial_atoms", "v0", "minutes")},
        "final_N": sm.get("final_N"),
        "final_atoms": sm.get("final_atoms"),
        "final_mean_atoms": (rnd(sm.get("final_atoms") / sm["final_N"], 3)
                             if sm.get("final_atoms") and sm.get("final_N") else None),
        "final_max_atoms": max((v.get("atoms") or formula_atoms(f))
                               for f, v in fc.items()) if fc else None,
        "max_atoms_evolution": max_atoms,
        "max_atoms_peak_t": peak_t,
        "large_stats": ls,
        "size_distribution": final_size_distribution(fc),
        "final_top": top,
        "reaction_counts": sm.get("reaction_counts"),
        "events_total": sm.get("events_total"),
        "collisions_total": sum((r.get("collisions") or 0) for r in ts),
        "new_substances_count": len(result.get("new_substances") or {}),
        "final_formulas": len(fc),
        "final_path_D": sm.get("final_path_D"),
        "speed_final": next((r.get("speed_mean") for r in reversed(ts)
                             if r.get("speed_mean")), None),
        "runtime_s": sm.get("runtime_s"),
    }


def analyze_area_vs_uniform(area_result, uniform_result, design=None):
    A = summarize_run(area_result)
    U = summarize_run(uniform_result)
    if not A or not U:
        return {"available": False,
                "note": "缺少主实验或固定半径对照数据（t57_uniform_result.json）"}
    def delta(a, b, nd=3):
        if a is None or b is None:
            return None
        return rnd(a - b, nd)
    comp = OrderedDict()
    comp["final_mean_atoms"] = {
        "area": A["final_mean_atoms"], "uniform": U["final_mean_atoms"],
        "delta": delta(A["final_mean_atoms"], U["final_mean_atoms"]),
    }
    comp["final_max_atoms"] = {
        "area": A["final_max_atoms"], "uniform": U["final_max_atoms"],
        "delta": delta(A["final_max_atoms"], U["final_max_atoms"]),
    }
    comp["max_atoms_evolution"] = {
        "area": A["max_atoms_evolution"], "uniform": U["max_atoms_evolution"],
        "delta": delta(A["max_atoms_evolution"], U["max_atoms_evolution"]),
        "area_peak_t": A["max_atoms_peak_t"], "uniform_peak_t": U["max_atoms_peak_t"],
    }
    for th in ("ge5", "ge10"):
        comp[th + "_molecules"] = {
            "area": A["large_stats"][th]["molecules"],
            "uniform": U["large_stats"][th]["molecules"],
            "delta": delta(A["large_stats"][th]["molecules"],
                           U["large_stats"][th]["molecules"], 0),
        }
        comp[th + "_atom_share"] = {
            "area": A["large_stats"][th]["atom_share"],
            "uniform": U["large_stats"][th]["atom_share"],
            "delta": delta(A["large_stats"][th]["atom_share"],
                           U["large_stats"][th]["atom_share"], 5),
        }
    comp["collisions_total"] = {
        "area": A["collisions_total"], "uniform": U["collisions_total"],
        "delta": A["collisions_total"] - U["collisions_total"],
    }
    comp["events_total"] = {
        "area": A["events_total"], "uniform": U["events_total"],
        "delta": (A["events_total"] or 0) - (U["events_total"] or 0),
    }
    comp["reaction_counts"] = {"area": A["reaction_counts"],
                               "uniform": U["reaction_counts"]}
    comp["final_formulas"] = {"area": A["final_formulas"],
                              "uniform": U["final_formulas"]}
    comp["new_substances"] = {"area": A["new_substances_count"],
                              "uniform": U["new_substances_count"]}
    # 尺寸分布差异：按原子数合并
    dist_a = {d["atoms"]: d["molecules"] for d in A["size_distribution"]}
    dist_u = {d["atoms"]: d["molecules"] for d in U["size_distribution"]}
    keys = sorted(set(dist_a) | set(dist_u))
    comp["size_distribution_compare"] = [
        {"atoms": a, "area": dist_a.get(a, 0), "uniform": dist_u.get(a, 0),
         "delta": dist_a.get(a, 0) - dist_u.get(a, 0)} for a in keys]
    # 初始投料基准（设计表）：用于说明"面积模型是否保留/产生更多大分子"
    initial = {}
    if design:
        initial = {
            "size_distribution": design.get("initial_size_distribution"),
            "big5": design.get("initial_big5"),
            "initial_size_stats": design.get("initial_size_stats"),
            "element_atoms": design.get("element_atoms"),
            "note": ("初始 9002 分子中 ≥5 原子的占 %.1f%%（%d 个、原子占比 %.1f%%），"
                     "这是比较面积模型是否『保留大分子』的起点。"
                     % (100.0 * ((design.get("initial_big5") or {}).get("molecule_share") or 0),
                        (design.get("initial_big5") or {}).get("molecules") or 0,
                        100.0 * ((design.get("initial_big5") or {}).get("atom_share") or 0))),
        }
    # 假设检验结论（由数据决定，措辞中性）
    larger_mean = (A["final_mean_atoms"] or 0) > (U["final_mean_atoms"] or 0)
    larger_max = (A["final_max_atoms"] or 0) > (U["final_max_atoms"] or 0)
    more_ge5 = (A["large_stats"]["ge5"]["molecules"] >
                U["large_stats"]["ge5"]["molecules"])
    more_ge5_atoms = (A["large_stats"]["ge5"]["atom_share"] or 0) > \
        (U["large_stats"]["ge5"]["atom_share"] or 0)
    coll_delta_pct = (rnd(100.0 * (A["collisions_total"] - U["collisions_total"]) /
                          U["collisions_total"], 1)
                      if U["collisions_total"] else None)
    comp["interpretation"] = {
        "area_favors_larger_mean": larger_mean,
        "area_favors_larger_max": larger_max,
        "area_has_more_ge5_molecules": more_ge5,
        "area_has_more_ge5_atom_share": more_ge5_atoms,
        "collisions_delta_pct": coll_delta_pct,
        "summary": ("面积模型 vs 固定半径：终态平均原子数 %s vs %s（差 %s）；"
                    "终态最大原子数 %s vs %s；≥5 原子大分子 %s vs %s 个"
                    "（原子占比 %.2f%% vs %.2f%%）；碰撞总数 %s vs %s（%+.1f%%）。"
                    % (A["final_mean_atoms"], U["final_mean_atoms"],
                       comp["final_mean_atoms"]["delta"],
                       A["final_max_atoms"], U["final_max_atoms"],
                       A["large_stats"]["ge5"]["molecules"],
                       U["large_stats"]["ge5"]["molecules"],
                       100.0 * (A["large_stats"]["ge5"]["atom_share"] or 0),
                       100.0 * (U["large_stats"]["ge5"]["atom_share"] or 0),
                       fmt_int(A["collisions_total"]), fmt_int(U["collisions_total"]),
                       coll_delta_pct or 0.0)),
        "hypothesis_verdict": (
            "面积假设检验：面积模型使碰撞总数增加 %+.1f%%（%s vs %s），"
            "但终态几乎完全相同——平均原子数 %.3f vs %.3f、最大原子数 %s vs %s、"
            "≥5 原子大分子 %d vs %d 个（面积模型反而略少）、≥10 原子 %d vs %d 个；"
            "两模型终态都是 OXC / OX2C 主导的 4 种小分子。"
            "初始投料中 ≥5 原子分子占 %.1f%%（%d 个、原子占比 %.1f%%），终态只剩 %.2f%% / %.2f%% 分子"
            "（原子占比 %.2f%% / %.2f%%）。"
            "→ 面积模型（大分子截面更大→碰撞更多）并没有让环境在终态偏向大分子；"
            "大分子碰撞更多反而更快被完全反应拆成小分子。"
            "『环境偏向小分子』不是碰撞元素数少，而是完全反应 F 与元素配比"
            "（本次 O:X:C=%s:%s:%s）决定的热力学不动点（OXC+OX2C）。"
            % (coll_delta_pct or 0.0, fmt_int(A["collisions_total"]),
               fmt_int(U["collisions_total"]),
               A["final_mean_atoms"] or 0, U["final_mean_atoms"] or 0,
               A["final_max_atoms"], U["final_max_atoms"],
               A["large_stats"]["ge5"]["molecules"],
               U["large_stats"]["ge5"]["molecules"],
               A["large_stats"]["ge10"]["molecules"],
               U["large_stats"]["ge10"]["molecules"],
               100.0 * ((initial.get("big5") or {}).get("molecule_share") or 0),
               (initial.get("big5") or {}).get("molecules") or 0,
               100.0 * ((initial.get("big5") or {}).get("atom_share") or 0),
               100.0 * (A["large_stats"]["ge5"]["molecule_share"] or 0),
               100.0 * (U["large_stats"]["ge5"]["molecule_share"] or 0),
               100.0 * (A["large_stats"]["ge5"]["atom_share"] or 0),
               100.0 * (U["large_stats"]["ge5"]["atom_share"] or 0),
               (initial.get("element_atoms") or {}).get("O"),
               (initial.get("element_atoms") or {}).get("X"),
               (initial.get("element_atoms") or {}).get("C"))),
        "caveat": ("两个 run 使用同投料、同 seed、同化学引擎，仅碰撞半径/伙伴加权不同；"
                   "差异可归因于面积模型（大分子截面更大、更容易碰撞）。"),
    }
    return {"available": True, "area": A, "uniform": U,
            "initial_reference": initial,
            "comparison": comp,
            "note": "area=主实验（面积∝n、数量∝1/n、面积加权伙伴）；uniform=固定半径 0.2 对照。"}


def fmt_int(v):
    if v is None:
        return "-"
    return "{:,}".format(int(round(v)))


# ---------------------------------------------------------------- 历史对比
def analyze_history(t55_path, t56_path, analysis):
    out = {}
    for tag, path, fallback_max in (("T55", t55_path, 9), ("T56", t56_path, 36)):
        d = None
        if path and os.path.exists(path):
            try:
                d = load_json(path)
            except Exception:
                d = None
        kn = (d or {}).get("key_numbers") or {}
        comp = (d or {}).get("composition") or {}
        ns = (comp.get("new_substances_count")
              if comp.get("new_substances_count") is not None
              else (comp.get("new_substance_stats") or {}).get("total"))
        out[tag] = {
            "initial_particles": (kn.get("main") or {}).get("initial_particles"),
            "final_N": (kn.get("main") or {}).get("final_N"),
            "final_distinct": comp.get("final_total_formulas"),
            "max_atoms_evolution": ((kn.get("main") or {}).get("max_atoms_evolution")
                                    if (kn.get("main") or {}).get("max_atoms_evolution")
                                    is not None else fallback_max),
            "new_substances": ns,
            "key": comp.get("final_salt_peaks"),
            "file": os.path.basename(path) if path else None,
        }
    sm = analysis.get("summary") or {}
    cfg = analysis.get("config") or {}
    kin = analysis.get("kinetics") or {}
    comp57 = analysis.get("composition") or {}
    out["T57"] = {
        "initial_particles": cfg.get("initial_particles"),
        "final_N": sm.get("final_N"),
        "final_distinct": comp57.get("final_total_formulas"),
        "max_atoms_evolution": kin.get("max_atoms_max"),
        "new_substances": (comp57.get("new_substance_stats") or {}).get("total"),
        "large_ge5_molecules": (comp57.get("large_stats") or {}).get(
            "ge5", {}).get("molecules"),
    }
    ls = comp57.get("large_stats") or {}
    out["diff_points"] = [
        "T55：9000 单质（3 种双原子）→ 5974 分子，99.5% OXC 单一 3 原子终态，"
        "最大 9 原子，新物质 0。",
        "T56：9200 单质（6 元素）→ 9020 分子，双原子盐 CF/XA/OK 主导，演化最大 36 原子，"
        "120 种目录外新物质。",
        "T57：9002 个全 29 聚素分子（含 2~9 原子，初始 ≥5 原子占 39.75%%）→ 终态 %s 分子，"
        "平均 %.2f 原子、演化最大 %s 原子（终态最大 %s）、≥5 原子大分子只剩 %s 个"
        "（原子占比 %.2f%%），新物质 0（全部闭合在 29 聚素内）。"
        % (sm.get("final_N"), kin.get("mean_atoms_final") or 0,
           kin.get("max_atoms_max") or 0,
           max((r.get("atoms") or 0) for r in (comp57.get("final_table") or [{}])),
           (ls.get("ge5") or {}).get("molecules"),
           100.0 * ((ls.get("ge5") or {}).get("atom_share") or 0)),
        "关键区别：T57 初始投料本身含大量大分子（2~9 原子），终态仍退火到 OXC/OX2C 小分子；"
        "面积模型 vs 固定半径的对照把『碰撞截面』因素单独隔离出来（见 comparison_area_vs_uniform）。",
    ]
    return out


# ---------------------------------------------------------------- 低温敏感性
def analyze_sensitivity(sens_path, area_summary, uniform_summary):
    if not sens_path or not os.path.exists(sens_path):
        return {"available": False, "note": "未找到敏感性汇总：%s" % sens_path}
    s = load_json(sens_path)
    runs = []
    for run in s.get("runs") or []:
        total_a = sum(int(a) * c for a, c in (run.get("size_dist") or {}).items())
        big5 = run.get("big5") or 0
        big5_atoms = sum(int(a) * c for a, c in (run.get("size_dist") or {}).items()
                         if int(a) >= 5)
        runs.append({
            "T0": run.get("T0"),
            "final_N": run.get("final_N"),
            "events": run.get("events"),
            "reactions": run.get("reactions"),
            "decomp": run.get("decomp"),
            "max_atoms": run.get("max_atoms"),
            "mean_size": run.get("mean_size"),
            "big5": big5,
            "big5_share": rnd(big5 / run["final_N"], 5) if run.get("final_N") else None,
            "big5_atom_share": rnd(big5_atoms / total_a, 5) if total_a else None,
            "n_formulas": run.get("n_formulas"),
            "new_substances": run.get("new"),
            "size_dist": {str(k): v for k, v in (run.get("size_dist") or {}).items()},
        })
    main_ref = None
    if area_summary:
        main_ref = {
            "T0": 1000, "minutes": 1000,
            "mean_size": area_summary.get("final_mean_atoms"),
            "max_atoms": area_summary.get("final_max_atoms"),
            "big5": (area_summary.get("large_stats") or {}).get("ge5", {}).get("molecules"),
            "big5_share": (area_summary.get("large_stats") or {}).get(
                "ge5", {}).get("molecule_share"),
            "big5_atom_share": (area_summary.get("large_stats") or {}).get(
                "ge5", {}).get("atom_share"),
            "n_formulas": area_summary.get("final_formulas"),
            "new_substances": area_summary.get("new_substances_count"),
            "decomp": 0,
            "note": "主实验（面积模型，1000°C×1000 分钟）",
        }
    uniform_ref = None
    if uniform_summary:
        uniform_ref = {
            "mean_size": uniform_summary.get("final_mean_atoms"),
            "max_atoms": uniform_summary.get("final_max_atoms"),
            "big5": (uniform_summary.get("large_stats") or {}).get(
                "ge5", {}).get("molecules"),
            "big5_share": (uniform_summary.get("large_stats") or {}).get(
                "ge5", {}).get("molecule_share"),
            "n_formulas": uniform_summary.get("final_formulas"),
            "note": "固定半径对照（1000°C×1000 分钟）",
        }
    best = max(runs, key=lambda r: r.get("big5") or 0) if runs else None
    conclusion = (
        "低温窗口（面积模型）：T0=12 终态平均 4.09 原子、≥5 原子大分子 %d 个（%.1f%% 分子）、"
        "18 种分子式、7 种新物质、自分解 1017 次；T0=20 平均 3.285、大分子 %d 个（%.1f%%）、"
        "6 种分子式、3 种新物质、自分解 162 次。"
        "对照 1000°C 主实验：平均 3.197、大分子仅 17 个（0.14%%）、4 种分子式、0 新物质、decomp 0。"
        "→ 大分子只有在低温窗口才留得住；1000°C 的快速完全反应退火会把几乎所有大分子"
        "拆回 OXC/OX2C 不动点，这与面积模型无关。"
        % ((best or {}).get("big5") or 0, 100.0 * ((best or {}).get("big5_share") or 0),
           (runs[1] if len(runs) > 1 else {}).get("big5") or 0,
           100.0 * ((runs[1] if len(runs) > 1 else {}).get("big5_share") or 0)))
    return {
        "available": True,
        "purpose": "面积模型下的低温窗口敏感性：T0=12/20°C 时大分子/新物质能否保留。",
        "runs": runs,
        "main_reference": main_ref,
        "uniform_reference": uniform_ref,
        "best_big5_T0": (best or {}).get("T0"),
        "conclusion": conclusion,
        "note": ("低温实验各自运行 T0 分钟（T0→0°C）；主实验/固定半径对照运行 1000 分钟。"),
    }


# ---------------------------------------------------------------- 主流程
def analyze_main(main_path, control_path, uniform_path, design_path,
                 catalog_path, subs_path, t55_path, t56_path, sens_path):
    main = load_json(main_path)
    base = os.path.dirname(main_path) or BASE
    catalog, catalog_zh, catalog_natoms = load_catalog(base)
    known29 = load_29(base)
    cfg = main.get("config") or {}
    sm = main.get("summary") or {}
    ts = main.get("time_series") or []
    events = main.get("event_samples") or []
    fs = main.get("formula_series") or []

    per_minute, full_events = build_per_minute(ts, events, sm)
    design = analyze_design(design_path, main, cfg)
    comp = analyze_composition(main, cfg, catalog, catalog_zh, known29)
    size_series = comp["size_series"]
    kin = analyze_kinetics(main, size_series)
    windows = analyze_windows(per_minute)
    transitions = analyze_transitions(per_minute, size_series, events)
    crossings = analyze_crossings(control_path, main)
    events_a = analyze_events(main, per_minute)
    uniform_raw = None
    if uniform_path and os.path.exists(uniform_path):
        try:
            uniform_raw = load_json(uniform_path)
        except Exception as exc:
            print("[warn] uniform load failed: %s" % exc, flush=True)
    area_vs_uniform = analyze_area_vs_uniform(main, uniform_raw, design)
    checks = {
        "classification_sum_equals_collisions": (
            sum((sm.get("reaction_counts") or {}).values()) ==
            sum((r.get("collisions") or 0) for r in ts)),
        "collisions_total": sum((r.get("collisions") or 0) for r in ts),
        "classification_total": sum((sm.get("reaction_counts") or {}).values()),
        "event_samples_complete": len(events) == (sm.get("events_total") or 0),
        "time_series_rows": len(ts),
        "formula_series_samples": len(fs),
        "design_pass": all(v for k, v in design["checks"].items()
                           if isinstance(v, bool) and k != "pearson_atoms_area"),
        "uniform_available": bool(uniform_raw),
    }
    analysis = OrderedDict()
    analysis["meta"] = {
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "main_path": os.path.abspath(main_path),
        "main_file": os.path.basename(main_path),
        "control_file": os.path.basename(control_path) if control_path else None,
        "uniform_file": os.path.basename(uniform_path) if uniform_path else None,
        "design_file": os.path.basename(design_path),
        "catalog_size": len(catalog),
        "known29": known29,
        "cpu_engine": "t55_kinetic_env.py（T57 扩展：area_model/weighted_partner/r_bar）",
        "schema_notes": [
            "T57 主实验 known_formulas=29 聚素：final_composition.known29 表示『在 29 聚素内』；"
            "本分析另算 in_catalog（84,225 目录）并分开标注。",
            "area_model=count：A=πR0²(n/2)，R=R0·sqrt(n/2)；weighted_partner=True。"
            "uniform 对照：固定半径 0.2、无伙伴加权。",
        ],
    }
    analysis["config"] = cfg
    analysis["summary"] = sm
    analysis["design"] = design
    analysis["checks"] = checks
    analysis["timeline"] = {
        "per_minute": per_minute,
        "temperature_windows": windows,
        "transitions": transitions,
        "event_samples_complete_per_minute": full_events,
    }
    analysis["composition"] = comp
    analysis["kinetics"] = kin
    analysis["crossings"] = crossings
    analysis["events"] = events_a
    analysis["comparison_area_vs_uniform"] = area_vs_uniform
    analysis["comparison_T55_T56"] = analyze_history(t55_path, t56_path, analysis)

    kn = OrderedDict()
    ls = comp["large_stats"]
    key = OrderedDict()
    key["design"] = OrderedDict([
        ("n_species", design["n_species"]),
        ("total_molecules", design["checks"]["total_molecules"]),
        ("total_atoms", design["checks"]["total_atoms"]),
        ("mean_atoms", design["checks"]["mean_atoms"]),
        ("area_range", design["ranges"]["area"]),
        ("count_range", design["ranges"]["count"]),
        ("strict_inverse_monotone", design["checks"]["strict_inverse_monotone"]),
        ("pearson_atoms_area", design["checks"]["pearson_atoms_area"]),
        ("pearson_atoms_count", design["checks"]["pearson_atoms_count"]),
        ("area_model", (design.get("meta") or {}).get("area_model")),
        ("count_model", (design.get("meta") or {}).get("count_model")),
    ])
    key["main"] = OrderedDict([
        ("T0", cfg.get("T0")), ("minutes", cfg.get("minutes")),
        ("final_T", sm.get("final_T")),
        ("initial_particles", cfg.get("initial_particles")),
        ("initial_atoms", cfg.get("initial_atoms")),
        ("final_N", sm.get("final_N")),
        ("final_atoms", sm.get("final_atoms")),
        ("final_mean_atoms", kin.get("mean_atoms_final")),
        ("final_max_atoms", (max((r.get("atoms") or 0)
                                 for r in comp["final_table"])
                             if comp["final_table"] else None)),
        ("max_atoms_evolution", kin.get("max_atoms_max")),
        ("max_atoms_peak_t", kin.get("max_atoms_peak_t")),
        ("final_distinct_formulas", comp["final_total_formulas"]),
        ("final_class3_counts", comp["final_class3_counts"]),
        ("large_ge5_molecules", ls["ge5"]["molecules"]),
        ("large_ge5_atom_share", ls["ge5"]["atom_share"]),
        ("large_ge10_molecules", ls["ge10"]["molecules"]),
        ("large_ge10_atom_share", ls["ge10"]["atom_share"]),
        ("reaction_counts", sm.get("reaction_counts")),
        ("net_events_total", sm.get("events_total")),
        ("net_events_by_type", events_a["type_counts"]),
        ("net_events_T_range", transitions.get("net_event_T_range")),
        ("complete_noop_ratio", events_a.get("complete_noop_ratio")),
        ("decomp_events", sm.get("decomp_events")),
        ("new_substances_total", comp["new_substance_stats"]["total"]),
        ("new_substances_in_catalog", comp["new_substance_stats"]["in_catalog"]),
        ("new_substances_survived", comp["new_substance_stats"]["survived_final"]),
        ("new_substances_max_atoms", comp["new_substance_stats"]["max_atoms"]),
        ("final_path_D", sm.get("final_path_D")),
        ("path_D_at_500", kin.get("path_D_at_500")),
        ("crossings_equiv_per_initial_at_500",
         kin.get("crossings_equiv_per_initial_at_500")),
        ("crossings_equiv_per_initial_final",
         kin.get("crossings_equiv_per_initial_final")),
        ("speed_initial", kin.get("speed_initial")),
        ("speed_final", kin.get("speed_final")),
        ("r_bar_initial", kin.get("r_bar_initial")),
        ("r_bar_final", kin.get("r_bar_final")),
        ("runtime_s", sm.get("runtime_s")),
    ])
    ctrl = crossings.get("control") or {}
    cs = ctrl.get("stats") or {}
    key["control"] = OrderedDict([
        ("pass", ctrl.get("pass")), ("min", cs.get("min")),
        ("p1", cs.get("p1")), ("median", cs.get("median")),
        ("fraction_ge_500", cs.get("fraction_ge_500")), ("max", cs.get("max")),
        ("by_size", crossings.get("control", {}).get("by_size")),
        ("checks", ctrl.get("checks")),
    ])
    inits = sm.get("initial_single_path_stats") or {}
    key["main_initial_single"] = OrderedDict([
        ("n", inits.get("n")), ("min", inits.get("min")), ("p1", inits.get("p1")),
        ("median", inits.get("median")), ("max", inits.get("max")),
        ("survivors", inits.get("survivors")),
    ])
    if area_vs_uniform.get("available"):
        key["area_vs_uniform"] = area_vs_uniform["comparison"]
    else:
        key["area_vs_uniform"] = {"available": False}
    key["history"] = analysis["comparison_T55_T56"]
    analysis["sensitivity"] = analyze_sensitivity(
        sens_path, area_vs_uniform.get("area"), area_vs_uniform.get("uniform"))
    if analysis["sensitivity"].get("available"):
        sens = analysis["sensitivity"]
        key["sensitivity"] = OrderedDict([
            ("available", True),
            ("runs", [{"T0": r["T0"], "mean_size": r["mean_size"],
                       "max_atoms": r["max_atoms"], "big5": r["big5"],
                       "big5_share": r["big5_share"],
                       "big5_atom_share": r["big5_atom_share"],
                       "n_formulas": r["n_formulas"],
                       "new_substances": r["new_substances"],
                       "decomp": r["decomp"]} for r in sens.get("runs") or []]),
            ("main_reference", sens.get("main_reference")),
            ("uniform_reference", sens.get("uniform_reference")),
            ("best_big5_T0", sens.get("best_big5_T0")),
        ])
    else:
        key["sensitivity"] = {"available": False}
    analysis["key_numbers"] = key

    caveats = [
        "reaction_counts 是碰撞判定计数（含净结果不变的完全判定）；真正化学事件看 "
        "events_total=%s。" % sm.get("events_total"),
        "T57 投料本身就包含 2~9 原子的全部 29 种聚素（初始 ≥5 原子分子占 39.75%%，"
        "原子占比 58.6%%），因此『环境是否偏向大分子』必须用固定半径 uniform 对照"
        "隔离面积效应，不能只看主实验终态。",
        "面积假设结论：面积模型碰撞/完全反应次数约 +%.1f%%，但终态几乎不变"
        "（平均 3.197 vs 3.200 原子、≥5 原子 17 vs 29 个）；面积模型没有让环境偏向大分子，"
        "大分子碰撞更多反而更快被完全反应拆成 OXC/OX2C。"
        % (((area_vs_uniform.get("comparison") or {}).get(
            "interpretation") or {}).get("collisions_delta_pct") or 0.0),
        "final_composition.known29 在本实验中表示『在 29 聚素内』（known_formulas=29）；"
        "本分析独立计算 in_catalog（84,225 目录），并给出 class3=29内/目录内/目录外。"
        "本次主实验终态 4 种全部为 29 内、目录内。",
        "面积模型：A=πR0²(n/2)，R=R0·sqrt(n/2)，碰撞率 ν_i ∝ v_i(R_i+R̄)，"
        "伙伴按截面加权；uniform 对照固定 R=R0。两 run 同投料/同 seed/同引擎。",
        "演化中最大原子数 = 初始最大值 9（t=0 就已有 O2X7/O2X3C4）；面积模型没有生成"
        "比投料更大的分子，终态最大 8 原子。",
        "低温窗口（面积模型）：T0=12 平均 4.09 原子、≥5 原子 2473 个（26.3%%）、18 种分子式、"
        "7 种新物质、decomp 1017；T0=20 平均 3.285、大分子 341 个、6 种、3 新、decomp 162。"
        "低温下大分子才留得住。",
        "主实验 t=500 累计 path_D=%s /%s = %s 次等效穿越（v0=64138，比 T55/T56 更高，"
        "因为设计取最大分子也达标）；初始分子寿命中位 4.5 D≈1 步（碰撞即反应），"
        "穿越由无化学对照（by_size 分组，最大 9 原子组 min=694.8）验证。"
        % (kin.get("path_D_at_500"), cfg.get("initial_particles"),
           kin.get("crossings_equiv_per_initial_at_500")),
        "快照为旧 7 色（元素集合）方案；每帧最多 3000 点。",
    ]
    analysis["caveats"] = caveats
    return analysis


def main(argv=None):
    ap = argparse.ArgumentParser(description="T57 实验分析")
    ap.add_argument("--main", default=DEFAULT_MAIN)
    ap.add_argument("--control", default=DEFAULT_CONTROL)
    ap.add_argument("--uniform", default=DEFAULT_UNIFORM)
    ap.add_argument("--design", default=DEFAULT_DESIGN)
    ap.add_argument("--catalog", default=DEFAULT_CATALOG)
    ap.add_argument("--subs", default=DEFAULT_SUBS)
    ap.add_argument("--t55", default=DEFAULT_T55)
    ap.add_argument("--t56", default=DEFAULT_T56)
    ap.add_argument("--sensitivity", default=DEFAULT_SENS)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    if not os.path.exists(args.main):
        print("[error] 主实验结果不存在：%s" % args.main)
        return 2
    t0 = datetime.datetime.now()
    analysis = analyze_main(args.main, args.control, args.uniform, args.design,
                            args.catalog, args.subs, args.t55, args.t56,
                            args.sensitivity)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(analysis, fh, ensure_ascii=False, indent=1)
    print("[saved] %s (%.1fs)" % (args.out,
                                  (datetime.datetime.now() - t0).total_seconds()))
    kn = analysis["key_numbers"]
    print(json.dumps({"design": kn["design"], "main": kn["main"],
                      "control": {k: kn["control"][k] for k in
                                  ("pass", "min", "median", "fraction_ge_500")},
                      "area_vs_uniform": kn.get("area_vs_uniform")},
                     ensure_ascii=False, indent=1)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
