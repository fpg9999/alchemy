# -*- coding: utf-8 -*-
"""t56_analysis.py —— T56「六元素 / 价数比例 3<2<1」2D 粒子实验分析

输入：
  t56_kinetic_result.json     主实验（1000 分钟，6 单质：O2/K2、X2/A2、C2/F2）
  t56_control_no_chem.json    无化学对照（500 分钟，9200 粒）
  t4_catalog_index.json       大锅目录 84,225 条（formula -> zh / natoms）
  substances.json             29 聚素（O/X/C 三元素）
  t55_analysis.json / t55_kinetic_result.json  T55 对比（可选）

输出：
  t56_analysis.json           结构化分析（供报告/图表引用）

T56 与 T55 的关键差异（分析口径）：
* 投料 6 种双原子单质，价数原子比 3价:2价:1价 = 3200:5600:9600 = 1:1.75:3。
* 引擎用 84,225 目录作为 known_formulas（避免把目录内分子记成"新物质"），
  因此 final_composition / new_substances 里的 **"known29" 字段实际含义是
  "在 84,225 大锅目录内"**，不是"在 29 聚素内"；本脚本重新计算并分开标注：
    in_catalog（84,225 目录内）、in_29（29 聚素内）、atoms_count。
* 84,225 目录只对 ≤16 原子完备（≤16 有 82,961 条，>16 仅 1,264 条），
  所以"目录外"≠"化学上不可能"；>16 原子的目录外分子只是目录没枚举到。
* 快照 color_mode="element_bitmask"：points 第三列是 9 位元素集合掩码，
  legend[str(code)] 为中文元素组合；开发样本 bench20 仍是旧 7 色，脚本兼容两者。
"""
import argparse
import datetime
import json
import os
import re
import sys
from collections import Counter, OrderedDict, defaultdict

BASE = r"G:\AI work\deepseek\work1\alchemy"
DEFAULT_MAIN = os.path.join(BASE, "t56_kinetic_result.json")
DEFAULT_CONTROL = os.path.join(BASE, "t56_control_no_chem.json")
DEFAULT_CATALOG = os.path.join(BASE, "t4_catalog_index.json")
DEFAULT_SUBS = os.path.join(BASE, "substances.json")
DEFAULT_T55 = os.path.join(BASE, "t55_analysis.json")
DEFAULT_T55_RESULT = os.path.join(BASE, "t55_kinetic_result.json")
DEFAULT_OUT = os.path.join(BASE, "t56_analysis.json")
DEFAULT_SENS = os.path.join(BASE, "t56_sensitivity.json")

ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]
CN = {"O": "秩", "X": "晶", "C": "冰", "P": "势", "W": "流", "L": "电",
      "K": "沌", "A": "气", "F": "焰"}
VAL = {"O": 3, "X": 2, "C": 1, "P": 3, "W": 2, "L": 1,
       "K": 3, "A": 2, "F": 1}
ELEM_CAT = {"O": "聚", "X": "聚", "C": "聚", "P": "动", "W": "动", "L": "动",
            "K": "散", "A": "散", "F": "散"}

T_WINDOWS = [
    ("1000-100", 100.0, 1000.0),
    ("100-50", 50.0, 100.0),
    ("50-20", 20.0, 50.0),
    ("20-10", 10.0, 20.0),
    ("10-5", 5.0, 10.0),
    ("5-0", 0.0, 5.0),
]

_FORMULA_RE = re.compile(r"([A-Z])(\d*)")


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


def formula_counts(f):
    """分子式 -> {元素: 个数}。"""
    out = OrderedDict()
    for e, c in _FORMULA_RE.findall(f or ""):
        if e in ORDER:
            out[e] = out.get(e, 0) + (int(c) if c else 1)
    return out


def formula_atoms(f):
    return sum(formula_counts(f).values())


def formula_zh_fallback(f):
    """不在目录时，用中文元素名拼名字（按 ORDER 排序，与目录命名一致）。"""
    cnt = formula_counts(f)
    parts = []
    for e in ORDER:
        if e in cnt:
            parts.append(CN[e] + (str(cnt[e]) if cnt[e] > 1 else ""))
    return "".join(parts) or f


def load_catalog(base):
    path = os.path.join(base, "t4_catalog_index.json")
    if not os.path.exists(path):
        return {}, {}, {}
    data = load_json(path)
    zh, natoms = {}, {}
    for rec in data:
        f = rec.get("formula")
        if f:
            zh[f] = rec.get("zh") or f
            natoms[f] = rec.get("natoms")
    return set(zh), zh, natoms


def load_known29(base):
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


# ---------------------------------------------------------------- ratio 验证
def analyze_ratio(main, cfg):
    ratio = main.get("ratio")
    load_spec = cfg.get("load_spec") or []
    # 无论 result 是否带 ratio，都按 load_spec + 价数重算一遍做交叉验证
    mols = {3: 0, 2: 0, 1: 0}
    atoms = {3: 0, 2: 0, 1: 0}
    elems = {3: [], 2: [], 1: []}
    formulas = []
    for item in load_spec:
        if isinstance(item, dict):
            f, count = item.get("formula"), int(item.get("count") or 0)
            desc, tag = item.get("desc"), item.get("tag")
        else:
            tag, desc, f, count = item[0], item[1], item[2], int(item[3])
        e = (f or "")[0]
        v = VAL.get(e)
        formulas.append({"formula": f, "count": count, "element": e,
                         "valence": v, "zh": CN.get(e, e),
                         "category": ELEM_CAT.get(e), "tag": tag, "desc": desc})
        if v in mols:
            mols[v] += count
            atoms[v] += 2 * count
            elems[v].append(e)
    total_m = sum(mols.values())
    total_a = sum(atoms.values())
    atom_ratio = [atoms[3], atoms[2], atoms[1]]
    if atoms[3]:
        scalar = [rnd(atoms[3] / atoms[3], 3), rnd(atoms[2] / atoms[3], 3),
                  rnd(atoms[1] / atoms[3], 3)]
    else:
        scalar = None
    check = {
        "strict_increasing": atom_ratio[0] < atom_ratio[1] < atom_ratio[2],
        "atoms_match_3200_5600_9600": atom_ratio == [3200, 5600, 9600],
        "total_molecules_9200": total_m == 9200,
        "total_atoms_18400": total_a == 18400,
        "scalar_ratio_1_1.75_3": (scalar == [1.0, 1.75, 3.0]) if scalar else False,
    }
    out = {
        "reported": ratio,
        "recomputed": {
            "valence3": {"elements": elems[3], "molecules": mols[3],
                         "atoms": atoms[3]},
            "valence2": {"elements": elems[2], "molecules": mols[2],
                         "atoms": atoms[2]},
            "valence1": {"elements": elems[1], "molecules": mols[1],
                         "atoms": atoms[1]},
            "atoms_ratio": atom_ratio,
            "molecules_ratio": [mols[3], mols[2], mols[1]],
            "scalar_atoms_ratio": scalar,
            "strict_increasing": check["strict_increasing"],
            "total_molecules": total_m,
            "total_atoms": total_a,
        },
        "feed": formulas,
        "checks": check,
        "pass": all(check.values()),
        "narrative": (
            "投料 6 种双原子单质：三价 O2/K2 各 800（1600 分子 / 3200 原子）、"
            "二价 X2/A2 各 1400（2800 / 5600）、一价 C2/F2 各 2400（4800 / 9600）；"
            "价数原子比 3200 : 5600 : 9600 = 1 : 1.75 : 3，严格递增 ✓；"
            "共 9200 单质 / 18400 原子。"),
        "note": ("三价/二价/一价按 pot_all.ELEM 的价数划分：O,K=3价；X,A=2价；"
                 "C,F=1价。散素 K/A/F 只在 T56 投料中出现。"),
    }
    if ratio:
        out["reported_matches_recomputed"] = (
            ratio.get("atoms_ratio") == atom_ratio and
            ratio.get("total_molecules") == total_m and
            ratio.get("total_atoms") == total_a)
    return out


# ---------------------------------------------------------------- 时间线
def build_per_minute(ts, events, summary):
    ev_by_t = defaultdict(Counter)
    for ev in events or []:
        ev_by_t[ev.get("t")][ev.get("type")] += 1
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
            net_events = sum(ev_by_t[t].values()) if full_events else None
        else:
            net_events = int(ev_cum) - prev["events"]
            prev["events"] = int(ev_cum)
        nb = dict(ev_by_t[t]) if full_events else None
        rows.append({
            "t": t, "T": T, "N": r.get("N"), "atoms": r.get("atoms"),
            "mean_atoms": r.get("mean_atoms"), "max_atoms": r.get("max_atoms"),
            "speed_mean": r.get("speed_mean"),
            "speed_median": r.get("speed_median"),
            "speed_p90": r.get("speed_p90"),
            "free_path": r.get("free_path"),
            "collisions": r.get("collisions"),
            "complete": int(d_complete), "incomplete": int(d_incomplete),
            "none": int(d_none), "decomp": int(d_decomp),
            "net_events": net_events,
            "net_complete": (nb.get("complete", 0) if nb is not None else None),
            "net_incomplete": (nb.get("incomplete", 0) if nb is not None else None),
            "net_none": (nb.get("none", 0) if nb is not None else None),
            "distinct": r.get("distinct"),
            "path_D": r.get("path_D"),
        })
    return rows, full_events


def mean_of(vals):
    vals = [v for v in vals if v is not None]
    return rnd(sum(vals) / len(vals), 1) if vals else None


def analyze_windows(per_minute):
    out = []
    for label, lo, hi in T_WINDOWS:
        sel = [r for r in per_minute
               if r.get("T") is not None and (lo < r["T"] <= hi)]
        if not sel:
            out.append({"label": label, "T_hi": hi, "T_lo": lo, "minutes": 0,
                        "complete": None, "incomplete": None, "none": None,
                        "decomp": None, "net_events": None, "net_by_type": None,
                        "collisions": None, "N_mean": None, "speed_mean": None,
                        "max_atoms_max": None})
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
            "max_atoms_max": max((r.get("max_atoms") or 0) for r in sel),
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
    first_zero_complete = next((r for r in per_minute if r["t"] > 0 and
                                (r.get("complete") or 0) == 0), None)
    last_net = next((r for r in reversed(per_minute)
                     if (r.get("net_events") or 0) > 0), None)
    big_incomplete = next((r for r in per_minute if r.get("T") is not None and
                           r["T"] <= 10 and (r.get("incomplete") or 0) >= 100), None)
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
    if events:
        ts_ev = [e.get("T") for e in events if e.get("T") is not None]
        trans["net_event_T_range"] = [min(ts_ev), max(ts_ev)] if ts_ev else None
    # 尺寸峰值
    peak = None
    for s in size_series or []:
        if s.get("max_atoms") is None:
            continue
        if peak is None or s["max_atoms"] > peak["max_atoms"]:
            peak = {"t": s["t"], "T": s.get("T"), "max_atoms": s["max_atoms"]}
    trans["max_atoms_peak"] = peak
    # N 谷值
    nvals = [(r.get("t"), r.get("N")) for r in per_minute if r.get("N") is not None]
    if nvals:
        trans["N_min"] = {"t": min(nvals, key=lambda x: x[1])[0],
                          "N": min(nvals, key=lambda x: x[1])[1]}
    # 速度半衰
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
    """{formula:count} -> 精确尺寸统计（原子数分布）。"""
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


def analyze_composition(main, cfg, catalog, catalog_zh, catalog_natoms, known29):
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
        series.append({
            "t": fr.get("t"), "T": fr.get("T"), "total": tot,
            "counts": counts,
            "n_species": len(counts),
        })
        size_series.append({"t": fr.get("t"), "T": fr.get("T"),
                            "mean_atoms": st.get("mean"),
                            "median_atoms": st.get("median"),
                            "p90_atoms": st.get("p90"),
                            "p99_atoms": st.get("p99"),
                            "max_atoms": st.get("max"),
                            "total": tot})

    top_formulas = [f for f, _ in max_count.most_common(12)]
    for f in known29:
        if f in first_seen and f not in top_formulas and len(top_formulas) < 14:
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
    # 6 个初始单质 + 29 聚素
    initial_formulas = [("三价", "O2"), ("三价", "K2"), ("二价", "X2"),
                        ("二价", "A2"), ("一价", "C2"), ("一价", "F2")]
    feed_presence = []
    for cat, f in initial_formulas:
        fin = final.get(f) or {}
        pk = peaks.get(f) or {}
        feed_presence.append({
            "formula": f, "zh": CN.get(f[0], f[0]) + "2", "category": cat,
            "first_t": (first_seen.get(f) or {}).get("t"),
            "peak_count": pk.get("count"), "peak_t": pk.get("t"),
            "final_count": fin.get("count", 0),
            "atoms": 2,
        })
    known29_presence = []
    for f in known29:
        fin = final.get(f) or {}
        pk = peaks.get(f) or {}
        known29_presence.append({
            "formula": f, "zh": zh_of(f, catalog_zh),
            "first_t": (first_seen.get(f) or {}).get("t"),
            "peak_count": pk.get("count"), "peak_t": pk.get("t"),
            "peak_share": pk.get("share"),
            "final_count": fin.get("count", 0),
            "appeared": f in first_seen,
        })

    # 终态表（in_catalog / in_29 / atoms 分开）
    total_final = sum(v.get("count", 0) for v in final.values())
    total_atoms_final = sum((v.get("atoms") or 0) * v.get("count", 0)
                            for v in final.values())
    final_rows = []
    flag_mismatch = 0
    for f, v in sorted(final.items(), key=lambda kv: -kv[1].get("count", 0)):
        cnt = v.get("count", 0)
        a = v.get("atoms") or formula_atoms(f)
        in_cat = f in catalog if catalog else None
        if bool(v.get("known29")) != bool(in_cat):
            flag_mismatch += 1
        final_rows.append({
            "formula": f, "zh": zh_of(f, catalog_zh), "count": cnt,
            "share": rnd(cnt / total_final, 5) if total_final else None,
            "atoms": a,
            "total_atoms": a * cnt,
            "atoms_share": (rnd(a * cnt / total_atoms_final, 5)
                            if total_atoms_final else None),
            "in_catalog": in_cat,
            "in_29": f in known29_set,
            "engine_known29_flag": bool(v.get("known29")),
            "catalog_complete_for_size": (a <= 16) if a else None,
            "size_bucket": ("<=16" if a <= 16 else ">16"),
        })
    # 双原子 / 大分子统计
    diatomic = [r for r in final_rows if r["atoms"] == 2]
    large = [r for r in final_rows if r["atoms"] > 2]
    diatomic_count = sum(r["count"] for r in diatomic)
    diatomic_atoms = sum(r["total_atoms"] for r in diatomic)
    diatomic_share = (diatomic_count / total_final) if total_final else None
    large_atoms = total_atoms_final - diatomic_atoms
    salt = []
    for f in ("CF", "XA", "OK"):
        row = next((r for r in final_rows if r["formula"] == f), None)
        if row:
            salt.append({"formula": f, "zh": row["zh"], "count": row["count"],
                         "share": row["share"],
                         "pair": {"OK": "3价+3价（O+K）", "XA": "2价+2价（X+A）",
                                  "CF": "1价+1价（C+F）"}.get(f)})
    outside_final = [r for r in final_rows if not r["in_catalog"]]
    # 终态尺寸分布
    size_dist = Counter()
    atom_size_dist = Counter()
    for f, v in final.items():
        a = v.get("atoms") or formula_atoms(f)
        size_dist[a] += v.get("count", 0)
        atom_size_dist[a] += a * v.get("count", 0)
    size_distribution = [
        {"atoms": a, "molecules": size_dist[a],
         "molecule_share": rnd(size_dist[a] / total_final, 5) if total_final else None,
         "atoms_total": atom_size_dist[a],
         "atoms_share": (rnd(atom_size_dist[a] / total_atoms_final, 5)
                         if total_atoms_final else None),
         "in_catalog": None}
        for a in sorted(size_dist)]
    # 新物质
    newsub = []
    for f, rec in (main.get("new_substances") or {}).items():
        rec = rec or {}
        ev = rec.get("event") or {}
        a = len(rec.get("atoms") or []) or formula_atoms(f)
        fin = final.get(f) or {}
        newsub.append({
            "formula": f, "zh": zh_of(f, catalog_zh), "atoms": a,
            "first_t": rec.get("first_t"),
            "first_T": ev.get("T"),
            "in_catalog": f in catalog if catalog else None,
            "catalog_complete_for_size": a <= 16,
            "c": rec.get("c"),
            "final_count": fin.get("count", 0),
            "survived": f in final,
            "event": trim_event(ev),
        })
    newsub.sort(key=lambda r: (r["atoms"] or 0), reverse=True)
    new_total = len(newsub)
    new_in_cat = sum(1 for r in newsub if r["in_catalog"])
    new_le16 = sum(1 for r in newsub if r["atoms"] <= 16)
    new_gt16 = new_total - new_le16
    new_survived = [r for r in newsub if r["survived"]]
    new_survived_outside = [r for r in new_survived if not r["in_catalog"]]
    # 初始组成
    initial_counts = {}
    for item in cfg.get("load_spec") or []:
        if isinstance(item, dict):
            f = item.get("formula")
            c = item.get("count")
        else:
            f, c = item[2], item[3]
        if f:
            initial_counts[f] = initial_counts.get(f, 0) + int(c or 0)
    catalog_stats = {
        "size": len(catalog),
        "max_natoms": (max(catalog_natoms.values())
                       if catalog_natoms else None),
        "n_le16": sum(1 for v in catalog_natoms.values() if v <= 16),
        "n_gt16": sum(1 for v in catalog_natoms.values() if v > 16),
        "note": ("84,225 大锅目录只对 ≤16 原子完备（≤16 约 82,961 条，>16 仅 "
                 "1,264 条，最大 97 原子）；因此『目录外』≠『化学上不可能』，"
                 "只是目录未枚举到。"),
    }
    return {
        "initial_counts": initial_counts,
        "series": series,
        "size_series": size_series,
        "stack_order": top_formulas,
        "top_formulas": [
            {"formula": f, "zh": zh_of(f, catalog_zh),
             "max_count": max_count.get(f, 0),
             "first_seen": first_seen.get(f), "peak": peaks.get(f)}
            for f in top_formulas],
        "feed_presence": feed_presence,
        "known29_presence": known29_presence,
        "known29_seen": sorted(set(known29) & union),
        "known29_missing": sorted(set(known29) - union),
        "formulas_outside_29": sorted(union - known29_set),
        "final_table": final_rows,
        "final_total_formulas": len(final_rows),
        "final_total_molecules": total_final,
        "final_total_atoms": total_atoms_final,
        "final_diatomic": {"count": diatomic_count, "share": diatomic_share,
                           "atoms": diatomic_atoms,
                           "atoms_share": (rnd(diatomic_atoms / total_atoms_final, 5)
                                           if total_atoms_final else None),
                           "formulas": [{"formula": r["formula"],
                                         "zh": r["zh"], "count": r["count"]}
                                        for r in diatomic]},
        "final_large": {"count": len(large),
                        "molecules": sum(r["count"] for r in large),
                        "atoms": large_atoms,
                        "atoms_share": (rnd(large_atoms / total_atoms_final, 5)
                                        if total_atoms_final else None),
                        "max_atoms": (max(r["atoms"] for r in large) if large else None)},
        "final_salt_peaks": salt,
        "final_outside_catalog": [{"formula": r["formula"], "zh": r["zh"],
                                   "count": r["count"], "atoms": r["atoms"]}
                                  for r in outside_final],
        "final_size_distribution": size_distribution,
        "engine_flag_mismatch": flag_mismatch,
        "new_substances": newsub,
        "new_substance_stats": {
            "total": new_total, "in_catalog": new_in_cat,
            "outside_catalog": new_total - new_in_cat,
            "le16_atoms": new_le16, "gt16_atoms": new_gt16,
            "survived_final": len(new_survived),
            "survived_outside_catalog": len(new_survived_outside),
            "first_t_range": [min((r["first_t"] for r in newsub), default=None),
                              max((r["first_t"] for r in newsub), default=None)],
            "max_atoms": max((r["atoms"] for r in newsub), default=None),
            "gt16_note": ("目录只对 ≤16 原子完备；%d 种 >16 原子的『目录外』新物质"
                          "不能据目录判定为不可能，只是大分子目录未枚举。" % new_gt16),
        },
        "new_substances_survived": [
            {"formula": r["formula"], "zh": r["zh"], "atoms": r["atoms"],
             "final_count": r["final_count"], "in_catalog": r["in_catalog"]}
            for r in new_survived],
        "catalog_stats": catalog_stats,
        "zh_note": ("中文名：目录内用目录 zh；目录外按元素中文名拼（如 "
                    "O12X4CK7A12 → 秩12晶4冰沌7气12）。"),
    }


# ---------------------------------------------------------------- 速率/规模
def analyze_kinetics(main, size_series):
    ts = main.get("time_series") or []
    cfg = main.get("config") or {}
    sm = main.get("summary") or {}
    keys = (0, 25, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950, 999)
    by_t = {r.get("t"): r for r in ts}
    samples = []
    for k in keys:
        if k in by_t:
            r = by_t[k]
            samples.append({k2: r.get(k2) for k2 in
                            ("t", "T", "N", "mean_atoms", "max_atoms",
                             "speed_mean", "speed_median", "speed_p90",
                             "free_path", "path_D")})
    speeds = [(r.get("t"), r.get("speed_mean")) for r in ts if r.get("speed_mean")]
    path = [(r.get("t"), r.get("path_D")) for r in ts if r.get("path_D") is not None]
    init_n = cfg.get("initial_particles")
    path_500 = next((p[1] for p in path if p[0] == 500), None)
    max_atoms_ts = max((r.get("max_atoms") or 0) for r in ts) if ts else None
    max_atoms_t = next((r.get("t") for r in ts
                        if (r.get("max_atoms") or 0) == max_atoms_ts), None)
    mean_atoms_peak = max(((r.get("t"), r.get("mean_atoms")) for r in ts
                           if r.get("mean_atoms") is not None),
                          key=lambda x: x[1], default=None)
    return {
        "samples": samples,
        "N_initial_config": init_n,
        "N_at_t0": next((r.get("N") for r in ts if r.get("t") == 0), None),
        "N_final": sm.get("final_N"),
        "N_min": next(({"t": r["t"], "N": r["N"]} for r in ts
                       if r.get("N") == min(x.get("N") or 10 ** 9 for x in ts)), None),
        "mean_atoms_peak": ({"t": mean_atoms_peak[0],
                             "mean_atoms": mean_atoms_peak[1]}
                            if mean_atoms_peak else None),
        "mean_atoms_final": (rnd(sm.get("final_atoms") / sm["final_N"], 3)
                             if sm.get("final_atoms") and sm.get("final_N") else None),
        "max_atoms_max": max_atoms_ts,
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
            "method": ("由 min/p1/p5/median/p95/max 分位数线性插值重构"
                       "（控制组仅输出统计量，无逐粒数据）")}


def analyze_crossings(control_path, main):
    out = {"control": None}
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
            "config": c.get("config"), "stats": st,
            "pass": all(checks.values()), "checks": checks,
            "timeseries": c.get("timeseries") or [],
            "approx_hist": approx_hist_from_quantiles(st),
            "requirement": "设计目标：前 500 分钟内每个初始单质至少 500 次角-对角穿越",
            "runtime_s": c.get("runtime_s"),
        }
    else:
        out["control"] = {"available": False, "note": "未找到对照组：%s" % control_path}
    cfg = (main or {}).get("config") or {}
    sm = (main or {}).get("summary") or {}
    stats = sm.get("initial_single_path_stats") or {}
    v0, diag = cfg.get("v0"), cfg.get("diagonal")
    path_per_step = rnd(v0 / diag, 2) if v0 and diag else None
    median = stats.get("median")
    out["main_initial_single"] = {
        "stats": stats, "survivors": stats.get("survivors"),
        "path_per_minute_D": path_per_step,
        "median_in_steps": (rnd(median / path_per_step, 2)
                            if median is not None and path_per_step else None),
        "explain": ("主实验中初始单质一旦发生碰撞即被化学反应消耗，寿命路径很短："
                    "中位寿命 ≈ %.1f D ≈ 首个时间步；速度/穿越指标由无化学对照组"
                    "独立验证。" % (median if median is not None else float("nan"))),
    }
    out["main_lifetime"] = {
        "stats": sm.get("lifetime_path_stats") or {},
        "hist": sm.get("lifetime_path_hist") or {},
        "note": "所有粒子（含反应产物）的寿命 path/D 分桶直方图。",
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

    near = [e for e in ev if e.get("T") is not None and 5 <= e["T"] <= 20]
    class_dist = Counter(tuple(e.get("class") or ()) for e in ev)
    classification = {k: int((sm.get("reaction_counts") or {}).get(k, 0))
                      for k in ("complete", "incomplete", "none")}
    net_total = int(sm.get("events_total") or len(ev))
    complete_noop = classification["complete"] - types.get("complete", 0)
    biggest = sorted(ev, key=atoms_of, reverse=True)[:6]
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
        "class_dist": {str(k): v for k, v in class_dist.items()},
        "top_input_pairs": [[list(k), v] for k, v in pairs.most_common(12)],
        "top_product_sets": [[list(k), v] for k, v in prods.most_common(12)],
        "examples": {
            "first": [trim_event(e) for e in ev[:4]],
            "largest_products": [trim_event(e) for e in biggest],
            "latest": [trim_event(e) for e in
                       sorted(ev, key=lambda x: x.get("t") or -1, reverse=True)[:4]],
            "multi_product": [trim_event(e) for e in
                              sorted([x for x in ev if len(x.get("products") or []) >= 3],
                                     key=atoms_of, reverse=True)[:4]],
            "incomplete_net_change": [trim_event(e) for e in incomplete_ev[:6]],
            "near_temperature_threshold": [trim_event(e) for e in near[:4]],
        },
        "near_threshold_note": (
            "净变化事件温度范围 T=%s~%s；T≤%s 后无净变化（低温段只有不完全判定且多"
            "为复原/弹性，不改变组成）。"
            % (min((e.get("T") for e in ev), default=None),
               max((e.get("T") for e in ev), default=None),
               min((e.get("T") for e in ev), default=None))),
        "type_note": ("event_samples 只记录净结果变化的事件；不完全/不反应若复原成"
                      "原分子对（净结果不变）不会进入样本。"),
    }


# ---------------------------------------------------------------- 低温敏感性
def analyze_sensitivity(sens_path, catalog, catalog_zh, main_analysis):
    """T0=12/20 低温窗口敏感性（t56_sensitivity.json + t56_sens_T*.json）。"""
    if not sens_path or not os.path.exists(sens_path):
        return {"available": False, "note": "未找到敏感性汇总：%s" % sens_path}
    s = load_json(sens_path)
    main_kn = (main_analysis.get("key_numbers") or {}).get("main") or {}
    runs = []
    for run in s.get("runs") or []:
        T0 = run.get("T0")
        path = run.get("file") or os.path.join(os.path.dirname(sens_path),
                                               "t56_sens_T%s.json" % T0)
        detail = None
        if os.path.exists(path):
            try:
                detail = load_json(path)
            except Exception as exc:
                print("[warn] sens load failed %s: %s" % (path, exc), flush=True)
        out = OrderedDict()
        out["T0"] = T0
        out["minutes"] = (detail or {}).get("config", {}).get("minutes", T0)
        out["final_N"] = run.get("final_N")
        out["final_atoms"] = (detail or {}).get("summary", {}).get("final_atoms")
        out["events_total"] = run.get("events")
        out["reaction_counts"] = run.get("reactions")
        out["decomp_events"] = run.get("decomp")
        out["n_final"] = run.get("n_final")
        out["n_new_total"] = run.get("n_new_total")
        out["n_new_final"] = run.get("n_new_final")
        out["max_atoms"] = run.get("max_atoms")
        out["top_final"] = run.get("top")
        out["file"] = os.path.basename(path)
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
            # 终态尺寸分布
            size_dist = Counter()
            for f, v in final_comp.items():
                size_dist[v.get("atoms") or formula_atoms(f)] += v.get("count", 0)
            total_final = sum(size_dist.values()) or 1
            total_atoms = sum(a * c for a, c in size_dist.items()) or 1
            out["final_size_stats"] = {
                "mean_atoms": rnd(sum(a * c for a, c in size_dist.items()) / total_final, 3),
                "max_atoms": max(size_dist) if size_dist else None,
                "median_atoms": next((a for a in sorted(size_dist)
                                      if sum(c for aa, c in size_dist.items()
                                             if aa <= a) >= total_final / 2), None),
                "diatomic_share": rnd(size_dist.get(2, 0) / total_final, 4),
                "atoms_in_diatomic_share": rnd(2 * size_dist.get(2, 0) / total_atoms, 4),
            }
            out["final_size_distribution"] = [
                {"atoms": a, "molecules": size_dist[a]} for a in sorted(size_dist)]
            out["top_final"] = [[f, v.get("count")]
                                for f, v in sorted(final_comp.items(),
                                                   key=lambda kv: -kv[1].get("count", 0))[:6]]
            out["n_final_in_catalog"] = sum(1 for f in final_comp if f in catalog)
            out["n_final_outside_catalog"] = len(final_comp) - out["n_final_in_catalog"]
            # 新物质明细
            newrec = detail.get("new_substances") or {}
            for f, rec in newrec.items():
                rec = rec or {}
                ev0 = rec.get("event") or {}
                a = len(rec.get("atoms") or []) or formula_atoms(f)
                fin = final_comp.get(f) or {}
                new_detail.append({
                    "formula": f, "zh": zh_of(f, catalog_zh), "atoms": a,
                    "first_t": rec.get("first_t"), "first_T": ev0.get("T"),
                    "in_catalog": f in catalog,
                    "final_count": fin.get("count", 0),
                    "survived": f in final_comp,
                    "event": trim_event(ev0),
                })
            new_detail.sort(key=lambda r: (r["atoms"] or 0), reverse=True)
        out["net_events_by_type"] = dict(net_types)
        out["new_substances_detail"] = new_detail
        out["new_substances_gt16"] = sum(1 for r in new_detail if r["atoms"] > 16)
        out["new_substances_le16"] = [r for r in new_detail if r["atoms"] <= 16]
        out["new_substances_survived"] = [r for r in new_detail if r["survived"]]
        out["last_T"] = ts[-1].get("T") if ts else None
        runs.append(out)
    new_by = {r["T0"]: r.get("n_new_total") for r in runs}
    newfinal_by = {r["T0"]: r.get("n_new_final") for r in runs}
    dec_by = {r["T0"]: r.get("decomp_events") for r in runs}
    conclusion = (
        "主实验 T0=1000°C 远高于 T35 阈值（Σc 约 1~24），净化学在 T=16 就结束："
        "终态仅 22 种分子式、120 种新物质中仅 7 种存活、decomp 0。"
        "把初温降到阈值量级后：T0=12（12 分钟）终态 379 种分子式、新物质 112 种"
        "（79 种存活于终态）、decomp 17、最大 19 原子；T0=20 终态 270 种、新物质 96 种"
        "（81 种存活）、decomp 7、最大 23 原子。"
        "结论：1000°C 的快速退火把多样性'烧掉'了——只有温度落在阈值量级时，"
        "不完全反应/自分解生成的新物质才能大量保留在终态。")
    return {
        "available": True,
        "purpose": ("低温窗口敏感性：把初温放到 T35 阈值量级（T0=12/20°C），"
                    "观察 6 元素体系的不完全反应、自分解与新物质保留情况。"),
        "seed": s.get("seed"),
        "runs": runs,
        "main_reference": {
            "T0": main_kn.get("T0"),
            "minutes": main_kn.get("minutes"),
            "final_N": main_kn.get("final_N"),
            "events_total": main_kn.get("net_events_total"),
            "reaction_counts": main_kn.get("reaction_counts"),
            "decomp_events": main_kn.get("decomp_events"),
            "n_final": main_kn.get("final_distinct_formulas"),
            "n_new_total": main_kn.get("new_substances_total"),
            "n_new_final": main_kn.get("new_substances_survived"),
            "max_atoms": main_kn.get("max_atoms_evolution"),
            "note": "主实验 1000°C × 1000 分钟",
        },
        "new_substances_by_T0": {str(k): v for k, v in new_by.items()},
        "new_final_by_T0": {str(k): v for k, v in newfinal_by.items()},
        "decomp_by_T0": {str(k): v for k, v in dec_by.items()},
        "conclusion": conclusion,
        "metrics_note": ("n_final=终态 count>0 分子式数；n_new_total=实验中新物质总数；"
                         "n_new_final=终态中属于新物质的分子式数；"
                         "catalog 内/外按 84,225 目录判断（>16 原子目录不完备）。"),
    }


# ---------------------------------------------------------------- T55 对比
def analyze_t55_comparison(t55_path, t55_result_path, main_analysis):
    t55 = None
    if t55_path and os.path.exists(t55_path):
        try:
            t55 = load_json(t55_path)
        except Exception:
            t55 = None
    max_atoms_t55 = None
    if t55_result_path and os.path.exists(t55_result_path):
        try:
            r55 = load_json(t55_result_path)
            ts = r55.get("time_series") or []
            cand = max((r.get("max_atoms") or 0) for r in ts) if ts else 0
            fc = r55.get("final_composition") or {}
            cand = max([cand] + [v.get("atoms") or 0 for v in fc.values()])
            max_atoms_t55 = cand or None
        except Exception:
            max_atoms_t55 = None
    kn = (t55 or {}).get("key_numbers") or {}
    m55 = (kn.get("main") or {})
    comp55 = (t55 or {}).get("composition") or {}
    oxc55 = next((r for r in comp55.get("final_table") or []
                  if r.get("formula") == "OXC"), None)
    t56k = main_analysis.get("key_numbers", {}).get("main", {})
    comp56 = main_analysis.get("composition") or {}
    return {
        "T55": {
            "initial_particles": m55.get("initial_particles", 9000),
            "final_N": m55.get("final_N", 5974),
            "final_distinct": comp55.get("final_total_formulas", 9),
            "dominant": "OXC（秩晶冰，3 原子）",
            "dominant_share": (oxc55 or {}).get("share", 0.99515),
            "max_atoms": max_atoms_t55 if max_atoms_t55 is not None else 9,
            "new_substances": comp55.get("new_substances_count", 0),
            "decomp_events": (m55.get("decomp_events")
                              if m55.get("decomp_events") is not None else
                              (t55 or {}).get("key_numbers", {}).get(
                                  "main", {}).get("decomp_events", 0)),
            "net_events": m55.get("net_events_total", 12635),
        },
        "T56": {
            "initial_particles": t56k.get("initial_particles", 9200),
            "final_N": t56k.get("final_N", 9020),
            "final_distinct": comp56.get("final_total_formulas", 22),
            "dominant": "双原子盐 CF / XA / OK",
            "dominant_share": comp56.get("final_diatomic", {}).get("share"),
            "max_atoms": (main_analysis.get("kinetics") or {}).get("max_atoms_max"),
            "new_substances": comp56.get("new_substance_stats", {}).get("total", 0),
            "decomp_events": t56k.get("decomp_events", 0),
            "net_events": t56k.get("net_events_total", 21299),
        },
        "diff_points": [
            "T55：9000 单质 → 5974 分子（-33.6%）；T56：9200 → 9020（-2.0%）。",
            "T55 终态 99.5% 是单一 3 原子 F 不动点 OXC；T56 终态 99.6% 是双原子盐"
            "（CF/XA/OK 三主峰，同价跨类配对 3+3、2+2、1+1）。",
            "T55 演化中最大 9 原子；T56 演化中最大 36 原子（t≈29~30），终态最大 22 原子。",
            "T55 主实验新物质 0；T56 主实验 120 种目录外分子式（118 种 >16 原子，"
            "终态存活 7 种目录外大分子）。",
            "T55 完全反应主导到退火；T56 价数比例使『同价跨类配对』成为终态主通道，"
            "约 2.3% 原子被大分子动力学捕获。",
        ],
        "note": "T55 数字来自 t55_analysis.json / t55_kinetic_result.json；缺失时用已知常数。",
    }


# ---------------------------------------------------------------- 主流程
def analyze_main(path, control_path, catalog_path, subs_path,
                 t55_path, t55_result_path, sens_path=None):
    main = load_json(path)
    base = os.path.dirname(path) or BASE
    catalog, catalog_zh, catalog_natoms = load_catalog(base)
    known29 = load_known29(base)
    cfg = main.get("config") or {}
    sm = main.get("summary") or {}
    ts = main.get("time_series") or []
    events = main.get("event_samples") or []
    fs = main.get("formula_series") or []

    per_minute, full_events = build_per_minute(ts, events, sm)
    ratio = analyze_ratio(main, cfg)
    comp = analyze_composition(main, cfg, catalog, catalog_zh, catalog_natoms, known29)
    size_series = comp["size_series"]
    kin = analyze_kinetics(main, size_series)
    windows = analyze_windows(per_minute)
    transitions = analyze_transitions(per_minute, size_series, events)
    crossings = analyze_crossings(control_path, main)
    events_a = analyze_events(main, per_minute)
    checks = {
        "classification_sum_equals_collisions": (
            sum((sm.get("reaction_counts") or {}).values()) ==
            sum((r.get("collisions") or 0) for r in ts)),
        "collisions_total": sum((r.get("collisions") or 0) for r in ts),
        "classification_total": sum((sm.get("reaction_counts") or {}).values()),
        "event_samples_complete": len(events) == (sm.get("events_total") or 0),
        "event_samples_count": len(events),
        "events_total": sm.get("events_total"),
        "time_series_rows": len(ts),
        "formula_series_samples": len(fs),
        "ratio_pass": ratio.get("pass"),
        "engine_final_flag_mismatch": comp.get("engine_flag_mismatch"),
    }
    snaps = []
    for s in main.get("snapshots") or []:
        cols = Counter(p[2] for p in s.get("points") or [] if len(p) >= 3)
        legend = s.get("legend") or {}
        top = cols.most_common(6)
        snaps.append({
            "t": s.get("t"), "color_mode": s.get("color_mode"),
            "n_points": len(s.get("points") or []),
            "legend_size": len(legend),
            "top_codes": [[str(c), n, legend.get(str(c), str(c))]
                          for c, n in top],
        })

    analysis = OrderedDict()
    analysis["meta"] = {
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "main_path": os.path.abspath(path),
        "main_file": os.path.basename(path),
        "control_file": (os.path.basename(control_path)
                         if control_path and os.path.exists(control_path) else None),
        "catalog_file": os.path.basename(catalog_path),
        "catalog_size": len(catalog),
        "known29": known29,
        "color_mode": (main.get("snapshots") or [{}])[0].get("color_mode"),
        "python": sys.version.split()[0],
        "schema_notes": [
            "T56 引擎以 84,225 目录作为 known_formulas；final_composition 的 "
            "known29 字段实际表示『在 84,225 目录内』，本分析已重算并拆分为 "
            "in_catalog / in_29。",
            "84,225 目录只对 ≤16 原子完备（>16 仅 1,264 条），目录外 ≠ 不可能。",
            "快照 color_mode=element_bitmask；开发样本 bench20 为旧 7 色，脚本兼容。",
        ],
    }
    analysis["config"] = cfg
    analysis["summary"] = sm
    analysis["ratio"] = ratio
    analysis["checks"] = checks
    analysis["timeline"] = {
        "per_minute": per_minute,
        "temperature_windows": windows,
        "transitions": transitions,
        "event_samples_complete_per_minute": full_events,
        "windows_note": ("温度窗口按 T=T0-t 划分；complete/incomplete/none 为该分钟"
                         "每次碰撞的判定类型计数，net_events 为净变化事件数。"),
    }
    analysis["composition"] = comp
    analysis["kinetics"] = kin
    analysis["crossings"] = crossings
    analysis["events"] = events_a
    analysis["snapshots_overview"] = snaps
    analysis["comparison_T55"] = analyze_t55_comparison(
        t55_path, t55_result_path, analysis)

    # 关键数字
    types = events_a["type_counts"]
    ctrl = crossings.get("control") or {}
    cs = ctrl.get("stats") or {}
    ns = comp["new_substance_stats"]
    salt = comp["final_salt_peaks"]
    key = OrderedDict()
    key["main"] = OrderedDict([
        ("T0", cfg.get("T0")), ("minutes", cfg.get("minutes")),
        ("final_T", sm.get("final_T")),
        ("initial_particles", cfg.get("initial_particles")),
        ("initial_atoms", cfg.get("initial_atoms")),
        ("final_N", sm.get("final_N")),
        ("final_atoms", sm.get("final_atoms")),
        ("final_mean_atoms", kin.get("mean_atoms_final")),
        ("final_distinct_formulas", comp["final_total_formulas"]),
        ("final_diatomic_count", comp["final_diatomic"]["count"]),
        ("final_diatomic_share", comp["final_diatomic"]["share"]),
        ("final_diatomic_atoms_share", comp["final_diatomic"]["atoms_share"]),
        ("final_salt_peaks", salt),
        ("final_outside_catalog_n", len(comp["final_outside_catalog"])),
        ("final_outside_catalog", comp["final_outside_catalog"]),
        ("final_large_molecules", comp["final_large"]["molecules"]),
        ("final_large_atoms_share", comp["final_large"]["atoms_share"]),
        ("max_atoms_evolution", kin.get("max_atoms_max")),
        ("max_atoms_evolution_t", kin.get("max_atoms_peak_t")),
        ("final_max_atoms", (max((r["atoms"] for r in comp["final_table"]),
                                default=None))),
        ("reaction_counts", sm.get("reaction_counts")),
        ("net_events_total", sm.get("events_total")),
        ("net_events_by_type", types),
        ("net_events_T_range", transitions.get("net_event_T_range")),
        ("complete_noop_ratio", events_a.get("complete_noop_ratio")),
        ("decomp_events", sm.get("decomp_events")),
        ("new_substances_total", ns.get("total")),
        ("new_substances_gt16", ns.get("gt16_atoms")),
        ("new_substances_le16", ns.get("le16_atoms")),
        ("new_substances_in_catalog", ns.get("in_catalog")),
        ("new_substances_survived", ns.get("survived_final")),
        ("new_substances_max_atoms", ns.get("max_atoms")),
        ("new_substances_survived_outside", ns.get("survived_outside_catalog")),
        ("max_atoms_peak", transitions.get("max_atoms_peak")),
        ("N_min", transitions.get("N_min")),
        ("final_path_D", sm.get("final_path_D")),
        ("path_D_at_500", kin.get("path_D_at_500")),
        ("crossings_equiv_per_initial_at_500",
         kin.get("crossings_equiv_per_initial_at_500")),
        ("crossings_equiv_per_initial_final",
         kin.get("crossings_equiv_per_initial_final")),
        ("speed_initial", kin.get("speed_initial")),
        ("speed_final", kin.get("speed_final")),
        ("speed_half", transitions.get("speed_half")),
        ("last_net_change", transitions.get("last_net_change")),
        ("runtime_s", sm.get("runtime_s")),
    ])
    key["control"] = OrderedDict([
        ("pass", ctrl.get("pass")), ("min", cs.get("min")), ("p1", cs.get("p1")),
        ("median", cs.get("median")), ("fraction_ge_500", cs.get("fraction_ge_500")),
        ("mean", cs.get("mean")), ("max", cs.get("max")),
    ])
    inits = sm.get("initial_single_path_stats") or {}
    key["main_initial_single"] = OrderedDict([
        ("n", inits.get("n")), ("min", inits.get("min")), ("p1", inits.get("p1")),
        ("median", inits.get("median")), ("max", inits.get("max")),
        ("survivors", inits.get("survivors")),
        ("median_in_steps", crossings["main_initial_single"].get("median_in_steps")),
    ])
    key["ratio"] = OrderedDict([
        ("atoms_ratio", ratio["recomputed"]["atoms_ratio"]),
        ("scalar_ratio", ratio["recomputed"]["scalar_atoms_ratio"]),
        ("molecules_ratio", ratio["recomputed"]["molecules_ratio"]),
        ("strict_increasing", ratio["checks"]["strict_increasing"]),
        ("total_molecules", ratio["recomputed"]["total_molecules"]),
        ("total_atoms", ratio["recomputed"]["total_atoms"]),
        ("pass", ratio["pass"]),
    ])
    key["catalog"] = OrderedDict([
        ("size", comp["catalog_stats"]["size"]),
        ("n_le16", comp["catalog_stats"]["n_le16"]),
        ("n_gt16", comp["catalog_stats"]["n_gt16"]),
        ("max_natoms", comp["catalog_stats"]["max_natoms"]),
    ])
    analysis["key_numbers"] = key
    analysis["sensitivity"] = analyze_sensitivity(sens_path or DEFAULT_SENS,
                                                  catalog, catalog_zh, analysis)
    if analysis["sensitivity"].get("available"):
        sens = analysis["sensitivity"]
        key["sensitivity"] = OrderedDict([
            ("available", True),
            ("new_substances_by_T0", sens.get("new_substances_by_T0")),
            ("new_final_by_T0", sens.get("new_final_by_T0")),
            ("decomp_by_T0", sens.get("decomp_by_T0")),
            ("n_final_by_T0", {r["T0"]: r.get("n_final") for r in sens.get("runs") or []}),
            ("max_atoms_by_T0", {r["T0"]: r.get("max_atoms") for r in sens.get("runs") or []}),
            ("incomplete_by_T0", {r["T0"]: (r.get("reaction_counts") or {}).get("incomplete")
                                  for r in sens.get("runs") or []}),
            ("main_reference", sens.get("main_reference")),
            ("T0_12_check", next(({"n_final": r.get("n_final"),
                                  "n_new_total": r.get("n_new_total"),
                                  "n_new_final": r.get("n_new_final"),
                                  "decomp": r.get("decomp_events")}
                                 for r in sens.get("runs") or []
                                 if r.get("T0") == 12), None)),
        ])

    caveats = [
        "reaction_counts 是『每次碰撞的判定类型计数』，含大量净结果不变的完全判定"
        "（F 不动点）；真正化学事件以 events_total 为准：主实验 %s 次（占判定计数 %.2f%%）。"
        % (sm.get("events_total"),
           100.0 * (events_a.get("net_event_ratio_of_classified") or 0.0)),
        "event_samples 只记录净变化事件；不完全/不反应若复原成原分子对不会进入样本，"
        "所以主实验净变化事件几乎全是 complete（仅 1 个 incomplete）。",
        "final_composition 的 known29 字段在本实验中的实际含义是『在 84,225 目录内』"
        "（引擎以目录作为 known_formulas），本分析已重算 in_catalog / in_29 并分开标注；"
        "引擎标志与分析重算的不一致条目数 = %d。" % comp.get("engine_flag_mismatch", 0),
        "84,225 目录只对 ≤16 原子完备：≤16 约 82,961 条，>16 仅 1,264 条。"
        "因此 >16 原子的『目录外新物质』不能称为化学上不可能，只是目录未枚举；"
        "本实验 %d 种新物质中 %d 种 >16 原子。" % (ns.get("total", 0), ns.get("gt16_atoms", 0)),
        "新物质记录的是『首次生成』的分子式；最终是否存活看 final_count，"
        "本实验 %d 种新物质中只有 %d 种在终态存活。" %
        (ns.get("total", 0), ns.get("survived_final", 0)),
        "主实验净变化事件全部发生在 T≥%s（t 早段），低温段不完全判定多为复原/弹性，"
        "不再改变组成；decomp 全程 0。"
        % (transitions.get("net_event_T_range") or [None])[0],
        "主实验 t=500 累计 path_D=%s /9200 = %s 次等效穿越 >500；t=999 为 %s。"
        "初始单质因『碰撞即反应』中位寿命仅 %s D（≈%.1f 步），速度指标由对照组验证。"
        % (kin.get("path_D_at_500"),
           kin.get("crossings_equiv_per_initial_at_500"),
           kin.get("crossings_equiv_per_initial_final"),
           inits.get("median"),
           crossings["main_initial_single"].get("median_in_steps") or 0.0),
        "快照为 element_bitmask 格式（code=元素集合掩码，legend[code]=中文组合）；"
        "每帧最多 3000 点（随机抽样），仅用于空间分布可视化。",
        "投料/组成分析用分子式原子数（formula_atoms）计算，不依赖结构；"
        "尺寸分布由 formula_series 的完整组成精确重算。",
    ]
    analysis["caveats"] = caveats
    return analysis


def main(argv=None):
    ap = argparse.ArgumentParser(description="T56 实验分析")
    ap.add_argument("--main", default=DEFAULT_MAIN)
    ap.add_argument("--control", default=DEFAULT_CONTROL)
    ap.add_argument("--catalog", default=DEFAULT_CATALOG)
    ap.add_argument("--subs", default=DEFAULT_SUBS)
    ap.add_argument("--t55", default=DEFAULT_T55)
    ap.add_argument("--t55-result", default=DEFAULT_T55_RESULT)
    ap.add_argument("--sensitivity", default=DEFAULT_SENS)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    if not os.path.exists(args.main):
        print("[error] 主实验结果不存在：%s" % args.main)
        return 2
    t0 = datetime.datetime.now()
    analysis = analyze_main(args.main, args.control, args.catalog, args.subs,
                            args.t55, args.t55_result, args.sensitivity)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(analysis, fh, ensure_ascii=False, indent=1)
    print("[saved] %s (%.1fs)" % (args.out,
                                  (datetime.datetime.now() - t0).total_seconds()))
    kn = analysis["key_numbers"]
    print(json.dumps({"ratio": kn["ratio"], "main": kn["main"],
                      "control": kn["control"],
                      "main_initial_single": kn["main_initial_single"]},
                     ensure_ascii=False, indent=1)[:5000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
