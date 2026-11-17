# -*- coding: utf-8 -*-
"""T65 生态群系实验：10 群系（每群系 >=4 元素）分析

读取 t65_biomes.json / t65_biome_index.json / t65_biome_C0x_result.json /
t65_biome_C0x_state.json / t65_control_C01.json（均缺失容忍），产出
t65_analysis.json：meta / design / schedule / biomes / cross / features /
control / t64_compare / key_numbers / caveats。
T64 对比读取 t64_analysis.json：12 群系汇总 vs 10 群系，并做
C10 vs B11 的可重复性检查（同元素/同投料/同 L，见 t64_compare.repeatability）。

用法：
    python t65_analysis.py                       # 默认全部群系
    python t65_analysis.py --only C01,C02        # 只分析部分群系（自测用）
"""
import argparse
import json
import math
import os
import re
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))

ELEMENT_CN = {"O": "秩", "X": "晶", "C": "冰", "P": "势", "W": "流",
              "L": "电", "K": "沌", "A": "气", "F": "焰"}
ELEMENT_VALENCE = {"O": 3, "X": 2, "C": 1, "P": 3, "W": 2, "L": 1,
                   "K": 3, "A": 2, "F": 1}
FORMULA_ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]
GROUP_OF = {"O": "poly", "X": "poly", "C": "poly",
            "P": "dyn", "W": "dyn", "L": "dyn",
            "K": "scat", "A": "scat", "F": "scat"}
GROUP_CN = {"poly": "聚素", "dyn": "动素", "scat": "散素", "mixed": "混合"}
GROUP_ORDER = ["poly", "dyn", "scat", "mixed"]

FEATURE_AXES = [
    ("diversity", "物种多样性", "effective_species", "有效物种数"),
    ("specialization", "产物专一性", "top1_share", "头号产物占比"),
    ("polymerization", "平均聚合度", "mean_atoms", "平均原子数"),
    ("max_size", "最大分子尺寸", "max_atoms", "最大原子数"),
    ("trivalent", "三价元素利用率", "trivalent_util", "三价原子利用率"),
    ("conversion", "单质转化率", "conversion", "原子进入化合物比例"),
    ("hold_activity", "恒温活性", "hold_activity", "25°C 每分钟事件"),
    ("novelty", "新物质数量", "new_substances", "目录外新物质"),
]


# ---------------------------------------------------------------- 基础工具
def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def fmt(x, nd=2):
    try:
        return float(("%." + str(nd) + "f") % float(x))
    except Exception:
        return x


def parse_formula(f):
    """'O2XC2' -> {'O':2,'X':1,'C':2}（元素均为单个大写字母，1 省略）。"""
    counts = {}
    i, n = 0, len(f)
    while i < n:
        ch = f[i]
        if not ch.isalpha():
            i += 1
            continue
        j = i + 1
        while j < n and f[j].isdigit():
            j += 1
        num = int(f[i + 1:j]) if j > i + 1 else 1
        counts[ch] = counts.get(ch, 0) + num
        i = j
    return counts


def formula_zh(counts):
    parts = []
    for e in FORMULA_ORDER:
        if e in counts:
            parts.append(ELEMENT_CN[e] + ("" if counts[e] == 1 else str(counts[e])))
    return "".join(parts)


def group_of(counts):
    gs = set()
    for e in counts:
        gs.add(GROUP_OF.get(e, "mixed"))
    if len(gs) == 1:
        return gs.pop()
    return "mixed"


def ref_key(counts):
    """按固定元素顺序重排分子式（输入来自环境已排序，这里只做兜底）。"""
    out = []
    for e in FORMULA_ORDER:
        if e in counts:
            out.append(e + ("" if counts[e] == 1 else str(counts[e])))
    return "".join(out)


def shannon_effective(counts_list):
    tot = float(sum(counts_list))
    if tot <= 0:
        return 0.0
    h = 0.0
    for c in counts_list:
        if c > 0:
            p = c / tot
            h -= p * math.log(p)
    return round(math.exp(h), 3)


def downsample(rows, step=None, max_n=90):
    if not rows:
        return rows
    if step is None:
        step = max(1, int(math.ceil(len(rows) / float(max_n))))
    return rows[::step]


# ---------------------------------------------------------------- 单群系分析
def analyze_biome(b, r, st, index_row):
    """b: t65_biomes.json 的群系设计；r: result dict；st: state dict；"""
    cfg = r.get("config") or {}
    s = r.get("summary") or {}
    fc = r.get("final_composition") or {}
    ts = r.get("time_series") or []
    last = ts[-1] if ts else {}
    elements = list(b.get("elements") or [])
    trivalent = list(b.get("trivalent") or
                     [e for e in elements if ELEMENT_VALENCE.get(e) == 3])
    per_elem = b.get("atoms_per_element")
    total_design = b.get("total_atoms")

    # ------- 终态分子组成
    comp = []
    n_total = 0
    atoms_total = 0
    for f, v in fc.items():
        c = int(v.get("count", 0))
        a = int(v.get("atoms", 0))
        if c <= 0:
            continue
        cnts = parse_formula(f)
        n_total += c
        atoms_total += a * c
        comp.append({"formula": f, "count": c, "atoms": a,
                     "share": 0.0, "atoms_share": 0.0,
                     "elements": cnts, "zh": formula_zh(cnts),
                     "known29": bool(v.get("known29"))})
    comp.sort(key=lambda x: (-x["count"], -x["atoms"], x["formula"]))
    for x in comp:
        x["share"] = round(x["count"] / float(n_total), 6) if n_total else 0.0
        x["atoms_share"] = round(x["atoms"] * x["count"] / float(atoms_total), 6) \
            if atoms_total else 0.0

    # ------- 元素守恒 / 终态元素原子数
    elem_atoms = {e: 0 for e in elements}
    for x in comp:
        for e, n in x["elements"].items():
            if e in elem_atoms:
                elem_atoms[e] += n * x["count"]
    elem_share = {e: (round(elem_atoms[e] / float(atoms_total), 6) if atoms_total else 0.0)
                  for e in elements}

    # ------- 家族（聚素/动素/散素/混合）
    fam_mol = {g: 0 for g in GROUP_ORDER}
    fam_atoms = {g: 0 for g in GROUP_ORDER}
    for x in comp:
        g = group_of(x["elements"])
        fam_mol[g] += x["count"]
        fam_atoms[g] += x["atoms"] * x["count"]
    for g in GROUP_ORDER:
        fam_mol[g + "_share"] = round(fam_mol[g] / float(n_total), 6) if n_total else 0.0
        fam_atoms[g + "_share"] = round(fam_atoms[g] / float(atoms_total), 6) \
            if atoms_total else 0.0

    # ------- 单质残留 / 元素利用率
    free_atoms = {e: 0 for e in elements}
    residue_mol = 0
    residue_atoms = 0
    for x in comp:
        if len(x["elements"]) == 1:
            e = list(x["elements"].keys())[0]
            if e in free_atoms:
                free_atoms[e] += x["atoms"] * x["count"]
            residue_mol += x["count"]
            residue_atoms += x["atoms"] * x["count"]
    usage = {}
    for e in elements:
        total = per_elem if per_elem else None
        if not total:
            total = int(b.get("total_atoms", 0)) / max(1, len(elements))
        free = free_atoms.get(e, 0)
        used = max(0, total - free)
        usage[e] = {"atoms": total, "free": free, "used": used,
                    "utilization": round(used / float(total), 6) if total else 0.0}
    tri_util = [usage[e]["utilization"] for e in trivalent if e in usage]
    trivalent_util = round(sum(tri_util) / len(tri_util), 6) if tri_util else 0.0
    conversion = round(1.0 - residue_atoms / float(atoms_total), 6) if atoms_total else 0.0

    # ------- 反应判定 / capped
    rc = dict(s.get("reaction_counts") or {})
    complete = int(rc.get("complete", 0))
    incomplete = int(rc.get("incomplete", 0))
    none_ev = int(rc.get("none", 0))
    capped = int(rc.get("capped", last.get("capped", 0) or 0))
    rsum = complete + incomplete + none_ev + capped
    capped_share = round(capped / float(rsum), 6) if rsum else 0.0

    # ------- 恒温段（25°C）活性
    hold_activity = None
    hold_events = None
    hold_n_changes = None
    if ts:
        idx = 0
        for i, row in enumerate(ts):
            if float(row.get("t", 0)) >= 975:
                idx = i
                break
        end_ev = float(ts[-1].get("events_total", 0))
        start_ev = float(ts[idx].get("events_total", 0))
        hold_events = end_ev - start_ev
        hold_activity = round(hold_events / 600.0, 3)
        n_start = float(ts[idx].get("N", 0))
        hold_n_changes = round(float(ts[-1].get("N", 0)) - n_start, 1)

    # ------- 终态结构（用于 render 画分子）
    fts = r.get("final_top_structures") or {}
    structures = []
    for x in comp[:12]:
        rec = fts.get(x["formula"])
        if rec:
            structures.append({"formula": x["formula"], "label": rec.get("label") or x["formula"],
                               "atoms": rec.get("atoms") or [], "edges": rec.get("edges") or [],
                               "count": x["count"], "family": group_of(x["elements"])})
    # state 兜底
    if not structures and st:
        for m in (st.get("molecules") or [])[:12]:
            x = next((y for y in comp if y["formula"] == m.get("formula")), None)
            if not x:
                continue
            structures.append({"formula": m.get("formula"), "label": m.get("formula"),
                               "atoms": m.get("atoms") or [], "edges": m.get("edges") or [],
                               "count": m.get("count", 0),
                               "family": group_of(x["elements"])})

    # ------- 时间线（降采样）
    tl = []
    step = max(1, int(math.ceil(len(ts) / 80.0))) if ts else 1
    for row in ts[::step]:
        tl.append([fmt(row.get("t"), 0), fmt(row.get("T"), 2),
                   int(row.get("N", 0)), int(row.get("capped", 0)),
                   fmt(row.get("mean_atoms"), 3), int(row.get("max_atoms", 0))])
    if ts and tl and tl[-1][0] != fmt(ts[-1].get("t"), 0):
        row = ts[-1]
        tl.append([fmt(row.get("t"), 0), fmt(row.get("T"), 2),
                   int(row.get("N", 0)), int(row.get("capped", 0)),
                   fmt(row.get("mean_atoms"), 3), int(row.get("max_atoms", 0))])
    dcurve = [[fmt(row.get("t"), 0), int(row.get("distinct", 0))]
              for row in ts[::step]] if ts else []

    # ------- 快照元数据（render 从原始 result 读点）
    snaps = []
    for sn in (r.get("snapshots") or []):
        snaps.append({"t": sn.get("t"), "n": len(sn.get("points") or []),
                      "color_mode": sn.get("color_mode")})
    if not snaps:
        for t in (r.get("config") or {}).get("snap_minutes") or []:
            snaps.append({"t": t, "n": 0, "color_mode": None})

    # ------- 多样性
    distinct = len(comp)
    distinct_ever = int(last.get("distinct", 0) or s.get("distinct_formulas", 0) or 0)
    eff = shannon_effective([x["count"] for x in comp])
    top1 = comp[0] if comp else None
    new_substances = len((r.get("new_substances") or {}))

    # ------- 保存的原始结果文件名（render 复用）
    idx_file = (index_row or {}).get("file") or ("t65_biome_%s_result.json" % b["id"])

    return {
        "id": b["id"],
        "name": b.get("name") or b["id"],
        "tag": b.get("tag") or "",
        "status": "done",
        "present": True,
        "n_elements": b.get("n_elements") or len(elements),
        "elements": elements,
        "trivalent": trivalent,
        "L": b.get("L"),
        "atoms_per_element": per_elem,
        "total_atoms_design": total_design,
        "seed": (b.get("seed") or (r.get("biome") or {}).get("seed")
                 or (r.get("config") or {}).get("seed") or 0),
        "runtime_s": s.get("runtime_s", (index_row or {}).get("runtime_s")),
        "result_file": idx_file,
        "config": {"L": cfg.get("L"), "initial_particles": cfg.get("initial_particles"),
                   "initial_atoms": cfg.get("initial_atoms"),
                   "max_reaction_atoms": cfg.get("max_reaction_atoms"),
                   "area_model": cfg.get("area_model"),
                   "minutes": cfg.get("minutes")},
        "final_T": fmt(s.get("final_T"), 2),
        "final_N": n_total,
        "final_atoms": atoms_total,
        "mean_atoms": fmt(atoms_total / float(n_total), 3) if n_total else 0.0,
        "max_atoms": max([x["atoms"] for x in comp] or [0]),
        "distinct_formulas": distinct,
        "distinct_ever": distinct_ever,
        "new_substances": new_substances,
        "effective_species": eff,
        "top1": {"formula": top1["formula"], "count": top1["count"],
                 "share": top1["share"]} if top1 else None,
        "top1_share": top1["share"] if top1 else 0.0,
        "top": [{"formula": x["formula"], "zh": x["zh"], "count": x["count"],
                 "atoms": x["atoms"], "share": x["share"],
                 "family": group_of(x["elements"])} for x in comp[:10]],
        "composition": [{"formula": x["formula"], "zh": x["zh"], "count": x["count"],
                         "atoms": x["atoms"], "share": x["share"],
                         "atoms_share": x["atoms_share"],
                         "family": group_of(x["elements"])} for x in comp],
        "elements": {e: {"atoms": elem_atoms[e], "share": elem_share[e]} for e in elements},
        "groups": {g: {"molecules": fam_mol[g], "atoms": fam_atoms[g],
                       "molecule_share": fam_mol[g + "_share"],
                       "atoms_share": fam_atoms[g + "_share"]} for g in GROUP_ORDER},
        "usage": usage,
        "trivalent_util": trivalent_util,
        "residue": {"molecules": residue_mol, "atoms": residue_atoms,
                    "molecule_share": round(residue_mol / float(n_total), 6) if n_total else 0.0,
                    "atoms_share": round(residue_atoms / float(atoms_total), 6) if atoms_total else 0.0,
                    "free_atoms": free_atoms},
        "conversion": conversion,
        "reaction_counts": {"complete": complete, "incomplete": incomplete,
                            "none": none_ev, "capped": capped},
        "capped": capped,
        "capped_share": capped_share,
        "events_total": int(s.get("events_total", 0) or 0),
        "hold_activity": hold_activity,
        "hold_events": hold_events,
        "hold_N_change": hold_n_changes,
        "conservation": {
            "elements_ok": all(abs(elem_atoms[e] - (per_elem or 0)) == 0 for e in elements),
            "atoms_ok": atoms_total == total_design,
            "element_delta": {e: elem_atoms[e] - (per_elem or 0) for e in elements},
        },
        "structures": structures,
        "timeline": tl,
        "distinct_curve": dcurve,
        "snapshots": snaps,
        "n_snapshots": len(snaps),
    }


def pending_biome(b):
    return {
        "id": b["id"], "name": b.get("name") or b["id"], "tag": b.get("tag") or "",
        "status": "pending", "present": False,
        "n_elements": b.get("n_elements") or len(b.get("elements") or []),
        "elements": list(b.get("elements") or []),
        "trivalent": list(b.get("trivalent") or []),
        "L": b.get("L"), "atoms_per_element": b.get("atoms_per_element"),
        "total_atoms_design": b.get("total_atoms"), "seed": b.get("seed") or 0,
        "runtime_s": None, "final_T": None, "final_N": None, "final_atoms": None,
        "mean_atoms": None, "max_atoms": None, "distinct_formulas": None,
        "distinct_ever": None, "new_substances": None, "effective_species": None,
        "top1": None, "top1_share": None, "top": [], "composition": [],
        "elements": {}, "groups": {}, "usage": {}, "trivalent_util": None,
        "residue": {}, "conversion": None, "reaction_counts": {},
        "capped": 0, "capped_share": None, "events_total": None,
        "hold_activity": None, "hold_events": None, "hold_N_change": None,
        "conservation": {}, "structures": [], "timeline": [], "distinct_curve": [],
        "snapshots": [], "n_snapshots": 0,
    }


# ---------------------------------------------------------------- 跨群系
def analyze_cross(biomes, design):
    done = [b for b in biomes if b.get("present")]
    ids = [b["id"] for b in done]

    # 分子式 × 群系 矩阵（取各群系 top 并集中最靠前的行）
    rows = {}
    for b in done:
        for x in b["composition"]:
            r = rows.setdefault(x["formula"], {"formula": x["formula"],
                                               "zh": x["zh"],
                                               "counts": {},
                                               "max_atoms": x["atoms"],
                                               "family": x["family"]})
            r["counts"][b["id"]] = x["count"]
            r["max_atoms"] = max(r["max_atoms"], x["atoms"])
    row_list = []
    for f, r in rows.items():
        vals = r["counts"]
        r["total"] = sum(vals.values())
        r["n_biomes"] = len([v for v in vals.values() if v > 0])
        r["counts"] = {bid: vals.get(bid, 0) for bid in ids}
        row_list.append(r)
    row_list.sort(key=lambda r: (-r["n_biomes"], -r["total"], -r["max_atoms"], r["formula"]))
    # 只保留有意义的行：至少出现在 1 个群系 top 组成里（全部），最多 30 行
    row_list = row_list[:30]

    # 家族矩阵
    fam_rows = []
    for b in done:
        fam_rows.append({
            "id": b["id"], "name": b["name"],
            "poly": b["groups"]["poly"]["atoms_share"],
            "dyn": b["groups"]["dyn"]["atoms_share"],
            "scat": b["groups"]["scat"]["atoms_share"],
            "mixed": b["groups"]["mixed"]["atoms_share"],
            "residue_atoms_share": b["residue"]["atoms_share"],
        })

    # 元素矩阵（各群系 9 元素原子占比）
    elem_rows = []
    for b in done:
        row = {"id": b["id"], "name": b["name"]}
        for e in FORMULA_ORDER:
            row[e] = b["elements"].get(e, {}).get("share", 0.0)
        elem_rows.append(row)

    # 元素利用率矩阵
    usage_rows = []
    for b in done:
        row = {"id": b["id"], "name": b["name"]}
        for e in FORMULA_ORDER:
            u = b["usage"].get(e)
            row[e] = u["utilization"] if u else None
        usage_rows.append(row)

    # 群系相似度（终态组成余弦）
    vec = {}
    for b in done:
        d = {}
        for x in b["composition"]:
            d[x["formula"]] = d.get(x["formula"], 0.0) + x["share"]
        vec[b["id"]] = d
    names = [x["formula"] for x in row_list]
    sim = []
    for got in done:
        grow = []
        for got2 in done:
            a, b2 = vec[got["id"]], vec[got2["id"]]
            num = sum(a.get(f, 0.0) * b2.get(f, 0.0) for f in names)
            na = math.sqrt(sum(v * v for v in a.values()))
            nb = math.sqrt(sum(v * v for v in b2.values()))
            grow.append(round(num / (na * nb), 4) if na and nb else 0.0)
        sim.append(grow)

    return {
        "n_present": len(done),
        "biome_ids": ids,
        "matrix": row_list,
        "families": fam_rows,
        "elements": elem_rows,
        "usage": usage_rows,
        "similarity": {"ids": ids, "values": sim},
        "totals": {
            "molecules": sum(b["final_N"] for b in done),
            "atoms": sum(b["final_atoms"] for b in done),
            "biomes": len(done),
        },
    }


# ---------------------------------------------------------------- 特色群系
def analyze_features(biomes):
    done = [b for b in biomes if b.get("present")]
    if len(done) < 2:
        return {"available": False, "ranking": [], "criteria": [], "note": "群系数据不足"}
    axis_vals = {}
    for key, cn, field, unit in FEATURE_AXES:
        axis_vals[key] = [float(b.get(field) or 0) for b in done]

    def zscores(vals):
        n = len(vals)
        mean = sum(vals) / n
        var = sum((v - mean) ** 2 for v in vals) / n
        sd = math.sqrt(var)
        if sd <= 1e-12:
            return [0.0] * n, mean, sd
        return [(v - mean) / sd for v in vals], mean, sd

    z = {}
    stats = {}
    for key, cn, field, unit in FEATURE_AXES:
        z[key], mean, sd = zscores(axis_vals[key])
        stats[key] = {"mean": mean, "sd": sd, "unit": unit, "cn": cn, "field": field}

    scored = []
    for i, b in enumerate(done):
        pos = {k: max(0.0, z[k][i]) for k in z}
        score = sum(v * v for v in pos.values())
        dom = max(z, key=lambda k: z[k][i])
        scored.append({"biome": b, "score": score, "z": {k: z[k][i] for k in z},
                       "pos": pos, "dominant": dom})

    # 先按"主导轴去重"选前 3，保证特色维度不同；不足再按分数补齐
    scored.sort(key=lambda x: (-x["score"], x["biome"]["id"]))
    picked = []
    seen = set()
    for s in scored:
        if s["dominant"] not in seen:
            picked.append(s)
            seen.add(s["dominant"])
        if len(picked) == 3:
            break
    for s in scored:
        if len(picked) >= 3:
            break
        if s not in picked:
            picked.append(s)

    def reason(s):
        b = s["biome"]
        zpos = sorted([k for k in s["z"] if s["z"][k] > 0.3],
                      key=lambda k: -s["z"][k])
        n_done = float(len(scored))
        out = []
        for k in zpos[:3]:
            st = stats[k]
            if k == "specialization":
                out.append("产物专一性突出：%s 占 %.1f%%（全体均值 %.1f%%）" % (
                    b["top1"]["formula"] if b["top1"] else "-",
                    b["top1_share"] * 100, st["mean"] * 100))
            elif k == "diversity":
                out.append("组成最分散：有效物种 %.1f 种、终态 %d 种（均值 %.1f 种）" % (
                    b["effective_species"], b["distinct_formulas"],
                    sum(x["biome"]["distinct_formulas"] for x in scored) / n_done))
            elif k == "polymerization":
                out.append("平均聚合度领先：%.2f 原子/分子（均值 %.2f）" % (
                    b["mean_atoms"], st["mean"]))
            elif k == "max_size":
                out.append("最大分子尺寸领先：%d 原子（均值 %.1f）" % (
                    b["max_atoms"], st["mean"]))
            elif k == "trivalent":
                out.append("三价元素利用率高：%.1f%%（均值 %.1f%%）" % (
                    b["trivalent_util"] * 100, st["mean"] * 100))
            elif k == "conversion":
                out.append("单质转化彻底：%.1f%% 原子进入化合物（均值 %.1f%%）" % (
                    b["conversion"] * 100, st["mean"] * 100))
            elif k == "hold_activity":
                out.append("25°C 恒温段相对活跃：%.3f 事件/分钟（均值 %.3f）" % (
                    b["hold_activity"] or 0, st["mean"]))
            elif k == "novelty":
                out.append("新物质较多：%d 种目录外产物（均值 %.1f 种）" % (
                    b["new_substances"], st["mean"]))
        return out

    ranking = []
    for rank, s in enumerate(picked[:3], 1):
        b = s["biome"]
        ranking.append({
            "rank": rank,
            "id": b["id"],
            "name": b["name"],
            "score": round(s["score"], 3),
            "dominant": s["dominant"],
            "dominant_cn": stats[s["dominant"]]["cn"],
            "reasons": reason(s),
            "highlights": {"final_N": b["final_N"],
                           "distinct_formulas": b["distinct_formulas"],
                           "top1_share": b["top1_share"],
                           "mean_atoms": b["mean_atoms"],
                           "max_atoms": b["max_atoms"],
                           "trivalent_util": b["trivalent_util"],
                           "capped": b["capped"]},
            "per_axis_z": {k: round(s["z"][k], 3) for k in s["z"]},
        })
    ranked_scores = []
    for s in sorted(scored, key=lambda x: (-x["score"], x["biome"]["id"])):
        b = s["biome"]
        ranked_scores.append({
            "id": b["id"], "name": b["name"], "score": round(s["score"], 3),
            "dominant": s["dominant"], "dominant_cn": stats[s["dominant"]]["cn"],
            "per_axis_z": {k: round(s["z"][k], 3) for k in s["z"]},
        })

    # 各维度领先群系：便于报告覆盖主要候选（聚合度/九元素/无氧/纯族/高 capped/双三价）
    per_axis_best = []
    for key, cn, field, unit in FEATURE_AXES:
        bi = max(range(len(done)), key=lambda i: (axis_vals[key][i], -i))
        b = done[bi]
        per_axis_best.append({
            "axis": key, "axis_cn": cn, "unit": unit,
            "id": b["id"], "name": b["name"],
            "value": round(axis_vals[key][bi], 4),
        })
    capped_leaders = [{"id": b["id"], "name": b["name"], "capped": b["capped"],
                       "capped_share": b["capped_share"]}
                      for b in sorted(done, key=lambda x: -x["capped"])[:3]
                      if b["capped"] > 0]
    return {
        "available": True,
        "criteria": [
            "各维指标在 10 群系内做 z-score 标准化，正向 z 值平方和为该群系特色分",
            "主导轴 = z 值最大的维度；前 3 名优先取自不同主导轴，避免选出同质群系",
            "维度：%s" % "、".join("%s(%s)" % (cn, unit) for _, cn, _, unit in FEATURE_AXES),
        ],
        "axes": [{"key": k, "cn": cn, "unit": unit,
                  "mean": round(stats[k]["mean"], 4),
                  "sd": round(stats[k]["sd"], 4)} for k, cn, _, unit in FEATURE_AXES],
        "ranking": ranking,
        "scores": ranked_scores,
        "per_axis_best": per_axis_best,
        "capped_leaders": capped_leaders,
    }


# ---------------------------------------------------------------- 对照
def analyze_control(path, biome_b01):
    r = load_json(path)
    if not r:
        return {"present": False, "note": "对照文件缺失或未就绪"}
    # T65 的对照是"无化学反应"的纯运动学对照（500 分钟），用于校验运移/碰撞标定，
    # 没有 final_composition，不能与 C01 终态组成直接对比。
    if "stats" in r and "final_composition" not in r:
        cfg = r.get("config") or {}
        st = r.get("stats") or {}
        ts = r.get("timeseries") or []
        med = st.get("median")
        frac = st.get("fraction_ge_500")
        passed = bool(med is not None and med >= 500.0
                      and (frac is None or frac >= 0.99))
        return {
            "present": True,
            "kind": "physical_control_no_chemistry",
            "minutes": cfg.get("minutes"),
            "n_particles": cfg.get("n_particles") or st.get("n"),
            "mean_free_path": (cfg.get("mean_free_path") or
                               (cfg.get("design") or {}).get("lambda_mean")),
            "stats": {"min": st.get("min"), "median": med, "max": st.get("max"),
                      "mean": st.get("mean"),
                      "fraction_ge_500": frac},
            "n_series": len(ts),
            "runtime_s": fmt(r.get("runtime_s"), 2),
            "pass": passed,
            "note": "对照关闭化学反应，只验证 500 分钟内粒子运移/路径长度标定"
                    "（median ≥500 为通过）；不含终态组成，不参与 C01 产物对比。",
        }
    fc = r.get("final_composition") or {}
    n = sum(int(v.get("count", 0)) for v in fc.values())
    comp = []
    for f, v in fc.items():
        c = int(v.get("count", 0))
        comp.append({"formula": f, "count": c, "atoms": int(v.get("atoms", 0)),
                     "share": round(c / float(n), 6) if n else 0.0})
    comp.sort(key=lambda x: -x["count"])
    s = r.get("summary") or {}
    out = {
        "present": True,
        "kind": "chemical_control_terminal_composition",
        "final_N": n,
        "final_atoms": s.get("final_atoms"),
        "final_T": fmt(s.get("final_T"), 2),
        "distinct_formulas": len(comp),
        "top1": comp[0] if comp else None,
        "top": comp[:10],
        "reaction_counts": s.get("reaction_counts") or {},
        "note": "",
    }
    if biome_b01 and biome_b01.get("present"):
        out["compare_C01"] = {
            "final_N_delta": n - biome_b01["final_N"],
            "distinct_delta": len(comp) - biome_b01["distinct_formulas"],
            "same_top1": bool(comp and biome_b01["top1"] and
                              comp[0]["formula"] == biome_b01["top1"]["formula"]),
        }
    return out


# ---------------------------------------------------------------- T64 对比
T64_METRICS = [
    ("n_elements", "元素数"), ("final_N", "终态分子数"),
    ("distinct_formulas", "终态种数"), ("mean_atoms", "平均原子数"),
    ("max_atoms", "最大原子数"), ("top1_share", "头号产物占比"),
    ("new_substances", "新物质数"), ("capped", "capped 次数"),
    ("effective_species", "有效物种数"), ("hold_activity", "恒温活性"),
]


def _agg(bs, getter):
    vals = [getter(b) for b in bs]
    vals = [v for v in vals if isinstance(v, (int, float))]
    if not vals:
        return None
    return {"mean": round(sum(vals) / len(vals), 3),
            "min": round(min(vals), 3), "max": round(max(vals), 3),
            "n": len(vals)}


def _mixed(b):
    return (b.get("groups") or {}).get("mixed", {}).get("atoms_share")


def _comp_counts(b):
    return {r["formula"]: r["count"] for r in (b.get("composition") or [])}


def _cos(x, y):
    import math
    vx, vy = _comp_counts(x), _comp_counts(y)
    keys = set(vx) | set(vy)
    num = sum(vx.get(k, 0) * vy.get(k, 0) for k in keys)
    den = (math.sqrt(sum(v * v for v in vx.values())) *
           math.sqrt(sum(v * v for v in vy.values())))
    return round(num / den, 4) if den else 0.0


def analyze_t64_compare(path, t65_biomes):
    t64 = load_json(path) or {}
    tb = [b for b in (t64.get("biomes") or []) if b.get("present")]
    if not tb:
        return {"available": False, "path": path,
                "note": "t64_analysis.json 未就绪，T64 对比与复现检查暂缺。"}
    metrics = []
    for key, cn in T64_METRICS:
        metrics.append({"key": key, "cn": cn,
                        "t64": _agg(tb, lambda b, k=key: b.get(k)),
                        "t65": _agg(t65_biomes, lambda b, k=key: b.get(k))})
    metrics.append({"key": "mixed_share", "cn": "混合家族占比",
                    "t64": _agg(tb, _mixed), "t65": _agg(t65_biomes, _mixed)})
    # 可重复性：C10 vs T64 B11（同元素/同投料/同 L）
    c10 = next((b for b in t65_biomes if b.get("id") == "C10" and b.get("present")), None)
    b11 = next((b for b in tb if b.get("id") == "B11"), None)
    rep = None
    if c10 and b11:
        seed64 = b11.get("seed") or 0
        if not seed64:
            tf = ((t64.get("meta") or {}).get("files") or {}).get("biomes") or {}
            rp = (tf.get(b11["id"]) or {}).get("result")
            if rp and os.path.exists(rp):
                raw = load_json(rp) or {}
                seed64 = (raw.get("biome") or {}).get("seed") \
                    or (raw.get("config") or {}).get("seed") or 0
        same = (sorted(c10.get("elements") or []) == sorted(b11.get("elements") or [])
                and c10.get("L") == b11.get("L")
                and c10.get("atoms_per_element") == b11.get("atoms_per_element")
                and c10.get("total_atoms_design") == b11.get("total_atoms_design"))
        sh = set(_comp_counts(c10)) & set(_comp_counts(b11))
        un = set(_comp_counts(c10)) | set(_comp_counts(b11))
        rep = {
            "t65_id": c10["id"], "t64_id": b11["id"],
            "same_elements": sorted(c10.get("elements") or []) == sorted(b11.get("elements") or []),
            "same_design": bool(same),
            "design": {
                "elements": c10.get("elements"),
                "L": {"t65": c10.get("L"), "t64": b11.get("L")},
                "atoms_per_element": {"t65": c10.get("atoms_per_element"),
                                      "t64": b11.get("atoms_per_element")},
                "total_atoms": {"t65": c10.get("total_atoms_design"),
                                "t64": b11.get("total_atoms_design")},
            },
            "seed": {"t65": c10.get("seed"), "t64": seed64,
                     "same_seed": (c10.get("seed") or 0) == (seed64 or 0) and bool(seed64)},
            "metrics": {
                "final_N": {"t65": c10.get("final_N"), "t64": b11.get("final_N")},
                "final_atoms": {"t65": c10.get("final_atoms"), "t64": b11.get("final_atoms")},
                "distinct_formulas": {"t65": c10.get("distinct_formulas"),
                                      "t64": b11.get("distinct_formulas")},
                "mean_atoms": {"t65": c10.get("mean_atoms"), "t64": b11.get("mean_atoms")},
                "max_atoms": {"t65": c10.get("max_atoms"), "t64": b11.get("max_atoms")},
                "top1_share": {"t65": round(c10.get("top1_share") or 0, 4),
                               "t64": round(b11.get("top1_share") or 0, 4)},
                "new_substances": {"t65": c10.get("new_substances"), "t64": b11.get("new_substances")},
                "capped": {"t65": c10.get("capped"), "t64": b11.get("capped")},
                "effective_species": {"t65": c10.get("effective_species"),
                                      "t64": b11.get("effective_species")},
                "mixed_share": {"t65": round(_mixed(c10) or 0, 4),
                                "t64": round(_mixed(b11) or 0, 4)},
            },
            "top1": {"t65": (c10.get("top1") or {}).get("formula"),
                     "t64": (b11.get("top1") or {}).get("formula")},
            "top5": {"t65": [r["formula"] for r in (c10.get("composition") or [])[:5]],
                     "t64": [r["formula"] for r in (b11.get("composition") or [])[:5]]},
            "composition_cosine": _cos(c10, b11),
            "shared_formulas": len(sh), "union_formulas": len(un),
            "jaccard_top_all": round(len(sh) / float(len(un)), 4) if un else 0.0,
            "note": "同元素集合、同每元素原子数、同 L、同 seed：若逐项一致则为确定性复现（same seed deterministic repeat）。",
        }
    return {"available": True, "path": path,
            "t64_n_present": len(tb), "t65_n_present": len(t65_biomes),
            "t64_experiment": (t64.get("meta") or {}).get("experiment"),
            "metrics": metrics, "repeatability": rep}


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", default=os.path.join(BASE, "t65_biomes.json"))
    ap.add_argument("--index", default=os.path.join(BASE, "t65_biome_index.json"))
    ap.add_argument("--dir", default=BASE)
    ap.add_argument("--control", default=os.path.join(BASE, "t65_control_C01.json"))
    ap.add_argument("--t64-analysis", default=os.path.join(BASE, "t64_analysis.json"))
    ap.add_argument("--only", default="", help="逗号分隔群系 id，仅分析这些（自测用）")
    ap.add_argument("--out", default=os.path.join(BASE, "t65_analysis.json"))
    args = ap.parse_args()

    t0 = time.time()
    design = load_json(args.design, {}) or {}
    index = load_json(args.index, {}) or {}
    idx_map = {}
    for row in index.get("biomes") or []:
        idx_map[row.get("id")] = row
    all_biomes = design.get("biomes") or []
    only = [s.strip() for s in args.only.split(",") if s.strip()]

    biomes = []
    files = {}
    for b in all_biomes:
        bid = b.get("id")
        if only and bid not in only:
            continue
        row = idx_map.get(bid)
        rf = os.path.join(args.dir, (row or {}).get("file") or
                          ("t65_biome_%s_result.json" % bid))
        sf = os.path.join(args.dir, "t65_biome_%s_state.json" % bid)
        r = load_json(rf)
        st = load_json(sf)
        if r:
            files[bid] = {"result": rf, "state": sf}
            biomes.append(analyze_biome(b, r, st, row or {}))
        else:
            biomes.append(pending_biome(b))

    schedule = design.get("schedule") or {}
    cross = analyze_cross(biomes, design)
    features = analyze_features(biomes)
    control = analyze_control(args.control, next((x for x in biomes if x["id"] == "C01"), None))
    t64_compare = analyze_t64_compare(args.t64_analysis, [b for b in biomes if b.get("present")])

    done = [b for b in biomes if b.get("present")]
    pending = [b["id"] for b in biomes if not b.get("present")]
    caveats = []
    if pending:
        caveats.append("本次分析仅含 %d/%d 个群系（缺失：%s），缺失群系在 JSON 中 status=pending、"
                       "图中以占位面板显示。" % (len(done), len(biomes), "、".join(pending)))
    if any((b.get("distinct_ever") or 0) > (b.get("distinct_formulas") or 0) for b in done):
        caveats.append("summary/time_series 的 distinct_formulas 是分子式历史累计键（fcnt），"
                       "大于终态实际分子式数；本报告终态种数统一取 len(final_composition)。")
    capped_b = [b for b in done if b.get("capped")]
    if capped_b:
        caveats.append("capped 为合并后 >40 原子的弹性截断计数（发生在退火前中期），"
                       "不计入 complete/incomplete/none 反应判定；本次涉及 %s。" %
                       "、".join("%s(%d)" % (b["id"], b["capped"]) for b in capped_b))
    if control.get("present"):
        if control.get("kind") == "physical_control_no_chemistry":
            caveats.append("t65_control_C01 为关闭化学反应的纯运动学对照（500 分钟），"
                           "用于验证运移/自由程标定（median 路径长度、≥500 比例），"
                           "不含终态组成，不能与 C01 产物谱直接对比。")
        else:
            caveats.append("t65_control_C01 为 C01 投料的化学对照，用于校验 C01 终态组成/产物判定口径"
                           "（对照仅记录终态组成，不参与模拟统计）。")
    else:
        caveats.append("t65_control_C01.json 未就绪，对照结论暂缺。")
    if t64_compare.get("available"):
        rep = t64_compare.get("repeatability") or {}
        if rep:
            caveats.append(
                "T64 对比使用 t64_analysis.json（%d 群系汇总）。可重复性检查 C10 vs T64 B11："
                "同元素/同每元素原子数/同 L；seed 分别为 %s 与 %s（%s）。"
                % (t64_compare.get("t64_n_present"),
                   rep["seed"]["t65"], rep["seed"]["t64"],
                   "相同，属同种子确定性复现" if rep["seed"]["same_seed"]
                   else "不同，仅种子差异的随机复现"))
    else:
        caveats.append("t64_analysis.json 未就绪，T64 对比与 C10/B11 复现检查暂缺。")
    caveats.append("所有群系含至少一种三价元素（O/P/K），但 25°C 恒温段事件数远低于退火段，"
                   "终态产物主要在 1000→25°C 退火过程中定型。")

    out = {
        "meta": {
            "experiment": design.get("experiment") or "T65 生态群系",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "python": sys.version.split()[0],
            "files": {"design": args.design, "index": args.index,
                      "control": args.control, "biomes": files},
            "n_biomes": len(biomes),
            "n_present": len(done),
            "elapsed_s": round(time.time() - t0, 2),
        },
        "design": {
            "seed_base": design.get("seed_base"),
            "cap": design.get("cap"), "event_limit": design.get("event_limit"),
            "area_model": design.get("area_model"),
            "snap_minutes": design.get("snap_minutes"),
            "element_order": FORMULA_ORDER,
            "element_cn": ELEMENT_CN,
            "element_valence": ELEMENT_VALENCE,
            "groups": {"poly": ["O", "X", "C"], "dyn": ["P", "W", "L"],
                       "scat": ["K", "A", "F"]},
            "group_cn": GROUP_CN,
            "biomes": [{"id": b.get("id"), "name": b.get("name"),
                        "tag": b.get("tag"), "elements": b.get("elements"),
                        "n_elements": b.get("n_elements"),
                        "trivalent": b.get("trivalent"), "L": b.get("L"),
                        "atoms_per_element": b.get("atoms_per_element"),
                        "total_atoms": b.get("total_atoms"),
                        "total_molecules": b.get("total_molecules"),
                        "load_spec": b.get("load_spec"),
                        "density_atoms_per_area": b.get("density_atoms_per_area")}
                       for b in all_biomes],
        },
        "schedule": schedule,
        "biomes": biomes,
        "cross": cross,
        "features": features,
        "control": control,
        "t64_compare": t64_compare,
        "key_numbers": {
            "n_present": len(done),
            "pending": pending,
            "total_molecules": cross["totals"]["molecules"],
            "total_atoms": cross["totals"]["atoms"],
            "max_atoms_overall": max([b["max_atoms"] for b in done] or [0]),
            "max_atoms_biome": next((b["id"] for b in done
                                     if b["max_atoms"] == max([x["max_atoms"] for x in done] or [0])), None),
            "mean_top1_share": round(sum(b["top1_share"] for b in done) / float(len(done)), 4) if done else None,
            "capped_total": sum(b["capped"] for b in done),
            "capped_biomes": [{"id": b["id"], "capped": b["capped"],
                               "share": b["capped_share"]}
                              for b in done if b["capped"]],
            "mean_atoms": round(sum(b["mean_atoms"] for b in done) / float(len(done)), 3) if done else None,
            "conservation_ok": all(
                (b.get("conservation") or {}).get("elements_ok", False)
                and (b.get("conservation") or {}).get("atoms_ok", False)
                for b in done),
            "control_pass": control.get("pass"),
            "feature_top3": [r["id"] for r in features.get("ranking") or []],
            "t64_compare_available": bool(t64_compare.get("available")),
            "repeatability": (t64_compare.get("repeatability") or {}).get("metrics"),
            "extremes": {
                "diversity": (max(done, key=lambda b: b["effective_species"])["id"] if done else None),
                "specialization": (max(done, key=lambda b: b["top1_share"])["id"] if done else None),
                "polymerization": (max(done, key=lambda b: b["mean_atoms"])["id"] if done else None),
                "max_size": (max(done, key=lambda b: b["max_atoms"])["id"] if done else None),
                "trivalent": (max(done, key=lambda b: b["trivalent_util"])["id"] if done else None),
                "conversion": (max(done, key=lambda b: b["conversion"])["id"] if done else None),
                "hold_activity": (max(done, key=lambda b: b["hold_activity"] or 0)["id"] if done else None),
                "novelty": (max(done, key=lambda b: b["new_substances"])["id"] if done else None),
            },
        },
        "caveats": caveats,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print("[ok] %s  %.0f KB  biomes=%d/%d  present=%d  elapsed=%.1fs" % (
        os.path.basename(args.out), os.path.getsize(args.out) / 1024.0,
        len(biomes), len(all_biomes), len(done), time.time() - t0))
    for b in done:
        print("  %s %-10s N=%-6d atoms=%-6d 种=%-3d capped=%-5d top1=%s %.1f%%" % (
            b["id"], b["name"], b["final_N"], b["final_atoms"],
            b["distinct_formulas"], b["capped"],
            b["top1"]["formula"] if b["top1"] else "-", b["top1_share"] * 100))
    if features.get("available"):
        print("  特色群系:", "、".join("%s(%s)" % (r["id"], r["dominant_cn"])
                                     for r in features["ranking"]))


if __name__ == "__main__":
    main()
