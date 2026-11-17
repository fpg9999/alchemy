# -*- coding: utf-8 -*-
"""t63_verify.py —— T63 四阶段独立验证脚本（只读结果 JSON，不修改实验文件）

T63 = 29 种纯聚素（O/X/C，9002 分子 / 38,532 原子）在 L=30000 退火
       → 加 8000 个 F2（16,000 F）重热退火
       → 加 8000 个 A2（16,000 A）重热退火
       → 加 8000 个 K2（16,000 K）重热退火。

独立实现（不 import pot_all / natural_engine / t55_kinetic_env / t63_staged），
自己实现分子式解析、价数表、结构合法性检查，避免与被验证代码共享逻辑。

验证 7 类检查：
  1 投料（stage1 29 种/9002 分子/38532 原子、仅 O/X/C；三次各 8000 分子/16000 原子）
  2 跨阶段质量与元素守恒（逐阶段初始 = 上阶段 state + 投放；终态逐元素 delta=0 等）
  3 价数守恒（F→1 价、A→2 价、K→3 价；逐阶段 delta=0）
  4 无化学对照（stats.min ≥500、fraction_ge_500 ≥0.9999、by_size min ≥500、装载一致）
  5 判定自洽（四类计数、累计一致、capped <1%、events_total/蓄水池、抽样事件守恒、max atoms ≤cap）
  6 终态表 sanity（final_composition.atoms 与公式一致、top 结构合法）
  7 state 与 result 一致性（总数/组成/元素/结构合法性）

输出 t63_verify.json：groups -> subchecks（逐项 PASS/FAIL/SKIP/INFO/PENDING + 实测值）、
summary（计数）、inputs（含 SHA256）、overall（PASS / FAIL / INCOMPLETE）。

用法（默认读脚本同目录 t63_*）：
  python t63_verify.py
"""
import argparse
import collections
import hashlib
import json
import os
import sys
import traceback
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

EXPECT_S1 = {"species": 29, "molecules": 9002, "atoms": 38532,
             "elements": ["O", "X", "C"]}
EXPECT_ADD = [
    {"stage": 2, "element": "F", "formula": "F2", "name": "焰单质",
     "molecules": 8000, "atoms": 16000},
    {"stage": 3, "element": "A", "formula": "A2", "name": "气单质",
     "molecules": 8000, "atoms": 16000},
    {"stage": 4, "element": "K", "formula": "K2", "name": "沌单质",
     "molecules": 8000, "atoms": 16000},
]
SAMPLE_CAP = 50000          # 任务要求抽样检查 ≤50,000 条即可
STAGES = (1, 2, 3, 4)


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


def dict_diff(actual, expected, keys):
    out = {}
    for k in keys:
        a = None if actual is None else actual.get(k)
        e = None if expected is None else expected.get(k)
        if a != e:
            out[k] = {"actual": a, "expected": e}
    return out


# ---------------------------------------------------------------- 检查收集器
class Checker:
    def __init__(self):
        self.groups = []
        self._cur = None

    def begin(self, gid, name):
        self._cur = {"id": gid, "name": name, "subchecks": []}
        self.groups.append(self._cur)

    def sub(self, sid, name, status, detail, values=None):
        rec = {"id": sid, "name": name, "status": status, "detail": detail}
        if values is not None:
            rec["values"] = jsafe(values)
        self._cur["subchecks"].append(rec)

    def skip_rest(self, reason):
        self.sub("", "整组", "SKIP", reason)

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
    st = {"n": n_total, "scanned": 0, "type_counts": {}, "product_len_hist": {},
          "atom_conserv_bad": 0, "valence_conserv_bad": 0, "parse_bad": 0,
          "empty_products": 0, "bad_examples": [], "product_lens": []}
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
    st["product_lens"] = plen
    return st


def load_result_compact(path, scan_events=True, scan_cap=SAMPLE_CAP):
    meta = file_meta(path)
    if not meta["exists"]:
        return None
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    cfg = d.get("config") or {}
    sm = d.get("summary") or {}
    R = {"meta": meta,
         "stage": d.get("stage", cfg.get("stage")),
         "config": {k: cfg.get(k) for k in (
             "initial_particles", "initial_atoms", "seed_initial_count",
             "max_reaction_atoms", "minutes", "T0", "T_end", "L",
             "area_model", "experiment")},
         "load_spec": [{"tag": r.get("tag"), "formula": r.get("formula"),
                        "count": r.get("count")}
                       for r in (cfg.get("load_spec") or [])],
         "summary": {k: sm.get(k) for k in (
             "final_N", "final_atoms", "events_total", "decomp_events",
             "reaction_counts", "final_T", "runtime_s")},
         "load_summary": d.get("load_summary")}
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
    ev = d.get("event_samples") or []
    R["events"] = analyze_events(ev, scan_cap) if scan_events else {
        "n": len(ev), "skipped": True}
    del d, ev
    return R


def load_state_compact(path):
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


def load_control_compact(path):
    meta = file_meta(path)
    if not meta["exists"]:
        return None
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    R = {"meta": meta, "config": d.get("config") or {},
         "stats": d.get("stats") or {}, "by_size": d.get("by_size") or {},
         "runtime_s": d.get("runtime_s")}
    del d
    return R


# ---------------------------------------------------------------- 统计/校验
def batch_stats(rows):
    """从 loads.stage1.species 独立复算投料统计。"""
    out = {"n_species": len(rows), "molecules": 0, "atoms": 0,
           "element_atoms": {e: 0 for e in ELEMS},
           "valence_atoms": {"v3": 0, "v2": 0, "v1": 0},
           "issues": [], "formulas": [], "size_counts": {}}
    size_counts = collections.Counter()
    seen = set()
    for idx, r in enumerate(rows):
        f = r.get("formula")
        try:
            p = parse_formula(f)
        except Exception as exc:
            if len(out["issues"]) < 8:
                out["issues"].append("第%d行 formula=%r 无法解析: %s" % (idx, f, exc))
            continue
        if f in seen:
            out["issues"].append("分子式重复: %r" % f)
        seen.add(f)
        try:
            c = int(r.get("count"))
        except Exception:
            out["issues"].append("第%d行 count=%r 非整数" % (idx, r.get("count")))
            continue
        if c <= 0:
            out["issues"].append("第%d行 count=%r ≤0" % (idx, c))
            continue
        na = sum(p.values())
        at_field = r.get("atoms")
        if at_field is not None and int(at_field) != na:
            out["issues"].append("第%d行 %s atoms 字段=%r 但公式为 %d"
                                 % (idx, f, at_field, na))
        out["formulas"].append(f)
        out["molecules"] += c
        out["atoms"] += c * na
        size_counts[na] += c
        for e, k in p.items():
            out["element_atoms"][e] += k * c
        v = formula_valence(f)
        for k in ("v3", "v2", "v1"):
            out["valence_atoms"][k] += v[k] * c
    out["size_counts"] = {str(k): int(v) for k, v in sorted(size_counts.items())}
    return out


def comp_stats(comp):
    out = {"n_formula": len(comp), "molecules": 0, "atoms": 0,
           "element_atoms": {e: 0 for e in ELEMS},
           "valence_atoms": {"v3": 0, "v2": 0, "v1": 0},
           "atoms_field_mismatch": [], "atoms_none": [],
           "parse_errors": [], "max_atoms": 0, "count_ge39": 0}
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
        if na >= 39:
            out["count_ge39"] += 1
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


def state_match(state, comp, summary):
    issues = []
    vals = {"state_total_molecules": state["total_molecules"],
            "state_total_atoms": state["total_atoms"],
            "sum_counts": state["sum_counts"], "sum_atoms": state["sum_atoms"]}
    if state["sum_counts"] != state["total_molecules"]:
        issues.append("Σmolecules.count=%d ≠ total_molecules=%r"
                      % (state["sum_counts"], state["total_molecules"]))
    if state["sum_atoms"] != state["total_atoms"]:
        issues.append("Σcount*len(atoms)=%d ≠ total_atoms=%r"
                      % (state["sum_atoms"], state["total_atoms"]))
    if state["total_molecules"] != summary.get("final_N"):
        issues.append("total_molecules=%r ≠ summary.final_N=%r"
                      % (state["total_molecules"], summary.get("final_N")))
    if state["total_atoms"] != summary.get("final_atoms"):
        issues.append("total_atoms=%r ≠ summary.final_atoms=%r"
                      % (state["total_atoms"], summary.get("final_atoms")))
    sc = state.get("comp") or {}
    cc = {f: r["count"] for f, r in comp.items()}
    if dict(sc) != cc:
        only_s = {f: sc[f] for f in set(sc) - set(cc)}
        only_c = {f: cc[f] for f in set(cc) - set(sc)}
        diff = {f: {"state": sc[f], "comp": cc[f]}
                for f in set(sc) & set(cc) if sc[f] != cc[f]}
        issues.append("组成不同: 仅state=%s 仅comp=%s 计数差=%s"
                      % (only_s, only_c, dict(list(diff.items())[:8])))
    return ("FAIL" if issues else "PASS",
            "state 总数/组成与结果一致" if not issues else "；".join(issues),
            vals)


# ---------------------------------------------------------------- 组状态工具
def status_of(issues, vals):
    if issues:
        return "FAIL"
    pending = [t for t, v in vals.items() if isinstance(v, dict) and v.get("pending")]
    return "PENDING" if pending else "PASS"


def detail_of(parts, issues, vals):
    base = "；".join([p for p in parts if p])
    if issues:
        base = (base + "；" if base else "") + "异常: " + "；".join(issues)
    pend = [t for t, v in vals.items() if isinstance(v, dict) and v.get("pending")]
    if pend:
        base = (base + "；" if base else "") + \
               "阶段 %s 数据 PENDING（待补验）" % ",".join(str(t) for t in pend)
    return base or "一致"


# ================================================================ 各阶段数据访问
class Ctx:
    """聚合 loads / results / states / control 与设计统计。"""

    def __init__(self, loads, results, states, control):
        self.loads = loads
        self.results = results        # {stage: compact result or None}
        self.states = states          # {stage: compact state or None}
        self.control = control
        self.design = None
        if loads:
            self.design = self._analyze_loads(loads)

    @staticmethod
    def _analyze_loads(loads):
        s1 = loads.get("stage1") or {}
        rows = s1.get("species") or []
        stats = batch_stats(rows)
        meta = s1.get("meta") or {}
        additions = []
        for a in (loads.get("additions") or []):
            additions.append({"stage": a.get("stage"), "element": a.get("element"),
                              "formula": a.get("formula"),
                              "name": a.get("name"),
                              "molecules": a.get("molecules"),
                              "atoms": a.get("atoms")})
        return {"stage1": stats, "meta": meta, "additions": additions,
                "L": loads.get("L"), "minutes": loads.get("minutes"),
                "max_reaction_atoms": loads.get("max_reaction_atoms"),
                "stage_design": loads.get("stage_design"),
                "config": loads.get("config")}

    def add_for(self, stage):
        for a in (self.design or {}).get("additions") or []:
            if a.get("stage") == stage:
                return a
        return None

    def comp(self, stage):
        R = self.results.get(stage)
        return comp_stats(R["comp"]) if R else None

    def state(self, stage):
        return self.states.get(stage)


def comp_ts_issue(R):
    ts = R.get("ts") or []
    if not ts:
        return ("SKIP", "time_series 为空", None)
    last = ts[-1]
    sm = R["summary"]
    issues = []
    if last.get("N") != sm.get("final_N"):
        issues.append("末行 N=%r ≠ final_N=%r" % (last.get("N"), sm.get("final_N")))
    if last.get("atoms") != sm.get("final_atoms"):
        issues.append("末行 atoms=%r ≠ final_atoms=%r"
                      % (last.get("atoms"), sm.get("final_atoms")))
    if issues:
        return ("FAIL", "；".join(issues), {"last_row": last, "summary": sm})
    return ("PASS", "末行 t=%r N=%r atoms=%r，与 summary 一致"
            % (last.get("t"), last.get("N"), last.get("atoms")),
            {"last_t": last.get("t"), "N": last.get("N"),
             "atoms": last.get("atoms")})


# ================================================================ 组 1 投料
def check_group1(ck, ctx):
    ck.begin(1, "投料设计（stage1 聚素 + 三次单质投放）")
    if not ctx.loads or not ctx.design:
        ck.skip_rest("t63_loads.json 缺失")
        return
    d = ctx.design
    s1 = d["stage1"]
    vals = {"stage1": {k: s1[k] for k in ("n_species", "molecules", "atoms",
                                          "element_atoms", "valence_atoms")},
            "additions": d["additions"]}

    # 1.1 stage1 规模
    ok = (s1["n_species"] == EXPECT_S1["species"] and
          s1["molecules"] == EXPECT_S1["molecules"] and
          s1["atoms"] == EXPECT_S1["atoms"] and not s1["issues"])
    ck.sub("1.1", "stage1 投料 = 29 种 / 9002 分子 / 38532 原子",
           "PASS" if ok else "FAIL",
           "复算 n_species=%d molecules=%d atoms=%d%s"
           % (s1["n_species"], s1["molecules"], s1["atoms"],
              "" if not s1["issues"] else "；issues=" + str(s1["issues"])),
           {"n_species": s1["n_species"], "molecules": s1["molecules"],
            "atoms": s1["atoms"], "issues": s1["issues"]})

    # 1.2 stage1 元素只含 O/X/C
    off = {e: s1["element_atoms"][e] for e in ELEMS
           if e not in EXPECT_S1["elements"] and s1["element_atoms"][e] != 0}
    cov = [e for e in EXPECT_S1["elements"] if s1["element_atoms"][e] > 0]
    ok = not off and sorted(cov) == sorted(EXPECT_S1["elements"]) and \
        s1["atoms"] == sum(s1["element_atoms"].values())
    ck.sub("1.2", "stage1 元素只含 O/X/C（其余 6 元素为 0）",
           "PASS" if ok else "FAIL",
           "元素原子=%s%s" % ({e: s1["element_atoms"][e] for e in ELEMS},
                              "" if not off else "；非零非 O/X/C: %s" % off),
           {"element_atoms": s1["element_atoms"], "off_elements": off,
            "covered": cov})

    # 1.3 三次投放设计
    issues = []
    adds = d["additions"]
    if len(adds) != 3:
        issues.append("additions 数量=%d ≠ 3" % len(adds))
    for exp, got in zip(EXPECT_ADD, adds):
        for k in ("stage", "element", "formula", "molecules", "atoms"):
            if got.get(k) != exp[k]:
                issues.append("stage%d %s: %r ≠ %r"
                              % (exp["stage"], k, got.get(k), exp[k]))
    ck.sub("1.3", "三次投放各 8000 分子 / 16000 原子（F2/A2/K2）",
           "FAIL" if issues else "PASS",
           "；".join("%s(%s) 8000/16000" % (a["formula"], a["element"])
                     for a in adds) if not issues else "；".join(issues),
           {"additions": adds})

    # 1.4 stage_design 一致
    issues = []
    sd = d.get("stage_design") or []
    if len(sd) != 4:
        issues.append("stage_design 长度=%d ≠ 4" % len(sd))
    else:
        if sd[0].get("initial_molecules") != s1["molecules"] or \
                sd[0].get("initial_atoms") != s1["atoms"]:
            issues.append("stage_design[0] 初始 %r/%r ≠ 复算 %d/%d"
                          % (sd[0].get("initial_molecules"),
                             sd[0].get("initial_atoms"),
                             s1["molecules"], s1["atoms"]))
        for i, exp in enumerate(EXPECT_ADD):
            if i + 1 >= len(sd):
                continue
            got = sd[i + 1].get("add") or {}
            if got.get("element") != exp["element"] or \
                    got.get("formula") != exp["formula"]:
                issues.append("stage_design[%d].add 与投放不符" % (i + 1))
    ck.sub("1.4", "loads.stage_design 与复算一致",
           "FAIL" if issues else "PASS",
           "一致" if not issues else "；".join(issues), {"issues": issues})

    # 1.5 loads.meta 与 rows 复算一致
    meta = d["meta"] or {}
    issues = []
    for k, v in (("n_species", s1["n_species"]), ("total_molecules", s1["molecules"]),
                 ("total_atoms", s1["atoms"])):
        if k in meta and meta[k] != v:
            issues.append("meta.%s=%r ≠ 复算=%r" % (k, meta[k], v))
    ck.sub("1.5", "loads.stage1.meta 与 species rows 复算一致",
           "FAIL" if issues else "PASS",
           "一致" if not issues else "；".join(issues),
           {"issues": issues, "meta": meta})

    # 1.6 投料 rows 自洽
    ck.sub("1.6", "stage1 species rows 字段自洽（formula/atoms/count）",
           "PASS" if not s1["issues"] else "FAIL",
           "无问题" if not s1["issues"] else "；".join(s1["issues"]),
           {"issues": s1["issues"]})


# ================================================================ 组 2 质量/元素守恒
def check_group2(ck, ctx):
    ck.begin(2, "跨阶段质量与元素守恒")
    if not ctx.loads or not ctx.design:
        ck.skip_rest("t63_loads.json 缺失")
        return
    s1 = ctx.design["stage1"]
    R1 = ctx.results.get(1)
    if R1 is None:
        ck.skip_rest("stage1 结果缺失")
        return

    # 2.1 stage1 初始装载 == 设计
    cfg = R1["config"]
    ok = (cfg.get("initial_particles") == s1["molecules"] and
          cfg.get("initial_atoms") == s1["atoms"])
    ck.sub("2.1", "stage1 初始粒子/原子 == 设计投料", "PASS" if ok else "FAIL",
           "initial_particles=%r（设计 %d）；initial_atoms=%r（设计 %d）"
           % (cfg.get("initial_particles"), s1["molecules"],
              cfg.get("initial_atoms"), s1["atoms"]),
           {"initial_particles": cfg.get("initial_particles"),
            "initial_atoms": cfg.get("initial_atoms")})

    c1 = ctx.comp(1)

    # 2.2 stage1 终态分子数/原子数
    issues = []
    if R1["summary"].get("final_N") != c1["molecules"]:
        issues.append("final_N=%r ≠ Σcomp=%d"
                      % (R1["summary"].get("final_N"), c1["molecules"]))
    if R1["summary"].get("final_atoms") != c1["atoms"]:
        issues.append("final_atoms=%r ≠ Σcount*atoms=%d"
                      % (R1["summary"].get("final_atoms"), c1["atoms"]))
    if c1["atoms"] != s1["atoms"]:
        issues.append("Σcomp atoms=%d ≠ 设计原子数=%d" % (c1["atoms"], s1["atoms"]))
    ck.sub("2.2", "stage1 终态分子数/原子数 == 设计（质量守恒）",
           "FAIL" if issues else "PASS",
           "；".join(issues) if issues else
           "final_N=%d（Σcount=%d）；final_atoms=%d（Σcount*atoms=%d）"
           % (R1["summary"].get("final_N"), c1["molecules"],
              R1["summary"].get("final_atoms"), c1["atoms"]),
           {"summary": R1["summary"], "comp_molecules": c1["molecules"],
            "comp_atoms": c1["atoms"]})

    # 2.3 stage1 逐元素 == 设计
    exp1 = dict(s1["element_atoms"])
    diff = dict_diff(c1["element_atoms"], exp1, ELEMS)
    ck.sub("2.3", "stage1 终态逐元素 == 聚素设计", "FAIL" if diff else "PASS",
           "逐元素一致" if not diff else
           "差异: %s" % json.dumps(diff, ensure_ascii=False),
           {"diff": diff, "final": c1["element_atoms"], "expected": exp1})

    # 2.4 各阶段初始 == 上阶段 state + 投放（k=2..4）
    issues = []
    parts = []
    vals = {}
    for k in (2, 3, 4):
        R = ctx.results.get(k)
        S = ctx.state(k - 1)
        add = ctx.add_for(k)
        if R is None or S is None or add is None:
            vals[k] = {"pending": True}
            if R is None:
                parts.append("stage%d 结果缺失" % k)
            else:
                parts.append("state%d 缺失" % (k - 1))
            continue
        exp_p = S["total_molecules"] + add["molecules"]
        exp_a = S["total_atoms"] + add["atoms"]
        got_p = R["config"].get("initial_particles")
        got_a = R["config"].get("initial_atoms")
        vals[k] = {"expected_particles": exp_p, "initial_particles": got_p,
                   "expected_atoms": exp_a, "initial_atoms": got_a,
                   "state_prev": {"molecules": S["total_molecules"],
                                  "atoms": S["total_atoms"]}}
        parts.append("stage%d 初始 %r/%r（期望 %d/%d）"
                     % (k, got_p, got_a, exp_p, exp_a))
        if got_p != exp_p:
            issues.append("stage%d initial_particles=%r ≠ state%d(%d)+%d=%d"
                          % (k, got_p, k - 1, S["total_molecules"],
                             add["molecules"], exp_p))
        if got_a != exp_a:
            issues.append("stage%d initial_atoms=%r ≠ state%d(%d)+%d=%d"
                          % (k, got_a, k - 1, S["total_atoms"],
                             add["atoms"], exp_a))
    ck.sub("2.4", "各阶段初始 == 上阶段 state + 投放（8000 分子/16000 原子）",
           status_of(issues, vals), detail_of(parts, issues, vals),
           {"phases": vals})

    # 2.5 各阶段终态分子数 == Σcomp == final N
    issues = []
    parts = []
    vals = {}
    for k in STAGES:
        R = ctx.results.get(k)
        if R is None:
            vals[k] = {"pending": True}
            continue
        c = ctx.comp(k)
        vals[k] = {"final_N": R["summary"].get("final_N"),
                   "comp_molecules": c["molecules"]}
        parts.append("stage%d final_N=%r Σcount=%d"
                     % (k, R["summary"].get("final_N"), c["molecules"]))
        if R["summary"].get("final_N") != c["molecules"]:
            issues.append("stage%d final_N=%r ≠ Σcomp=%d"
                          % (k, R["summary"].get("final_N"), c["molecules"]))
    ck.sub("2.5", "各阶段终态分子数 == Σfinal_composition.count == final_N",
           status_of(issues, vals), detail_of(parts, issues, vals), {"phases": vals})

    # 2.6 各阶段终态原子数 == initial_atoms == Σcount*atoms
    issues = []
    parts = []
    vals = {}
    for k in STAGES:
        R = ctx.results.get(k)
        if R is None:
            vals[k] = {"pending": True}
            continue
        c = ctx.comp(k)
        exp = s1["atoms"] if k == 1 else R["config"].get("initial_atoms")
        vals[k] = {"summary_final_atoms": R["summary"].get("final_atoms"),
                   "comp_atoms": c["atoms"], "initial_atoms": R["config"].get("initial_atoms"),
                   "expected": exp}
        parts.append("stage%d final_atoms=%r Σcomp=%d initial=%r"
                     % (k, R["summary"].get("final_atoms"), c["atoms"],
                        R["config"].get("initial_atoms")))
        if R["summary"].get("final_atoms") != c["atoms"]:
            issues.append("stage%d final_atoms=%r ≠ Σcomp=%d"
                          % (k, R["summary"].get("final_atoms"), c["atoms"]))
        if exp is not None and c["atoms"] != exp:
            issues.append("stage%d Σcomp atoms=%d ≠ 期望原子数=%r"
                          % (k, c["atoms"], exp))
    ck.sub("2.6", "各阶段终态原子数 == initial_atoms == Σcount*atoms",
           status_of(issues, vals), detail_of(parts, issues, vals), {"phases": vals})

    # 2.7 跨阶段逐元素守恒（stage k == stage k-1 + 投放元素 16000）
    issues = []
    parts = []
    vals = {}
    for k in (2, 3, 4):
        R = ctx.results.get(k)
        prev = ctx.comp(k - 1)
        add = ctx.add_for(k)
        if R is None or prev is None or add is None:
            vals[k] = {"pending": True}
            continue
        c = ctx.comp(k)
        exp = dict(prev["element_atoms"])
        exp[add["element"]] = exp.get(add["element"], 0) + 16000
        diff = dict_diff(c["element_atoms"], exp, ELEMS)
        vals[k] = {"diff": diff, "final": c["element_atoms"], "expected": exp}
        parts.append("stage%d 元素原子=%s" % (k, c["element_atoms"]))
        if diff:
            issues.append("stage%d 逐元素差异: %s"
                          % (k, json.dumps(diff, ensure_ascii=False)))
    ck.sub("2.7", "跨阶段逐元素守恒：stage k == stage k-1 + 投放元素 16,000",
           status_of(issues, vals), detail_of(parts, issues, vals), {"phases": vals})

    # 2.8 time_series 末行 == summary（各阶段）
    issues = []
    parts = []
    vals = {}
    for k in STAGES:
        R = ctx.results.get(k)
        if R is None:
            vals[k] = {"pending": True}
            continue
        st, det, v = comp_ts_issue(R)
        vals[k] = v or {}
        parts.append("stage%d %s" % (k, det))
        if st == "FAIL":
            issues.append("stage%d %s" % (k, det))
    ck.sub("2.8", "各阶段 time_series 末行 N/原子数 == summary",
           status_of(issues, vals), detail_of(parts, issues, vals), {"phases": vals})

    # 2.9 各阶段 config.load_spec 与设计一致
    issues = []
    vals = {}
    for k in STAGES:
        R = ctx.results.get(k)
        if R is None:
            vals[k] = {"pending": True}
            continue
        spec = R["load_spec"]
        if k == 1:
            rows = (ctx.loads.get("stage1") or {}).get("species") or []
            bad = []
            if len(spec) != len(rows):
                bad.append("load_spec 长度 %d ≠ species 行数 %d"
                           % (len(spec), len(rows)))
            for i, (sr, rr) in enumerate(zip(spec, rows)):
                if sr.get("formula") != rr.get("formula") or \
                        sr.get("count") != rr.get("count"):
                    bad.append("第%d项不同" % i)
                    break
            vals[k] = {"spec_len": len(spec), "rows_len": len(rows),
                       "issues": bad}
            if bad:
                issues.append("stage1 load_spec 与 29 聚素不一致: %s" % bad)
        else:
            add = ctx.add_for(k)
            exp = [{"formula": add["formula"], "count": add["molecules"]}]
            ok = len(spec) == 1 and spec[0].get("formula") == exp[0]["formula"] \
                and spec[0].get("count") == exp[0]["count"]
            vals[k] = {"spec": spec, "expected": exp}
            if not ok:
                issues.append("stage%d load_spec=%r ≠ %r" % (k, spec, exp))
    ck.sub("2.9", "各阶段 config.load_spec 与投放设计一致",
           status_of(issues, vals), "一致" if not issues else "；".join(issues),
           {"phases": vals})

    # 2.10 全程原子总量闭合
    vals = {}
    issues = []
    parts = []
    R4 = ctx.results.get(4)
    if R4 is None:
        vals[4] = {"pending": True}
        parts.append("stage4 结果缺失")
    else:
        c4 = ctx.comp(4)
        exp_atoms = s1["atoms"] + sum(a["atoms"] for a in EXPECT_ADD)
        exp_e = dict(s1["element_atoms"])
        for a in EXPECT_ADD:
            exp_e[a["element"]] = exp_e.get(a["element"], 0) + a["atoms"]
        vals[4] = {"final_atoms": c4["atoms"], "expected_atoms": exp_atoms,
                   "final_elements": c4["element_atoms"],
                   "expected_elements": exp_e}
        parts.append("stage4 终态原子数=%d（期望 %d）" % (c4["atoms"], exp_atoms))
        if c4["atoms"] != exp_atoms:
            issues.append("stage4 原子数=%d ≠ 38532+3*16000=%d"
                          % (c4["atoms"], exp_atoms))
        diff = dict_diff(c4["element_atoms"], exp_e, ELEMS)
        if diff:
            issues.append("stage4 逐元素差异: %s"
                          % json.dumps(diff, ensure_ascii=False))
    ck.sub("2.10", "全程原子总量闭合（stage4 == 38532 + 3×16000，逐元素）",
           status_of(issues, vals), detail_of(parts, issues, vals), {"phases": vals})


# ================================================================ 组 3 价数守恒
def check_group3(ck, ctx):
    ck.begin(3, "价数守恒（F=1价 / A=2价 / K=3价）")
    if not ctx.loads or not ctx.design or not ctx.results.get(1):
        ck.skip_rest("loads 或 stage1 结果缺失")
        return
    s1 = ctx.design["stage1"]
    keys = ("v3", "v2", "v1")

    # 3.1 stage1 终态价数 == 设计
    c1 = ctx.comp(1)
    exp1 = s1["valence_atoms"]
    diff = dict_diff(c1["valence_atoms"], exp1, keys)
    ck.sub("3.1", "stage1 终态 v3/v2/v1 == 聚素设计",
           "FAIL" if diff else "PASS",
           "终态 %s；设计 %s" % (c1["valence_atoms"], exp1)
           if not diff else "差异: %s" % json.dumps(diff, ensure_ascii=False),
           {"diff": diff, "final": c1["valence_atoms"], "expected": exp1})

    # 3.2 逐阶段价数守恒
    issues = []
    parts = []
    vals = {}
    for k in (2, 3, 4):
        R = ctx.results.get(k)
        prev = ctx.comp(k - 1)
        add = ctx.add_for(k)
        if R is None or prev is None or add is None:
            vals[k] = {"pending": True}
            continue
        c = ctx.comp(k)
        exp = dict(prev["valence_atoms"])
        key = "v%d" % VALENCE[add["element"]]
        exp[key] = exp.get(key, 0) + add["atoms"]
        diff = dict_diff(c["valence_atoms"], exp, keys)
        vals[k] = {"diff": diff, "final": c["valence_atoms"], "expected": exp}
        parts.append("stage%d 价数=%s（期望 %s）"
                     % (k, c["valence_atoms"], exp))
        if diff:
            issues.append("stage%d 价数差异: %s"
                          % (k, json.dumps(diff, ensure_ascii=False)))
    ck.sub("3.2", "各阶段价数 == 上阶段 + 投放元素价数（F→v1/A→v2/K→v3）",
           status_of(issues, vals), detail_of(parts, issues, vals), {"phases": vals})

    # 3.3 Σ价数 == 总原子数（各阶段）
    issues = []
    vals = {}
    parts = []
    for k in STAGES:
        c = ctx.comp(k)
        if c is None:
            vals[k] = {"pending": True}
            continue
        tot = sum(c["valence_atoms"].values())
        vals[k] = {"sum_valence": tot, "atoms": c["atoms"]}
        parts.append("stage%d Σv=%d atoms=%d" % (k, tot, c["atoms"]))
        if tot != c["atoms"]:
            issues.append("stage%d Σ价数=%d ≠ 原子数=%d" % (k, tot, c["atoms"]))
    ck.sub("3.3", "各阶段 Σ价数原子数 == 总原子数",
           status_of(issues, vals), detail_of(parts, issues, vals), {"phases": vals})

    # 3.4 INFO 各阶段价数占比
    shares = {}
    parts = []
    for k in STAGES:
        c = ctx.comp(k)
        if c is None:
            continue
        tot = sum(c["valence_atoms"].values())
        sh = [c["valence_atoms"][x] / tot if tot else None for x in keys]
        shares[k] = {"valence_atoms": c["valence_atoms"], "shares": sh}
        parts.append("stage%d v3/v2/v1 占比=%s" % (k, [fnum(x) for x in sh]))
    ck.sub("3.4", "各阶段价数占比概览", "INFO",
           "；".join(parts) or "无数据", {"stages": shares})


# ================================================================ 组 4 无化学对照
def check_group4(ck, ctx, tol_min, tol_frac):
    ck.begin(4, "无化学对照（stage1 500 次穿越要求）")
    ctl = ctx.control
    if not ctl:
        ck.skip_rest("t63_control_s1.json 缺失")
        return
    s1 = ctx.design["stage1"] if ctx.design else None
    cfg = ctl["config"]
    st = ctl["stats"]
    bs = ctl["by_size"]

    ok = cfg.get("chemical_reactions") is False
    ck.sub("4.1", "对照组化学开关关闭", "PASS" if ok else "FAIL",
           "config.chemical_reactions=%r" % (cfg.get("chemical_reactions"),),
           {"chemical_reactions": cfg.get("chemical_reactions")})

    v = st.get("min")
    ok = isinstance(v, (int, float)) and v >= tol_min
    ck.sub("4.2", "stats.min ≥%g" % tol_min, "PASS" if ok else "FAIL",
           "stats.min=%r（要求 ≥%g）" % (v, tol_min), {"min": v})

    v = st.get("fraction_ge_500")
    ok = isinstance(v, (int, float)) and v >= tol_frac
    ck.sub("4.3", "stats.fraction_ge_500 ≥%g" % tol_frac,
           "PASS" if ok else "FAIL",
           "fraction_ge_500=%r（要求 ≥%g）" % (v, tol_frac),
           {"fraction_ge_500": v})

    bad = []
    for size, rec in sorted(bs.items(), key=lambda kv: int(kv[0])):
        if rec.get("min") is None or rec.get("min") < tol_min:
            bad.append("size=%s min=%r n=%r" % (size, rec.get("min"), rec.get("n")))
        if not rec.get("n"):
            bad.append("size=%s n=%r" % (size, rec.get("n")))
    ck.sub("4.4", "by_size 每组 min ≥%g" % tol_min,
           "PASS" if not bad else "FAIL",
           "共 %d 组，全部 min ≥%g" % (len(bs), tol_min)
           if not bad else "；".join(bad[:8]),
           {"by_size_min": {k: rec.get("min") for k, rec in bs.items()},
            "issues": bad[:8]})

    issues = []
    vals = {}
    if s1 is not None:
        vals = {"n_particles": cfg.get("n_particles"),
                "expected_particles": s1["molecules"],
                "stats_n": st.get("n")}
        if cfg.get("n_particles") != s1["molecules"]:
            issues.append("config.n_particles=%r ≠ stage1 分子数=%d"
                          % (cfg.get("n_particles"), s1["molecules"]))
        if st.get("n") != cfg.get("n_particles"):
            issues.append("stats.n=%r ≠ config.n_particles=%r"
                          % (st.get("n"), cfg.get("n_particles")))
        ls = cfg.get("load_spec") or []
        rows = (ctx.loads.get("stage1") or {}).get("species") or []
        if len(ls) != len(rows):
            issues.append("load_spec 长度=%d ≠ stage1 物种数=%d"
                          % (len(ls), len(rows)))
        else:
            for i, (sr, rr) in enumerate(zip(ls, rows)):
                if sr.get("formula") != rr.get("formula") or \
                        sr.get("count") != rr.get("count"):
                    issues.append("load_spec 第%d项与 stage1 rows 不同" % i)
                    break
        if cfg.get("L") is not None and ctx.design is not None and \
                cfg.get("L") != ctx.design.get("L"):
            issues.append("control L=%r ≠ loads L=%r"
                          % (cfg.get("L"), ctx.design.get("L")))
    sum_bs = sum(int(rec.get("n", 0)) for rec in bs.values())
    if st.get("n") is not None and sum_bs != st.get("n"):
        issues.append("Σby_size.n=%d ≠ stats.n=%r" % (sum_bs, st.get("n")))
    ck.sub("4.5", "对照组装载与 stage1 一致且统计分组完备",
           "FAIL" if issues else "PASS",
           "一致" if not issues else "；".join(issues),
           {"issues": issues, "vals": vals, "sum_by_size_n": sum_bs})

    ck.sub("4.6", "对照路径统计概览", "INFO",
           "min=%.1f p1=%.1f median=%.1f p95=%.1f max=%.1f mean=%.1f"
           % (st.get("min") or 0, st.get("p1") or 0, st.get("median") or 0,
              st.get("p95") or 0, st.get("max") or 0, st.get("mean") or 0),
           {"stats": st})


# ================================================================ 组 5 判定自洽
def check_group5(ck, ctx, cap_expected):
    ck.begin(5, "反应判定自洽（四阶段）")
    if not ctx.results.get(1):
        ck.skip_rest("stage1 结果缺失")
        return

    def pending_stages():
        return [k for k in STAGES if ctx.results.get(k) is None]

    # 5.1 rc 类型
    issues = []
    vals = {}
    for k in STAGES:
        R = ctx.results.get(k)
        if R is None:
            vals[k] = {"pending": True}
            continue
        rc = R["summary"].get("reaction_counts") or {}
        extra = set(rc) - set(RC_TYPES)
        vals[k] = {"reaction_counts": rc,
                   "missing_types": [t for t in RC_TYPES if t not in rc]}
        if extra:
            issues.append("stage%d 出现意外判定类型 %s" % (k, sorted(extra)))
        for t in RC_TYPES:
            v = rc.get(t, 0)
            if not isinstance(v, int) or v < 0:
                issues.append("stage%d.reaction_counts[%s]=%r 非负整数" % (k, t, v))
    ck.sub("5.1", "reaction_counts 类型合法且非负", status_of(issues, vals),
           detail_of([], issues, vals), {"phases": vals})

    # 5.2 逐类型累计 == reaction_counts == 末行累计
    issues = []
    vals = {}
    for k in STAGES:
        R = ctx.results.get(k)
        if R is None:
            vals[k] = {"pending": True}
            continue
        rc = R["summary"].get("reaction_counts") or {}
        ts = R.get("ts") or []
        if not ts:
            vals[k] = {"note": "time_series 为空"}
            issues.append("stage%d time_series 为空" % k)
            continue
        last = ts[-1]
        per = {}
        for t in RC_TYPES:
            s = sum((row.get("d_" + t) or 0) for row in ts)
            cum = last.get(t)
            per[t] = {"sum_delta": s, "summary": rc.get(t, 0),
                      "last_cumulative": cum}
            if s != rc.get(t, 0) or cum != rc.get(t, 0):
                issues.append("stage%d[%s] Σd=%r summary=%r 末行累计=%r"
                              % (k, t, s, rc.get(t, 0), cum))
        vals[k] = per
    ck.sub("5.2", "逐类型累计判定数自洽（Σd_* == reaction_counts == 末行累计）",
           status_of(issues, vals), detail_of([], issues, vals), {"phases": vals})

    # 5.3 合计
    issues = []
    vals = {}
    parts = []
    for k in STAGES:
        R = ctx.results.get(k)
        if R is None:
            vals[k] = {"pending": True}
            continue
        rc = R["summary"].get("reaction_counts") or {}
        total_rc = sum(int(rc.get(t, 0)) for t in RC_TYPES)
        ts = R.get("ts") or []
        total_d = sum(sum((row.get("d_" + t) or 0) for row in ts)
                      for t in RC_TYPES) if ts else 0
        vals[k] = {"sum_reaction_counts": total_rc, "sum_deltas": total_d}
        parts.append("stage%d 合计=%d" % (k, total_rc))
        if total_rc != total_d:
            issues.append("stage%d Σreaction_counts=%d ≠ Σd=%d"
                          % (k, total_rc, total_d))
    ck.sub("5.3", "四类判定数之和 == 碰撞判定总数（Σd_*）",
           status_of(issues, vals), detail_of(parts, issues, vals), {"phases": vals})

    # 5.4 capped 占比 <1%
    issues = []
    vals = {}
    parts = []
    for k in STAGES:
        R = ctx.results.get(k)
        if R is None:
            vals[k] = {"pending": True}
            continue
        rc = R["summary"].get("reaction_counts") or {}
        total = sum(int(rc.get(t, 0)) for t in RC_TYPES)
        frac = (rc.get("capped", 0) / total) if total else None
        vals[k] = {"capped": rc.get("capped", 0), "total": total, "frac": frac}
        if frac is None:
            issues.append("stage%d capped 占比不可计算（判定总数=0）" % k)
        else:
            parts.append("stage%d capped=%r/%r (%.4f%%)"
                         % (k, rc.get("capped", 0), total, 100.0 * frac))
            if frac >= 0.01:
                issues.append("stage%d capped 占比=%.4f%% ≥1%%" % (k, 100.0 * frac))
    ck.sub("5.4", "capped 占比 <1%", status_of(issues, vals),
           detail_of(parts, issues, vals), {"phases": vals})

    # 5.5 events_total / 蓄水池抽样
    limit_candidates = set()
    for k in STAGES:
        R = ctx.results.get(k)
        if R is None:
            continue
        et = R["summary"].get("events_total")
        n = R["events"].get("n", 0)
        if isinstance(et, int) and et > n:
            limit_candidates.add(n)
    reservoir = None
    if len(limit_candidates) == 1:
        reservoir = limit_candidates.pop()
    issues = []
    vals = {}
    parts = []
    for k in STAGES:
        R = ctx.results.get(k)
        if R is None:
            vals[k] = {"pending": True}
            continue
        et = R["summary"].get("events_total")
        ts = R.get("ts") or []
        last_et = ts[-1].get("events_total") if ts else None
        n = R["events"].get("n", 0)
        vals[k] = {"events_total": et, "last_ts_events_total": last_et,
                   "event_samples": n,
                   "expected_samples": (min(et, reservoir) if reservoir else
                                        (et if reservoir is None else None))}
        parts.append("stage%d events_total=%r 末行=%r 抽样=%d"
                     % (k, et, last_et, n))
        if last_et != et:
            issues.append("stage%d 末行 events_total=%r ≠ summary=%r"
                          % (k, last_et, et))
        if reservoir is not None:
            if n != min(et, reservoir):
                issues.append("stage%d 抽样数=%d ≠ min(events_total,%d)=%r"
                              % (k, n, reservoir, min(et, reservoir)))
        else:
            if n != et:
                issues.append("stage%d 抽样数=%d ≠ events_total=%r（无更大阶段可推定上限）"
                              % (k, n, et))
        if n > SAMPLE_CAP:
            issues.append("stage%d 抽样数=%d > 50000" % (k, n))
    if reservoir is not None and reservoir > SAMPLE_CAP:
        issues.append("推定蓄水池上限=%d > 50000" % reservoir)
    ck.sub("5.5", "events_total 与 time_series/蓄水池抽样一致（上限 ≤50,000）",
           status_of(issues, vals), detail_of(parts, issues, vals),
           {"reservoir_limit_inferred": reservoir, "phases": vals})

    # 5.6 抽样事件逐条守恒
    issues = []
    vals = {}
    parts = []
    for k in STAGES:
        R = ctx.results.get(k)
        if R is None:
            vals[k] = {"pending": True}
            continue
        ev = R["events"]
        vals[k] = {x: ev.get(x) for x in (
            "n", "scanned", "atom_conserv_bad", "valence_conserv_bad",
            "parse_bad", "empty_products", "type_counts")}
        parts.append("stage%d scanned=%d atom_bad=%d valence_bad=%d parse_bad=%d empty=%d"
                     % (k, ev.get("scanned", 0), ev.get("atom_conserv_bad", 0),
                        ev.get("valence_conserv_bad", 0), ev.get("parse_bad", 0),
                        ev.get("empty_products", 0)))
        for x in ("atom_conserv_bad", "valence_conserv_bad", "parse_bad",
                  "empty_products"):
            if ev.get(x):
                issues.append("stage%d %s=%d" % (k, x, ev[x]))
    ck.sub("5.6", "抽样事件逐条原子/价数守恒（≤50,000 条/阶段，无空产物）",
           status_of(issues, vals), detail_of(parts, issues, vals),
           {"phases": vals})

    # 5.7 终态最大原子数 ≤ cap
    issues = []
    vals = {}
    parts = []
    for k in STAGES:
        R = ctx.results.get(k)
        if R is None:
            vals[k] = {"pending": True}
            continue
        cap = R["config"].get("max_reaction_atoms")
        c = ctx.comp(k)
        ts = R.get("ts") or []
        ts_max = max((row.get("max_atoms") or 0) for row in ts) if ts else None
        top_max = max((len(v["atoms"]) for v in R["top"].values()), default=None)
        vals[k] = {"cap": cap, "comp_max_atoms": c["max_atoms"],
                   "ts_max_atoms": ts_max, "top_max_atoms": top_max}
        parts.append("stage%d cap=%r comp_max=%r ts_max=%r"
                     % (k, cap, c["max_atoms"], ts_max))
        if cap is None:
            issues.append("stage%d 无 max_reaction_atoms" % k)
            continue
        for name, v in (("comp_max_atoms", c["max_atoms"]),
                        ("ts_max_atoms", ts_max), ("top_max_atoms", top_max)):
            if v is not None and v > cap:
                issues.append("stage%d %s=%d > cap=%d" % (k, name, v, cap))
    ck.sub("5.7", "各阶段终态最大原子数 ≤ cap", status_of(issues, vals),
           detail_of(parts, issues, vals), {"phases": vals})

    # 5.8 decomp 一致 + cap 期望值
    issues = []
    vals = {}
    parts = []
    for k in STAGES:
        R = ctx.results.get(k)
        if R is None:
            vals[k] = {"pending": True}
            continue
        ts = R.get("ts") or []
        last = ts[-1] if ts else {}
        vals[k] = {"summary_decomp": R["summary"].get("decomp_events"),
                   "ts_decomp": last.get("decomp")}
        parts.append("stage%d decomp summary=%r ts=%r"
                     % (k, R["summary"].get("decomp_events"), last.get("decomp")))
        if R["summary"].get("decomp_events") != last.get("decomp"):
            issues.append("stage%d summary.decomp_events=%r ≠ 末行 decomp=%r"
                          % (k, R["summary"].get("decomp_events"),
                             last.get("decomp")))
    ck.sub("5.8", "decomp 事件与 time_series 一致", status_of(issues, vals),
           detail_of(parts, issues, vals), {"phases": vals})

    # 5.9 cap 期望 40
    if cap_expected is not None:
        issues = []
        vals = {}
        parts = []
        for k in STAGES:
            R = ctx.results.get(k)
            if R is None:
                vals[k] = {"pending": True}
                continue
            cap = R["config"].get("max_reaction_atoms")
            vals[k] = {"cap": cap}
            parts.append("stage%d cap=%r" % (k, cap))
            if cap != cap_expected:
                issues.append("stage%d cap=%r ≠ %r" % (k, cap, cap_expected))
        ck.sub("5.9", "各阶段 cap == %r" % (cap_expected,),
               status_of(issues, vals), detail_of(parts, issues, vals),
               {"phases": vals})

    # 5.10 INFO ΔN 抽样一致性
    info = {}
    parts = []
    for k in STAGES:
        R = ctx.results.get(k)
        if R is None:
            continue
        pl = R["events"].get("product_lens") or []
        et = R["summary"].get("events_total")
        n0 = R["config"].get("initial_particles")
        nf = R["summary"].get("final_N")
        if not pl or not isinstance(et, int) or et <= 0 or n0 is None or nf is None:
            continue
        exact = (nf - n0) / float(et)
        mean = sum(pl) / float(len(pl)) - 2.0
        var = sum((x - 2.0 - mean) ** 2 for x in pl) / float(len(pl))
        se = (var / len(pl)) ** 0.5 if len(pl) else 0.0
        info[k] = {"dN": nf - n0, "events_total": et,
                   "exact_mean_delta": round(exact, 6),
                   "sample_mean_delta": round(mean, 6),
                   "se": round(se, 6),
                   "diff": round(abs(mean - exact), 6)}
        parts.append("stage%d ΔN=%d 精确均值=%.5f 抽样均值=%.5f SE=%.5f"
                     % (k, nf - n0, exact, mean, se))
    ck.sub("5.10", "ΔN 与抽样事件一致性概览", "INFO",
           "；".join(parts) or "无数据", {"stages": info})


# ================================================================ 组 6 终态表
def check_group6(ck, ctx):
    ck.begin(6, "终态表 sanity（final_composition / top structures）")
    if not ctx.results.get(1):
        ck.skip_rest("stage1 结果缺失")
        return

    # 6.1 atoms 字段与公式一致
    issues = []
    vals = {}
    parts = []
    for k in STAGES:
        R = ctx.results.get(k)
        if R is None:
            vals[k] = {"pending": True}
            continue
        c = ctx.comp(k)
        vals[k] = {"n_formula": c["n_formula"],
                   "atoms_none": len(c["atoms_none"]),
                   "atoms_field_mismatch": len(c["atoms_field_mismatch"]),
                   "parse_errors": len(c["parse_errors"])}
        parts.append("stage%d 分子式=%d atoms=None=%d 不一致=%d 解析错误=%d"
                     % (k, c["n_formula"], len(c["atoms_none"]),
                        len(c["atoms_field_mismatch"]), len(c["parse_errors"])))
        if c["atoms_field_mismatch"] or c["parse_errors"]:
            issues.append("stage%d 字段不一致=%d 解析错误=%d"
                          % (k, len(c["atoms_field_mismatch"]),
                             len(c["parse_errors"])))
    ck.sub("6.1", "final_composition.atoms 与公式原子数一致",
           status_of(issues, vals), detail_of(parts, issues, vals), {"phases": vals})

    # 6.2 top 结构合法
    issues = []
    vals = {}
    parts = []
    for k in STAGES:
        R = ctx.results.get(k)
        if R is None:
            vals[k] = {"pending": True}
            continue
        cap = R["config"].get("max_reaction_atoms")
        bad = []
        for f, t in R["top"].items():
            probs = validate_structure(f, t["atoms"], t["edges"], cap)
            if probs:
                bad.append({"formula": f, "problems": probs[:3]})
        vals[k] = {"n_top": len(R["top"]), "bad": bad[:8]}
        parts.append("stage%d top=%d 非法=%d" % (k, len(R["top"]), len(bad)))
        if bad:
            issues.append("stage%d top 非法结构 %d 个" % (k, len(bad)))
    ck.sub("6.2", "final_top_structures atoms/edges 合法（价数填满、无自环/重复边/越界）",
           status_of(issues, vals), detail_of(parts, issues, vals), {"phases": vals})

    # 6.3 top 公式 ⊆ final_composition
    issues = []
    for k in STAGES:
        R = ctx.results.get(k)
        if R is None:
            continue
        missing = [f for f in R["top"] if f not in R["comp"]]
        if missing:
            issues.append("stage%d top 中存在 final_composition 未收录公式: %s"
                          % (k, missing[:5]))
    pend = any(ctx.results.get(k) is None for k in STAGES)
    ck.sub("6.3", "top 结构公式均在 final_composition 中",
           "FAIL" if issues else ("PENDING" if pend else "PASS"),
           ("一致" if not issues else "；".join(issues))
           + ("；部分阶段 PENDING" if pend else ""), {"issues": issues[:5]})

    # 6.4 INFO atoms=None 概览
    info = {}
    for k in STAGES:
        c = ctx.comp(k)
        if c is None:
            continue
        info[k] = {"n_formula": c["n_formula"],
                   "atoms_none": c["atoms_none"][:5],
                   "n_atoms_none": None}
        info[k]["n_atoms_none"] = len(c["atoms_none"])
    ck.sub("6.4", "final_composition atoms=None 概览", "INFO",
           "；".join("stage%d: %d/%d" % (k, v["n_atoms_none"], v["n_formula"])
                     for k, v in info.items()) or "无数据", {"stages": info})


# ================================================================ 组 7 state 一致性
def check_group7(ck, ctx):
    ck.begin(7, "state 与 result 一致性")
    if not ctx.results.get(1):
        ck.skip_rest("stage1 结果缺失")
        return

    # 7.1 总数 + 组成
    issues = []
    vals = {}
    parts = []
    for k in STAGES:
        R = ctx.results.get(k)
        S = ctx.state(k)
        if R is None or S is None:
            vals[k] = {"pending": True}
            continue
        st, det, v = state_match(S, R["comp"], R["summary"])
        vals[k] = v
        parts.append("stage%d %s" % (k, det))
        if st == "FAIL":
            issues.append("stage%d %s" % (k, det))
    ck.sub("7.1", "各阶段 state 总分子/总原子/组成 == result 终态",
           status_of(issues, vals), detail_of(parts, issues, vals), {"phases": vals})

    # 7.2 元素计数一致
    issues = []
    vals = {}
    parts = []
    for k in STAGES:
        R = ctx.results.get(k)
        S = ctx.state(k)
        if R is None or S is None:
            vals[k] = {"pending": True}
            continue
        c = ctx.comp(k)
        diff = dict_diff(S["element_atoms"], c["element_atoms"], ELEMS)
        vals[k] = {"diff": diff, "state": S["element_atoms"],
                   "result": c["element_atoms"]}
        parts.append("stage%d 元素计数一致" % k if not diff else "stage%d 元素差异" % k)
        if diff:
            issues.append("stage%d 元素计数差异: %s"
                          % (k, json.dumps(diff, ensure_ascii=False)))
    ck.sub("7.2", "state_k.molecules 元素计数 == result_k 元素计数",
           status_of(issues, vals), detail_of(parts, issues, vals), {"phases": vals})

    # 7.3 state 结构合法
    issues = []
    vals = {}
    parts = []
    for k in STAGES:
        S = ctx.state(k)
        if S is None:
            vals[k] = {"pending": True}
            continue
        bad = []
        for m in S["molecules"]:
            probs = validate_structure(m["formula"], m["atoms"], m["edges"])
            if probs:
                bad.append({"formula": m["formula"], "problems": probs[:3]})
        vals[k] = {"n_structures": len(S["molecules"]), "bad": bad[:8]}
        parts.append("stage%d 结构=%d 非法=%d" % (k, len(S["molecules"]), len(bad)))
        if bad:
            issues.append("stage%d state 非法结构 %d 个" % (k, len(bad)))
    ck.sub("7.3", "各阶段 state.molecules 结构合法（价数填满/无重复边/越界）",
           status_of(issues, vals), detail_of(parts, issues, vals), {"phases": vals})

    # 7.4 INFO state 概览
    info = {}
    for k in STAGES:
        S = ctx.state(k)
        if S is None:
            continue
        info[k] = {"total_molecules": S["total_molecules"],
                   "total_atoms": S["total_atoms"],
                   "distinct_structures": S["distinct_structures"],
                   "distinct_formulas": S["distinct_formulas"]}
    ck.sub("7.4", "各阶段 state 概览", "INFO",
           "；".join("stage%d %d 分子/%d 原子/%d 结构"
                     % (k, v["total_molecules"], v["total_atoms"],
                        v["distinct_structures"]) for k, v in info.items())
           or "无数据", {"stages": info})


# ================================================================ 主流程
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="T63 四阶段独立验证脚本（只读 JSON，输出 t63_verify.json）")
    D = lambda name: os.path.join(BASE, name)
    ap.add_argument("--loads", default=D("t63_loads.json"))
    ap.add_argument("--r1", default=D("t63_phase1_result.json"))
    ap.add_argument("--r2", default=D("t63_phase2_result.json"))
    ap.add_argument("--r3", default=D("t63_phase3_result.json"))
    ap.add_argument("--r4", default=D("t63_phase4_result.json"))
    ap.add_argument("--s1", default=D("t63_state1.json"))
    ap.add_argument("--s2", default=D("t63_state2.json"))
    ap.add_argument("--s3", default=D("t63_state3.json"))
    ap.add_argument("--s4", default=D("t63_state4.json"))
    ap.add_argument("--control", default=D("t63_control_s1.json"))
    ap.add_argument("--out", default=D("t63_verify.json"))
    ap.add_argument("--cap", type=int, default=40)
    ap.add_argument("--control-min", type=float, default=500.0)
    ap.add_argument("--control-frac", type=float, default=0.9999)
    ap.add_argument("--no-events-scan", action="store_true",
                    help="跳过 event_samples 逐条扫描（仅调试加速用）")
    args = ap.parse_args(argv)

    t0 = datetime.now()
    print("T63 四阶段独立验证开始", iso_now())
    print("BASE =", BASE)
    paths = [("loads", args.loads),
             ("phase1", args.r1), ("phase2", args.r2),
             ("phase3", args.r3), ("phase4", args.r4),
             ("state1", args.s1), ("state2", args.s2),
             ("state3", args.s3), ("state4", args.s4),
             ("control_s1", args.control)]
    inputs = {name: file_meta(p) for name, p in paths}
    for name, meta in inputs.items():
        print("  %-10s %-8s %s" % (name, "OK" if meta["exists"] else "MISSING",
                                   meta["path"]))

    scan_ev = not args.no_events_scan
    loads = None
    if inputs["loads"]["exists"]:
        with open(args.loads, encoding="utf-8") as fh:
            loads = json.load(fh)
    results = {}
    for k, p in ((1, args.r1), (2, args.r2), (3, args.r3), (4, args.r4)):
        results[k] = load_result_compact(p, scan_ev)
    states = {}
    for k, p in ((1, args.s1), (2, args.s2), (3, args.s3), (4, args.s4)):
        states[k] = load_state_compact(p)
    control = load_control_compact(args.control)
    print("数据加载完成，耗时 %.1fs"
          % (datetime.now() - t0).total_seconds(), flush=True)

    ctx = Ctx(loads, results, states, control)
    ck = Checker()
    group_fns = [
        (1, lambda: check_group1(ck, ctx)),
        (2, lambda: check_group2(ck, ctx)),
        (3, lambda: check_group3(ck, ctx)),
        (4, lambda: check_group4(ck, ctx, args.control_min, args.control_frac)),
        (5, lambda: check_group5(ck, ctx, args.cap)),
        (6, lambda: check_group6(ck, ctx)),
        (7, lambda: check_group7(ck, ctx)),
    ]
    for gid, fn in group_fns:
        try:
            fn()
        except Exception as exc:
            ck.begin(gid, "GROUP%d（执行异常）" % gid)
            ck.sub("%d.E" % gid, "执行异常", "FAIL",
                   "%s: %s" % (type(exc).__name__, exc),
                   {"traceback": traceback.format_exc().splitlines()[-8:]})
    ck.finalize()

    required = {1, 2, 3, 4, 5, 6, 7}
    statuses = [s["status"] for g in ck.groups for s in g["subchecks"]]
    counts = {k: statuses.count(k)
              for k in ("PASS", "FAIL", "SKIP", "INFO", "PENDING")}
    overall = "PASS"
    if counts["FAIL"]:
        overall = "FAIL"
    elif counts["PENDING"] or any(g["id"] in required and g["status"] == "SKIP"
                                  for g in ck.groups):
        overall = "INCOMPLETE"

    pending = [{"group": g["id"], "id": s["id"], "name": s["name"],
                "detail": s["detail"]}
               for g in ck.groups for s in g["subchecks"]
               if s["status"] == "PENDING"]
    out = {
        "script": "t63_verify.py",
        "description": "T63 四阶段独立验证：投料/跨阶段守恒/价数/对照/判定自洽/终态表/state",
        "generated_at": iso_now(),
        "elapsed_s": round((datetime.now() - t0).total_seconds(), 1),
        "base_dir": BASE,
        "args": {k: v for k, v in vars(args).items()},
        "tolerances": {"control_min": args.control_min,
                       "control_fraction_ge_500": args.control_frac,
                       "capped_frac_max": 0.01,
                       "cap": args.cap,
                       "sample_scan_cap": SAMPLE_CAP},
        "inputs": inputs,
        "groups": ck.groups,
        "summary": counts,
        "overall": overall,
        "pending": pending,
        "notes": [],
    }
    for g in ck.groups:
        for s in g["subchecks"]:
            if s["status"] in ("SKIP", "PENDING"):
                out["notes"].append("[%s] %s: %s" % (g["id"], s["name"],
                                                    s["detail"]))
    if args.no_events_scan:
        out["notes"].append("event_samples 扫描已禁用（--no-events-scan）")

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(jsafe(out), fh, ensure_ascii=False, indent=1)

    # 控制台汇报
    print("\n" + "=" * 78)
    for g in ck.groups:
        print("[%s] %s —— %s" % (g["id"], g["name"], g["status"]))
        for s in g["subchecks"]:
            sid = ("%s " % s["id"]) if s["id"] else ""
            print("    %s%s: %s —— %s"
                  % (sid, s["name"], s["status"], s["detail"]))
    print("=" * 78)
    print("汇总: PASS=%d FAIL=%d PENDING=%d SKIP=%d INFO=%d"
          % (counts["PASS"], counts["FAIL"], counts["PENDING"],
             counts["SKIP"], counts["INFO"]))
    print("overall: %s" % overall)
    if pending:
        print("待补验（PENDING）项 %d 个：%s"
              % (len(pending), ", ".join(p["id"] or "-" for p in pending)))
    print("输出: %s（耗时 %.1fs）" % (args.out, out["elapsed_s"]))
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
