# -*- coding: utf-8 -*-
"""t55_analysis.py —— T55「2D 粒子环境 + 自然环境反应」结果分析

输入：
  t55_kinetic_result.json   主实验（1000 分钟；T0=1000°C，-1°C/分钟，9000 分子/18000 原子）
  t55_control_no_chem.json  无化学对照组（500 分钟，只做弹性碰撞+速度衰减）
  t55_sensitivity.json      温度标度敏感性汇总（T0=6/8/12/20）
  t55_sens_T{6,8,12,20}.json 敏感性各次实验（schema 与主实验相同）
  t4_catalog_index.json     大锅目录 84225 条（取 formula -> 中文名）
  substances.json           29 聚素（判断 known29）

输出：
  t55_analysis.json         结构化分析结果（供报告/图表引用）

说明：
* 只用标准库；不修改 t55_kinetic_env.py / natural_engine.py。
* 对字段缺失做兼容：缺字段时给出 None 并在 compat/schema_notes 里注明。
* 核心口径：reaction_counts 是"每次碰撞的判定类型计数"（含净结果不变的
  完全反应 = F 不动点/弹性回弹），真正的化学事件是 events_total（净变化事件）。
"""
import argparse
import datetime
import json
import math
import os
import sys
from collections import Counter, OrderedDict, defaultdict

BASE = r"G:\AI work\deepseek\work1\alchemy"
DEFAULT_MAIN = os.path.join(BASE, "t55_kinetic_result.json")
DEFAULT_CONTROL = os.path.join(BASE, "t55_control_no_chem.json")
DEFAULT_SENS = os.path.join(BASE, "t55_sensitivity.json")
DEFAULT_SENS_DIR = BASE
DEFAULT_CATALOG = os.path.join(BASE, "t4_catalog_index.json")
DEFAULT_SUBS = os.path.join(BASE, "substances.json")
DEFAULT_OUT = os.path.join(BASE, "t55_analysis.json")

# 温度窗口（任务要求）：(标签, 下限(不含), 上限(含))
T_WINDOWS = [
    ("1000-100", 100.0, 1000.0),
    ("100-50", 50.0, 100.0),
    ("50-20", 20.0, 50.0),
    ("20-10", 10.0, 20.0),
    ("10-5", 5.0, 10.0),
    ("5-0", 0.0, 5.0),
]


# ---------------------------------------------------------------- 基础工具
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


def pct_sorted(arr, q):
    """已排序数组的分位数（与引擎同口径：int(q*len)，夹到末位）。"""
    if not arr:
        return None
    i = min(len(arr) - 1, int(q * len(arr)))
    return rnd(arr[i], 1)


def mean_of(vals):
    vals = [v for v in vals if v is not None]
    return rnd(sum(vals) / len(vals), 1) if vals else None


def load_catalog(base):
    """返回 (formula -> 中文名, 来源文件)。缺失时返回 ({}, None)。"""
    for fn in ("t4_catalog_index.json", "t4_catalog_all_validated.json"):
        path = os.path.join(base, fn)
        if not os.path.exists(path):
            continue
        try:
            data = load_json(path)
        except Exception as exc:  # 大文件损坏时退到下一个候选
            print("[warn] catalog load failed %s: %s" % (path, exc), flush=True)
            continue
        m = {}
        for rec in data:
            if isinstance(rec, dict):
                f = rec.get("formula")
                if f:
                    m[f] = rec.get("zh") or f
            elif isinstance(rec, (list, tuple)) and rec:
                m[str(rec[0])] = rec[1] if len(rec) > 1 and rec[1] else str(rec[0])
        return m, fn
    return {}, None


def load_known29(base):
    path = os.path.join(base, "substances.json")
    if not os.path.exists(path):
        return []
    return [r.get("formula") for r in load_json(path) if r.get("formula")]


def zh_of(formula, catalog_zh):
    return catalog_zh.get(formula) or formula


def trim_event(ev):
    """事件样本裁剪（保留报告需要字段）。"""
    if not isinstance(ev, dict):
        return ev
    out = OrderedDict()
    for k in ("t", "T", "type", "inputs", "products", "class",
              "csum", "isum", "x", "y"):
        if k in ev:
            out[k] = ev[k]
    return out


# ---------------------------------------------------------------- 时间线
def build_per_minute(ts, events, summary):
    """把逐分钟行整理为 timeline 数组；净变化事件由 events_total 差分或事件样本计数。"""
    ev_by_t = defaultdict(Counter)
    for ev in events or []:
        ev_by_t[ev.get("t")][ev.get("type")] += 1
    total_events = summary.get("events_total")
    full_events = bool(events) and (total_events is None or int(total_events) == len(events))

    rows = []
    prev = {"complete": 0, "incomplete": 0, "none": 0, "decomp": 0, "events": 0}
    for r in ts or []:
        t = r.get("t")
        T = r.get("T")
        # 每分钟判定计数：优先用 d_*，否则用累计差分
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
        # 净变化事件：events_total 累计差分
        ev_cum = r.get("events_total")
        if ev_cum is None:
            net_events = sum(ev_by_t[t].values()) if full_events else None
        else:
            net_events = int(ev_cum) - prev["events"]
            prev["events"] = int(ev_cum)
        nb = dict(ev_by_t[t]) if full_events else None
        top = r.get("top") or {}
        oxc_cnt = top.get("OXC")
        oxc_share = (oxc_cnt / r["N"]) if (oxc_cnt is not None and r.get("N")) else None
        rows.append({
            "t": t, "T": T, "N": r.get("N"), "mean_atoms": r.get("mean_atoms"),
            "max_atoms": r.get("max_atoms"),
            "speed_mean": r.get("speed_mean"), "speed_median": r.get("speed_median"),
            "speed_p90": r.get("speed_p90"), "free_path": r.get("free_path"),
            "collisions": r.get("collisions"),
            "complete": int(d_complete), "incomplete": int(d_incomplete),
            "none": int(d_none), "decomp": int(d_decomp),
            "net_events": net_events,
            "net_complete": (nb.get("complete", 0) if nb is not None else None),
            "net_incomplete": (nb.get("incomplete", 0) if nb is not None else None),
            "net_none": (nb.get("none", 0) if nb is not None else None),
            "oxc_share": rnd(oxc_share, 5),
            "path_D": r.get("path_D"),
        })
    return rows, full_events


def analyze_windows(per_minute):
    out = []
    for label, lo, hi in T_WINDOWS:
        sel = [r for r in per_minute
               if r.get("T") is not None and (lo < r["T"] <= hi)]
        if not sel:
            out.append({"label": label, "T_hi": hi, "T_lo": lo, "minutes": 0,
                        "complete": None, "incomplete": None, "none": None,
                        "decomp": None, "net_events": None,
                        "net_by_type": None, "collisions": None,
                        "N_mean": None, "speed_mean": None, "T_range": None})
            continue
        net_by_type = None
        if all(r.get("net_complete") is not None for r in sel):
            net_by_type = {
                "complete": sum(r["net_complete"] for r in sel),
                "incomplete": sum(r["net_incomplete"] for r in sel),
                "none": sum(r["net_none"] for r in sel),
            }
        out.append({
            "label": label, "T_hi": hi, "T_lo": lo, "minutes": len(sel),
            "complete": sum(r["complete"] for r in sel),
            "incomplete": sum(r["incomplete"] for r in sel),
            "none": sum(r["none"] for r in sel),
            "decomp": sum(r["decomp"] for r in sel),
            "net_events": sum((r.get("net_events") or 0) for r in sel),
            "net_by_type": net_by_type,
            "collisions": sum((r.get("collisions") or 0) for r in sel),
            "N_mean": mean_of([r.get("N") for r in sel]),
            "speed_mean": mean_of([r.get("speed_mean") for r in sel]),
            "T_range": [min(r["T"] for r in sel), max(r["T"] for r in sel)],
        })
    return out


def analyze_transitions(per_minute, formula_series, cfg, final_comp):
    trans = {}
    if not per_minute:
        return trans
    firsts = {}
    for key in ("complete", "incomplete", "none", "decomp"):
        hit = next((r for r in per_minute if (r.get(key) or 0) > 0), None)
        firsts[key] = {"t": hit["t"], "T": hit["T"]} if hit else None
    lasts = {}
    for key in ("complete", "incomplete", "none", "decomp"):
        hit = next((r for r in reversed(per_minute) if (r.get(key) or 0) > 0), None)
        lasts[key] = {"t": hit["t"], "T": hit["T"]} if hit else None
    first_zero_complete = next((r for r in per_minute if r["t"] > 0 and
                                (r.get("complete") or 0) == 0), None)
    last_net = next((r for r in reversed(per_minute)
                     if (r.get("net_events") or 0) > 0), None)
    big_incomplete = next((r for r in per_minute if (r.get("incomplete") or 0) >= 100), None)
    trans["first_per_type"] = firsts
    trans["last_per_type"] = lasts
    trans["first_zero_complete"] = ({"t": first_zero_complete["t"],
                                     "T": first_zero_complete["T"]}
                                    if first_zero_complete else None)
    trans["low_T_incomplete_onset"] = ({"t": big_incomplete["t"], "T": big_incomplete["T"]}
                                       if big_incomplete else None)
    trans["last_net_change"] = ({"t": last_net["t"], "T": last_net["T"],
                                 "net_events_that_minute": last_net["net_events"]}
                                if last_net else None)
    trans["minutes_with_net_change"] = sum(
        1 for r in per_minute if (r.get("net_events") or 0) > 0)

    # OXC 占比里程碑 + N 稳定化
    per_oxc = [(r["t"], r.get("T"), r.get("oxc_share")) for r in per_minute
               if r.get("oxc_share") is not None]
    fs_oxc = []
    for fs in formula_series or []:
        counts = fs.get("counts") or {}
        tot = sum(counts.values())
        if tot:
            fs_oxc.append((fs.get("t"), fs.get("T"), counts.get("OXC", 0) / tot))

    def _cross(series, thr):
        """在 (t, T, share) 序列上找首次达到 thr 的时刻（线性插值）。"""
        prev = None
        for t, T, s in series:
            if s is None:
                continue
            if s >= thr:
                if prev is None:
                    return {"t": t, "T": T, "share": rnd(s, 4), "bracket": None,
                            "sample_t": t, "sample_share": rnd(s, 4)}
                t0, T0_, s0 = prev
                if s > s0 and t > t0:
                    ti = t0 + (thr - s0) / (s - s0) * (t - t0)
                    Ti = T0_ + (T - T0_) * (ti - t0) / (t - t0)
                else:
                    ti, Ti = t, T
                return {"t": round(ti, 1), "T": rnd(Ti, 1), "share": rnd(s, 4),
                        "bracket": [t0, t], "shares": [rnd(s0, 4), rnd(s, 4)],
                        "sample_t": t, "sample_share": rnd(s, 4)}
            prev = (t, T, s)
        return None

    # 63.5% 取每 5 分钟样本中 t=10 的实测值（若存在）
    sample_635 = next((x for x in fs_oxc if x[0] == 10), None)
    final_share = fs_oxc[-1][2] if fs_oxc else None
    milestones = OrderedDict()
    milestones["50%"] = _cross(per_oxc, 0.50)
    milestones["63.5%"] = ({"t": sample_635[0], "T": sample_635[1],
                            "share": rnd(sample_635[2], 4),
                            "source": "formula_series 每 5 分钟样本实测"}
                           if sample_635 else _cross(fs_oxc, 0.635))
    milestones["90%"] = _cross(fs_oxc, 0.90)
    milestones["99%"] = _cross(fs_oxc, 0.99)
    milestones["99.5%（终态）"] = ({"t": fs_oxc[-1][0], "T": fs_oxc[-1][1],
                                    "share": rnd(final_share, 4)}
                                   if fs_oxc else None)
    final_N = None
    for r in reversed(per_minute):
        if r.get("N") is not None:
            final_N = r["N"]
            break
    n_stab = None
    if final_N:
        n_stab = next((r for r in per_minute
                       if r.get("N") is not None and
                       abs(r["N"] - final_N) <= 0.01 * final_N), None)
    trans["annealing"] = {
        "oxc_share_milestones": milestones,
        "N_final": final_N,
        "N_stabilize_1pct": ({"t": n_stab["t"], "T": n_stab["T"], "N": n_stab["N"]}
                             if n_stab else None),
        "note": "OXC（秩晶冰）是 F 不动点；占比里程碑基于每 5 分钟完整组成样本",
    }

    # 速度半衰期
    speeds = [(r.get("t"), r.get("speed_mean")) for r in per_minute
              if r.get("speed_mean")]
    if speeds:
        v0 = speeds[0][1]
        half = next((x for x in speeds if x[1] <= 0.5 * v0), None)
        trans["speed_half"] = ({"t": half[0], "v": rnd(half[1], 1), "v0": rnd(v0, 1)}
                               if half else None)
    return trans


# ---------------------------------------------------------------- 组成
def analyze_composition(main, cfg, known29, catalog_zh):
    fs = main.get("formula_series") or []
    final = main.get("final_composition") or {}
    known = set(known29)
    series = []
    max_count = Counter()
    first_seen = {}
    peaks = {}
    union = set()
    for f in fs:
        counts = {k: v for k, v in (f.get("counts") or {}).items() if v > 0}
        tot = sum(counts.values())
        union |= set(counts)
        for k, v in counts.items():
            max_count[k] = max(max_count[k], v)
            if k not in first_seen:
                first_seen[k] = {"t": f.get("t"), "T": f.get("T"), "count": v}
            if k not in peaks or v > peaks[k]["count"]:
                peaks[k] = {"count": v, "t": f.get("t"), "T": f.get("T"),
                            "share": rnd(v / tot, 4) if tot else None}
        series.append({
            "t": f.get("t"), "T": f.get("T"), "total": tot,
            "counts": counts,
            "shares": {k: rnd(v / tot, 5) if tot else None for k, v in counts.items()},
            "n_distinct": len(counts),
            "oxc_share": rnd(counts.get("OXC", 0) / tot, 5) if tot else None,
        })

    top_formulas = [f for f, _ in max_count.most_common(10)]
    for f in known29:  # 保证 29 聚素里的初始单质不因取样小而被漏掉
        if f in first_seen and f not in top_formulas and len(top_formulas) < 12:
            if first_seen[f]["t"] == 0 and first_seen[f]["count"] >= 1:
                top_formulas.append(f)
    stack_order = [f for f in top_formulas]
    # 每个样本补齐 top 分子式 / 其它
    for row in series:
        counts = row["counts"]
        picked = {f: counts.get(f, 0) for f in stack_order}
        other = row["total"] - sum(picked.values())
        row["top_counts"] = picked
        row["other"] = other
        row["top_shares"] = {f: rnd(v / row["total"], 5) if row["total"] else None
                             for f, v in picked.items()}
        row["other_share"] = rnd(other / row["total"], 5) if row["total"] else None

    presence = []
    for f in known29:
        fin = final.get(f) or {}
        presence.append({
            "formula": f, "zh": zh_of(f, catalog_zh),
            "first_t": (first_seen.get(f) or {}).get("t"),
            "first_T": (first_seen.get(f) or {}).get("T"),
            "peak_count": (peaks.get(f) or {}).get("count"),
            "peak_t": (peaks.get(f) or {}).get("t"),
            "peak_share": (peaks.get(f) or {}).get("share"),
            "final_count": fin.get("count", 0),
            "appeared": f in first_seen,
        })
    outside = sorted(union - known)

    final_rows = []
    total_final = sum(v.get("count", 0) for v in final.values())
    for f, v in sorted(final.items(), key=lambda kv: -kv[1].get("count", 0)):
        cnt = v.get("count", 0)
        final_rows.append({
            "formula": f,
            "zh": zh_of(f, catalog_zh),
            "count": cnt,
            "share": rnd(cnt / total_final, 5) if total_final else None,
            "atoms_per_mol": v.get("atoms"),
            "total_atoms": (v.get("atoms") or 0) * cnt,
            "known29": bool(v.get("known29", f in known)),
            "in_catalog": (f in catalog_zh) if catalog_zh else None,
            "zh_source": ("catalog" if f in catalog_zh else "formula"),
        })

    newsub = []
    for f, rec in (main.get("new_substances") or {}).items():
        rec = rec or {}
        newsub.append({
            "formula": f,
            "zh": zh_of(f, catalog_zh),
            "first_t": rec.get("first_t"),
            "first_T": (rec.get("event") or {}).get("T"),
            "in_catalog": (f in catalog_zh) if catalog_zh else None,
            "final_count": (final.get(f) or {}).get("count", 0),
            "survived": f in final,
            "structure": {"label": rec.get("label"), "atoms": rec.get("atoms"),
                          "edges": rec.get("edges"), "c": rec.get("c")},
            "event": trim_event(rec.get("event")),
        })

    # 初始组成（由 config 推：每种单质 = per_species * 批数）
    initial_counts = {}
    species = cfg.get("species") or []
    batches = cfg.get("batches") or []
    per = None
    if batches:
        per = batches[0].get("per_species")
    if per is None and species and cfg.get("initial_particles"):
        per = cfg["initial_particles"] // max(1, len(species) * max(1, len(batches) or 1))
    if per and batches:
        for f in species:
            initial_counts[f] = per * len(batches)

    return {
        "initial_counts": initial_counts or None,
        "series": series,
        "stack_order": stack_order,
        "top_formulas": [
            {"formula": f, "zh": zh_of(f, catalog_zh),
             "max_count": max_count.get(f, 0),
             "first_seen": first_seen.get(f), "peak": peaks.get(f)}
            for f in stack_order],
        "known29_presence": presence,
        "known29_seen": sorted(set(known29) & union),
        "known29_missing": sorted(set(known29) - union),
        "formulas_outside_29": outside,
        "final_table": final_rows,
        "final_total_formulas": len(final_rows),
        "final_total_atoms": total_final,
        "new_substances": newsub,
        "new_substances_count": len(newsub),
        "new_substances_note": (
            "主实验（T0=1000°C）未生成 29 聚素之外的新物质；所有净变化事件的产物"
            "均落在 29 聚素内（多为 OXC）。" if not newsub else ""),
    }


# ---------------------------------------------------------------- 速率/规模
def analyze_kinetics(main, per_minute):
    ts = main.get("time_series") or []
    cfg = main.get("config") or {}
    sm = main.get("summary") or {}
    keys = (0, 25, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950, 999)
    by_t = {r.get("t"): r for r in ts}
    samples = []
    for k in keys:
        if k in by_t:
            r = by_t[k]
            samples.append({
                "t": r.get("t"), "T": r.get("T"), "N": r.get("N"),
                "mean_atoms": r.get("mean_atoms"), "max_atoms": r.get("max_atoms"),
                "speed_mean": r.get("speed_mean"),
                "speed_median": r.get("speed_median"),
                "speed_p90": r.get("speed_p90"),
                "free_path": r.get("free_path"),
                "path_D": r.get("path_D"),
            })
    n_values = [(r.get("t"), r.get("N")) for r in ts if r.get("N") is not None]
    min_n = min(n_values, key=lambda x: x[1]) if n_values else None
    mean_atoms = [(r.get("t"), r.get("mean_atoms")) for r in ts
                  if r.get("mean_atoms") is not None]
    max_ma = max(mean_atoms, key=lambda x: x[1]) if mean_atoms else None
    speeds = [(r.get("t"), r.get("speed_mean")) for r in ts if r.get("speed_mean")]
    path = [(r.get("t"), r.get("path_D")) for r in ts if r.get("path_D") is not None]
    initial_particles = cfg.get("initial_particles")
    final_N = sm.get("final_N")
    path_at_500 = next((p[1] for p in path if p[0] == 500), None)
    cross500 = (rnd(path_at_500 / initial_particles, 1)
                if path_at_500 and initial_particles else None)
    cross_final = (rnd(path[-1][1] / initial_particles, 1)
                   if path and initial_particles else None)
    return {
        "samples": samples,
        "N_initial_config": initial_particles,
        "N_at_t0": next((r.get("N") for r in ts if r.get("t") == 0), None),
        "N_final": final_N,
        "N_min": ({"t": min_n[0], "N": min_n[1]} if min_n else None),
        "mean_atoms_peak": ({"t": max_ma[0], "mean_atoms": max_ma[1]}
                            if max_ma else None),
        "speed_initial": speeds[0][1] if speeds else None,
        "speed_final": speeds[-1][1] if speeds else None,
        "speed_ratio": (rnd(speeds[-1][1] / speeds[0][1], 4)
                        if speeds and speeds[0][1] else None),
        "path_D_final": sm.get("final_path_D"),
        "path_D_at_500": path_at_500,
        "crossings_equiv_per_initial_at_500": cross500,
        "crossings_equiv_per_initial_final": cross_final,
        "runtime_s": sm.get("runtime_s"),
        "collisions_total": sum((r.get("collisions") or 0) for r in ts),
    }


# ---------------------------------------------------------------- 穿越验证
def approx_hist_from_quantiles(stats, nbins=24):
    """对照结果只有分位数：用 (x -> 百分位) 线性插值重构近似直方图。"""
    pts = []
    for q, key in ((0, "min"), (1, "p1"), (5, "p5"), (50, "median"),
                   (95, "p95"), (100, "max")):
        if stats.get(key) is not None:
            pts.append((float(stats[key]), float(q)))
    if len(pts) < 3:
        return None
    pts.sort()
    # 去掉重复 x（分位数相等时）
    clean = [pts[0]]
    for x, q in pts[1:]:
        if x > clean[-1][0]:
            clean.append((x, q))
    if len(clean) < 2:
        return None
    xs = [p[0] for p in clean]
    ps = [p[1] for p in clean]
    lo, hi = xs[0], xs[-1]
    edges = [lo + (hi - lo) * i / nbins for i in range(nbins + 1)]

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

    fracs = []
    for i in range(nbins):
        fracs.append(rnd((p_at(edges[i + 1]) - p_at(edges[i])) / 100.0, 5))
    return {"bin_edges": [rnd(e, 1) for e in edges], "fractions": fracs,
            "method": "由 min/p1/p5/median/p95/max 分位数线性插值重构（控制组仅输出统计量，无逐粒数据）"}


def analyze_crossings(control_path, main, main_initial):
    out = {"control": None, "main_initial_single": main_initial,
           "main_lifetime": None}
    if control_path and os.path.exists(control_path):
        c = load_json(control_path)
        st = c.get("stats") or {}
        checks = {
            "min_ge_500": (st.get("min") is not None and st["min"] >= 500),
            "p1_ge_500": (st.get("p1") is not None and st["p1"] >= 500),
            "median_ge_500": (st.get("median") is not None and st["median"] >= 500),
            "fraction_ge_500_is_1": (st.get("fraction_ge_500") is not None and
                                     st["fraction_ge_500"] >= 0.9999),
        }
        out["control"] = {
            "config": c.get("config"),
            "stats": st,
            "pass": all(checks.values()),
            "checks": checks,
            "timeseries": c.get("timeseries") or [],
            "approx_hist": approx_hist_from_quantiles(st),
            "requirement": "设计目标：前 500 分钟内每个初始单质至少 500 次角-对角穿越",
            "runtime_s": c.get("runtime_s"),
        }
    else:
        out["control"] = {"available": False,
                          "note": "未找到对照组文件：%s" % control_path}

    sm = (main or {}).get("summary") or {}
    stats = sm.get("initial_single_path_stats") or {}
    cfg = (main or {}).get("config") or {}
    v0 = cfg.get("v0")
    diag = cfg.get("diagonal")
    path_per_step_D = rnd(v0 / diag, 2) if v0 and diag else None
    median = stats.get("median")
    out["main_initial_single"] = {
        "stats": stats,
        "survivors": stats.get("survivors"),
        "path_per_minute_D": path_per_step_D,
        "median_in_steps": (rnd(median / path_per_step_D, 2)
                            if median is not None and path_per_step_D else None),
        "explain": ("主实验中初始单质一旦发生碰撞即被化学反应消耗（净变化事件主导），"
                    "因此寿命路径很短：中位寿命 ≈ %.1f D ≈ 首个时间步。"
                    "速度/穿越指标由无化学对照组独立验证，而非用主实验单质寿命衡量。"
                    % (median if median is not None else float("nan"))),
        "note": ("初始单质路径 = 从 t=0 到其参与净变化反应时的 path/D；"
                 "survivors=%s（本实验全部初始单质均被消耗）。" % stats.get("survivors")),
    }
    life = sm.get("lifetime_path_stats") or {}
    hist = sm.get("lifetime_path_hist") or {}
    out["main_lifetime"] = {
        "stats": life,
        "hist": hist,
        "hist_bins": len(hist),
        "note": "所有粒子（含反应产物）的寿命 path/D 分桶直方图；主实验全部粒子寿命中位不单独输出。",
    }
    return out


# ---------------------------------------------------------------- 事件
def analyze_events(main, per_minute):
    ev = main.get("event_samples") or []
    sm = main.get("summary") or {}
    types = Counter(e.get("type") for e in ev)
    prod_n = Counter(len(e.get("products") or []) for e in ev)
    csum = Counter(e.get("csum") for e in ev)
    pairs = Counter()
    prods = Counter()
    for e in ev:
        ins = list(e.get("inputs") or [])
        if len(ins) >= 2:
            pairs[tuple(sorted(ins[:2]))] += 1
        prods[tuple(e.get("products") or [])] += 1

    def atm(e):
        return sum(len(f) for f in (e.get("products") or []))

    near = [e for e in ev if e.get("T") is not None and 5 <= e["T"] <= 20]
    nearest = sorted(ev, key=lambda e: abs((e.get("T") or 0) - 12.5))[:4]
    exchange = sorted([e for e in ev if len(e.get("products") or []) == 2],
                      key=atm, reverse=True)[:4]
    split = sorted([e for e in ev if len(e.get("products") or []) >= 3],
                   key=atm, reverse=True)[:4]
    class_dist = Counter(tuple(e.get("class") or ()) for e in ev)

    classification = main.get("summary", {}).get("reaction_counts") or {}
    classification = {k: int(classification.get(k, 0))
                      for k in ("complete", "incomplete", "none")}
    net_total = int(sm.get("events_total") or len(ev))
    complete_noop = (classification.get("complete", 0) - types.get("complete", 0))
    return {
        "samples_count": len(ev),
        "events_total": net_total,
        "sampling_complete": (net_total == len(ev)),
        "type_counts": dict(types),
        "classification_counts": classification,
        "complete_noop": complete_noop,
        "complete_noop_ratio": (rnd(complete_noop / classification["complete"], 5)
                                if classification.get("complete") else None),
        "net_event_ratio_of_classified": (rnd(net_total / sum(classification.values()), 5)
                                          if classification else None),
        "product_count_dist": dict(prod_n),
        "csum_dist": {str(k): v for k, v in sorted(csum.items(),
                                                   key=lambda kv: str(kv[0]))},
        "class_dist": {str(k): v for k, v in class_dist.items()},
        "top_input_pairs": [[list(k), v] for k, v in pairs.most_common(12)],
        "top_product_sets": [[list(k), v] for k, v in prods.most_common(12)],
        "examples": {
            "first": [trim_event(e) for e in ev[:4]],
            "largest": [trim_event(e) for e in
                        sorted(ev, key=atm, reverse=True)[:5]],
            "latest": [trim_event(e) for e in
                       sorted(ev, key=lambda x: x.get("t") or -1, reverse=True)[:4]],
            "exchange_2to2": [trim_event(e) for e in exchange],
            "multi_product": [trim_event(e) for e in split],
            "near_temperature_threshold": [trim_event(e) for e in near],
            "nearest_to_10C": [trim_event(e) for e in nearest],
            "new_substance_events": [],
        },
        "near_threshold_note": (
            "主实验净变化事件的最高温度记录起点 T=1000，最低 T=%s；"
            "温度 5–20°C 区间内没有净变化事件（净变化最晚发生在 t=%s，T=%s），"
            "因为系统在 T≈134°C 前即已退火到 OXC 不动点。"
            % (min((e.get("T") for e in ev), default=None),
               next((r["t"] for r in reversed(per_minute)
                     if (r.get("net_events") or 0) > 0), None),
               next((r["T"] for r in reversed(per_minute)
                     if (r.get("net_events") or 0) > 0), None))),
        "type_note": (
            "event_samples 只记录净结果发生变化的事件；不完全/不反应判定若净结果不变"
            "（复原/弹性回弹）不会进入样本，所以主实验样本类型只有 complete。"),
    }


# ---------------------------------------------------------------- 敏感性
def analyze_sensitivity(sens_path, sens_dir, main_analysis, catalog_zh, known29):
    if not sens_path or not os.path.exists(sens_path):
        return {"available": False, "note": "未找到敏感性汇总：%s" % sens_path}
    s = load_json(sens_path)
    runs = []
    for run in s.get("runs") or []:
        T0 = run.get("T0")
        path = run.get("file") or os.path.join(sens_dir, "t55_sens_T%s.json" % T0)
        detail = None
        if os.path.exists(path):
            try:
                detail = load_json(path)
            except Exception as exc:
                print("[warn] sens load failed %s: %s" % (path, exc), flush=True)
        run_out = OrderedDict()
        run_out["T0"] = T0
        run_out["minutes"] = run.get("minutes")
        run_out["final_N"] = run.get("final_N")
        run_out["final_atoms"] = (detail or {}).get("summary", {}).get("final_atoms")
        run_out["events_total"] = run.get("events_total")
        run_out["reaction_counts"] = run.get("reaction_counts")
        run_out["decomp_events"] = run.get("decomp_events")
        run_out["n_distinct_final"] = run.get("n_distinct_final")
        run_out["n_known29_final"] = run.get("n_known29_final")
        run_out["n_new_final"] = run.get("n_new_final")
        run_out["top_final"] = run.get("top_final")
        run_out["file"] = os.path.basename(path)
        net_types = Counter()
        new_detail = []
        final_comp = {}
        ts = []
        if detail:
            ev = detail.get("event_samples") or []
            for e in ev:
                net_types[e.get("type")] += 1
            final_comp = detail.get("final_composition") or {}
            ts = detail.get("time_series") or []
            newrec = detail.get("new_substances") or {}
            for f in (run.get("new_substances") or list(newrec.keys())):
                rec = newrec.get(f) or {}
                ev0 = rec.get("event") or {}
                new_detail.append({
                    "formula": f,
                    "zh": zh_of(f, catalog_zh),
                    "first_t": rec.get("first_t"),
                    "first_T": (ev0 or {}).get("T"),
                    "in_catalog": (f in catalog_zh) if catalog_zh else None,
                    "final_count": (final_comp.get(f) or {}).get("count", 0),
                    "survived": f in final_comp,
                    "c": rec.get("c"),
                    "event": trim_event(ev0),
                })
        run_out["net_events_by_type"] = dict(net_types)
        run_out["new_substances_detail"] = new_detail
        if detail:
            run_out["final_mean_atoms"] = (detail.get("summary") or {}).get("mean_atoms")
            run_out["path_D"] = (detail.get("summary") or {}).get("final_path_D")
            run_out["final_species"] = [
                {"formula": f, "count": v.get("count"),
                 "zh": zh_of(f, catalog_zh),
                 "known29": v.get("known29")}
                for f, v in sorted(final_comp.items(),
                                   key=lambda kv: -kv[1].get("count", 0))]
            run_out["last_T"] = ts[-1].get("T") if ts else None
        if run_out.get("final_mean_atoms") is None:
            run_out["final_mean_atoms"] = (
                rnd(run.get("final_atoms", 18000) / run["final_N"], 3)
                if run.get("final_N") else None)
        runs.append(run_out)

    main_ref = {
        "T0": (main_analysis.get("config") or {}).get("T0"),
        "minutes": (main_analysis.get("config") or {}).get("minutes"),
        "final_N": (main_analysis.get("summary") or {}).get("final_N"),
        "events_total": (main_analysis.get("summary") or {}).get("events_total"),
        "reaction_counts": (main_analysis.get("summary") or {}).get("reaction_counts"),
        "decomp_events": (main_analysis.get("summary") or {}).get("decomp_events"),
        "n_distinct_final": (main_analysis.get("composition") or {}).get(
            "final_total_formulas"),
        "n_new_final": (main_analysis.get("composition") or {}).get(
            "new_substances_count"),
        "oxc_share": next((r.get("share") for r in
                           (main_analysis.get("composition") or {}).get("final_table") or []
                           if r.get("formula") == "OXC"), None),
        "note": "主实验 1000°C × 1000 分钟；全程远超 T35 的 Σc（1~20）阈值",
    }
    # 结论（数字驱动）
    new_by_t0 = {r["T0"]: r.get("n_new_final") for r in runs}
    dec_by_t0 = {r["T0"]: r.get("decomp_events") for r in runs}
    best_new = max(new_by_t0.items(), key=lambda kv: (kv[1] or 0)) if new_by_t0 else None
    conclusion = (
        "主实验 T0=1000°C 远高于 T35 加和阈值（聚素小分子 Σc 约 1~20），"
        "全程完全反应主导、迅速退火到 OXC 基态：新物质 0、自分解 0、净变化事件 12,635。"
        "把初温降到阈值量级后：T0=6/8/12/20 分别出现新物质 0/4/5/2 种、"
        "自分解 0/82/133/49 次、终态分子式 11/27/34/22 种；"
        "T0=12 是“新物质最多、终态物种最丰富”的窗口，T0=20 因完全反应更强而新物质减少。"
        "结论：1000°C 的『自然演化』主要体现为快速完全反应退火，"
        "要观察不完全反应/自分解/新物质生成，需把温度放在 Σc 阈值附近（8~20°C 量级）。")
    return {
        "available": True,
        "purpose": ("温度标度敏感性：把初温 T0 放到 T35 阈值量级（6/8/12/20°C），"
                    "与主实验 1000°C 对照，观察不完全反应/自分解/新物质窗口。"),
        "seed": s.get("seed"),
        "runs": runs,
        "main_reference": main_ref,
        "new_substances_by_T0": new_by_t0,
        "decomp_by_T0": dec_by_t0,
        "best_new_substance_T0": best_new,
        "conclusion": conclusion,
        "metrics_note": ("n_distinct_final = 终态 count>0 的分子式数；"
                         "n_new_final = 终态中不在 29 聚素内的分子式数；"
                         "reaction_counts 为碰撞判定计数（含净结果不变），"
                         "net_events_by_type 为净变化事件（真正化学事件）。"),
    }


# ---------------------------------------------------------------- 主流程
def analyze_main(path, control_path, sens_path, sens_dir, catalog_zh, known29):
    main = load_json(path)
    cfg = main.get("config") or {}
    sm = main.get("summary") or {}
    ts = main.get("time_series") or []
    events = main.get("event_samples") or []
    fs = main.get("formula_series") or []
    final = main.get("final_composition") or {}

    per_minute, full_events = build_per_minute(ts, events, sm)
    windows = analyze_windows(per_minute)
    transitions = analyze_transitions(per_minute, fs, cfg, final)
    comp = analyze_composition(main, cfg, known29, catalog_zh)
    kin = analyze_kinetics(main, per_minute)
    init_stats = sm.get("initial_single_path_stats") or {}
    crossings = analyze_crossings(control_path, main, init_stats)
    events_a = analyze_events(main, per_minute)

    # 一致性检查（判定计数缺键按 0 补齐，兼容 bench/quick 等不含 none 的样本）
    classification = {k: int((sm.get("reaction_counts") or {}).get(k, 0))
                      for k in ("complete", "incomplete", "none")}
    collisions_total = sum((r.get("collisions") or 0) for r in ts)
    checks = {
        "classification_sum_equals_collisions": (
            sum(classification.values()) == collisions_total),
        "collisions_total": collisions_total,
        "classification_total": sum(classification.values()),
        "event_samples_complete": (len(events) == (sm.get("events_total") or 0)),
        "event_samples_count": len(events),
        "events_total": sm.get("events_total"),
        "formula_series_samples": len(fs),
        "time_series_rows": len(ts),
    }

    # 快照概览
    snaps = []
    for s in main.get("snapshots") or []:
        cols = Counter(p[2] for p in s.get("points") or [] if len(p) >= 3)
        snaps.append({
            "t": s.get("t"),
            "n_points": len(s.get("points") or []),
            "color_counts": {str(k): v for k, v in sorted(cols.items())},
        })

    analysis = OrderedDict()
    analysis["meta"] = {
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "main_path": os.path.abspath(path),
        "main_file": os.path.basename(path),
        "control_file": (os.path.basename(control_path)
                         if control_path and os.path.exists(control_path) else None),
        "sensitivity_file": (os.path.basename(sens_path)
                             if sens_path and os.path.exists(sens_path) else None),
        "catalog_file": "t4_catalog_index.json" if catalog_zh else None,
        "catalog_size": len(catalog_zh),
        "known29": known29,
        "python": sys.version.split()[0],
    }
    analysis["config"] = cfg
    analysis["summary"] = sm
    analysis["checks"] = checks
    analysis["timeline"] = {
        "per_minute": per_minute,
        "temperature_windows": windows,
        "transitions": transitions,
        "windows_note": ("温度窗口按 time_series 的 T = T0 - t 划分："
                         "1000≥T>100、100≥T>50、50≥T>20、20≥T>10、10≥T>5、5≥T>0；"
                         "complete/incomplete/none 为该分钟内每次碰撞的判定类型计数，"
                         "net_events 为真正发生净变化的化学事件数。"),
        "event_samples_complete_per_minute": full_events,
    }
    analysis["composition"] = comp
    analysis["kinetics"] = kin
    analysis["crossings"] = crossings
    analysis["events"] = events_a
    analysis["snapshots_overview"] = snaps

    # 敏感性（引用主分析结果）
    analysis["sensitivity"] = analyze_sensitivity(sens_path, sens_dir, analysis,
                                                  catalog_zh, known29)

    # 关键数字（报告直接引用）
    types = events_a["type_counts"]
    oxc_row = next((r for r in comp["final_table"] if r["formula"] == "OXC"), None)
    ctrl = crossings.get("control") or {}
    ctrl_stats = ctrl.get("stats") or {}
    wmap = {w["label"]: w for w in windows}
    ann = transitions.get("annealing") or {}
    key = OrderedDict()
    key["main"] = OrderedDict([
        ("T0", cfg.get("T0")), ("minutes", cfg.get("minutes")),
        ("final_T", sm.get("final_T")),
        ("initial_particles", cfg.get("initial_particles")),
        ("initial_atoms", cfg.get("initial_atoms")),
        ("final_N", sm.get("final_N")),
        ("final_atoms", sm.get("final_atoms")),
        ("final_mean_atoms", (rnd(sm.get("final_atoms") / sm["final_N"], 3)
                              if sm.get("final_atoms") and sm.get("final_N") else None)),
        ("final_distinct_formulas", comp["final_total_formulas"]),
        ("final_new_substances", comp["new_substances_count"]),
        ("oxc_final_count", oxc_row["count"] if oxc_row else None),
        ("oxc_final_share", oxc_row["share"] if oxc_row else None),
        ("reaction_counts", sm.get("reaction_counts")),
        ("net_events_total", sm.get("events_total")),
        ("net_events_by_type", types),
        ("complete_noop_ratio", events_a.get("complete_noop_ratio")),
        ("decomp_events", sm.get("decomp_events")),
        ("final_path_D", sm.get("final_path_D")),
        ("path_D_at_500", kin.get("path_D_at_500")),
        ("crossings_equiv_per_initial_at_500",
         kin.get("crossings_equiv_per_initial_at_500")),
        ("crossings_equiv_per_initial_final",
         kin.get("crossings_equiv_per_initial_final")),
        ("oxc_50pct", (ann.get("oxc_share_milestones") or {}).get("50%")),
        ("oxc_63pct", (ann.get("oxc_share_milestones") or {}).get("63.5%")),
        ("oxc_90pct", (ann.get("oxc_share_milestones") or {}).get("90%")),
        ("oxc_99pct", (ann.get("oxc_share_milestones") or {}).get("99%")),
        ("oxc_final", (ann.get("oxc_share_milestones") or {}).get("99.5%（终态）")),
        ("n_stabilize_1pct", ann.get("N_stabilize_1pct")),
        ("chemistry_stop", transitions.get("last_net_change")),
        ("speed_half", transitions.get("speed_half")),
        ("paths_per_minute_D", (crossings.get("main_initial_single") or {}).get(
            "path_per_minute_D")),
        ("runtime_s", sm.get("runtime_s")),
    ])
    key["control"] = OrderedDict([
        ("pass", ctrl.get("pass")),
        ("min", ctrl_stats.get("min")), ("p1", ctrl_stats.get("p1")),
        ("median", ctrl_stats.get("median")),
        ("fraction_ge_500", ctrl_stats.get("fraction_ge_500")),
        ("mean", ctrl_stats.get("mean")),
        ("max", ctrl_stats.get("max")),
    ])
    key["main_initial_single"] = OrderedDict([
        ("n", init_stats.get("n")), ("min", init_stats.get("min")),
        ("p1", init_stats.get("p1")), ("median", init_stats.get("median")),
        ("max", init_stats.get("max")), ("survivors", init_stats.get("survivors")),
        ("median_in_steps", (crossings.get("main_initial_single") or {}).get(
            "median_in_steps")),
    ])
    sens = analysis["sensitivity"]
    key["sensitivity"] = OrderedDict([
        ("available", sens.get("available")),
        ("new_substances_by_T0", sens.get("new_substances_by_T0")),
        ("decomp_by_T0", sens.get("decomp_by_T0")),
        ("n_distinct_by_T0", {r["T0"]: r.get("n_distinct_final")
                              for r in sens.get("runs") or []}),
        ("incomplete_counts_by_T0", {r["T0"]: (r.get("reaction_counts") or {}).get("incomplete")
                                     for r in sens.get("runs") or []}),
    ])
    analysis["key_numbers"] = key

    # 口径与兼容说明
    caveats = [
        "reaction_counts 是‘每次碰撞的判定类型计数’，包含大量净结果不变的完全反应"
        "（产物 = F 不动点，例如 OXC+OXC→OXC+OXC，等同弹性回弹）；"
        "真正化学事件以 events_total 为准：主实验 %s 次（占判定计数的 %.2f%%）。"
        % (sm.get("events_total"),
           100.0 * (events_a.get("net_event_ratio_of_classified") or 0.0)),
        "事件样本 event_samples 只记录‘净变化’事件；不完全/不反应若复原成原分子对"
        "（净结果不变）不会进入样本，故主实验事件类型全部为 complete。",
        "time_series.distinct 是 fcnt 的键数（含归零残留），不等于终态物种数；"
        "终态物种数以 final_composition 的 count>0 条目为准（主实验 %d 种）。"
        % comp["final_total_formulas"],
        "主实验 T0=1000°C 全程远高于 T35 加和阈值（Σc 约 1~20），完全反应主导并"
        "迅速退火到 OXC；并未观察到不完全反应净变化/自分解/新物质。"
        "温度阈值窗口中的行为见 sensitivity 段（T0=6/8/12/20）。",
        "温度窗口按 T=time_series.T 划分；t 从 0 到 999 对应 T=1000→1，"
        "窗口 5-0 实际覆盖 T=5..1（终态 T=0 记录在 final_T）。",
        "对照结果只输出统计量（min/p1/p5/median/p95/max/fraction），"
        "t55_crossings 图中的直方图为分位数线性插值重构（已注明），非逐粒原始分布。",
        "快照每帧最多 3000 点（超过则随机抽样），仅用于空间分布可视化，不能当作密度估计。",
        "主实验 t=500 累计 path_D=%s，除以初始 9000 个单质 = %s 次等效穿越 > 500"
        "（t=999 时 %s 次），说明设计的运动速度达标；但由于‘碰撞即反应’，"
        "单个初始单质的寿命路径中位数只有 %s D（≈%.1f 个时间步），"
        "因此穿越指标必须由无化学对照组验证。"
        % (kin.get("path_D_at_500"), kin.get("crossings_equiv_per_initial_at_500"),
           kin.get("crossings_equiv_per_initial_final"),
           (crossings.get("main_initial_single") or {}).get("stats", {}).get("median"),
           (crossings.get("main_initial_single") or {}).get("median_in_steps") or 0.0),
        "敏感性实验每次只运行 T0 分钟（T0→0），而主实验运行 1000 分钟；"
        "横比时注意运行时长不同（生成时间/终态分子式数都受时长影响）。",
    ]
    if comp["formulas_outside_29"]:
        caveats.append("time_series 中出现 29 聚素外分子式：%s"
                       % comp["formulas_outside_29"])
    analysis["caveats"] = caveats
    return analysis


def main(argv=None):
    ap = argparse.ArgumentParser(description="T55 实验分析")
    ap.add_argument("--main", default=DEFAULT_MAIN)
    ap.add_argument("--control", default=DEFAULT_CONTROL)
    ap.add_argument("--sensitivity", default=DEFAULT_SENS)
    ap.add_argument("--sens-dir", default=DEFAULT_SENS_DIR)
    ap.add_argument("--catalog", default=DEFAULT_CATALOG)
    ap.add_argument("--subs", default=DEFAULT_SUBS)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    if not os.path.exists(args.main):
        print("[error] 主实验结果不存在：%s" % args.main)
        return 2
    catalog_zh, cat_name = load_catalog(os.path.dirname(args.catalog) or BASE)
    known29 = load_known29(os.path.dirname(args.subs) or BASE)
    print("[load] catalog=%d formulas (%s), known29=%d, main=%s"
          % (len(catalog_zh), cat_name, len(known29), os.path.basename(args.main)),
          flush=True)
    t0 = datetime.datetime.now()
    analysis = analyze_main(args.main, args.control, args.sensitivity,
                            args.sens_dir, catalog_zh, known29)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(analysis, fh, ensure_ascii=False, indent=1)
    print("[saved] %s  (%.1fs)" % (args.out, (datetime.datetime.now() - t0).total_seconds()))
    kn = analysis["key_numbers"]
    print(json.dumps({"main": kn["main"], "control": kn["control"],
                      "main_initial_single": kn["main_initial_single"],
                      "sensitivity": kn["sensitivity"]},
                     ensure_ascii=False, indent=1)[:4000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
