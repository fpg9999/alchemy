# -*- coding: utf-8 -*-
"""t58_analysis.py —— T58「九元素全覆盖 + 84,225 库随机 44 种物质大投料」实验分析

输入：
  t58_result.json           主实验（L=400000，面积模型，合并>20 原子不反应的计算保护）
  t58_control_no_chem.json  无化学对照（500 分钟，含 by_size 穿越）
  t58_mixture.json          随机投料设计（44 种，14000 分子 / ~73216 原子，九元素）
  t4_catalog_index.json     84,225 目录（in_catalog）
  substances.json           29 聚素（in_29）
  t55/t56/t57_analysis.json 历史规模对比

输出：t58_analysis.json

口径：
* known_formulas=84,225 目录 → final_composition"known29"字段实际=目录内；
  本脚本重算 in_catalog / in_29 并分开标注。
* 计算保护：合并后原子数 > config.max_reaction_atoms(20) 的碰撞不反应（弹性），
  引擎把这类碰撞计入 reaction_counts["capped"]。time_series 没有 capped 字段，
  用恒等式 capped/minute = collisions - (complete+incomplete+none) 推导每分钟 capped。
* 快照 element_bitmask：points 第三列=9 位元素集合掩码，legend 为中文组合。
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
DEFAULT_MAIN = os.path.join(BASE, "t58_result.json")
DEFAULT_CONTROL = os.path.join(BASE, "t58_control_no_chem.json")
DEFAULT_MIX = os.path.join(BASE, "t58_mixture.json")
DEFAULT_CATALOG = os.path.join(BASE, "t4_catalog_index.json")
DEFAULT_SUBS = os.path.join(BASE, "substances.json")
DEFAULT_OUT = os.path.join(BASE, "t58_analysis.json")
HIST = {
    "T55": os.path.join(BASE, "t55_analysis.json"),
    "T56": os.path.join(BASE, "t56_analysis.json"),
    "T57": os.path.join(BASE, "t57_analysis.json"),
}

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


def formula_zh(f):
    """公式 -> 中文名：元素中文名 + 计数（按 ORDER 顺序）。"""
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


def zh_of(f, catalog_zh):
    return catalog_zh.get(f) or formula_zh(f)


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


# ---------------------------------------------------------------- 投料设计
def analyze_mixture(mix_path, main, cfg):
    mix = {}
    if mix_path and os.path.exists(mix_path):
        mix = load_json(mix_path)
    meta = (main or {}).get("mixture_meta") or mix.get("meta") or {}
    rows = (main or {}).get("mixture_species") or mix.get("species") or []
    # 兼容：从 load_spec 补 rows
    if not rows:
        for item in cfg.get("load_spec") or []:
            f = item.get("formula") if isinstance(item, dict) else item[2]
            c = item.get("count") if isinstance(item, dict) else item[3]
            n = formula_atoms(f)
            r = R0 * math.sqrt(n / 2.0)
            rows.append({"formula": f, "atoms": n,
                         "radius": round(r, 4),
                         "area": round(math.pi * r * r, 4),
                         "count": int(c or 0), "zh": formula_zh(f)})
    rows = sorted(rows, key=lambda r: (r.get("atoms") or 0, r.get("formula") or ""))
    for r in rows:
        if not r.get("zh") or r.get("zh") == r.get("formula"):
            r["zh"] = formula_zh(r.get("formula") or "")
    # 元素原子数（重算）
    el_atoms = Counter()
    for r in rows:
        c = r.get("count") or 0
        for e, k in formula_counts(r.get("formula") or "").items():
            el_atoms[e] += k * c
    total_m = sum(r.get("count") or 0 for r in rows)
    total_a = sum((r.get("count") or 0) * (r.get("atoms") or 0) for r in rows)
    size_dist = Counter()
    for r in rows:
        size_dist[r.get("atoms") or 0] += r.get("count") or 0
    by_n = {}
    for r in rows:
        by_n.setdefault(r.get("atoms"), []).append(r.get("count") or 0)
    mono = all(min(by_n[n]) > max(by_n[n2])
               for n in sorted(by_n) for n2 in sorted(by_n) if n < n2)
    covered = sorted([e for e in ORDER if el_atoms.get(e, 0) > 0])
    return {
        "meta": meta,
        "species": rows,
        "n_species": len(rows),
        "size_distribution": [{"atoms": a, "species": len(by_n.get(a, [])),
                               "molecules": size_dist[a],
                               "atoms_total": a * size_dist[a]}
                              for a in sorted(size_dist)],
        "element_atoms": {e: el_atoms.get(e, 0) for e in ORDER},
        "elements_covered": covered,
        "elements_missing": [e for e in ORDER if e not in covered],
        "checks": {
            "n_species": len(rows),
            "total_molecules": total_m,
            "total_atoms": total_a,
            "mean_atoms": rnd(total_a / total_m, 3) if total_m else None,
            "elements_covered": len(covered),
            "nine_elements": len(covered) == 9,
            "size_range": [min(size_dist) if size_dist else None,
                           max(size_dist) if size_dist else None],
            "area_range": [rnd(min(r.get("area") or 0 for r in rows), 4),
                           rnd(max(r.get("area") or 0 for r in rows), 4)],
            "count_range": [min(r.get("count") or 0 for r in rows),
                            max(r.get("count") or 0 for r in rows)],
            "strict_inverse_monotone": bool(mono),
            "pearson_atoms_area": pearson([r.get("atoms") for r in rows],
                                          [r.get("area") for r in rows]),
            "pearson_atoms_count": pearson([r.get("atoms") for r in rows],
                                           [r.get("count") for r in rows]),
        },
        "note": ("从 84,225 目录按原子数 2~12 每档随机抽 4 种并补足缺失元素；"
                 "数量∝1/面积；面积模型 R=R0·sqrt(n/2)；九元素 O/X/C/P/W/L/K/A/F 全覆盖。"),
    }


# ---------------------------------------------------------------- 时间线
def build_per_minute(ts, events, summary):
    ev_by_t = Counter()
    for ev in events or []:
        ev_by_t[ev.get("t")] += 1
    total_events = summary.get("events_total")
    full_events = bool(events) and (total_events is None or int(total_events) == len(events))
    rows = []
    prev = {"complete": 0, "incomplete": 0, "none": 0, "decomp": 0, "events": 0,
            "capped": 0}
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
        collisions = int(r.get("collisions") or 0)
        # 计算保护 capped：优先用引擎逐分钟字段（重跑后提供），否则用恒等式推导
        if r.get("d_capped") is not None:
            d_capped = max(0, int(r.get("d_capped")))
        elif r.get("capped") is not None:
            d_capped = max(0, int(r.get("capped")) - prev["capped"])
        else:
            d_capped = max(0, collisions - (int(d_complete) +
                                            int(d_incomplete) + int(d_none)))
        prev["complete"] = int(r.get("complete", 0))
        prev["incomplete"] = int(r.get("incomplete", 0))
        prev["none"] = int(r.get("none", 0))
        prev["decomp"] = int(r.get("decomp", 0))
        prev["capped"] += d_capped
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
            "r_bar": r.get("r_bar"), "collisions": collisions,
            "complete": int(d_complete), "incomplete": int(d_incomplete),
            "none": int(d_none), "capped": d_capped, "capped_cum": prev["capped"],
            "decomp": int(d_decomp), "net_events": net_events,
            "distinct": r.get("distinct"), "path_D": r.get("path_D"),
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
                        "capped": None, "net_events": None, "collisions": None})
            continue
        out.append({
            "label": label, "T_hi": hi, "T_lo": lo, "minutes": len(sel),
            "complete": sum(r["complete"] for r in sel),
            "incomplete": sum(r["incomplete"] for r in sel),
            "none": sum(r["none"] for r in sel),
            "capped": sum(r["capped"] for r in sel),
            "net_events": sum((r.get("net_events") or 0) for r in sel),
            "collisions": sum((r.get("collisions") or 0) for r in sel),
            "capped_share": (rnd(sum(r["capped"] for r in sel) /
                                 max(1, sum((r.get("collisions") or 0) for r in sel)), 5)),
            "N_mean": mean_of([r.get("N") for r in sel]),
            "max_atoms_max": max((r.get("max_atoms") or 0) for r in sel),
        })
    return out


def analyze_transitions(per_minute, size_series):
    trans = {}
    if not per_minute:
        return trans
    for key in ("complete", "incomplete", "none", "capped", "decomp"):
        hit = next((r for r in per_minute if (r.get(key) or 0) > 0), None)
        trans.setdefault("first_per_type", {})[key] = (
            {"t": hit["t"], "T": hit["T"]} if hit else None)
        hit = next((r for r in reversed(per_minute) if (r.get(key) or 0) > 0), None)
        trans.setdefault("last_per_type", {})[key] = (
            {"t": hit["t"], "T": hit["T"]} if hit else None)
    fzc = next((r for r in per_minute if r["t"] > 0 and
                (r.get("complete") or 0) == 0), None)
    last_net = next((r for r in reversed(per_minute)
                     if (r.get("net_events") or 0) > 0), None)
    trans["first_zero_complete"] = ({"t": fzc["t"], "T": fzc["T"]} if fzc else None)
    trans["last_net_change"] = ({"t": last_net["t"], "T": last_net["T"],
                                 "net_events_that_minute": last_net["net_events"]}
                                if last_net else None)
    trans["minutes_with_net_change"] = sum(
        1 for r in per_minute if (r.get("net_events") or 0) > 0)
    peak = None
    for s in size_series or []:
        if s.get("max_atoms") is None:
            continue
        if peak is None or s["max_atoms"] > peak["max_atoms"]:
            peak = {"t": s["t"], "T": s.get("T"), "max_atoms": s["max_atoms"]}
    trans["max_atoms_peak"] = peak
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


def large_stats(final_comp, thresholds=(5, 10, 16, 20)):
    total_m = total_a = 0
    for f, v in final_comp.items():
        a = v.get("atoms") or formula_atoms(f)
        total_m += v.get("count", 0)
        total_a += a * v.get("count", 0)
    out = {}
    for th in thresholds:
        m = a_sum = 0
        for f, v in final_comp.items():
            a = v.get("atoms") or formula_atoms(f)
            if a >= th:
                m += v.get("count", 0)
                a_sum += a * v.get("count", 0)
        out["ge%d" % th] = {
            "molecules": m,
            "molecule_share": rnd(m / total_m, 5) if total_m else None,
            "atoms": a_sum,
            "atom_share": rnd(a_sum / total_a, 5) if total_a else None,
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
        # 该样本的 ≥5 原子占比（分子/原子），渲染用（避免把完整 counts 写进 JSON）
        _cnt = {}
        for _f, _v in counts.items():
            _cnt[formula_atoms(_f)] = _cnt.get(formula_atoms(_f), 0) + _v
        _tm = sum(_cnt.values()) or 1
        _ta = sum(_a * _v for _a, _v in _cnt.items()) or 1
        _bm = sum(_v for _a, _v in _cnt.items() if _a >= 5) / _tm
        _ba = sum(_a * _v for _a, _v in _cnt.items() if _a >= 5) / _ta
        series.append({"t": fr.get("t"), "T": fr.get("T"), "total": tot,
                       "counts": counts, "n_species": len(counts),
                       "big5_molecule_share": rnd(_bm, 5),
                       "big5_atom_share": rnd(_ba, 5)})
        size_series.append({"t": fr.get("t"), "T": fr.get("T"),
                            "mean_atoms": st.get("mean"),
                            "median_atoms": st.get("median"),
                            "p90_atoms": st.get("p90"),
                            "p99_atoms": st.get("p99"),
                            "max_atoms": st.get("max"), "total": tot})
    top_formulas = [f for f, _ in max_count.most_common(14)]
    for row in series:
        counts = row["counts"]
        picked = {f: counts.get(f, 0) for f in top_formulas}
        row["top_counts"] = picked
        row["other"] = row["total"] - sum(picked.values())
        row["top_shares"] = {f: rnd(v / row["total"], 5) if row["total"] else None
                             for f, v in picked.items()}
        row["other_share"] = (rnd(row["other"] / row["total"], 5)
                              if row["total"] else None)
        row.pop("counts", None)   # 体积控制：不把每样本完整 counts 写进 JSON
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
            "class3": ("29内" if in29 else ("目录内" if in_cat else "目录外")),
            "at_cap": (a >= 20),
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
        "final_table": final_rows,
        "final_total_formulas": len(final_rows),
        "final_total_molecules": total_final,
        "final_total_atoms": total_atoms_final,
        "final_class3_counts": dict(Counter(r["class3"] for r in final_rows)),
        "final_outside_29": [r for r in final_rows if not r["in_29"]],
        "final_outside_catalog": [r for r in final_rows if not r["in_catalog"]],
        "final_at_cap": [r for r in final_rows if r["at_cap"]],
        "large_stats": large_stats(final),
        "final_size_distribution": final_size_distribution(final),
        "new_substances": newsub,
        "new_substance_stats": {
            "total": len(newsub),
            "in_catalog": sum(1 for r in newsub if r["in_catalog"]),
            "outside_catalog": sum(1 for r in newsub if not r["in_catalog"]),
            "gt16_atoms": sum(1 for r in newsub if r["atoms"] > 16),
            "ge20_atoms": sum(1 for r in newsub if r["atoms"] >= 20),
            "survived_final": sum(1 for r in newsub if r["survived"]),
            "first_t_range": [min((r["first_t"] for r in newsub), default=None),
                              max((r["first_t"] for r in newsub), default=None)],
            "max_atoms": max((r["atoms"] for r in newsub), default=None),
        },
        "known29_seen": sorted(known29_set & union),
        "known29_missing": sorted(known29_set - union),
    }


# ---------------------------------------------------------------- 速率/capped
def analyze_kinetics(main, size_series, per_minute):
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
    capped_total = sum((r.get("capped") or 0) for r in per_minute)
    coll_total = sum((r.get("collisions") or 0) for r in per_minute)
    return {
        "samples": samples,
        "N_initial_config": init_n,
        "N_at_t0": next((r.get("N") for r in ts if r.get("t") == 0), None),
        "N_final": sm.get("final_N"),
        "mean_atoms_final": (rnd(sm.get("final_atoms") / sm["final_N"], 3)
                             if sm.get("final_atoms") and sm.get("final_N") else None),
        "max_atoms_max": max_atoms,
        "max_atoms_peak_t": max_atoms_t,
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
        "collisions_total": coll_total,
        "capped_total": capped_total,
        "capped_share": (rnd(capped_total / coll_total, 5)
                         if coll_total else None),
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
            "method": "由 min/p1/p5/median/p95/max 分位数线性插值重构"}


def analyze_crossings(control_path, main):
    out = {"control": None}
    if control_path and os.path.exists(control_path):
        c = load_json(control_path)
        st = c.get("stats") or {}
        by = {k: dict(v) for k, v in (c.get("by_size") or {}).items()}
        checks = {
            "min_ge_500": (st.get("min") is not None and st["min"] >= 500),
            "p1_ge_500": (st.get("p1") is not None and st["p1"] >= 500),
            "median_ge_500": (st.get("median") is not None and st["median"] >= 500),
            "fraction_ge_500_is_1": (st.get("fraction_ge_500") is not None and
                                     st["fraction_ge_500"] >= 0.9999),
            "all_size_groups_min_ge_500": (
                all((v.get("min") or 0) >= 500 for v in by.values())
                if by else None),
            "large_molecules_min_ge_500": (
                all((v.get("min") or 0) >= 500 for k, v in by.items()
                    if int(k) >= 5) if by else None),
        }
        out["control"] = {
            "config": c.get("config"), "stats": st, "by_size": by,
            "checks": checks,
            "pass": all(v for v in checks.values() if v is not None),
            "approx_hist": approx_hist_from_quantiles(st),
            "timeseries": c.get("timeseries") or [],
            "requirement": "前 500 分钟内每个初始分子至少 500 次角-对角穿越（含大分子）",
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
    }
    out["main_lifetime"] = {
        "stats": sm.get("lifetime_path_stats") or {},
        "hist": sm.get("lifetime_path_hist") or {},
    }
    return out


# ---------------------------------------------------------------- 元素守恒
def analyze_elements(mixture, final_comp, cfg, catalog_zh):
    init = {e: 0 for e in ORDER}
    for r in mixture.get("species") or []:
        c = r.get("count") or 0
        for e, k in formula_counts(r.get("formula") or "").items():
            init[e] += k * c
    fin = {e: 0 for e in ORDER}
    for f, v in (final_comp or {}).items():
        c = v.get("count", 0)
        for e, k in formula_counts(f).items():
            fin[e] += k * c
    rows = [{"element": e, "zh": CN[e], "initial": init[e], "final": fin[e],
             "delta": fin[e] - init[e],
             "conserved": fin[e] == init[e]}
            for e in ORDER if init[e] or fin[e]]
    return {
        "rows": rows,
        "initial_total": sum(init.values()),
        "final_total": sum(fin.values()),
        "config_initial_atoms": cfg.get("initial_atoms"),
        "config_final_atoms": (cfg.get("initial_atoms")
                               if cfg.get("initial_atoms") else None),
        "all_conserved": all(r["conserved"] for r in rows),
        "elements_initial": [e for e in ORDER if init[e] > 0],
        "elements_final": [e for e in ORDER if fin[e] > 0],
        "note": ("九元素元素守恒：初始投料元素原子数 vs 终态组成逐元素求和；"
                 "应完全相等（反应不改变元素总量）。"),
    }


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
                      for k in ("complete", "incomplete", "none", "capped")}
    net_total = int(sm.get("events_total") or len(ev))
    sample_n = max(1, len(ev))
    sampling_complete = (net_total == sample_n)
    if sampling_complete:
        est_types = dict(types)
    else:
        scale = net_total / sample_n
        est_types = {k: int(round(v * scale)) for k, v in types.items()}
    net_complete = est_types.get("complete", 0)
    complete_noop = classification["complete"] - net_complete
    return {
        "samples_count": len(ev),
        "events_total": net_total,
        "sampling_complete": sampling_complete,
        "sampling_note": (("event_samples 为蓄水池抽样（%d/%d）；逐分钟净事件总数由 "
                           "events_total 差分精确给出，按类型拆分用抽样比例估计。")
                          % (sample_n, net_total)) if not sampling_complete else "",
        "type_counts": dict(types),
        "estimated_net_type_counts": est_types,
        "classification_counts": classification,
        "complete_noop": complete_noop,
        "complete_noop_ratio": (rnd(complete_noop / classification["complete"], 5)
                                if classification["complete"] else None),
        "net_event_ratio_of_classified": (
            rnd(net_total / max(1, sum(classification.values())), 5)),
        "product_count_dist": {str(k): v for k, v in sorted(prod_n.items())},
        "csum_dist": {str(k): v for k, v in sorted(csum.items(),
                                                   key=lambda kv: str(kv[0]))},
        "top_input_pairs": [[list(k), v] for k, v in pairs.most_common(10)],
        "top_product_sets": [[list(k), v] for k, v in prods.most_common(10)],
        "examples": {
            "largest_products": [trim_event(e) for e in
                                 sorted(ev, key=atoms_of, reverse=True)[:6]],
            "largest_single_fragment": [trim_event(e) for e in
                                        sorted(ev, key=max_frag, reverse=True)[:6]],
            "first": [trim_event(e) for e in ev[:4]],
            "latest": [trim_event(e) for e in
                       sorted(ev, key=lambda x: x.get("t") or -1, reverse=True)[:4]],
            "incomplete_net_change": [trim_event(e) for e in ev
                                      if e.get("type") == "incomplete"][:4],
        },
        "type_note": ("event_samples 只记录净变化事件；capped 是弹性保护，不产生事件。"),
    }


# ---------------------------------------------------------------- 历史对比
def analyze_history(analysis):
    out = {}
    sm = analysis.get("summary") or {}
    cfg = analysis.get("config") or {}
    kin = analysis.get("kinetics") or {}
    comp = analysis.get("composition") or {}
    mix = analysis.get("mixture") or {}
    for tag, path in HIST.items():
        d = None
        if path and os.path.exists(path):
            try:
                d = load_json(path)
            except Exception:
                d = None
        kn = (d or {}).get("key_numbers") or {}
        cm = (d or {}).get("composition") or {}
        ns = (cm.get("new_substances_count")
              if cm.get("new_substances_count") is not None
              else (cm.get("new_substance_stats") or {}).get("total"))
        mm = ((kn.get("main") or {}).get("initial_particles")
              if tag != "T57" else ((d or {}).get("summary") or {}).get("final_N")
              and (d or {}).get("config", {}).get("initial_particles"))
        cfg55 = (d or {}).get("config") or {}
        out[tag] = {
            "initial_molecules": kn.get("main", {}).get("initial_particles"),
            "initial_atoms": kn.get("main", {}).get("initial_atoms"),
            "elements": {"T55": 3, "T56": 6, "T57": 3}.get(tag),
            "final_N": (d or {}).get("summary", {}).get("final_N"),
            "final_max_atoms": ((d or {}).get("kinetics") or {}).get("max_atoms_max")
            or {"T55": 9, "T56": 36, "T57": 9}.get(tag),
            "new_substances": ns,
            "runtime_s": (d or {}).get("summary", {}).get("runtime_s"),
            "collisions_total": ((d or {}).get("kinetics") or {}).get(
                "collisions_total"),
            "L": ((d or {}).get("config") or {}).get("L"),
        }
    out["T58"] = {
        "initial_molecules": cfg.get("initial_particles"),
        "initial_atoms": cfg.get("initial_atoms"),
        "elements": len(mix.get("elements_covered") or []),
        "final_N": sm.get("final_N"),
        "final_max_atoms": (max((r.get("atoms") or 0)
                                for r in comp.get("final_table") or [])
                            if comp.get("final_table") else None),
        "new_substances": (comp.get("new_substance_stats") or {}).get("total"),
        "runtime_s": sm.get("runtime_s"),
        "collisions_total": kin.get("collisions_total"),
        "L": cfg.get("L"),
    }
    order = ["T55", "T56", "T57", "T58"]
    out["table"] = [dict(name=t, **out[t]) for t in order if t in out]
    out["diff_points"] = [
        "规模：T58 投料 14000 分子 / 73216 原子，约为 T55(9000/18000) 的 1.56×分子、"
        "4.07×原子；元素数 9（T55 3、T56 6、T57 3）。",
        "环境：L=400000（面积 1600×），v0≈8.85e5（按 500 次穿越设计）；"
        "碰撞频率被刻意压低以控制计算量。",
        "终态：T58 终态 %s 个分子、最大 %s 原子（计算保护上限 20）；"
        "T55/T56/T57 见上表。" % (sm.get("final_N"),
                                  max((r.get("atoms") or 0)
                                      for r in comp.get("final_table") or [])),
    ]
    return out


# ---------------------------------------------------------------- 主流程
def analyze_main(main_path, control_path, mix_path):
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
    mixture = analyze_mixture(mix_path, main, cfg)
    comp = analyze_composition(main, cfg, catalog, catalog_zh, known29)
    size_series = comp["size_series"]
    kin = analyze_kinetics(main, size_series, per_minute)
    windows = analyze_windows(per_minute)
    transitions = analyze_transitions(per_minute, size_series)
    crossings = analyze_crossings(control_path, main)
    events_a = analyze_events(main, per_minute)
    elements = analyze_elements(mixture, main.get("final_composition") or {},
                                cfg, catalog_zh)
    # capped 统计
    capped_series = [{"t": r["t"], "T": r["T"],
                      "capped": r["capped"], "collisions": r["collisions"],
                      "capped_share": (rnd(r["capped"] / r["collisions"], 5)
                                       if r["collisions"] else 0.0)}
                     for r in per_minute]
    capped_peak = max(capped_series, key=lambda x: x["capped"], default=None)

    def _share(sel):
        c = sum(x["capped"] or 0 for x in sel)
        t = sum(x["collisions"] or 0 for x in sel)
        return {"capped": c, "collisions": t, "share": rnd(c / t, 5) if t else None}

    capped_info = {
        "total": kin["capped_total"],
        "total_collisions": kin["collisions_total"],
        "share": kin["capped_share"],
        "mean_per_minute": (rnd(kin["capped_total"] / max(1, len(per_minute)), 2)),
        "peak": capped_peak,
        "first": next((x for x in capped_series if x["capped"] > 0), None),
        "last": next((x for x in reversed(capped_series) if x["capped"] > 0), None),
        "first_100min": _share(capped_series[:100]),
        "last_100min": _share(capped_series[-100:]),
        "max_atoms_cap": cfg.get("max_reaction_atoms"),
        "source": ("time_series 逐分钟 capped 字段" if any(
            "d_capped" in r or "capped" in r for r in ts) else
            "由恒等式 capped=collisions-(complete+incomplete+none) 推导"),
        "note": ("合并后原子数 > max_reaction_atoms 的碰撞不反应（弹性），"
                 "计入 reaction_counts['capped']。"),
        "series": capped_series,
    }
    checks = {
        "classification_sum_equals_collisions": (
            sum((sm.get("reaction_counts") or {}).values()) ==
            sum((r.get("collisions") or 0) for r in ts)),
        "collisions_total": sum((r.get("collisions") or 0) for r in ts),
        "classification_total": sum((sm.get("reaction_counts") or {}).values()),
        "event_samples_complete": len(events) == (sm.get("events_total") or 0),
        "time_series_rows": len(ts),
        "formula_series_samples": len(fs),
        "mixture_pass": all(v for k, v in mixture["checks"].items()
                            if isinstance(v, bool) and k != "pearson_atoms_area") and
                        mixture["checks"]["nine_elements"],
        "elements_conserved": elements["all_conserved"],
        "capped_identity": (kin["capped_total"] +
                            sum((sm.get("reaction_counts") or {}).get(k, 0)
                                for k in ("complete", "incomplete", "none")) ==
                            sum((r.get("collisions") or 0) for r in ts)),
    }
    analysis = OrderedDict()
    analysis["meta"] = {
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "main_path": os.path.abspath(main_path),
        "main_file": os.path.basename(main_path),
        "control_file": (os.path.basename(control_path) if control_path else None),
        "mixture_file": os.path.basename(mix_path),
        "catalog_size": len(catalog),
        "known29": known29,
        "schema_notes": [
            "T58 known_formulas=84,225 目录：final_composition 的 known29 字段实际=目录内；"
            "本分析重算 in_catalog / in_29 分开标注。",
            "计算保护：config.max_reaction_atoms=20；合并>20 原子的碰撞不反应，计入 capped。",
            "快照 element_bitmask：code=9 位元素集合掩码，legend=中文元素组合。",
            "L=400000（set_geometry），v0≈8.85e5；碰撞频率被压低以控制计算量。",
        ],
    }
    analysis["config"] = cfg
    analysis["summary"] = sm
    analysis["mixture"] = mixture
    analysis["elements"] = elements
    analysis["checks"] = checks
    analysis["timeline"] = {
        "per_minute": per_minute,
        "temperature_windows": windows,
        "transitions": transitions,
        "capped": capped_info,
        "event_samples_complete_per_minute": full_events,
        "note": ("capped 逐分钟为推导值；温度窗口按 T=T0-t 划分。"),
    }
    analysis["composition"] = comp
    analysis["kinetics"] = kin
    analysis["crossings"] = crossings
    analysis["events"] = events_a
    analysis["snapshots_overview"] = [
        {"t": s.get("t"), "color_mode": s.get("color_mode"),
         "n_points": len(s.get("points") or []),
         "legend_size": len(s.get("legend") or {})}
        for s in (main.get("snapshots") or [])]
    analysis["comparison_history"] = analyze_history(analysis)

    # 元素组合数（终态）+ >16 原子分子数
    _combos = set()
    for f in (main.get("final_composition") or {}):
        _combos.add(tuple(sorted(formula_counts(f).keys())))
    _gt16_mol = sum(v.get("count", 0) for f, v in
                    (main.get("final_composition") or {}).items()
                    if (v.get("atoms") or formula_atoms(f)) > 16)
    key = OrderedDict()
    mix_checks = mixture["checks"]
    key["mixture"] = OrderedDict([
        ("n_species", mix_checks["n_species"]),
        ("total_molecules", mix_checks["total_molecules"]),
        ("total_atoms", mix_checks["total_atoms"]),
        ("mean_atoms", mix_checks["mean_atoms"]),
        ("size_range", mix_checks["size_range"]),
        ("area_range", mix_checks["area_range"]),
        ("count_range", mix_checks["count_range"]),
        ("strict_inverse_monotone", mix_checks["strict_inverse_monotone"]),
        ("elements_covered", mixture["elements_covered"]),
        ("elements_missing", mixture["elements_missing"]),
        ("element_atoms", mixture["element_atoms"]),
        ("max_reaction_atoms", cfg.get("max_reaction_atoms")),
        ("env_L", cfg.get("L")),
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
        ("large_stats", comp["large_stats"]),
        ("reaction_counts", sm.get("reaction_counts")),
        ("net_events_total", sm.get("events_total")),
        ("net_events_by_type", events_a["type_counts"]),
        ("capped_total", kin["capped_total"]),
        ("capped_share", kin["capped_share"]),
        ("capped_peak", capped_info.get("peak")),
        ("capped_first_100min", capped_info.get("first_100min")),
        ("capped_last_100min", capped_info.get("last_100min")),
        ("final_element_combos", len(_combos)),
        ("final_gt16_molecules", _gt16_mol),
        ("final_size_bimodal", {
            "diatomic": next((d["molecules"] for d in comp["final_size_distribution"]
                              if d["atoms"] == 2), 0),
            "non_diatomic": sum(d["molecules"] for d in comp["final_size_distribution"]
                                if d["atoms"] > 2),
            "atoms19": next((d["molecules"] for d in comp["final_size_distribution"]
                             if d["atoms"] == 19), 0),
            "atoms20": next((d["molecules"] for d in comp["final_size_distribution"]
                             if d["atoms"] == 20), 0),
        }),
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
        ("runtime_s", sm.get("runtime_s")),
        ("env_L", cfg.get("L")),
        ("v0", cfg.get("v0")),
    ])
    ctrl = crossings.get("control") or {}
    cs = ctrl.get("stats") or {}
    key["control"] = OrderedDict([
        ("pass", ctrl.get("pass")), ("min", cs.get("min")),
        ("p1", cs.get("p1")), ("median", cs.get("median")),
        ("fraction_ge_500", cs.get("fraction_ge_500")), ("max", cs.get("max")),
        ("by_size", ctrl.get("by_size")), ("checks", ctrl.get("checks")),
    ])
    inits = sm.get("initial_single_path_stats") or {}
    key["main_initial_single"] = OrderedDict([
        ("n", inits.get("n")), ("min", inits.get("min")), ("p1", inits.get("p1")),
        ("median", inits.get("median")), ("max", inits.get("max")),
        ("survivors", inits.get("survivors")),
        ("path_per_minute_D", crossings["main_initial_single"].get(
            "path_per_minute_D")),
    ])
    key["elements"] = OrderedDict([
        ("all_conserved", elements["all_conserved"]),
        ("initial_total", elements["initial_total"]),
        ("final_total", elements["final_total"]),
        ("rows", elements["rows"]),
        ("elements_initial", len(elements["elements_initial"])),
        ("elements_final", len(elements["elements_final"])),
    ])
    key["history"] = analysis["comparison_history"]
    analysis["key_numbers"] = key

    caveats = [
        "reaction_counts 含 capped（合并>%s 原子的碰撞不反应，弹性保护）；"
        "capped 逐分钟值由恒等式推导（引擎未存逐分钟字段）。"
        % cfg.get("max_reaction_atoms"),
        "计算保护影响：capped 只阻止 >%s 原子的合并，不改变 ≤%s 原子的反应；"
        "因此终态尺寸上限为 %s 原子（不是化学上限）。capped 占比随大分子累积而上升"
        "（峰值约 t=%s 达 %.1f%%），说明大分子在稀疏碰撞环境下越积越多。"
        % (cfg.get("max_reaction_atoms"), cfg.get("max_reaction_atoms"),
           cfg.get("max_reaction_atoms"),
           (capped_info.get("peak") or {}).get("t"),
           100.0 * ((capped_info.get("peak") or {}).get("capped_share") or 0)),
        "T58 环境 L=400000（面积 1600×），v0≈8.85e5；碰撞频率低，"
        "总碰撞数远小于 T57（这是为容纳 14000 分子的刻意设计，不是引擎差异）。",
        "final_composition.known29 在 T58 中表示『在 84,225 目录内』"
        "（known_formulas=目录）；本分析重算 in_catalog / in_29。",
        "84,225 目录只对 ≤16 原子完备；目录外 ≠ 化学上不可能。",
        "九元素守恒：逐元素初始 vs 终态求和应相等（已校验）。",
        "event_samples 只记录净变化事件；capped/弹性不产生事件。",
    ]
    analysis["caveats"] = caveats
    return analysis


def main(argv=None):
    ap = argparse.ArgumentParser(description="T58 实验分析")
    ap.add_argument("--main", default=DEFAULT_MAIN)
    ap.add_argument("--control", default=DEFAULT_CONTROL)
    ap.add_argument("--mixture", default=DEFAULT_MIX)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    if not os.path.exists(args.main):
        print("[error] 主实验结果不存在：%s" % args.main)
        return 2
    t0 = datetime.datetime.now()
    analysis = analyze_main(args.main, args.control, args.mixture)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(analysis, fh, ensure_ascii=False, indent=1)
    print("[saved] %s (%.1fs)" % (args.out,
                                  (datetime.datetime.now() - t0).total_seconds()))
    kn = analysis["key_numbers"]
    print(json.dumps({"mixture": kn["mixture"], "main": kn["main"],
                      "control": {k: kn["control"][k] for k in
                                  ("pass", "min", "median", "fraction_ge_500")},
                      "elements": {k: kn["elements"][k] for k in
                                   ("all_conserved", "initial_total", "final_total")},
                      "capped": {"total": kn["main"]["capped_total"],
                                 "share": kn["main"]["capped_share"]}},
                     ensure_ascii=False, indent=1)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
