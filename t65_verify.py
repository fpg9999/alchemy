# -*- coding: utf-8 -*-
"""t65_verify.py —— T65 生态群系独立验证脚本（只读结果 JSON，不修改实验文件）

T65 = 12 个生态群系 C01~C10，每个群系只投入其声明元素的双原子单质
（每元素原子数相等 2000~4000），1000°C→25°C 退火 975 分钟，
随后 25°C 浮动 600 分钟（±8°C/240min 日周期 + ±3°C/900min 季节周期），
总 1575 分钟；cap=40、EVENT_LIMIT=30000、种子 20261128+i。

独立实现（不 import t65_biomes / t55_kinetic_env / pot_all），自己实现
分子式解析、价数表、结构合法性检查、温度日程公式，避免与被验证代码共享逻辑。

验证分组：
  1 设计与投料合规（t65_biomes.json）
  2 每群系投料（result config / load_spec / biome 元数据）
  3 质量与元素守恒（终态分子数/原子数/逐元素/state 汇总）
  4 温度日程（config.temp_schedule、逐分钟 T、hold 段范围与波动、final_T）
  5 判定自洽（四类计数、累计一致、events_total/蓄水池、抽样事件守恒、cap）
  6 快照（数量/时间点/每帧点数）
  7 终态表 sanity（final_composition / top structures）
  8 state 与 result 一致性（总数/组成/逐元素/结构合法性）
  9 无化学对照 t65_control_C01.json（min/fraction_ge_500/by_size/装载）
 10 index 与 result 一致性（t65_biome_index.json）
 11 输入文件 SHA256（10 result + 10 state + design + index + control，共 23 个）

输出 t65_verify.json：groups -> subchecks（逐项 PASS/FAIL/PENDING/SKIP/INFO + 实测值）、
summary（计数）、inputs（含 SHA256）、overall（PASS / FAIL / INCOMPLETE）。

用法（默认读脚本同目录 t65_*）：
  python t65_verify.py
  python t65_verify.py --design ... --index ... --control ... --out ...
"""
import argparse
import collections
import hashlib
import json
import math
import os
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- 常量（独立定义）
ELEMS = ("O", "X", "C", "P", "W", "L", "K", "A", "F")
VALENCE = {"O": 3, "P": 3, "K": 3,
           "X": 2, "W": 2, "A": 2,
           "C": 1, "L": 1, "F": 1}
V3 = ("O", "P", "K")
V2 = ("X", "W", "A")
V1 = ("C", "L", "F")
RC_TYPES = ("complete", "incomplete", "none", "capped")

# T65 设计常量（独立于生成脚本重新声明，用于核对）
EXPECT_BIOMES = [
    # (id, name, elements, atoms_per_element, L)
    ("C01", "双骨架平原", ["O", "P", "X", "W"], 3500, 18000),
    ("C02", "散素配位谷", ["O", "K", "C", "L"], 3500, 18000),
    ("C03", "动素配位台地", ["P", "X", "A", "L"], 3500, 18000),
    ("C04", "散素晶原", ["K", "A", "F", "X"], 3500, 18000),
    ("C05", "聚动五元林", ["O", "X", "C", "P", "W"], 3000, 19000),
    ("C06", "三骨架麓", ["O", "P", "K", "X", "A"], 3000, 19000),
    ("C07", "聚动散混合坡", ["O", "X", "C", "P", "K", "A"], 2500, 19000),
    ("C08", "七元雨林带", ["O", "X", "C", "P", "W", "L", "K"], 2400, 20000),
    ("C09", "缺焰八元生态", ["O", "X", "C", "P", "W", "L", "K", "A"], 2100, 20000),
    ("C10", "九元大生态复现", list(ELEMS), 2000, 20000),
]
EXPECT_SCHEDULE = {
    "model": "t65_biome", "T0": 1000.0, "T_mid": 25.0,
    "anneal_minutes": 975, "hold_minutes": 600,
    "anneal_rate_c_per_min": 1.0, "minutes": 1575,
    "day_amp": 8.0, "day_period": 240.0,
    "year_amp": 3.0, "year_period": 900.0, "year_phase": 0.7,
    "hold_T_min": 14.0, "hold_T_max": 36.0,
}
EXPECT_SNAP = [0, 25, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900,
               950, 975, 1000, 1050, 1100, 1150, 1200, 1300, 1400,
               1500, 1560, 1570, 1574]
EXPECT_SEED_BASE = 20261128
EXPECT_CAP = 40
EXPECT_EVENT_LIMIT = 30000
EXPECT_MINUTES = 1575
T0 = 1000.0
T_MID = 25.0
ANNEAL_MINUTES = 975
HOLD_MINUTES = 600
DAY_AMP = 8.0
DAY_PERIOD = 240.0
YEAR_AMP = 3.0
YEAR_PERIOD = 900.0
YEAR_PHASE = 0.7
HOLD_T_MIN = 14.0
HOLD_T_MAX = 36.0
EXPECT_CONTROL_MOLECULES = 7000
EXPECT_CONTROL_L = 18000
EXPECT_CONTROL_MINUTES = 500

SAMPLE_CAP = 30000  # 任务要求：抽样事件检查 ≤50,000 条/群系；T65 蓄水池 30,000


# ---------------------------------------------------------------- 基础工具
def iso_now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_formula(f):
    if not isinstance(f, str) or f == "":
        raise ValueError("空/非字符串分子式: %r" % (f,))
    counts = {}
    i, n = 0, len(f)
    while i < n:
        c = f[i]
        if c not in VALENCE:
            raise ValueError("未知元素符号 %r（分子式 %r）" % (c, f))
        j = i + 1
        num = 0
        while j < n and f[j].isdigit():
            num = num * 10 + int(f[j])
            j += 1
        counts[c] = counts.get(c, 0) + (num if num > 0 else 1)
        i = j
    return counts


def formula_atoms(f):
    return sum(parse_formula(f).values())


def formula_valence(f):
    p = parse_formula(f)
    return {k: sum(p.get(e, 0) for e in grp)
            for k, grp in (("v3", V3), ("v2", V2), ("v1", V1))}


def fnum(x, nd=4):
    if x is None:
        return "None"
    if isinstance(x, bool):
        return str(x)
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        return ("%%.%df" % nd) % x
    return str(x)


def jsafe(o):
    if isinstance(o, collections.Counter):
        return {str(k): int(v) for k, v in sorted(o.items())}
    if isinstance(o, dict):
        return {str(k): jsafe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsafe(v) for v in o]
    if isinstance(o, set):
        return sorted(jsafe(v) for v in o)
    if isinstance(o, (bool, int, float, str)) or o is None:
        return o
    return str(o)


def file_meta(path):
    if not path or not os.path.isfile(path):
        return {"path": path, "exists": False}
    st = os.stat(path)
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return {"path": path, "exists": True, "size_bytes": st.st_size,
            "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
            "sha256": h.hexdigest()}


def temp_profile(t):
    """独立复算温度日程（°C）：前 975 分钟线性 1000→25，之后 25 + 8sin(2πtt/240) + 3sin(2πtt/900+0.7)。"""
    if t < ANNEAL_MINUTES:
        return T0 + (T_MID - T0) * (float(t) / float(ANNEAL_MINUTES))
    tt = t - ANNEAL_MINUTES
    return T_MID + DAY_AMP * math.sin(2.0 * math.pi * tt / DAY_PERIOD) \
        + YEAR_AMP * math.sin(2.0 * math.pi * tt / YEAR_PERIOD + YEAR_PHASE)


EXPECTED_T = [temp_profile(t) for t in range(EXPECT_MINUTES)]


# ---------------------------------------------------------------- 检查收集器
class Checker:
    def __init__(self):
        self.groups = []
        self._cur = None
        self.notes = []

    def begin(self, gid, name):
        self._cur = {"id": gid, "name": name, "subchecks": []}
        self.groups.append(self._cur)

    def sub(self, sid, name, status, detail, values=None):
        rec = {"id": sid, "name": name, "status": status, "detail": detail}
        if values is not None:
            rec["values"] = jsafe(values)
        self._cur["subchecks"].append(rec)
        return rec

    def note(self, text):
        self.notes.append(text)

    def finalize(self):
        for g in self.groups:
            sts = [s["status"] for s in g["subchecks"]]
            if "FAIL" in sts:
                g["status"] = "FAIL"
            elif "PENDING" in sts:
                g["status"] = "PENDING"
            elif "PASS" in sts:
                g["status"] = "PASS"
            else:
                g["status"] = "SKIP"


# ---------------------------------------------------------------- 数据加载（紧凑化）
def analyze_events(ev_samples, scan_cap=SAMPLE_CAP):
    """逐条检查抽样事件的原子/价数守恒（最多扫描 scan_cap 条）。"""
    n_total = len(ev_samples)
    st = {"n": n_total, "scanned": 0, "type_counts": {},
          "product_len_hist": {}, "atom_conserv_bad": 0,
          "valence_conserv_bad": 0, "parse_bad": 0, "empty_products": 0,
          "bad_examples": []}
    tcount = collections.Counter()
    plen = []
    for e in ev_samples[:scan_cap]:
        ins = e.get("inputs") or []
        prods = e.get("products") or []
        tcount[str(e.get("type"))] += 1
        plen.append(len(prods))
        if not prods:
            st["empty_products"] += 1
        try:
            ai = collections.Counter()
            ao = collections.Counter()
            vi = 0
            vo = 0
            for f in ins:
                p = parse_formula(f)
                ai.update(p)
                vi += sum(VALENCE[k] * v for k, v in p.items())
            for f in prods:
                p = parse_formula(f)
                ao.update(p)
                vo += sum(VALENCE[k] * v for k, v in p.items())
        except Exception:
            st["parse_bad"] += 1
            continue
        if ai != ao:
            st["atom_conserv_bad"] += 1
            if len(st["bad_examples"]) < 5:
                st["bad_examples"].append({"kind": "atom", "inputs": ins,
                                           "products": prods})
        if vi != vo:
            st["valence_conserv_bad"] += 1
            if len(st["bad_examples"]) < 5:
                st["bad_examples"].append({"kind": "valence", "inputs": ins,
                                           "products": prods})
    st["scanned"] = min(n_total, scan_cap)
    st["type_counts"] = dict(tcount)
    st["product_len_hist"] = {str(k): int(v)
                              for k, v in sorted(collections.Counter(plen).items())}
    return st


def load_design(path):
    meta = file_meta(path)
    if not meta["exists"]:
        return None
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    rows = []
    for b in d.get("biomes") or []:
        load_spec = []
        for r in b.get("load_spec") or []:
            load_spec.append({"desc": r.get("desc"), "formula": r.get("formula"),
                              "count": r.get("count")})
        rows.append({
            "id": b.get("id"), "name": b.get("name"), "tag": b.get("tag"),
            "elements": list(b.get("elements") or []),
            "n_elements": b.get("n_elements"), "trivalent": list(b.get("trivalent") or []),
            "L": b.get("L"), "atoms_per_element": b.get("atoms_per_element"),
            "total_atoms": b.get("total_atoms"),
            "total_molecules": b.get("total_molecules"),
            "load_spec": load_spec,
            "density": b.get("density_atoms_per_area")})
    return {"meta": meta, "experiment": d.get("experiment"),
            "seed_base": d.get("seed_base"), "schedule": d.get("schedule"),
            "cap": d.get("cap"), "event_limit": d.get("event_limit"),
            "area_model": d.get("area_model"), "snap_minutes": d.get("snap_minutes"),
            "biomes": rows}


def load_biome_result(path, scan_events=True, scan_cap=SAMPLE_CAP):
    meta = file_meta(path)
    if not meta["exists"]:
        return None
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    cfg = d.get("config") or {}
    sm = d.get("summary") or {}
    R = {"meta": meta,
         "config": {k: cfg.get(k) for k in (
             "L", "T0", "T_end", "minutes", "initial_particles",
             "initial_atoms", "seed", "seed_initial_count",
             "max_reaction_atoms", "area_model", "snap_minutes",
             "temp_schedule", "experiment", "weighted_partner")},
         "load_spec": [{"tag": r.get("tag"), "desc": r.get("desc"),
                        "formula": r.get("formula"), "count": r.get("count")}
                       for r in (cfg.get("load_spec") or [])],
         "biome": d.get("biome") or {},
         "summary": {k: sm.get(k) for k in (
             "final_N", "final_atoms", "final_T", "events_total",
             "reaction_counts", "decomp_events", "runtime_s",
             "biome_id", "biome_name")}}
    comp = {}
    for f, r in (d.get("final_composition") or {}).items():
        try:
            c = int(r.get("count", 0))
        except Exception:
            c = 0
        if c > 0:
            comp[f] = {"count": c, "atoms": r.get("atoms")}
    R["comp"] = comp
    tops = {}
    for f, r in (d.get("final_top_structures") or {}).items():
        tops[f] = {"atoms": list(r.get("atoms") or []),
                   "edges": [list(e) for e in (r.get("edges") or [])],
                   "label": r.get("label")}
    R["top"] = tops
    ts = []
    for row in (d.get("time_series") or []):
        ts.append({k: row.get(k) for k in (
            "t", "T", "N", "atoms", "max_atoms", "complete", "incomplete",
            "none", "capped", "events_total", "decomp",
            "d_complete", "d_incomplete", "d_none", "d_capped")})
    R["ts"] = ts
    snaps = []
    for s in (d.get("snapshots") or []):
        pts = s.get("points") or []
        shape_bad = 0
        for p in pts[:50]:
            if not isinstance(p, (list, tuple)) or len(p) < 3 or \
                    not all(isinstance(v, (int, float)) for v in p[:3]):
                shape_bad += 1
        snaps.append({"t": s.get("t"), "n": len(pts), "shape_bad": shape_bad})
    R["snaps"] = snaps
    ev = d.get("event_samples") or []
    R["events"] = analyze_events(ev, scan_cap) if scan_events else {
        "n": len(ev), "skipped": True}
    del d, ev
    return R


def load_state(path):
    meta = file_meta(path)
    if not meta["exists"]:
        return None
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    mols = []
    for m in (d.get("molecules") or []):
        mols.append({"formula": m.get("formula"),
                     "count": int(m.get("count", 0)),
                     "atoms": list(m.get("atoms") or []),
                     "edges": [list(e) for e in (m.get("edges") or [])]})
    R = {"meta": meta,
         "total_molecules": d.get("total_molecules"),
         "total_atoms": d.get("total_atoms"),
         "distinct_formulas": d.get("distinct_formulas"),
         "distinct_structures": d.get("distinct_structures"),
         "t": d.get("t"), "T": d.get("T"),
         "biome_id": d.get("biome_id"),
         "molecules": mols,
         "sum_counts": sum(m["count"] for m in mols),
         "sum_atoms": sum(m["count"] * len(m["atoms"]) for m in mols)}
    comp = collections.Counter()
    elem = collections.Counter()
    val = {"v3": 0, "v2": 0, "v1": 0}
    try:
        for m in mols:
            p = parse_formula(m["formula"])
            comp[m["formula"]] += m["count"]
            for e, k in p.items():
                elem[e] += k * m["count"]
            v = formula_valence(m["formula"])
            for k in ("v3", "v2", "v1"):
                val[k] += v[k] * m["count"]
    except Exception:
        pass
    R["comp"] = dict(comp)
    R["element_atoms"] = {e: elem.get(e, 0) for e in ELEMS}
    R["valence_atoms"] = val
    del d
    return R


def load_control(path):
    meta = file_meta(path)
    if not meta["exists"]:
        return None
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    R = {"meta": meta, "config": d.get("config") or {},
         "stats": d.get("stats") or {}, "by_size": d.get("by_size") or {},
         "timeseries": d.get("timeseries") or [],
         "runtime_s": d.get("runtime_s")}
    del d
    return R


def load_index(path):
    meta = file_meta(path)
    if not meta["exists"]:
        return None
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    rows = []
    for b in d.get("biomes") or []:
        rows.append({"id": b.get("id"), "name": b.get("name"),
                     "status": b.get("status"), "file": b.get("file"),
                     "elements": b.get("elements"), "L": b.get("L"),
                     "total_atoms": b.get("total_atoms"),
                     "runtime_s": b.get("runtime_s"),
                     "final_N": b.get("final_N"),
                     "final_atoms": b.get("final_atoms"),
                     "final_T": b.get("final_T"),
                     "reaction_counts": b.get("reaction_counts")})
    return {"meta": meta, "experiment": d.get("experiment"),
            "schedule": d.get("schedule"), "biomes": rows}


# ---------------------------------------------------------------- 统计/校验
def comp_stats(comp):
    out = {"n_formula": len(comp), "molecules": 0, "atoms": 0,
           "element_atoms": {e: 0 for e in ELEMS},
           "valence_atoms": {"v3": 0, "v2": 0, "v1": 0},
           "atoms_field_mismatch": [], "atoms_none": [],
           "parse_errors": [], "max_atoms": 0}
    for f, r in comp.items():
        try:
            p = parse_formula(f)
        except Exception as exc:
            out["parse_errors"].append({"formula": f, "error": str(exc)})
            continue
        c = int(r.get("count", 0))
        na = sum(p.values())
        out["molecules"] += c
        out["atoms"] += c * na
        if na > out["max_atoms"]:
            out["max_atoms"] = na
        for e, k in p.items():
            out["element_atoms"][e] += k * c
        v = formula_valence(f)
        for k in ("v3", "v2", "v1"):
            out["valence_atoms"][k] += v[k] * c
        af = r.get("atoms")
        if af is None:
            out["atoms_none"].append(f)
        elif int(af) != na:
            out["atoms_field_mismatch"].append(
                {"formula": f, "field": af, "formula_atoms": na})
    out["atoms_field_mismatch"] = out["atoms_field_mismatch"][:8]
    out["atoms_none"] = out["atoms_none"][:8]
    out["parse_errors"] = out["parse_errors"][:8]
    return out


def validate_structure(f, atoms, edges, cap=None):
    issues = []
    try:
        p = parse_formula(f)
    except Exception as exc:
        return ["分子式无法解析: %s" % exc]
    n = len(atoms)
    if sum(p.values()) != n:
        issues.append("atoms 数 %d ≠ 公式原子数 %d" % (n, sum(p.values())))
    if collections.Counter(atoms) != collections.Counter(p):
        issues.append("atoms 元素组成 ≠ 公式")
    for a in atoms:
        if a not in VALENCE:
            issues.append("未知元素 %r" % a)
            break
    if cap is not None and n > cap:
        issues.append("原子数 %d > cap %d" % (n, cap))
    deg = [0] * n
    seen = set()
    for k, e in enumerate(edges):
        if not isinstance(e, (list, tuple)) or len(e) < 3:
            issues.append("第%d条边格式非法: %r" % (k, e))
            continue
        i, j, o = e[0], e[1], e[2]
        if not isinstance(i, int) or not isinstance(j, int) or not isinstance(o, int):
            issues.append("第%d条边非整数: %r" % (k, e))
            continue
        if not (0 <= i < n and 0 <= j < n):
            issues.append("第%d条边下标越界: %r" % (k, e))
            continue
        if i == j:
            issues.append("第%d条边为自环" % k)
            continue
        if o < 1:
            issues.append("第%d条边键级 %d <1" % (k, o))
            continue
        key = (min(i, j), max(i, j))
        if key in seen:
            issues.append("原子对 %r 重复出现" % (key,))
            continue
        seen.add(key)
        deg[i] += o
        deg[j] += o
    if len(issues) < 3:
        for idx, a in enumerate(atoms):
            if a in VALENCE and deg[idx] != VALENCE[a]:
                issues.append("原子%d(%s) 键数 %d ≠ 价数 %d"
                              % (idx, a, deg[idx], VALENCE[a]))
                if len(issues) >= 3:
                    break
    return issues


# ---------------------------------------------------------------- 上下文
class Ctx:
    def __init__(self, design, results, states, control, index):
        self.design = design
        self.results = results   # {bid: compact result or None}
        self.states = states     # {bid: compact state or None}
        self.control = control
        self.index = index
        self.design_by_id = {}
        if design:
            for b in design["biomes"]:
                self.design_by_id[b["id"]] = b
        self.event_limit = (design or {}).get("event_limit") or EXPECT_EVENT_LIMIT

    def biome(self, bid):
        return self.design_by_id.get(bid)


def missing_files(ck, sid, name, bid, misses):
    ck.sub(sid, name, "PENDING",
           "缺失文件: %s（待生成/待补验）" % ", ".join(misses))
    return False


# ================================================================ 组 1 设计合规
def check_group1(ck, ctx):
    ck.begin(1, "设计与投料合规（t65_biomes.json）")
    D = ctx.design
    if not D:
        ck.sub("1.0", "设计文件", "PENDING", "t65_biomes.json 缺失（待生成）")
        return
    rows = D["biomes"]
    ids = [b["id"] for b in rows]
    exp_ids = [b[0] for b in EXPECT_BIOMES]
    if ids == exp_ids:
        ck.sub("1.1", "10 群系 id 完整且顺序正确", "PASS",
               "C01~C10 共 %d 个群系" % len(ids))
    else:
        ck.sub("1.1", "10 群系 id 完整且顺序正确", "FAIL",
               "实际 id=%s，期望 %s" % (ids, exp_ids))

    def cmp_rows(keyfn, label):
        issues = []
        vals = {}
        for expected in EXPECT_BIOMES:
            bid, name, elems, ape, L = expected
            b = ctx.design_by_id.get(bid)
            if not b:
                issues.append("%s 缺失" % bid)
                continue
            vals[bid] = keyfn(b, elems, ape, L)
            for t in keyfn(b, elems, ape, L):
                if t.get("ok") is False:
                    issues.append("%s: %s" % (bid, t.get("why")))
        if not issues:
            ck.sub(label, "群系设计字段（元素/每元素原子数/L/名称）", "PASS",
                   "10 群系 elements/atoms_per_element/L/name 与独立预期一致",
                   {"rows": vals})
        else:
            ck.sub(label, "群系设计字段（元素/每元素原子数/L/名称）", "FAIL",
                   "；".join(issues[:10]), {"rows": vals})

    def row_check(b, elems, ape, L):
        out = []
        ok = (set(b["elements"]) == set(elems) and b["atoms_per_element"] == ape
              and b["L"] == L and b["name"] == [x for x in EXPECT_BIOMES
                                              if x[0] == b["id"]][0][1])
        out.append({"ok": ok, "why": "字段不一致: elements=%r ape=%r L=%r name=%r"
                    % (b["elements"], b["atoms_per_element"], b["L"], b["name"])})
        return out

    cmp_rows(row_check, "1.2")

    # 1.3 投料：只含声明元素的双原子单质
    issues = []
    vals = {}
    for expected in EXPECT_BIOMES:
        bid, name, elems, ape, L = expected
        b = ctx.design_by_id.get(bid)
        if not b:
            issues.append("%s 缺失" % bid)
            continue
        rows_ = b["load_spec"]
        formulas = [r["formula"] for r in rows_]
        want = [e + "2" for e in elems]
        if sorted(formulas) != sorted(want):
            issues.append("%s 投料公式=%s，期望=%s" % (bid, formulas, want))
        n_atoms = 0
        n_mol = 0
        for r in rows_:
            try:
                p = parse_formula(r["formula"])
            except Exception as exc:
                issues.append("%s 公式 %r 解析失败: %s" % (bid, r["formula"], exc))
                continue
            if len(p) != 1 or list(p.values()) != [2]:
                issues.append("%s 非双原子单质: %r" % (bid, r["formula"]))
            if int(r["count"]) != ape // 2:
                issues.append("%s %s count=%r ≠ %d"
                              % (bid, r["formula"], r["count"], ape // 2))
            n_mol += int(r["count"])
            n_atoms += int(r["count"]) * 2
        if n_mol != b["total_molecules"]:
            issues.append("%s Σ分子=%d ≠ total_molecules=%r"
                          % (bid, n_mol, b["total_molecules"]))
        if n_atoms != b["total_atoms"]:
            issues.append("%s Σ原子=%d ≠ total_atoms=%r"
                          % (bid, n_atoms, b["total_atoms"]))
        vals[bid] = {"formulas": formulas, "molecules": n_mol, "atoms": n_atoms}
    if not issues:
        ck.sub("1.3", "投料只含声明元素的 X2 双原子单质，count==每元素原子数/2",
               "PASS", "10 群系均只投声明元素的双原子单质，每元素 count=atoms_per_element//2",
               {"rows": vals})
    else:
        ck.sub("1.3", "投料只含声明元素的 X2 双原子单质，count==每元素原子数/2",
               "FAIL", "；".join(issues[:10]), {"rows": vals})

    # 1.4 total_atoms/molecules 复算
    issues = []
    vals = {}
    for expected in EXPECT_BIOMES:
        bid, name, elems, ape, L = expected
        b = ctx.design_by_id.get(bid)
        if not b:
            continue
        ta = len(elems) * ape
        tm = len(elems) * (ape // 2)
        vals[bid] = {"total_atoms": ta, "total_molecules": tm,
                     "declared_atoms": b["total_atoms"],
                     "declared_molecules": b["total_molecules"]}
        if b["total_atoms"] != ta:
            issues.append("%s total_atoms=%r ≠ %d" % (bid, b["total_atoms"], ta))
        if b["total_molecules"] != tm:
            issues.append("%s total_molecules=%r ≠ %d"
                          % (bid, b["total_molecules"], tm))
        if b["n_elements"] != len(elems):
            issues.append("%s n_elements=%r ≠ %d" % (bid, b["n_elements"], len(elems)))
    if not issues:
        ck.sub("1.4", "total_atoms/total_molecules/n_elements 复算一致", "PASS",
               "10 群系 total_atoms=n×ape、total_molecules=n×(ape/2) 一致；"
               "原子数 14000~18000", {"rows": vals})
    else:
        ck.sub("1.4", "total_atoms/total_molecules/n_elements 复算一致", "FAIL",
               "；".join(issues[:10]), {"rows": vals})

    # 1.5 schedule
    sched = D.get("schedule") or {}
    diff = {}
    for k, v in EXPECT_SCHEDULE.items():
        if sched.get(k) != v:
            diff[k] = {"actual": sched.get(k), "expected": v}
    extra = sorted(set(sched) - set(EXPECT_SCHEDULE))
    if not diff and not extra:
        ck.sub("1.5", "schedule 与独立预期一致", "PASS",
               "T0=1000、T_mid=25、anneal=975、hold=600、day±8/240、year±3/900、"
               "hold∈[14,36]、minutes=1575", {"schedule": sched})
    else:
        ck.sub("1.5", "schedule 与独立预期一致", "FAIL",
               "字段不符: %s；额外字段: %s" % (jsafe(diff), extra),
               {"schedule": sched})

    # 1.6 cap/event_limit/snap/seed_base
    issues = []
    if D.get("cap") != EXPECT_CAP:
        issues.append("cap=%r ≠ 40" % D.get("cap"))
    if D.get("event_limit") != EXPECT_EVENT_LIMIT:
        issues.append("event_limit=%r ≠ 30000" % D.get("event_limit"))
    sm = D.get("snap_minutes")
    if sm != EXPECT_SNAP:
        issues.append("snap_minutes=%r ≠ 预期 25 个时间点" % (sm,))
    if D.get("seed_base") != EXPECT_SEED_BASE:
        issues.append("seed_base=%r ≠ 20261128" % D.get("seed_base"))
    am = str(D.get("area_model") or "")
    if "count" not in am:
        issues.append("area_model=%r 非 count 模型" % D.get("area_model"))
    if not issues:
        ck.sub("1.6", "cap/event_limit/snap_minutes/seed_base/area_model 一致",
               "PASS", "cap=40、event_limit=30000、snap 25 点、seed_base=20261128、"
               "area_model=count", {"snap_minutes": sm})
    else:
        ck.sub("1.6", "cap/event_limit/snap_minutes/seed_base/area_model 一致",
               "FAIL", "；".join(issues))

    # 1.7 元素种数 3~9 且至少含一种三价元素
    issues = []
    for expected in EXPECT_BIOMES:
        bid, name, elems, ape, L = expected
        b = ctx.design_by_id.get(bid)
        if not b:
            continue
        n = len(b["elements"])
        tri = sorted(set(b["elements"]) & set(V3))
        decl = sorted(b.get("trivalent") or [])
        if not (4 <= n <= 9):
            issues.append("%s 元素种数=%d 不在 4~9" % (bid, n))
        if len(set(b["elements"])) != n:
            issues.append("%s 元素列表有重复: %r" % (bid, b["elements"]))
        if not tri:
            issues.append("%s 无 O/P/K 三价元素" % bid)
        if decl != tri:
            issues.append("%s 声明 trivalent=%s ≠ 复算=%s" % (bid, decl, tri))
    if not issues:
        ck.sub("1.7", "元素种数 4~9、元素互不重复，且至少含一种 O/P/K 三价元素", "PASS",
               "10 群系元素种数 4~9、无重复元素、trivalent 字段与复算一致")
    else:
        ck.sub("1.7", "元素种数 4~9、元素互不重复，且至少含一种 O/P/K 三价元素", "FAIL",
               "；".join(issues[:10]))

    # 1.8 atoms_per_element 偶数 + density 字段自洽
    issues = []
    for expected in EXPECT_BIOMES:
        bid, name, elems, ape, L = expected
        b = ctx.design_by_id.get(bid)
        if not b:
            continue
        if not (isinstance(b["atoms_per_element"], int)
                and b["atoms_per_element"] % 2 == 0):
            issues.append("%s atoms_per_element=%r 非偶数"
                          % (bid, b["atoms_per_element"]))
        want = round(b["total_atoms"] / float(b["L"]) ** 2, 8)
        got = b.get("density")
        if got is None:
            issues.append("%s density 缺失" % bid)
        elif abs(float(got) - want) > 1e-7:
            issues.append("%s density=%r ≠ %.8f" % (bid, got, want))
    if not issues:
        ck.sub("1.8", "atoms_per_element 为偶数且 density 字段自洽", "PASS",
               "10 群系 atoms_per_element 全为偶数、density=total_atoms/L² 一致（8 位小数）")
    else:
        ck.sub("1.8", "atoms_per_element 为偶数且 density 字段自洽", "FAIL",
               "；".join(issues[:10]))


# ================================================================ 组 2 每群系投料
def check_group2(ck, ctx):
    ck.begin(2, "每群系投料（result config/load_spec/biome 元数据）")
    for idx, expected in enumerate(EXPECT_BIOMES):
        bid, name, elems, ape, L = expected
        sid = "2.%d" % (idx + 1)
        R = ctx.results.get(bid)
        if not R:
            missing_files(ck, sid, "%s 投料" % bid, bid,
                          ["t65_biome_%s_result.json" % bid])
            continue
        cfg = R["config"]
        bio = R["biome"]
        issues = []
        want_atoms = len(elems) * ape
        want_mol = len(elems) * (ape // 2)
        if cfg.get("L") != L:
            issues.append("config.L=%r ≠ %d" % (cfg.get("L"), L))
        if cfg.get("initial_particles") != want_mol:
            issues.append("initial_particles=%r ≠ %d"
                          % (cfg.get("initial_particles"), want_mol))
        if cfg.get("initial_atoms") != want_atoms:
            issues.append("initial_atoms=%r ≠ %d"
                          % (cfg.get("initial_atoms"), want_atoms))
        if cfg.get("max_reaction_atoms") != EXPECT_CAP:
            issues.append("max_reaction_atoms=%r ≠ 40" % cfg.get("max_reaction_atoms"))
        if "count" not in str(cfg.get("area_model")):
            issues.append("area_model=%r 非 count" % cfg.get("area_model"))
        if cfg.get("seed") != EXPECT_SEED_BASE + idx:
            issues.append("seed=%r ≠ %d" % (cfg.get("seed"), EXPECT_SEED_BASE + idx))
        if cfg.get("snap_minutes") != EXPECT_SNAP:
            issues.append("config.snap_minutes 与预期 25 点不一致")
        if not isinstance(cfg.get("temp_schedule"), dict):
            issues.append("config.temp_schedule 缺失")
        # load_spec
        got_spec = [(r["formula"], int(r["count"])) for r in R["load_spec"]]
        want_spec = [(e + "2", ape // 2) for e in elems]
        if sorted(got_spec) != sorted(want_spec):
            issues.append("load_spec=%s ≠ %s" % (got_spec, want_spec))
        n_mol = sum(c for _f, c in got_spec)
        n_atom = 0
        for f, c in got_spec:
            try:
                n_atom += c * formula_atoms(f)
            except Exception as exc:
                issues.append("load_spec %r 解析失败: %s" % (f, exc))
        if n_mol != want_mol:
            issues.append("load_spec Σcount=%d ≠ %d" % (n_mol, want_mol))
        if n_atom != want_atoms:
            issues.append("load_spec Σatoms=%d ≠ %d" % (n_atom, want_atoms))
        # biome 元数据
        if bio.get("id") != bid:
            issues.append("biome.id=%r ≠ %s" % (bio.get("id"), bid))
        if bio.get("name") != name:
            issues.append("biome.name=%r ≠ %r" % (bio.get("name"), name))
        if set(bio.get("elements") or []) != set(elems):
            issues.append("biome.elements=%r ≠ %r" % (bio.get("elements"), elems))
        if bio.get("L") != L:
            issues.append("biome.L=%r ≠ %d" % (bio.get("L"), L))
        if bio.get("atoms_per_element") != ape:
            issues.append("biome.atoms_per_element=%r ≠ %d"
                          % (bio.get("atoms_per_element"), ape))
        if bio.get("total_atoms") != want_atoms:
            issues.append("biome.total_atoms=%r ≠ %d"
                          % (bio.get("total_atoms"), want_atoms))
        if bio.get("seed") != EXPECT_SEED_BASE + idx:
            issues.append("biome.seed=%r ≠ %d" % (bio.get("seed"), EXPECT_SEED_BASE + idx))
        if R["summary"].get("biome_id") != bid:
            issues.append("summary.biome_id=%r ≠ %s" % (R["summary"].get("biome_id"), bid))
        if issues:
            ck.sub(sid, "%s 投料合规" % bid, "FAIL", "；".join(issues[:10]),
                   {"expected": {"elements": elems, "atoms": want_atoms,
                                 "molecules": want_mol}, "load_spec": got_spec})
        else:
            ck.sub(sid, "%s 投料合规" % bid, "PASS",
                   "L=%d，%d 种元素、每元素 %d 原子；装载 %s；初始 %d 分子/%d 原子；"
                   "cap=40、seed=%d"
                   % (L, len(elems), ape, got_spec, want_mol, want_atoms,
                      EXPECT_SEED_BASE + idx), {"load_spec": got_spec})


# ================================================================ 组 3 质量/元素守恒
def check_group3(ck, ctx):
    ck.begin(3, "质量与元素守恒（终态分子/原子/逐元素/state 汇总）")
    for idx, expected in enumerate(EXPECT_BIOMES):
        bid, name, elems, ape, L = expected
        sid = "3.%d" % (idx + 1)
        R = ctx.results.get(bid)
        S = ctx.states.get(bid)
        if not R or not S:
            miss = []
            if not R:
                miss.append("t65_biome_%s_result.json" % bid)
            if not S:
                miss.append("t65_biome_%s_state.json" % bid)
            missing_files(ck, sid, "%s 质量守恒" % bid, bid, miss)
            continue
        C = comp_stats(R["comp"])
        want_atoms = len(elems) * ape
        want_mol = len(elems) * (ape // 2)
        want_elem = {e: ape for e in elems}
        issues = []
        # 分子数链路：Σcomp -> final_N -> state
        if C["molecules"] != R["summary"].get("final_N"):
            issues.append("Σcomp.count=%d ≠ final_N=%r"
                          % (C["molecules"], R["summary"].get("final_N")))
        if S["sum_counts"] != S["total_molecules"]:
            issues.append("state Σcount=%d ≠ total_molecules=%r"
                          % (S["sum_counts"], S["total_molecules"]))
        if R["summary"].get("final_N") != S["total_molecules"]:
            issues.append("final_N=%r ≠ state.total_molecules=%r"
                          % (R["summary"].get("final_N"), S["total_molecules"]))
        # 原子数链路
        if C["atoms"] != R["summary"].get("final_atoms"):
            issues.append("Σcomp.count*atoms=%d ≠ final_atoms=%r"
                          % (C["atoms"], R["summary"].get("final_atoms")))
        if R["summary"].get("final_atoms") != want_atoms:
            issues.append("final_atoms=%r ≠ 设计总原子数 %d"
                          % (R["summary"].get("final_atoms"), want_atoms))
        if S["sum_atoms"] != S["total_atoms"]:
            issues.append("state Σcount*len(atoms)=%d ≠ total_atoms=%r"
                          % (S["sum_atoms"], S["total_atoms"]))
        if S["total_atoms"] != want_atoms:
            issues.append("state.total_atoms=%r ≠ 设计 %d"
                          % (S["total_atoms"], want_atoms))
        if C["parse_errors"]:
            issues.append("comp 解析错误: %s" % C["parse_errors"][:3])
        # 逐元素
        for e, want in want_elem.items():
            got = C["element_atoms"].get(e, 0)
            if got != want:
                issues.append("终态元素 %s=%d ≠ 投料 %d" % (e, got, want))
        for e in ELEMS:
            if e not in want_elem and C["element_atoms"].get(e, 0) != 0:
                issues.append("终态出现未投料元素 %s=%d"
                              % (e, C["element_atoms"].get(e, 0)))
        for e in elems:
            if S["element_atoms"].get(e, 0) != ape:
                issues.append("state 元素 %s=%d ≠ %d"
                              % (e, S["element_atoms"].get(e, 0), ape))
        # state 组成 == comp
        sc = S.get("comp") or {}
        cc = {f: r["count"] for f, r in R["comp"].items()}
        if sc != cc:
            only_s = {f: sc[f] for f in set(sc) - set(cc)}
            only_c = {f: cc[f] for f in set(cc) - set(sc)}
            diff = {f: {"state": sc[f], "comp": cc[f]}
                    for f in set(sc) & set(cc) if sc[f] != cc[f]}
            issues.append("state 组成 ≠ result 组成: 仅state=%s 仅comp=%s 计数差=%s"
                          % (only_s, only_c, dict(list(diff.items())[:5])))
        v = C["valence_atoms"]
        vsum = sum(v.values())
        if vsum != want_atoms:
            issues.append("Σ价数原子=%d ≠ %d" % (vsum, want_atoms))
        shares = [round(v["v3"] / float(want_atoms), 4),
                  round(v["v2"] / float(want_atoms), 4),
                  round(v["v1"] / float(want_atoms), 4)]
        vals = {"final_N": R["summary"].get("final_N"),
                "final_atoms": R["summary"].get("final_atoms"),
                "design_atoms": want_atoms,
                "element_atoms": {e: C["element_atoms"].get(e, 0) for e in ELEMS},
                "valence_atoms": v, "valence_shares": shares,
                "state_total_molecules": S["total_molecules"],
                "state_total_atoms": S["total_atoms"]}
        if issues:
            ck.sub(sid, "%s 质量/元素守恒" % bid, "FAIL",
                   "；".join(issues[:10]), vals)
        else:
            ck.sub(sid, "%s 质量/元素守恒" % bid, "PASS",
                   "final_N=%s（Σcomp、state 一致）、final_atoms=%s（设计值、逐元素 O/X/C/... 全对）"
                   "价数占比 v3/v2/v1=%s；state 组成与 result 一致"
                   % (R["summary"].get("final_N"), R["summary"].get("final_atoms"),
                      shares), vals)


# ================================================================ 组 4 温度日程
def check_group4(ck, ctx):
    ck.begin(4, "温度日程（1000→25°C 退火 975 + 25°C 浮动 600）")
    for idx, expected in enumerate(EXPECT_BIOMES):
        bid, name, elems, ape, L = expected
        sid = "4.%d" % (idx + 1)
        R = ctx.results.get(bid)
        if not R:
            missing_files(ck, sid, "%s 温度日程" % bid, bid,
                          ["t65_biome_%s_result.json" % bid])
            continue
        cfg = R["config"]
        ts = R["ts"]
        issues = []
        sched = cfg.get("temp_schedule")
        if not isinstance(sched, dict):
            issues.append("config.temp_schedule 缺失或非 dict")
        else:
            for k, v in EXPECT_SCHEDULE.items():
                if sched.get(k) != v:
                    issues.append("temp_schedule.%s=%r ≠ %r"
                                  % (k, sched.get(k), v))
        if not ts:
            issues.append("time_series 为空")
        else:
            if len(ts) != EXPECT_MINUTES:
                issues.append("time_series 行数=%d ≠ %d" % (len(ts), EXPECT_MINUTES))
            if ts[0].get("t") != 0 or ts[0].get("T") != 1000.0:
                issues.append("首行 t=%r T=%r ≠ (0, 1000.0)"
                              % (ts[0].get("t"), ts[0].get("T")))
            max_dt = 0.0
            for i, row in enumerate(ts):
                if row.get("t") != i:
                    issues.append("第 %d 行 t=%r ≠ %d" % (i, row.get("t"), i))
                    break
                d = abs(float(row.get("T")) - EXPECTED_T[i])
                if d > max_dt:
                    max_dt = d
                if d > 1e-6:
                    issues.append("t=%d 行 T=%r ≠ 独立复算 %.9f（|Δ|=%.2e）"
                                  % (i, row.get("T"), EXPECTED_T[i], d))
                    break
            hold = ts[ANNEAL_MINUTES:]
            if hold:
                hmin = min(float(r.get("T")) for r in hold)
                hmax = max(float(r.get("T")) for r in hold)
                fluct = hmax - hmin
                if hmin < HOLD_T_MIN - 1e-6 or hmax > HOLD_T_MAX + 1e-6:
                    issues.append("hold 段 T 超出 [14,36]: min=%.4f max=%.4f"
                                  % (hmin, hmax))
                if fluct < 8.0:
                    issues.append("hold 段波动仅 %.3f°C < 8°C" % fluct)
            else:
                hmin = hmax = fluct = None
            final_T = R["summary"].get("final_T")
            want_final = EXPECTED_T[-1]
            if final_T is None or abs(float(final_T) - want_final) > 0.011:
                issues.append("summary.final_T=%r ≠ 日程末值 %.6f（舍入差 ≤0.01）"
                              % (final_T, want_final))
            if abs(float(ts[-1].get("T")) - want_final) > 1e-6:
                issues.append("time_series 末行 T=%r ≠ %.6f"
                              % (ts[-1].get("T"), want_final))
        vals = {"T0": 1000.0, "T_mid": 25.0, "anneal_minutes": 975,
                "hold_minutes": 600, "hold_T_min": None, "hold_T_max": None,
                "hold_fluct": None, "final_T": R["summary"].get("final_T"),
                "max_abs_dT": max_dt if ts else None}
        if ts and len(ts) >= EXPECT_MINUTES:
            hold = ts[ANNEAL_MINUTES:]
            vals["hold_T_min"] = round(min(float(r.get("T")) for r in hold), 4)
            vals["hold_T_max"] = round(max(float(r.get("T")) for r in hold), 4)
            vals["hold_fluct"] = round(vals["hold_T_max"] - vals["hold_T_min"], 4)
        if issues:
            ck.sub(sid, "%s 温度日程" % bid, "FAIL",
                   "；".join(issues[:10]), vals)
        else:
            ck.sub(sid, "%s 温度日程" % bid, "PASS",
                   "config.temp_schedule 一致；1575 行 T 逐分钟复算一致（max|ΔT|<1e-6）；"
                   "hold 段 %.2f~%.2f°C（波动 %.2f°C）；final_T=%.2f == 日程末值"
                   % (vals["hold_T_min"], vals["hold_T_max"], vals["hold_fluct"],
                      float(vals["final_T"])), vals)


# ================================================================ 组 5 判定自洽
def check_group5(ck, ctx):
    ck.begin(5, "判定自洽（reaction_counts/events_total/抽样事件/cap）")
    for idx, expected in enumerate(EXPECT_BIOMES):
        bid, name, elems, ape, L = expected
        sid = "5.%d" % (idx + 1)
        R = ctx.results.get(bid)
        if not R:
            missing_files(ck, sid, "%s 判定自洽" % bid, bid,
                          ["t65_biome_%s_result.json" % bid])
            continue
        sm = R["summary"]
        ts = R["ts"]
        rc = sm.get("reaction_counts") or {}
        issues = []
        # 类型合法性
        for k, v in rc.items():
            if k not in RC_TYPES:
                issues.append("reaction_counts 未知类型 %r" % k)
            elif not isinstance(v, int) or v < 0:
                issues.append("reaction_counts[%s]=%r 非非负整数" % (k, v))
        total = sum(int(v) for v in rc.values() if isinstance(v, int) and v >= 0)
        # 末行累计
        last = ts[-1] if ts else {}
        cum = {k: int(last.get(k) or 0) for k in RC_TYPES}
        if sum(cum.values()) != total:
            issues.append("末行四类合计=%d ≠ Σreaction_counts=%d"
                          % (sum(cum.values()), total))
        for k in RC_TYPES:
            if cum[k] != int(rc.get(k) or 0):
                issues.append("末行 %s=%d ≠ reaction_counts=%r"
                              % (k, cum.get(k), rc.get(k)))
        # d_* 增量求和
        if ts and all(("d_" + k) in ts[0] for k in RC_TYPES):
            for k in RC_TYPES:
                s = sum(int(r.get("d_" + k) or 0) for r in ts)
                if s != int(rc.get(k) or 0):
                    issues.append("Σd_%s=%d ≠ reaction_counts[%s]=%r"
                                  % (k, s, k, rc.get(k)))
        # events_total / 蓄水池
        ev_total = sm.get("events_total")
        last_ev = last.get("events_total")
        if ev_total != last_ev:
            issues.append("events_total=%r ≠ 末行 events_total=%r"
                          % (ev_total, last_ev))
        ev = R["events"]
        exp_samples = min(int(ev_total or 0), int(ctx.event_limit))
        if ev["n"] != exp_samples:
            issues.append("event_samples 数=%d ≠ min(events_total,%d)=%d"
                          % (ev["n"], ctx.event_limit, exp_samples))
        if ev.get("type_counts"):
            for t_ in ev["type_counts"]:
                if t_ not in RC_TYPES:
                    issues.append("抽样事件未知类型 %r" % t_)
        if not ev.get("skipped"):
            bad = (ev.get("atom_conserv_bad", 0) + ev.get("valence_conserv_bad", 0)
                   + ev.get("parse_bad", 0) + ev.get("empty_products", 0))
            if bad:
                issues.append("抽样事件守恒异常: atom_bad=%d valence_bad=%d "
                              "parse_bad=%d empty=%d"
                              % (ev.get("atom_conserv_bad", 0),
                                 ev.get("valence_conserv_bad", 0),
                                 ev.get("parse_bad", 0),
                                 ev.get("empty_products", 0)))
        # decomp
        if sm.get("decomp_events") != last.get("decomp"):
            issues.append("decomp_events=%r ≠ 末行 decomp=%r"
                          % (sm.get("decomp_events"), last.get("decomp")))
        # cap / max atoms
        cap = R["config"].get("max_reaction_atoms")
        if cap != EXPECT_CAP:
            issues.append("cap=%r ≠ 40" % cap)
        C = comp_stats(R["comp"])
        ts_max = max([int(r.get("max_atoms") or 0) for r in ts] or [0])
        if C["max_atoms"] > EXPECT_CAP:
            issues.append("终态最大原子数=%d > cap 40" % C["max_atoms"])
        if ts_max > EXPECT_CAP:
            issues.append("time_series 最大原子数=%d > cap 40" % ts_max)
        # capped 占比
        capped = int(rc.get("capped") or 0)
        frac = (capped / float(total)) if total else 0.0
        if frac >= 0.05:
            ck.note("%s capped 占比 %.3f%% >5%%（capped=%d / 判定总数=%d）"
                    % (bid, frac * 100.0, capped, total))
        # capped 与末行一致已覆盖
        vals = {"reaction_counts": rc, "total_judgements": total,
                "events_total": ev_total, "event_samples": ev["n"],
                "event_types": ev.get("type_counts"),
                "capped": capped, "capped_frac": round(frac, 6),
                "comp_max_atoms": C["max_atoms"], "ts_max_atoms": ts_max,
                "decomp_events": sm.get("decomp_events")}
        if issues:
            ck.sub(sid, "%s 判定自洽" % bid, "FAIL",
                   "；".join(issues[:10]), vals)
        else:
            ck.sub(sid, "%s 判定自洽" % bid, "PASS",
                   "判定总数=%d（complete=%d/incomplete=%d/none=%d/capped=%d，"
                   "capped 占比 %.3f%%）；events_total=%r、抽样 %d 条 0 违规；"
                   "max atoms=%d/%d ≤40；decomp=%r"
                   % (total, cum["complete"], cum["incomplete"], cum["none"],
                      cum["capped"], frac * 100.0, ev_total, ev["n"],
                      C["max_atoms"], ts_max, sm.get("decomp_events")), vals)


# ================================================================ 组 6 快照
def check_group6(ck, ctx):
    ck.begin(6, "快照（snapshots 数量/时间点/每帧点数）")
    for idx, expected in enumerate(EXPECT_BIOMES):
        bid, name, elems, ape, L = expected
        sid = "6.%d" % (idx + 1)
        R = ctx.results.get(bid)
        if not R:
            missing_files(ck, sid, "%s 快照" % bid, bid,
                          ["t65_biome_%s_result.json" % bid])
            continue
        snaps = R["snaps"]
        issues = []
        want_t = EXPECT_SNAP
        if len(snaps) != len(want_t):
            issues.append("快照数=%d ≠ snap_minutes 数=%d" % (len(snaps), len(want_t)))
        gt = [s.get("t") for s in snaps]
        if gt != want_t:
            issues.append("快照时间点=%s ≠ %s" % (gt, want_t))
        empty = [s.get("t") for s in snaps if int(s.get("n") or 0) <= 0]
        if empty:
            issues.append("空快照时间点: %s" % empty[:10])
        shape_bad = sum(int(s.get("shape_bad") or 0) for s in snaps)
        if shape_bad:
            issues.append("采样点前 50 个形状异常计数=%d（期望 [x,y,color]）" % shape_bad)
        pts = [int(s.get("n") or 0) for s in snaps]
        vals = {"snapshots": len(snaps), "expected": len(want_t),
                "points_min": min(pts) if pts else None,
                "points_max": max(pts) if pts else None,
                "points_total": sum(pts), "time_points": gt}
        if issues:
            ck.sub(sid, "%s 快照" % bid, "FAIL",
                   "；".join(issues[:8]), vals)
        else:
            ck.sub(sid, "%s 快照" % bid, "PASS",
                   "%d 帧（时间点与 snap_minutes 完全一致），每帧点数 %d~%d，"
                   "合计 %d 点" % (len(snaps), min(pts), max(pts), sum(pts)), vals)


# ================================================================ 组 7 终态表
def check_group7(ck, ctx):
    ck.begin(7, "终态表 sanity（final_composition / top structures）")
    for idx, expected in enumerate(EXPECT_BIOMES):
        bid, name, elems, ape, L = expected
        sid = "7.%d" % (idx + 1)
        R = ctx.results.get(bid)
        if not R:
            missing_files(ck, sid, "%s 终态表" % bid, bid,
                          ["t65_biome_%s_result.json" % bid])
            continue
        C = comp_stats(R["comp"])
        issues = []
        if not R["comp"]:
            issues.append("final_composition 为空")
        if C["atoms_none"]:
            issues.append("atoms 字段为 None: %s" % C["atoms_none"][:5])
        if C["atoms_field_mismatch"]:
            issues.append("atoms 字段与公式不符: %s"
                          % C["atoms_field_mismatch"][:3])
        bad_tops = {}
        for f, info in R["top"].items():
            iss = validate_structure(f, info["atoms"], info["edges"], cap=EXPECT_CAP)
            if iss:
                bad_tops[f] = iss[:4]
            if f not in R["comp"]:
                issues.append("top 结构 %r 不在 final_composition 中" % f)
        if bad_tops:
            issues.append("top 结构非法: %s" % bad_tops)
        vals = {"n_comp": len(R["comp"]), "n_top": len(R["top"]),
                "atoms_mismatch": len(C["atoms_field_mismatch"]),
                "atoms_none": len(C["atoms_none"]),
                "invalid_tops": len(bad_tops),
                "comp_max_atoms": C["max_atoms"]}
        if issues:
            ck.sub(sid, "%s 终态表" % bid, "FAIL",
                   "；".join(issues[:8]), vals)
        else:
            ck.sub(sid, "%s 终态表" % bid, "PASS",
                   "final_composition %d 个分子式（atoms 字段全一致、0 个 None）；"
                   "top 结构 %d 个全部合法（价数填满/无自环/重复边/越界），最大 atoms=%d"
                   % (len(R["comp"]), len(R["top"]), C["max_atoms"]), vals)


# ================================================================ 组 8 state 一致性
def check_group8(ck, ctx):
    ck.begin(8, "state 与 result 一致性（总数/组成/逐元素/结构合法性）")
    for idx, expected in enumerate(EXPECT_BIOMES):
        bid, name, elems, ape, L = expected
        sid = "8.%d" % (idx + 1)
        R = ctx.results.get(bid)
        S = ctx.states.get(bid)
        if not R or not S:
            miss = []
            if not R:
                miss.append("t65_biome_%s_result.json" % bid)
            if not S:
                miss.append("t65_biome_%s_state.json" % bid)
            missing_files(ck, sid, "%s state 一致性" % bid, bid, miss)
            continue
        issues = []
        if S.get("biome_id") != bid:
            issues.append("state.biome_id=%r ≠ %s" % (S.get("biome_id"), bid))
        if S["total_molecules"] != R["summary"].get("final_N"):
            issues.append("state.total_molecules=%r ≠ final_N=%r"
                          % (S["total_molecules"], R["summary"].get("final_N")))
        if S["total_atoms"] != R["summary"].get("final_atoms"):
            issues.append("state.total_atoms=%r ≠ final_atoms=%r"
                          % (S["total_atoms"], R["summary"].get("final_atoms")))
        if S["sum_counts"] != S["total_molecules"]:
            issues.append("Σstate.count=%d ≠ total_molecules" % S["sum_counts"])
        if S["sum_atoms"] != S["total_atoms"]:
            issues.append("Σstate.count*atoms=%d ≠ total_atoms" % S["sum_atoms"])
        if S["distinct_structures"] != len(S["molecules"]):
            issues.append("distinct_structures=%r ≠ molecules 数=%d"
                          % (S["distinct_structures"], len(S["molecules"])))
        cc = {f: r["count"] for f, r in R["comp"].items()}
        if S["comp"] != cc:
            issues.append("state 组成 ≠ result final_composition")
        for e in elems:
            if S["element_atoms"].get(e, 0) != ape:
                issues.append("state 元素 %s=%d ≠ %d"
                              % (e, S["element_atoms"].get(e, 0), ape))
        bad = {}
        for m in S["molecules"]:
            iss = validate_structure(m["formula"], m["atoms"], m["edges"],
                                     cap=EXPECT_CAP)
            if iss:
                bad[m["formula"]] = iss[:4]
        if bad:
            issues.append("state 结构非法: %s" % bad)
        vals = {"state_molecules": S["total_molecules"],
                "state_atoms": S["total_atoms"],
                "structures": len(S["molecules"]),
                "distinct_formulas": S["distinct_formulas"],
                "invalid_structures": len(bad)}
        if issues:
            ck.sub(sid, "%s state 一致性" % bid, "FAIL",
                   "；".join(issues[:8]), vals)
        else:
            ck.sub(sid, "%s state 一致性" % bid, "PASS",
                   "state %d 分子/%d 原子、%d 种结构（distinct_formulas=%r），"
                   "组成/逐元素与 result 一致，结构全部合法"
                   % (S["total_molecules"], S["total_atoms"],
                      len(S["molecules"]), S["distinct_formulas"]), vals)


# ================================================================ 组 9 对照
def check_group9(ck, ctx):
    ck.begin(9, "无化学对照（t65_control_C01.json）")
    ctl = ctx.control
    if not ctl:
        ck.sub("9.0", "对照文件", "PENDING",
               "t65_control_C01.json 缺失（待生成/待补验）")
        return
    cfg = ctl["config"]
    stats = ctl["stats"]
    by = ctl["by_size"]
    # 9.1 化学关闭
    if cfg.get("chemical_reactions") is False:
        ck.sub("9.1", "对照组化学开关关闭", "PASS",
               "config.chemical_reactions=False")
    else:
        ck.sub("9.1", "对照组化学开关关闭", "FAIL",
               "config.chemical_reactions=%r ≠ False"
               % cfg.get("chemical_reactions"))
    # 9.2 装载
    issues = []
    if cfg.get("n_particles") != EXPECT_CONTROL_MOLECULES:
        issues.append("n_particles=%r ≠ %d"
                      % (cfg.get("n_particles"), EXPECT_CONTROL_MOLECULES))
    if cfg.get("L") != EXPECT_CONTROL_L:
        issues.append("L=%r ≠ %d" % (cfg.get("L"), EXPECT_CONTROL_L))
    if cfg.get("minutes") != EXPECT_CONTROL_MINUTES:
        issues.append("minutes=%r ≠ %d" % (cfg.get("minutes"), EXPECT_CONTROL_MINUTES))
    b01 = ctx.biome("C01") or {}
    spec = [(r.get("formula"), int(r.get("count") or 0))
            for r in (cfg.get("load_spec") or [])]
    want = [(r["formula"], int(r["count"])) for r in (b01.get("load_spec") or [])]
    if sorted(spec) != sorted(want):
        issues.append("load_spec=%s ≠ C01 投料 %s" % (spec, want))
    if sum(c for _f, c in spec) != EXPECT_CONTROL_MOLECULES:
        issues.append("Σload count=%d ≠ %d"
                      % (sum(c for _f, c in spec), EXPECT_CONTROL_MOLECULES))
    vals = {"n_particles": cfg.get("n_particles"), "L": cfg.get("L"),
            "minutes": cfg.get("minutes"), "load_spec": spec}
    if issues:
        ck.sub("9.2", "对照组装载与 C01 投料一致", "FAIL",
               "；".join(issues[:8]), vals)
    else:
        ck.sub("9.2", "对照组装载与 C01 投料一致", "PASS",
               "7000 分子（O2/P2/X2/W2 各 1750，14000 原子）、L=18000、500 分钟", vals)
    # 9.3 stats.n
    if stats.get("n") == EXPECT_CONTROL_MOLECULES:
        ck.sub("9.3", "stats.n == 7000", "PASS", "stats.n=%r" % stats.get("n"))
    else:
        ck.sub("9.3", "stats.n == 7000", "FAIL",
               "stats.n=%r ≠ %d" % (stats.get("n"), EXPECT_CONTROL_MOLECULES))
    # 9.4 min ≥500
    mn = stats.get("min")
    if isinstance(mn, (int, float)) and mn >= 500:
        ck.sub("9.4", "stats.min ≥ 500", "PASS", "stats.min=%.1f" % mn)
    else:
        ck.sub("9.4", "stats.min ≥ 500", "FAIL", "stats.min=%r < 500" % (mn,))
    # 9.5 fraction_ge_500 ≥ 0.9999
    fr = stats.get("fraction_ge_500")
    if isinstance(fr, (int, float)) and fr >= 0.9999:
        ck.sub("9.5", "fraction_ge_500 ≥ 0.9999", "PASS",
               "fraction_ge_500=%r" % fr)
    else:
        ck.sub("9.5", "fraction_ge_500 ≥ 0.9999", "FAIL",
               "fraction_ge_500=%r < 0.9999" % (fr,))
    # 9.6 by_size 每组 min≥500
    issues = []
    n_sum = 0
    details = {}
    for k, r in by.items():
        n_sum += int(r.get("n") or 0)
        details[str(k)] = {"n": r.get("n"), "min": r.get("min")}
        if not isinstance(r.get("min"), (int, float)) or r.get("min") < 500:
            issues.append("size=%s min=%r < 500" % (k, r.get("min")))
    if n_sum != EXPECT_CONTROL_MOLECULES:
        issues.append("Σby_size.n=%d ≠ 7000" % n_sum)
    if issues:
        ck.sub("9.6", "by_size 每组 min ≥ 500 且分组总数=7000", "FAIL",
               "；".join(issues[:8]), {"by_size": details})
    else:
        ck.sub("9.6", "by_size 每组 min ≥ 500 且分组总数=7000", "PASS",
               "%d 个大小组，每组 min ≥500（全部 ≥500），Σn=%d"
               % (len(by), n_sum), {"by_size": details})
    # 9.7 INFO
    ck.sub("9.7", "对照路径统计概览", "INFO",
           "min=%.1f p1=%.1f median=%.1f p95=%.1f max=%.1f mean=%.1f "
           "fraction_ge_500=%r"
           % (float(stats.get("min") or 0), float(stats.get("p1") or 0),
              float(stats.get("median") or 0), float(stats.get("p95") or 0),
              float(stats.get("max") or 0), float(stats.get("mean") or 0),
              stats.get("fraction_ge_500")),
           {"stats": stats})


# ================================================================ 组 10 index
def check_group10(ck, ctx):
    ck.begin(10, "index 与 result 一致性（t65_biome_index.json）")
    I = ctx.index
    if not I:
        ck.sub("10.0", "index 文件", "PENDING", "t65_biome_index.json 缺失")
        return
    issues = []
    rows = I["biomes"]
    ids = [r.get("id") for r in rows]
    exp_ids = [b[0] for b in EXPECT_BIOMES]
    if ids != exp_ids:
        issues.append("index id=%s ≠ %s" % (ids, exp_ids))
    if I.get("experiment") != "T65 生态群系":
        issues.append("index.experiment=%r ≠ 'T65 生态群系'" % I.get("experiment"))
    if I.get("schedule") != EXPECT_SCHEDULE:
        issues.append("index.schedule ≠ 预期日程")
    per = {}
    pending_rows = []
    stale_index = []
    for idx, expected in enumerate(EXPECT_BIOMES):
        bid = expected[0]
        r = rows[idx] if idx < len(rows) else {}
        R = ctx.results.get(bid)
        per[bid] = {"status": r.get("status"), "final_N": r.get("final_N"),
                    "final_atoms": r.get("final_atoms"), "final_T": r.get("final_T")}
        want_file = "t65_biome_%s_result.json" % bid
        if not R:
            pending_rows.append(bid)
            continue
        if r.get("status") != "done" and r.get("file") is None \
                and r.get("final_N") is None:
            stale_index.append(bid)
            continue
        if r.get("file") != want_file:
            issues.append("%s file=%r ≠ %s" % (bid, r.get("file"), want_file))
        if r.get("status") != "done":
            issues.append("%s index status=%r ≠ done" % (bid, r.get("status")))
        if r.get("final_N") != R["summary"].get("final_N"):
            issues.append("%s index.final_N=%r ≠ result=%r"
                          % (bid, r.get("final_N"), R["summary"].get("final_N")))
        if r.get("final_atoms") != R["summary"].get("final_atoms"):
            issues.append("%s index.final_atoms=%r ≠ result=%r"
                          % (bid, r.get("final_atoms"),
                             R["summary"].get("final_atoms")))
        if r.get("final_T") != R["summary"].get("final_T"):
            issues.append("%s index.final_T=%r ≠ result=%r"
                          % (bid, r.get("final_T"), R["summary"].get("final_T")))
        irc = r.get("reaction_counts") or {}
        src = R["summary"].get("reaction_counts") or {}
        for k in RC_TYPES:
            if int(irc.get(k) or 0) != int(src.get(k) or 0):
                issues.append("%s index.rc[%s]=%r ≠ result=%r"
                              % (bid, k, irc.get(k), src.get(k)))
                break
    pending_ids = list(pending_rows)
    stale_ids = list(stale_index)
    if issues:
        ck.sub("10.1", "index 10 行完成状态与 result 一致", "FAIL",
               "；".join(issues[:10]), {"rows": per})
    elif pending_ids or stale_ids:
        ck.sub("10.1", "index 10 行完成状态与 result 一致", "PENDING",
               "等待 result/index 刷新: result 缺失=%s；index 未刷新=%s"
               % (pending_ids, stale_ids), {"rows": per})
    else:
        ck.sub("10.1", "index 10 行完成状态与 result 一致", "PASS",
               "10 行均 done，final_N/final_atoms/final_T/reaction_counts 与 result 一致",
               {"rows": per})
    # 10.2 index 汇总与设计一致（未生成 result 的 pending 行不参与比较）
    issues = []
    stale = []
    for r in rows:
        b = ctx.biome(r.get("id"))
        if not b:
            issues.append("%s 不在设计" % r.get("id"))
            continue
        if ctx.results.get(r.get("id")) is None:
            continue
        if r.get("total_atoms") is None or r.get("L") is None \
                or r.get("elements") is None:
            stale.append(r.get("id"))
            continue
        if r.get("total_atoms") != b["total_atoms"]:
            issues.append("%s total_atoms=%r ≠ 设计=%r"
                          % (r.get("id"), r.get("total_atoms"), b["total_atoms"]))
        if r.get("L") != b["L"]:
            issues.append("%s L=%r ≠ 设计=%r" % (r.get("id"), r.get("L"), b["L"]))
        if sorted(r.get("elements") or []) != sorted(b["elements"]):
            issues.append("%s elements=%r ≠ 设计=%r"
                          % (r.get("id"), r.get("elements"), b["elements"]))
    if issues:
        ck.sub("10.2", "index 元数据与设计一致", "FAIL", "；".join(issues[:10]))
    elif pending_rows or stale:
        ck.sub("10.2", "index 元数据与设计一致", "PENDING",
               "等待 result/index 刷新: %s" % (pending_rows + stale))
    else:
        ck.sub("10.2", "index 元数据与设计一致", "PASS",
               "10 行 elements/L/total_atoms 与 t65_biomes.json 一致")


# ================================================================ 组 11 输入文件
def check_group11(ck, ctx, paths):
    ck.begin(11, "输入文件 SHA256（10 result + 10 state + design + index + control）")
    inputs = {}
    missing = []
    for key, p in paths.items():
        m = file_meta(p)
        inputs[key] = m
        if not m.get("exists"):
            missing.append(key)
    if missing:
        ck.sub("11.1", "全部输入文件存在", "PENDING",
               "缺失: %s（待生成/待补验）" % ", ".join(missing),
               {"missing": missing})
    else:
        ck.sub("11.1", "全部输入文件存在", "PASS",
               "%d 个输入文件全部存在" % len(inputs))
    res_keys = [k for k in inputs if k.startswith("result_")]
    res_exist = [k for k in res_keys if inputs[k].get("exists")]
    sha_ok = all(inputs[k].get("sha256") and len(inputs[k]["sha256"]) == 64
                 for k in res_exist) if res_exist else False
    if len(res_exist) < 10:
        ck.sub("11.2", "10 个 result 文件 SHA256 已记录", "PENDING",
               "已记录 %d/10 个 result SHA256，等待 %d 个 result 文件生成"
               % (len(res_exist), 10 - len(res_exist)))
    elif sha_ok:
        ck.sub("11.2", "10 个 result 文件 SHA256 已记录", "PASS",
               "10 个 result SHA256（64 位 hex）、共 %d 个输入文件（含 state/design/"
               "index/control）" % len(inputs),
               {"sha256": {k: inputs[k]["sha256"] for k in sorted(inputs)}})
    else:
        ck.sub("11.2", "10 个 result 文件 SHA256 已记录", "FAIL",
               "10 个 result 均存在但 SHA256 不完整")
    analysis = os.path.join(BASE, "t65_analysis.json")
    if os.path.isfile(analysis):
        m = file_meta(analysis)
        ck.sub("11.3", "t65_analysis.json（可选）", "INFO",
               "已生成，size=%d bytes，sha256=%s"
               % (m.get("size_bytes", 0), m.get("sha256", "")[:16]),
               {"meta": m})
    else:
        ck.sub("11.3", "t65_analysis.json（可选）", "INFO", "未生成（可选输入，不影响结论）")

    # 11.4 INFO：C10 与 T64 B11 确定性复现旁证（条件与种子相同）
    t64_b11 = os.path.join(BASE, "t64_biome_B11_result.json")
    R10 = ctx.results.get("C10")
    if R10 and os.path.isfile(t64_b11):
        try:
            with open(t64_b11, encoding="utf-8") as fh:
                old = json.load(fh)
            old_comp = {}
            for f, r in (old.get("final_composition") or {}).items():
                c = int((r or {}).get("count", 0))
                if c > 0:
                    old_comp[f] = c
            new_comp = {f: r["count"] for f, r in R10["comp"].items()}
            forms = sorted(set(old_comp) | set(new_comp))
            a = [old_comp.get(f, 0) for f in forms]
            b = [new_comp.get(f, 0) for f in forms]
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(y * y for y in b))
            cos = (sum(x * y for x, y in zip(a, b)) / (na * nb)) \
                if na and nb else None
            old_seed = (old.get("config") or {}).get("seed")
            new_seed = R10["config"].get("seed")
            old_n = (old.get("summary") or {}).get("final_N")
            new_n = R10["summary"].get("final_N")
            same = (old_seed == new_seed and old_n == new_n and
                    old_comp == new_comp)
            ck.sub("11.4", "C10 与 T64 B11 确定性复现旁证（同条件同种子）", "INFO",
                   "T64 B11 seed=%r final_N=%r 公式数=%d；C10 seed=%r final_N=%r "
                   "公式数=%d；组成余弦=%.9f；完全一致=%s"
                   % (old_seed, old_n, len(old_comp), new_seed, new_n,
                      len(new_comp), cos if cos is not None else -1.0, same),
                   {"seed_t64": old_seed, "seed_c10": new_seed,
                    "final_N_t64": old_n, "final_N_c10": new_n,
                    "n_formula_t64": len(old_comp), "n_formula_c10": len(new_comp),
                    "cosine": cos, "identical": same})
        except Exception as exc:
            ck.sub("11.4", "C10 与 T64 B11 确定性复现旁证（同条件同种子）", "INFO",
                   "对比失败: %s" % exc)
    else:
        ck.sub("11.4", "C10 与 T64 B11 确定性复现旁证（同条件同种子）", "INFO",
               "T64 B11 result 或 C10 result 缺失，跳过")
    return inputs


# ================================================================ 主流程
def build_paths(args):
    rd = args.results_dir
    paths = {"design": args.design,
             "index": args.index,
             "control": args.control}
    for idx, expected in enumerate(EXPECT_BIOMES):
        bid = expected[0]
        paths["result_%s" % bid] = os.path.join(
            rd, args.result_pattern % {"id": bid})
        paths["state_%s" % bid] = os.path.join(
            rd, args.state_pattern % {"id": bid})
    return paths


def main(argv=None):
    ap = argparse.ArgumentParser(description="T65 生态群系独立验证")
    ap.add_argument("--design", default=os.path.join(BASE, "t65_biomes.json"))
    ap.add_argument("--index", default=os.path.join(BASE, "t65_biome_index.json"))
    ap.add_argument("--control", default=os.path.join(BASE, "t65_control_C01.json"))
    ap.add_argument("--results-dir", default=BASE)
    ap.add_argument("--result-pattern", default="t65_biome_%(id)s_result.json")
    ap.add_argument("--state-pattern", default="t65_biome_%(id)s_state.json")
    ap.add_argument("--out", default=os.path.join(BASE, "t65_verify.json"))
    ap.add_argument("--cap", type=int, default=EXPECT_CAP)
    ap.add_argument("--event-limit", type=int, default=EXPECT_EVENT_LIMIT)
    ap.add_argument("--control-min", type=float, default=500.0)
    ap.add_argument("--control-frac", type=float, default=0.9999)
    ap.add_argument("--scan-cap", type=int, default=SAMPLE_CAP)
    ap.add_argument("--no-events-scan", action="store_true",
                    help="跳过抽样事件逐条守恒扫描（更快）")
    args = ap.parse_args(argv)

    t_begin = datetime.now()
    print("T65 生态群系独立验证开始", iso_now())
    print("BASE =", BASE)
    paths = build_paths(args)
    print("  design     %s" % paths["design"])
    print("  index      %s" % paths["index"])
    print("  control    %s" % paths["control"])

    design = load_design(paths["design"])
    index = load_index(paths["index"])
    control = load_control(paths["control"])
    results = {}
    states = {}
    for idx, expected in enumerate(EXPECT_BIOMES):
        bid = expected[0]
        results[bid] = load_biome_result(
            paths["result_%s" % bid], scan_events=not args.no_events_scan,
            scan_cap=args.scan_cap)
        states[bid] = load_state(paths["state_%s" % bid])
        flag = "OK " if results[bid] else "---"
        flag2 = "OK " if states[bid] else "---"
        print("  %s result=%s state=%s  %s" % (bid, flag, flag2,
              paths["result_%s" % bid]))
    t_load = (datetime.now() - t_begin).total_seconds()
    print("数据加载完成，耗时 %.1fs" % t_load)

    ctx = Ctx(design, results, states, control, index)
    ck = Checker()
    check_group1(ck, ctx)
    check_group2(ck, ctx)
    check_group3(ck, ctx)
    check_group4(ck, ctx)
    check_group5(ck, ctx)
    check_group6(ck, ctx)
    check_group7(ck, ctx)
    check_group8(ck, ctx)
    check_group9(ck, ctx)
    check_group10(ck, ctx)
    inputs = check_group11(ck, ctx, paths)
    ck.finalize()

    # 汇总
    counts = collections.Counter()
    pending_ids = []
    for g in ck.groups:
        for s in g["subchecks"]:
            counts[s["status"]] += 1
            if s["status"] == "PENDING":
                pending_ids.append(s["id"])
    if counts["FAIL"] > 0:
        overall = "FAIL"
    elif counts["PENDING"] > 0:
        overall = "INCOMPLETE"
    elif counts["SKIP"] > 0 and counts["PASS"] == 0:
        overall = "INCOMPLETE"
    else:
        overall = "PASS"
    out = {
        "script": "t65_verify.py",
        "generated_at": iso_now(),
        "base": BASE,
        "experiment": "T65 生态群系（10 群系 C01~C10，双原子单质投料，1000→25°C 退火 975min + 浮动 600min）",
        "inputs": inputs,
        "tolerances": {
            "T_recompute_abs": 1e-6,
            "final_T_rounding": 0.011,
            "hold_T_range": [HOLD_T_MIN, HOLD_T_MAX],
            "hold_fluct_min": 8.0,
            "control_min": args.control_min,
            "control_fraction_ge_500": args.control_frac,
            "capped_note_threshold": 0.05,
            "scan_cap": args.scan_cap,
            "event_limit": ctx.event_limit,
        },
        "groups": ck.groups,
        "summary": {"PASS": counts["PASS"], "FAIL": counts["FAIL"],
                    "PENDING": counts["PENDING"], "SKIP": counts["SKIP"],
                    "INFO": counts["INFO"]},
        "pending": pending_ids,
        "notes": ck.notes,
        "overall": overall,
        "elapsed_s": round((datetime.now() - t_begin).total_seconds(), 1),
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(jsafe(out), fh, ensure_ascii=False, indent=1)

    # 控制台输出
    print()
    for g in ck.groups:
        print("[%d] %s —— %s" % (g["id"], g["name"], g["status"]))
        for s in g["subchecks"]:
            print("    %-6s %s: %s —— %s"
                  % (s["id"], s["name"], s["status"], s["detail"]))
    print()
    print("汇总: PASS=%d FAIL=%d PENDING=%d SKIP=%d INFO=%d"
          % (counts["PASS"], counts["FAIL"], counts["PENDING"],
             counts["SKIP"], counts["INFO"]))
    print("overall:", overall)
    if ck.notes:
        print("NOTE:")
        for n in ck.notes:
            print("  -", n)
    if pending_ids:
        print("待补验（PENDING）项:", ", ".join(pending_ids))
    print("输出:", args.out, "（耗时 %.1fs）" % out["elapsed_s"])
    return 0 if overall == "PASS" else (1 if overall == "FAIL" else 2)


if __name__ == "__main__":
    sys.exit(main())
