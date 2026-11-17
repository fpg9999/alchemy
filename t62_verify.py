# -*- coding: utf-8 -*-
"""t62_verify.py —— T62 独立验证脚本（只读结果 JSON，不修改任何实验文件）

独立实现（不 import pot_all / natural_engine / t55_kinetic_env），自己实现
分子式解析、价数表（O/P/K=3，X/W/A=2，C/L/F=1）、结构合法性检查，
避免与被验证代码共享同一套逻辑。

验证 7 类检查：
  1 投料等量性（batchA / batchB / 合计：三/二/一价各≈1/3、9 元素各≈1/9、
    九元素覆盖、species ≥100）
  2 质量/元素守恒（phaseA、phaseB、stateA/stateB）
  3 价数原子守恒（逐类原子数、占比≈1/3）
  4 无化学对照（stats.min ≥500、fraction_ge_500 ≥0.9999、by_size 每组 min ≥500）
  5 反应判定自洽（reaction_counts 合计、capped <1%、events_total/蓄水池抽样、
    终态最大原子数 ≤ cap）
  6 cap40 vs cap60 对比（hf 文件缺失则 SKIP）
  7 终态表 sanity（atoms 与公式一致、top/state 结构价数填满、无重复原子）

输出 t62_verify.json：groups -> subchecks（逐项 PASS/FAIL/SKIP/INFO + 实测值）、
summary（计数）、overall（PASS / FAIL / INCOMPLETE）。

用法（默认读脚本同目录 t62_*）：
  python t62_verify.py
  python t62_verify.py --a t59_phaseA_result.json --b t59_phaseB_result.json ...
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
ELEMS = ("O", "X", "C", "P", "W", "L", "K", "A", "F")   # pot_all.ORDER
VALENCE = {"O": 3, "P": 3, "K": 3,                      # 三价
           "X": 2, "W": 2, "A": 2,                      # 二价
           "C": 1, "L": 1, "F": 1}                      # 一价
V3 = ("O", "P", "K")
V2 = ("X", "W", "A")
V1 = ("C", "L", "F")
EVENT_RESERVOIR = 50000          # t62_two_phase.py 的 EVENT_LIMIT
RC_TYPES = ("complete", "incomplete", "none", "capped")


# ---------------------------------------------------------------- 基础工具
def iso_now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_formula(f):
    """严格解析分子式（元素均为单大写字母，如 O2XP2WK2A）。返回 {元素: 原子数}。"""
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


def pp(x):
    return None if x is None else round(100.0 * x, 4)


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
            "sha256_16": h.hexdigest()[:16]}


def dict_diff(actual, expected, keys):
    """返回 {key: {actual, expected}}（只列不同项）。"""
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
        """当前组剩余未写子项时，加一条整组 SKIP 说明。"""
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
def analyze_events(ev_samples):
    """逐条检查抽样事件的原子/价数守恒与产物数（用于 ΔN 一致性估计）。"""
    st = {"n": len(ev_samples), "type_counts": {}, "product_len_hist": {},
          "atom_conserv_bad": 0, "valence_conserv_bad": 0,
          "parse_bad": 0, "empty_products": 0,
          "bad_examples": [], "product_lens": []}
    tcount = collections.Counter()
    plen = []
    for e in ev_samples:
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
                ai.update(parse_formula(f))
                vi += sum(VALENCE[k] * v for k, v in parse_formula(f).items())
            for f in prods:
                ao.update(parse_formula(f))
                vo += sum(VALENCE[k] * v for k, v in parse_formula(f).items())
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
    st["type_counts"] = dict(tcount)
    st["product_len_hist"] = {str(k): int(v)
                              for k, v in sorted(collections.Counter(plen).items())}
    st["product_lens"] = plen
    return st


def load_result_compact(path, scan_events=True):
    meta = file_meta(path)
    if not meta["exists"]:
        return None
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    cfg = d.get("config") or {}
    sm = d.get("summary") or {}
    R = {"meta": meta, "phase": d.get("phase"),
         "config": {k: cfg.get(k) for k in (
             "initial_particles", "initial_atoms", "seed_initial_count",
             "max_reaction_atoms", "minutes", "T0", "T_end",
             "area_model", "experiment")},
         "load_spec": [{"tag": r.get("tag"), "formula": r.get("formula"),
                        "count": r.get("count")}
                       for r in (cfg.get("load_spec") or [])],
         "summary": {k: sm.get(k) for k in (
             "final_N", "final_atoms", "events_total", "decomp_events",
             "reaction_counts", "final_T", "runtime_s")},
         "load_summary": d.get("load_summary"),
         "seed_state_summary": d.get("seed_state_summary")}
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
    R["events"] = analyze_events(ev) if scan_events else {"n": len(ev),
                                                          "skipped": True}
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
    del d
    return R


def load_control_compact(path):
    meta = file_meta(path)
    if not meta["exists"]:
        return None
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    R = {"meta": meta,
         "config": d.get("config") or {},
         "stats": d.get("stats") or {},
         "by_size": d.get("by_size") or {},
         "runtime_s": d.get("runtime_s")}
    del d
    return R


# ---------------------------------------------------------------- 投料/终态统计
def analyze_batch(rows):
    """从 loads rows 独立复算投料统计（不采用 summary 数字）。"""
    out = {"n_species": len(rows), "molecules": 0, "atoms": 0,
           "element_atoms": {e: 0 for e in ELEMS},
           "valence_atoms": {"v3": 0, "v2": 0, "v1": 0},
           "issues": [], "size_counts": {}, "formulas": []}
    size_counts = collections.Counter()
    for idx, r in enumerate(rows):
        f = r.get("formula")
        try:
            p = parse_formula(f)
        except Exception as exc:
            if len(out["issues"]) < 8:
                out["issues"].append("第%d行 formula=%r 无法解析: %s" % (idx, f, exc))
            continue
        try:
            c = int(r.get("count"))
        except Exception:
            if len(out["issues"]) < 8:
                out["issues"].append("第%d行 count=%r 非整数" % (idx, r.get("count")))
            continue
        if c <= 0:
            if len(out["issues"]) < 8:
                out["issues"].append("第%d行 count=%r ≤0" % (idx, c))
            continue
        na = sum(p.values())
        at_field = r.get("atoms")
        if at_field is not None and int(at_field) != na:
            if len(out["issues"]) < 8:
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
        # rows 自带 v3/v2/v1 字段的自洽检查
        for k in ("v3", "v2", "v1"):
            if k in r and r[k] is not None:
                try:
                    rv = int(r[k])
                except Exception:
                    rv = None
                if rv != v[k] and len(out["issues"]) < 8:
                    out["issues"].append("第%d行 %s %s 字段=%r 但公式计算=%d"
                                         % (idx, f, k, r[k], v[k]))
    tot_v = sum(out["valence_atoms"].values())
    out["valence_shares"] = [out["valence_atoms"][k] / tot_v
                             if tot_v else None
                             for k in ("v3", "v2", "v1")]
    out["element_shares"] = {e: (out["element_atoms"][e] / out["atoms"]
                                 if out["atoms"] else None) for e in ELEMS}
    out["size_counts"] = {str(k): int(v) for k, v in sorted(size_counts.items())}
    return out


def comp_stats(comp):
    """从 final_composition（formula -> {count, atoms}）复算终态统计。"""
    out = {"n_formula": len(comp), "molecules": 0, "atoms": 0,
           "element_atoms": {e: 0 for e in ELEMS},
           "valence_atoms": {"v3": 0, "v2": 0, "v1": 0},
           "atoms_field_mismatch": [], "atoms_none": [],
           "parse_errors": [], "max_atoms": 0,
           "count_ge39": 0, "count_ge_cap": 0}
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
    tot_v = sum(out["valence_atoms"].values())
    out["valence_shares"] = [out["valence_atoms"][k] / tot_v if tot_v else None
                             for k in ("v3", "v2", "v1")]
    out["element_shares"] = {e: (out["element_atoms"][e] / out["atoms"]
                                 if out["atoms"] else None) for e in ELEMS}
    return out


def state_composition(state):
    c = collections.Counter()
    for m in state["molecules"]:
        c[m["formula"]] += m["count"]
    return c


# ---------------------------------------------------------------- 结构合法性检查
def validate_structure(f, atoms, edges, cap=None):
    """返回问题列表（价数填满、原子与公式一致、边合法、无重复原子/边）。"""
    issues = []
    try:
        p = parse_formula(f)
    except Exception as exc:
        return ["分子式无法解析: %s" % exc]
    n = len(atoms)
    if sum(p.values()) != n:
        issues.append("atoms 数 %d ≠ 公式原子数 %d" % (n, sum(p.values())))
    cnt = collections.Counter(atoms)
    if cnt != collections.Counter(p):
        issues.append("atoms 元素组成 %s ≠ 公式 %s"
                      % (dict(cnt), dict(p)))
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


# ================================================================ 各组检查
def check_group1(ck, loads, tol_val_pp, tol_elem_pp):
    ck.begin(1, "投料等量性（batchA / batchB / 合计）")
    if not loads:
        ck.skip_rest("t62_loads.json 缺失，无法检查投料设计")
        return
    A = analyze_batch((loads.get("batchA") or {}).get("rows") or [])
    B = analyze_batch((loads.get("batchB") or {}).get("rows") or [])
    both_elem = {e: A["element_atoms"][e] + B["element_atoms"][e] for e in ELEMS}
    both_val = {k: A["valence_atoms"][k] + B["valence_atoms"][k]
                for k in ("v3", "v2", "v1")}
    both_atoms = A["atoms"] + B["atoms"]
    both_mols = A["molecules"] + B["molecules"]
    comb = {"atoms": both_atoms, "molecules": both_mols,
            "element_atoms": both_elem, "valence_atoms": both_val}
    for d in (comb,):
        tv = sum(d["valence_atoms"].values())
        d["valence_shares"] = [d["valence_atoms"][k] / tv if tv else None
                               for k in ("v3", "v2", "v1")]
        d["element_shares"] = {e: (d["element_atoms"][e] / d["atoms"]
                                   if d["atoms"] else None) for e in ELEMS}

    vals = {"batchA": {k: A[k] for k in ("n_species", "molecules", "atoms",
                                         "valence_atoms", "valence_shares",
                                         "element_atoms", "element_shares")},
            "batchB": {k: B[k] for k in ("n_species", "molecules", "atoms",
                                         "valence_atoms", "valence_shares",
                                         "element_atoms", "element_shares")},
            "combined": {"molecules": both_mols, "atoms": both_atoms,
                         "valence_atoms": both_val,
                         "valence_shares": comb["valence_shares"],
                         "element_atoms": both_elem,
                         "element_shares": comb["element_shares"]}}

    # 1.1 物种数
    ok = A["n_species"] >= 100 and B["n_species"] >= 100
    ck.sub("1.1", "batchA/batchB 物种数 ≥100", "PASS" if ok else "FAIL",
           "batchA=%d 种，batchB=%d 种" % (A["n_species"], B["n_species"]),
           {"batchA_n_species": A["n_species"],
            "batchB_n_species": B["n_species"]})

    # 1.2-1.4 价数占比 ≈1/3
    for sid, tag, d in (("1.2", "batchA", A), ("1.3", "batchB", B),
                        ("1.4", "合计", comb)):
        dev = max(abs(s - 1.0 / 3.0) for s in d["valence_shares"]) * 100.0
        ok = dev <= tol_val_pp
        ck.sub(sid, "%s 三/二/一价原子各 ≈1/3（偏差 ≤%.1fpp）" % (tag, tol_val_pp),
               "PASS" if ok else "FAIL",
               "%s 价数原子 v3/v2/v1=%s，占比=%s，最大偏差=%.3fpp"
               % (tag, [d["valence_atoms"][k] for k in ("v3", "v2", "v1")],
                  [fnum(x) for x in d["valence_shares"]], dev),
               {"valence_atoms": d["valence_atoms"],
                "valence_shares": d["valence_shares"],
                "max_dev_pp": round(dev, 4)})

    # 1.5-1.7 元素占比 ≈1/9
    for sid, tag, d in (("1.5", "batchA", A), ("1.6", "batchB", B),
                        ("1.7", "合计", comb)):
        dev = max(abs(s - 1.0 / 9.0) for s in d["element_shares"].values()) * 100.0
        ok = dev <= tol_elem_pp
        ck.sub(sid, "%s 9 元素原子各 ≈1/9（偏差 ≤%.1fpp）" % (tag, tol_elem_pp),
               "PASS" if ok else "FAIL",
               "%s 元素原子=%s，最大偏差=%.3fpp"
               % (tag, {e: d["element_atoms"][e] for e in ELEMS}, dev),
               {"element_atoms": d["element_atoms"],
                "element_shares": d["element_shares"],
                "max_dev_pp": round(dev, 4)})

    # 1.8 九元素覆盖
    cov_a = set(e for e in ELEMS if A["element_atoms"][e] > 0)
    cov_b = set(e for e in ELEMS if B["element_atoms"][e] > 0)
    cov_all = set(ELEMS)
    ok = cov_a == cov_all and cov_b == cov_all
    ck.sub("1.8", "九元素全覆盖", "PASS" if ok else "FAIL",
           "batchA 覆盖=%s；batchB 覆盖=%s；应为全部 %d 种"
           % (sorted(cov_a), sorted(cov_b), len(ELEMS)),
           {"batchA_covered": sorted(cov_a), "batchB_covered": sorted(cov_b),
            "expected": list(ELEMS)})

    # 1.9 rows 数据自洽
    ok = not A["issues"] and not B["issues"]
    ck.sub("1.9", "投料 rows 字段自洽（atoms/v3/v2/v1/count）",
           "PASS" if ok else "FAIL",
           "batchA issues=%s；batchB issues=%s"
           % (A["issues"] or "无", B["issues"] or "无"),
           {"batchA_issues": A["issues"], "batchB_issues": B["issues"]})

    # 1.10 loads summary 与 rows 复算一致
    sum_issues = []
    for tag, rows_stats in (("batchA", A), ("batchB", B)):
        sm = (loads.get(tag) or {}).get("summary") or {}
        if not sm:
            sum_issues.append("%s 缺 summary" % tag)
            continue
        pairs = (("n_species", rows_stats["n_species"]),
                 ("molecules", rows_stats["molecules"]),
                 ("atoms", rows_stats["atoms"]))
        for k, v in pairs:
            if k in sm and sm[k] != v:
                sum_issues.append("%s.%s summary=%r 复算=%r" % (tag, k, sm[k], v))
        if "element_atoms" in sm:
            for e in ELEMS:
                if int(sm["element_atoms"].get(e, -1)) != rows_stats["element_atoms"][e]:
                    sum_issues.append("%s.element_atoms[%s] summary=%r 复算=%d"
                                      % (tag, e, sm["element_atoms"].get(e),
                                         rows_stats["element_atoms"][e]))
        if "valence_atoms" in sm:
            for k in ("v3", "v2", "v1"):
                if int(sm["valence_atoms"].get(k, -1)) != rows_stats["valence_atoms"][k]:
                    sum_issues.append("%s.valence_atoms[%s] summary=%r 复算=%d"
                                      % (tag, k, sm["valence_atoms"].get(k),
                                         rows_stats["valence_atoms"][k]))
        if "valence_shares" in sm:
            for i, k in enumerate(("v3", "v2", "v1")):
                if abs(float(sm["valence_shares"][i]) - rows_stats["valence_shares"][i]) > 0.0003:
                    sum_issues.append("%s.valence_shares[%d] 差 >3e-4" % (tag, i))
        if "max_valence_deviation_pp" in sm:
            dev = max(abs(s - 1.0 / 3.0) for s in rows_stats["valence_shares"]) * 100.0
            if abs(float(sm["max_valence_deviation_pp"]) - dev) > 0.01:
                sum_issues.append("%s.max_valence_deviation_pp 记录=%r 复算=%.4f"
                                  % (tag, sm["max_valence_deviation_pp"], dev))
        if "max_element_deviation_pp" in sm:
            dev = max(abs(s - 1.0 / 9.0) for s in rows_stats["element_shares"].values()) * 100.0
            if abs(float(sm["max_element_deviation_pp"]) - dev) > 0.01:
                sum_issues.append("%s.max_element_deviation_pp 记录=%r 复算=%.4f"
                                  % (tag, sm["max_element_deviation_pp"], dev))
    if sum_issues:
        ck.sub("1.10", "loads summary 与 rows 复算一致", "FAIL",
               "；".join(sum_issues[:8]), {"issues": sum_issues[:8]})
    else:
        ck.sub("1.10", "loads summary 与 rows 复算一致", "PASS",
               "batchA/batchB summary 的 species/分子/原子/元素/价数统计均与 rows 复算一致")

    return vals


def check_group2(ck, loads, RA, SA, RB, SB):
    ck.begin(2, "质量/元素守恒")
    if not loads or not RA:
        ck.skip_rest("t62_loads.json 或 t62_phaseA_result.json 缺失")
        return
    A = analyze_batch((loads.get("batchA") or {}).get("rows") or [])
    B = analyze_batch((loads.get("batchB") or {}).get("rows") or [])
    cA = comp_stats(RA["comp"])
    cB = comp_stats(RB["comp"]) if RB else None

    # 2.1 phaseA 初始装载 == batchA
    cfg = RA["config"]
    ip, ia = cfg.get("initial_particles"), cfg.get("initial_atoms")
    ok = (ip == A["molecules"] and ia == A["atoms"])
    ck.sub("2.1", "phaseA 初始粒子/原子 == batchA 投料",
           "PASS" if ok else "FAIL",
           "config.initial_particles=%r（batchA=%d）；initial_atoms=%r（batchA=%d）"
           % (ip, A["molecules"], ia, A["atoms"]),
           {"initial_particles": ip, "batchA_molecules": A["molecules"],
            "initial_atoms": ia, "batchA_atoms": A["atoms"]})

    # 2.2 phaseA load_spec == batchA rows
    spec = RA["load_spec"]
    rows = (loads.get("batchA") or {}).get("rows") or []
    bad = []
    if len(spec) != len(rows):
        bad.append("load_spec 长度 %d ≠ rows 长度 %d" % (len(spec), len(rows)))
    for i, (sr, rr) in enumerate(zip(spec, rows)):
        if sr.get("formula") != rr.get("formula") or sr.get("count") != rr.get("count"):
            bad.append("第%d项 spec=(%r,%r) rows=(%r,%r)"
                       % (i, sr.get("formula"), sr.get("count"),
                          rr.get("formula"), rr.get("count")))
            if len(bad) >= 5:
                break
    ck.sub("2.2", "phaseA load_spec 与 batchA rows 一致",
           "PASS" if not bad else "FAIL",
           "共 %d 项%s" % (len(rows), "" if not bad else "；" + "；".join(bad[:5])),
           {"spec_len": len(spec), "rows_len": len(rows),
            "issues": bad[:5]})

    # 2.3 phaseA 终态分子数
    sm = RA["summary"]
    ok = (sm.get("final_N") == cA["molecules"])
    ck.sub("2.3", "phaseA 终态分子数 == Σfinal_composition.count == summary.final_N",
           "PASS" if ok else "FAIL",
           "summary.final_N=%r；Σcount=%d" % (sm.get("final_N"), cA["molecules"]),
           {"final_N": sm.get("final_N"), "comp_molecules": cA["molecules"]})

    # 2.4 phaseA 终态原子数
    ok = (sm.get("final_atoms") == cA["atoms"] and cA["atoms"] == A["atoms"])
    ck.sub("2.4", "phaseA 终态原子数 == Σcount*atoms == batchA 原子数 == summary.final_atoms",
           "PASS" if ok else "FAIL",
           "summary.final_atoms=%r；Σcomp=%d；batchA=%d"
           % (sm.get("final_atoms"), cA["atoms"], A["atoms"]),
           {"final_atoms": sm.get("final_atoms"), "comp_atoms": cA["atoms"],
            "batchA_atoms": A["atoms"]})

    # 2.5 phaseA 逐元素守恒
    diff = dict_diff(cA["element_atoms"], A["element_atoms"], ELEMS)
    ck.sub("2.5", "phaseA 终态逐元素原子数 == batchA",
           "PASS" if not diff else "FAIL",
           "逐元素一致" if not diff else "差异: %s" % json.dumps(diff, ensure_ascii=False),
           {"diff": diff, "final": cA["element_atoms"],
            "expected": A["element_atoms"]})

    # 2.6 phaseA time_series 末行
    issue = ts_last_issue(RA)
    ck.sub("2.6", "phaseA time_series 末行 N/原子数 == summary", issue[0],
           issue[1], issue[2])

    # 2.7 stateA 与 phaseA 结果一致
    if SA is None:
        ck.sub("2.7", "stateA 与 phaseA 结果一致", "SKIP", "t62_stateA.json 缺失")
    else:
        st, det, vals = state_match(SA, RA["comp"], sm)
        ck.sub("2.7", "stateA 与 phaseA 结果一致（总数/组成/守恒）", st, det, vals)

    if RB is None:
        for sid, nm in (
                ("2.8", "phaseB 初始装载 == stateA + batchB"),
                ("2.9", "phaseB seed_state 与 stateA 一致"),
                ("2.10", "phaseB load_spec 与 batchB 一致"),
                ("2.11", "phaseB 终态分子数守恒"),
                ("2.12", "phaseB 终态原子数守恒"),
                ("2.13", "phaseB 逐元素 == phaseA 终态 + batchB"),
                ("2.14", "phaseB time_series 末行 == summary"),
                ("2.15", "stateB 与 phaseB 结果一致")):
            ck.sub(sid, nm, "PENDING",
                   "PENDING：t62_phaseB_result.json / t62_stateB.json 尚未生成，"
                   "待数据齐全后补验")
        return

    bcfg = RB["config"]
    base_mol = SA["total_molecules"] if SA else cA["molecules"]
    base_at = SA["total_atoms"] if SA else cA["atoms"]
    exp_p = base_mol + B["molecules"]
    exp_a = base_at + B["atoms"]
    ok = (bcfg.get("initial_particles") == exp_p and
          bcfg.get("initial_atoms") == exp_a)
    ck.sub("2.8", "phaseB 初始装载 == stateA + batchB",
           "PASS" if ok else "FAIL",
           "config.initial_particles=%r（期望 %d+%d=%d）；"
           "initial_atoms=%r（期望 %d+%d=%d）"
           % (bcfg.get("initial_particles"), base_mol, B["molecules"], exp_p,
              bcfg.get("initial_atoms"), base_at, B["atoms"], exp_a),
           {"initial_particles": bcfg.get("initial_particles"),
            "expected_particles": exp_p,
            "initial_atoms": bcfg.get("initial_atoms"),
            "expected_atoms": exp_a})

    seed = RB.get("seed_state_summary") or {}
    seed_n = bcfg.get("seed_initial_count")
    exp_base = (SA["total_molecules"], SA["total_atoms"]) if SA else (None, None)
    issues = []
    if seed.get("total_molecules") != exp_base[0]:
        issues.append("seed_state_summary.total_molecules=%r ≠ stateA=%r"
                      % (seed.get("total_molecules"), exp_base[0]))
    if seed.get("total_atoms") != exp_base[1]:
        issues.append("seed_state_summary.total_atoms=%r ≠ stateA=%r"
                      % (seed.get("total_atoms"), exp_base[1]))
    if seed_n != exp_base[0]:
        issues.append("config.seed_initial_count=%r ≠ stateA 分子数=%r"
                      % (seed_n, exp_base[0]))
    ck.sub("2.9", "phaseB seed_state_summary / seed_initial_count == stateA",
           "FAIL" if issues else "PASS",
           "一致" if not issues else "；".join(issues),
           {"seed_state_summary": seed, "seed_initial_count": seed_n})

    bad = []
    specB = RB["load_spec"]
    rowsB = (loads.get("batchB") or {}).get("rows") or []
    if len(specB) != len(rowsB):
        bad.append("load_spec 长度 %d ≠ rows 长度 %d" % (len(specB), len(rowsB)))
    for i, (sr, rr) in enumerate(zip(specB, rowsB)):
        if sr.get("formula") != rr.get("formula") or sr.get("count") != rr.get("count"):
            bad.append("第%d项 spec=(%r,%r) rows=(%r,%r)"
                       % (i, sr.get("formula"), sr.get("count"),
                          rr.get("formula"), rr.get("count")))
            if len(bad) >= 5:
                break
    ck.sub("2.10", "phaseB load_spec 与 batchB rows 一致",
           "PASS" if not bad else "FAIL",
           "共 %d 项%s" % (len(rowsB), "" if not bad else "；" + "；".join(bad[:5])),
           {"issues": bad[:5]})

    ok = (RB["summary"].get("final_N") == cB["molecules"])
    ck.sub("2.11", "phaseB 终态分子数 == Σfinal_composition.count == summary.final_N",
           "PASS" if ok else "FAIL",
           "summary.final_N=%r；Σcount=%d"
           % (RB["summary"].get("final_N"), cB["molecules"]),
           {"final_N": RB["summary"].get("final_N"),
            "comp_molecules": cB["molecules"]})

    ok = (RB["summary"].get("final_atoms") == cB["atoms"] and
          cB["atoms"] == bcfg.get("initial_atoms"))
    ck.sub("2.12", "phaseB 终态原子数 == Σcount*atoms == initial_atoms == summary.final_atoms",
           "PASS" if ok else "FAIL",
           "summary.final_atoms=%r；Σcomp=%d；initial_atoms=%r"
           % (RB["summary"].get("final_atoms"), cB["atoms"],
              bcfg.get("initial_atoms")),
           {"final_atoms": RB["summary"].get("final_atoms"),
            "comp_atoms": cB["atoms"],
            "initial_atoms": bcfg.get("initial_atoms")})

    exp_e = {e: cA["element_atoms"][e] + B["element_atoms"][e] for e in ELEMS}
    diff = dict_diff(cB["element_atoms"], exp_e, ELEMS)
    ck.sub("2.13", "phaseB 终态逐元素 == phaseA 终态 + batchB",
           "PASS" if not diff else "FAIL",
           "逐元素一致" if not diff else "差异: %s" % json.dumps(diff, ensure_ascii=False),
           {"diff": diff, "final": cB["element_atoms"], "expected": exp_e})

    issue = ts_last_issue(RB)
    ck.sub("2.14", "phaseB time_series 末行 N/原子数 == summary", issue[0],
           issue[1], issue[2])

    if SB is None:
        ck.sub("2.15", "stateB 与 phaseB 结果一致", "SKIP", "t62_stateB.json 缺失")
    else:
        st, det, vals = state_match(SB, RB["comp"], RB["summary"])
        ck.sub("2.15", "stateB 与 phaseB 结果一致（总数/组成/守恒）", st, det, vals)


def ts_last_issue(R):
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


def state_match(state, comp, summary):
    """state 文件与结果 final_composition/summary 的一致性。"""
    issues = []
    vals = {"state_total_molecules": state["total_molecules"],
            "state_total_atoms": state["total_atoms"],
            "sum_counts": state["sum_counts"],
            "sum_atoms": state["sum_atoms"]}
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
    sc = state_composition(state)
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


def check_group3(ck, loads, RA, RB):
    ck.begin(3, "价数原子守恒与 ≈1/3")
    if not loads or not RA:
        ck.skip_rest("loads 或 phaseA 结果缺失")
        return
    A = analyze_batch((loads.get("batchA") or {}).get("rows") or [])
    B = analyze_batch((loads.get("batchB") or {}).get("rows") or [])
    cA = comp_stats(RA["comp"])
    cB = comp_stats(RB["comp"]) if RB else None
    keys = ("v3", "v2", "v1")
    expA = A["valence_atoms"]
    diffA = dict_diff(cA["valence_atoms"], expA, keys)
    ck.sub("3.1", "phaseA 终态 v3:v2:v1 原子数 == batchA 初始",
           "PASS" if not diffA else "FAIL",
           "终态 %s；batchA %s" % (cA["valence_atoms"], expA)
           if not diffA else "差异: %s" % json.dumps(diffA, ensure_ascii=False),
           {"diff": diffA, "final": cA["valence_atoms"], "expected": expA})

    devA = max(abs(s - 1.0 / 3.0) for s in cA["valence_shares"]) * 100.0
    ok = devA <= 1.0
    ck.sub("3.2", "phaseA 终态价数占比仍 ≈1/3（≤1pp）", "PASS" if ok else "FAIL",
           "占比=%s，最大偏差=%.3fpp"
           % ([fnum(x) for x in cA["valence_shares"]], devA),
           {"shares": cA["valence_shares"], "max_dev_pp": round(devA, 4)})

    if cB is None:
        ck.sub("3.3", "phaseB 终态价数 == phaseA 终态 + batchB", "PENDING",
               "PENDING：phaseB 结果尚未生成，待补验")
        ck.sub("3.4", "phaseB 终态价数占比仍 ≈1/3", "PENDING",
               "PENDING：phaseB 结果尚未生成，待补验")
    else:
        expB = {k: cA["valence_atoms"][k] + B["valence_atoms"][k] for k in keys}
        diffB = dict_diff(cB["valence_atoms"], expB, keys)
        ck.sub("3.3", "phaseB 终态价数 == phaseA 终态 + batchB",
               "PASS" if not diffB else "FAIL",
               "终态 %s；期望 %s" % (cB["valence_atoms"], expB)
               if not diffB else "差异: %s" % json.dumps(diffB, ensure_ascii=False),
               {"diff": diffB, "final": cB["valence_atoms"], "expected": expB})
        devB = max(abs(s - 1.0 / 3.0) for s in cB["valence_shares"]) * 100.0
        ok = devB <= 1.0
        ck.sub("3.4", "phaseB 终态价数占比仍 ≈1/3（≤1pp）", "PASS" if ok else "FAIL",
               "占比=%s，最大偏差=%.3fpp"
               % ([fnum(x) for x in cB["valence_shares"]], devB),
               {"shares": cB["valence_shares"], "max_dev_pp": round(devB, 4)})

    # 3.5 价数原子总数 == 总原子数
    issues = []
    for tag, c in (("phaseA", cA), ("phaseB", cB)):
        if c is None:
            continue
        if sum(c["valence_atoms"].values()) != c["atoms"]:
            issues.append("%s Σvalence=%d ≠ atoms=%d"
                          % (tag, sum(c["valence_atoms"].values()), c["atoms"]))
    ck.sub("3.5", "价数原子总数 == 总原子数（A/B 终态）",
           "FAIL" if issues else ("PENDING" if cB is None else "PASS"),
           ("一致" if not issues else "；".join(issues))
           + ("；phaseB 数据 PENDING（待补验）" if cB is None else ""))


def check_group4(ck, loads, ctl, tol_min, tol_frac):
    ck.begin(4, "无化学对照（500 次穿越要求）")
    if not ctl:
        ck.skip_rest("t62_control_A.json 缺失")
        return
    A = analyze_batch((loads.get("batchA") or {}).get("rows") or []) if loads else None
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
    if A is not None:
        if cfg.get("n_particles") != A["molecules"]:
            issues.append("config.n_particles=%r ≠ batchA 分子数=%d"
                          % (cfg.get("n_particles"), A["molecules"]))
        if st.get("n") != cfg.get("n_particles"):
            issues.append("stats.n=%r ≠ config.n_particles=%r"
                          % (st.get("n"), cfg.get("n_particles")))
        ls = cfg.get("load_spec") or []
        if len(ls) != A["n_species"]:
            issues.append("load_spec 长度=%d ≠ batchA 物种数=%d"
                          % (len(ls), A["n_species"]))
        else:
            rowsA = (loads.get("batchA") or {}).get("rows") or []
            for i, (sr, rr) in enumerate(zip(ls, rowsA)):
                if sr.get("formula") != rr.get("formula") or \
                        sr.get("count") != rr.get("count"):
                    issues.append("load_spec 第%d项与 batchA rows 不同" % i)
                    break
    sum_bs = sum(int(rec.get("n", 0)) for rec in bs.values())
    if st.get("n") is not None and sum_bs != st.get("n"):
        issues.append("Σby_size.n=%d ≠ stats.n=%r" % (sum_bs, st.get("n")))
    ck.sub("4.5", "对照组装载与 batchA 一致且统计分组完备",
           "FAIL" if issues else "PASS",
           "一致" if not issues else "；".join(issues),
           {"issues": issues, "n_particles": cfg.get("n_particles"),
            "stats_n": st.get("n"), "sum_by_size_n": sum_bs})

    ck.sub("4.6", "对照路径统计概览", "INFO",
           "min=%.1f p1=%.1f median=%.1f p95=%.1f max=%.1f mean=%.1f"
           % (st.get("min"), st.get("p1") or 0, st.get("median") or 0,
              st.get("p95") or 0, st.get("max") or 0, st.get("mean") or 0),
           {"stats": st})


def check_group5(ck, RA, RB, cap_main):
    ck.begin(5, "反应判定自洽")
    phases = [("phaseA", RA), ("phaseB", RB)]
    if not RA:
        ck.skip_rest("phaseA 结果缺失")
        return

    def pending_tags(vals):
        return [t for t, v in vals.items()
                if isinstance(v, dict) and v.get("pending")]

    def status_of(issues, vals):
        if issues:
            return "FAIL"
        return "PENDING" if pending_tags(vals) else "PASS"

    def detail_of(parts, issues, vals):
        base = "；".join([p for p in parts if p])
        if issues:
            base = (base + "；" if base else "") + "异常: " + "；".join(issues)
        pend = pending_tags(vals)
        if pend:
            base = (base + "；" if base else "") + \
                   "%s 数据 PENDING（待补验）" % "/".join(pend)
        return base or "一致"

    # 5.1 类型齐全/非负
    issues = []
    vals = {}
    for tag, R in phases:
        if R is None:
            vals[tag] = {"pending": True}
            continue
        rc = R["summary"].get("reaction_counts") or {}
        vals[tag] = {"reaction_counts": rc,
                     "missing_types": [k for k in RC_TYPES if k not in rc]}
        extra = set(rc) - set(RC_TYPES)
        if extra:
            issues.append("%s 出现意外判定类型 %s" % (tag, sorted(extra)))
        for k in RC_TYPES:
            v = rc.get(k, 0)
            if not isinstance(v, int) or v < 0:
                issues.append("%s.reaction_counts[%s]=%r 非负整数" % (tag, k, v))
    ck.sub("5.1", "reaction_counts 类型齐全且非负", status_of(issues, vals),
           detail_of([], issues, vals), {"phases": vals})

    # 5.2 逐类型累计自洽（time_series d_* 求和 == reaction_counts == 末行累计）
    issues = []
    vals = {}
    for tag, R in phases:
        if R is None:
            vals[tag] = {"pending": True}
            continue
        rc = R["summary"].get("reaction_counts") or {}
        ts = R.get("ts") or []
        if not ts:
            vals[tag] = {"note": "time_series 为空"}
            issues.append("%s time_series 为空" % tag)
            continue
        last = ts[-1]
        per = {}
        for k in RC_TYPES:
            s = sum((row.get("d_" + k) or 0) for row in ts)
            cum = last.get(k)
            per[k] = {"sum_delta": s, "summary": rc.get(k, 0),
                      "last_cumulative": cum}
            if s != rc.get(k, 0) or cum != rc.get(k, 0):
                issues.append("%s[%s] Σd=%r summary=%r 末行累计=%r"
                              % (tag, k, s, rc.get(k, 0), cum))
        vals[tag] = per
    ck.sub("5.2", "逐类型累计判定数自洽（Σd_* == reaction_counts == 末行累计）",
           status_of(issues, vals), detail_of([], issues, vals),
           {"phases": vals})

    # 5.3 合计
    issues = []
    vals = {}
    for tag, R in phases:
        if R is None:
            vals[tag] = {"pending": True}
            continue
        rc = R["summary"].get("reaction_counts") or {}
        total_rc = sum(int(rc.get(k, 0)) for k in RC_TYPES)
        ts = R.get("ts") or []
        total_d = 0
        if ts:
            total_d = sum(sum((row.get("d_" + k) or 0) for row in ts)
                          for k in RC_TYPES)
        vals[tag] = {"sum_reaction_counts": total_rc, "sum_deltas": total_d}
        if total_rc != total_d:
            issues.append("%s Σreaction_counts=%d ≠ Σd=%d"
                          % (tag, total_rc, total_d))
    ck.sub("5.3", "四类判定数之和 == 碰撞判定总数（Σd_*）",
           status_of(issues, vals), detail_of([], issues, vals),
           {"phases": vals})

    # 5.4 capped 占比 <1%
    issues = []
    vals = {}
    parts = []
    for tag, R in phases:
        if R is None:
            vals[tag] = {"pending": True}
            continue
        rc = R["summary"].get("reaction_counts") or {}
        total = sum(int(rc.get(k, 0)) for k in RC_TYPES)
        frac = (rc.get("capped", 0) / total) if total else None
        vals[tag] = {"capped": rc.get("capped", 0), "total": total,
                     "frac": frac}
        if frac is None:
            issues.append("%s capped 占比不可计算（判定总数=0）" % tag)
        else:
            parts.append("%s capped=%r/%r (%.4f%%)"
                         % (tag, rc.get("capped", 0), total, 100.0 * frac))
            if frac >= 0.01:
                issues.append("%s capped 占比=%.4f%% ≥1%%" % (tag, 100.0 * frac))
    ck.sub("5.4", "capped 占比 <1%", status_of(issues, vals),
           detail_of(parts, issues, vals), {"phases": vals})

    # 5.5 events_total 与蓄水池抽样
    issues = []
    vals = {}
    parts = []
    for tag, R in phases:
        if R is None:
            vals[tag] = {"pending": True}
            continue
        sm = R["summary"]
        ts = R.get("ts") or []
        et = sm.get("events_total")
        n_samp = R["events"]["n"]
        last_et = ts[-1].get("events_total") if ts else None
        exp_cap = min(et, EVENT_RESERVOIR) if isinstance(et, int) else None
        vals[tag] = {"events_total": et, "last_ts_events_total": last_et,
                     "event_samples": n_samp,
                     "expected_samples": exp_cap}
        parts.append("%s events_total=%r 末行=%r 抽样数=%d 期望=%r"
                     % (tag, et, last_et, n_samp, exp_cap))
        if last_et != et:
            issues.append("%s 末行 events_total=%r ≠ summary=%r"
                          % (tag, last_et, et))
        if not isinstance(et, int) or et < n_samp:
            issues.append("%s events_total=%r < 抽样数=%d" % (tag, et, n_samp))
        elif n_samp != exp_cap:
            issues.append("%s 抽样数=%d ≠ min(events_total,%d)=%r（蓄水池异常）"
                          % (tag, n_samp, EVENT_RESERVOIR, exp_cap))
    ck.sub("5.5", "events_total 与蓄水池抽样一致", status_of(issues, vals),
           detail_of(parts, issues, vals), {"phases": vals})

    # 5.6 抽样事件逐条守恒
    issues = []
    vals = {}
    parts = []
    for tag, R in phases:
        if R is None:
            vals[tag] = {"pending": True}
            continue
        ev = R["events"]
        vals[tag] = {k: ev.get(k) for k in (
            "n", "atom_conserv_bad", "valence_conserv_bad", "parse_bad",
            "empty_products", "type_counts")}
        parts.append("%s n=%d atom_bad=%d valence_bad=%d parse_bad=%d empty=%d"
                     % (tag, ev.get("n", 0), ev.get("atom_conserv_bad", 0),
                        ev.get("valence_conserv_bad", 0),
                        ev.get("parse_bad", 0), ev.get("empty_products", 0)))
        for k in ("atom_conserv_bad", "valence_conserv_bad", "parse_bad",
                  "empty_products"):
            if ev.get(k):
                issues.append("%s %s=%d" % (tag, k, ev[k]))
    ck.sub("5.6", "抽样事件逐条原子/价数守恒（无空产物）",
           status_of(issues, vals), detail_of(parts, issues, vals),
           {"phases": vals,
            "bad_examples": (RA["events"].get("bad_examples", []) if RA else [])})

    # 5.7 ΔN 与抽样事件一致性（蓄水池均匀抽样）
    issues = []
    vals = {}
    parts = []
    for tag, R in phases:
        if R is None:
            vals[tag] = {"pending": True}
            continue
        ev = R["events"]
        pl = ev.get("product_lens") or []
        et = R["summary"].get("events_total")
        n0 = R["config"].get("initial_particles")
        nf = R["summary"].get("final_N")
        if not pl or not isinstance(et, int) or et <= 0 or n0 is None or nf is None:
            vals[tag] = {"note": "数据不足"}
            continue
        exact = (nf - n0) / float(et)
        mean = sum(pl) / float(len(pl)) - 2.0
        var = sum((x - 2.0 - mean) ** 2 for x in pl) / float(len(pl))
        se = (var / len(pl)) ** 0.5 if len(pl) else 0.0
        diff = abs(mean - exact)
        tol = max(8.0 * se, 1e-9)
        vals[tag] = {"dN": nf - n0, "events_total": et,
                     "exact_mean_delta": round(exact, 6),
                     "sample_mean_delta": round(mean, 6),
                     "se": round(se, 6), "diff": round(diff, 6),
                     "tolerance": round(tol, 6),
                     "sample_n": len(pl)}
        parts.append("%s ΔN=%d 精确均值=%.5f 抽样均值=%.5f |差|=%.5f 容差(8SE)=%.5f"
                     % (tag, nf - n0, exact, mean, diff, tol))
        if diff > tol:
            issues.append("%s 抽样 ΔN 均值=%.5f 与精确 %.5f 差 %.5f > 8SE=%.5f"
                          % (tag, mean, exact, diff, tol))
    ck.sub("5.7", "ΔN 与抽样事件一致（蓄水池抽样均匀性）",
           status_of(issues, vals), detail_of(parts, issues, vals),
           {"phases": vals})

    # 5.8 终态最大原子数 ≤ cap
    issues = []
    vals = {}
    parts = []
    for tag, R in phases:
        if R is None:
            vals[tag] = {"pending": True}
            continue
        cap = R["config"].get("max_reaction_atoms")
        c = comp_stats(R["comp"])
        ts = R.get("ts") or []
        ts_max = max((row.get("max_atoms") or 0) for row in ts) if ts else None
        top_max = max((len(v["atoms"]) for v in R["top"].values()), default=None)
        vals[tag] = {"cap": cap, "comp_max_atoms": c["max_atoms"],
                     "ts_max_atoms": ts_max, "top_max_atoms": top_max}
        parts.append("%s cap=%r comp_max=%r ts_max=%r top_max=%r"
                     % (tag, cap, c["max_atoms"], ts_max, top_max))
        if cap is None:
            issues.append("%s 无 max_reaction_atoms" % tag)
            continue
        for k in ("comp_max_atoms", "ts_max_atoms", "top_max_atoms"):
            v = vals[tag][k]
            if v is not None and v > cap:
                issues.append("%s %s=%d > cap=%d" % (tag, k, v, cap))
    ck.sub("5.8", "终态最大原子数 ≤ cap", status_of(issues, vals),
           detail_of(parts, issues, vals), {"phases": vals})

    # 5.9 decomp_events 与 time_series 一致
    issues = []
    vals = {}
    parts = []
    for tag, R in phases:
        if R is None:
            vals[tag] = {"pending": True}
            continue
        ts = R.get("ts") or []
        last = ts[-1] if ts else {}
        vals[tag] = {"summary_decomp": R["summary"].get("decomp_events"),
                     "ts_decomp": last.get("decomp")}
        parts.append("%s summary=%r ts=%r"
                     % (tag, R["summary"].get("decomp_events"),
                        last.get("decomp")))
        if R["summary"].get("decomp_events") != last.get("decomp"):
            issues.append("%s summary.decomp_events=%r ≠ 末行 decomp=%r"
                          % (tag, R["summary"].get("decomp_events"),
                             last.get("decomp")))
    ck.sub("5.9", "decomp_events 与 time_series 一致",
           status_of(issues, vals), detail_of(parts, issues, vals),
           {"phases": vals})

    # 5.10 cap 主实验期望值
    if cap_main is not None:
        caps = {tag: (R["config"].get("max_reaction_atoms") if R else None)
                for tag, R in phases}
        vals = {tag: {"cap": caps[tag]} for tag in caps}
        if RB is None:
            vals["phaseB"] = {"pending": True}
        issues = []
        for tag, v in caps.items():
            if v is not None and v != cap_main:
                issues.append("%s cap=%r ≠ %r" % (tag, v, cap_main))
        ck.sub("5.10", "主实验 cap == %r" % (cap_main,),
               status_of(issues, vals),
               detail_of(["A/B cap=%r" % (caps,)], issues, vals),
               {"caps": caps})


def check_group6(ck, loads, RA, RB, HFA, HFB, SAh, SBh, cap_main, cap_hf):
    ck.begin(6, "cap%r vs cap%r 对比" % (cap_main, cap_hf))
    if HFA is None or HFB is None:
        ck.sub("6.0", "cap%r 高保真对照" % cap_hf, "PENDING",
               "PENDING：t62_phaseA_hf_result.json / t62_phaseB_hf_result.json "
               "尚未生成，cap%r 对比待数据齐全后补验" % cap_hf,
               {"phaseA_hf_exists": HFA is not None,
                "phaseB_hf_exists": HFB is not None})
        return
    if not loads or not RA or not RB:
        ck.skip_rest("主实验结果或 loads 缺失，无法对比")
        return
    A = analyze_batch((loads.get("batchA") or {}).get("rows") or [])
    B = analyze_batch((loads.get("batchB") or {}).get("rows") or [])
    cA = comp_stats(RA["comp"])
    cB = comp_stats(RB["comp"])
    hA = comp_stats(HFA["comp"])
    hB = comp_stats(HFB["comp"])
    ELEMS_KEYS = ("v3", "v2", "v1")

    # 6.1 cap 值
    caps = {"mainA": RA["config"].get("max_reaction_atoms"),
            "mainB": RB["config"].get("max_reaction_atoms"),
            "hfA": HFA["config"].get("max_reaction_atoms"),
            "hfB": HFB["config"].get("max_reaction_atoms")}
    ok = (all(v == cap_main for v in (caps["mainA"], caps["mainB"])) and
          all(v == cap_hf for v in (caps["hfA"], caps["hfB"])))
    ck.sub("6.1", "主实验 cap==%r、hf cap==%r" % (cap_main, cap_hf),
           "PASS" if ok else "FAIL", "实测 cap=%s" % (caps,), {"caps": caps})

    # 6.2 hf phaseA 守恒
    issues = []
    if HFA["config"].get("initial_particles") != A["molecules"]:
        issues.append("initial_particles=%r ≠ batchA=%d"
                      % (HFA["config"].get("initial_particles"), A["molecules"]))
    if HFA["config"].get("initial_atoms") != A["atoms"]:
        issues.append("initial_atoms=%r ≠ batchA=%d"
                      % (HFA["config"].get("initial_atoms"), A["atoms"]))
    if HFA["summary"].get("final_N") != hA["molecules"]:
        issues.append("final_N=%r ≠ Σcount=%d"
                      % (HFA["summary"].get("final_N"), hA["molecules"]))
    if HFA["summary"].get("final_atoms") != A["atoms"] or hA["atoms"] != A["atoms"]:
        issues.append("final_atoms=%r / Σcomp=%d ≠ batchA=%d"
                      % (HFA["summary"].get("final_atoms"), hA["atoms"], A["atoms"]))
    diff = dict_diff(hA["element_atoms"], A["element_atoms"], ELEMS)
    if diff:
        issues.append("逐元素差异: %s" % json.dumps(diff, ensure_ascii=False))
    diff = dict_diff(hA["valence_atoms"], A["valence_atoms"], ELEMS_KEYS)
    if diff:
        issues.append("价数差异: %s" % json.dumps(diff, ensure_ascii=False))
    ck.sub("6.2", "hf phaseA 质量/元素/价数守恒 == batchA",
           "FAIL" if issues else "PASS",
           "一致" if not issues else "；".join(issues),
           {"issues": issues, "final_N": HFA["summary"].get("final_N"),
            "final_atoms": HFA["summary"].get("final_atoms"),
            "formula_species": hA["n_formula"], "max_atoms": hA["max_atoms"]})

    # 6.3 hf phaseB 初始/终态守恒
    issues = []
    seed = HFB.get("seed_state_summary") or {}
    base_mol = seed.get("total_molecules")
    base_at = seed.get("total_atoms")
    if base_mol is None or base_at is None:
        issues.append("hf phaseB 缺 seed_state_summary")
    else:
        if base_mol != HFA["summary"].get("final_N"):
            issues.append("seed.total_molecules=%r ≠ hfA.final_N=%r"
                          % (base_mol, HFA["summary"].get("final_N")))
        if base_at != HFA["summary"].get("final_atoms"):
            issues.append("seed.total_atoms=%r ≠ hfA.final_atoms=%r"
                          % (base_at, HFA["summary"].get("final_atoms")))
        exp_p = base_mol + B["molecules"]
        exp_a = base_at + B["atoms"]
        if HFB["config"].get("initial_particles") != exp_p:
            issues.append("initial_particles=%r ≠ %d+%d=%d"
                          % (HFB["config"].get("initial_particles"),
                             base_mol, B["molecules"], exp_p))
        if HFB["config"].get("initial_atoms") != exp_a:
            issues.append("initial_atoms=%r ≠ %d+%d=%d"
                          % (HFB["config"].get("initial_atoms"),
                             base_at, B["atoms"], exp_a))
    if HFB["summary"].get("final_N") != hB["molecules"]:
        issues.append("hfB final_N=%r ≠ Σcount=%d"
                      % (HFB["summary"].get("final_N"), hB["molecules"]))
    if HFB["summary"].get("final_atoms") != hB["atoms"]:
        issues.append("hfB final_atoms=%r ≠ Σcomp=%d"
                      % (HFB["summary"].get("final_atoms"), hB["atoms"]))
    if hB["atoms"] != hA["atoms"] + B["atoms"]:
        issues.append("hfB Σcomp atoms=%d ≠ hfA(%d)+batchB(%d)"
                      % (hB["atoms"], hA["atoms"], B["atoms"]))
    exp_e = {e: hA["element_atoms"][e] + B["element_atoms"][e] for e in ELEMS}
    diff = dict_diff(hB["element_atoms"], exp_e, ELEMS)
    if diff:
        issues.append("逐元素差异: %s" % json.dumps(diff, ensure_ascii=False))
    exp_v = {k: hA["valence_atoms"][k] + B["valence_atoms"][k]
             for k in ELEMS_KEYS}
    diff = dict_diff(hB["valence_atoms"], exp_v, ELEMS_KEYS)
    if diff:
        issues.append("价数差异: %s" % json.dumps(diff, ensure_ascii=False))
    ck.sub("6.3", "hf phaseB 初始 == hfA+ batchB、终态守恒",
           "FAIL" if issues else "PASS",
           "一致" if not issues else "；".join(issues),
           {"issues": issues, "seed_state_summary": seed,
            "hfB_final_N": HFB["summary"].get("final_N"),
            "hfB_final_atoms": HFB["summary"].get("final_atoms")})

    # 6.4 capped 占比对比
    def capped_frac(R):
        rc = R["summary"].get("reaction_counts") or {}
        tot = sum(int(rc.get(k, 0)) for k in RC_TYPES)
        return (rc.get("capped", 0), tot,
                (rc.get("capped", 0) / tot) if tot else None)
    rows = {}
    for tag, mainR, hfR in (("A", RA, HFA), ("B", RB, HFB)):
        mc, mt, mf = capped_frac(mainR)
        hc, ht, hf = capped_frac(hfR)
        rows[tag] = {"main_capped": mc, "main_total": mt, "main_frac": mf,
                     "hf_capped": hc, "hf_total": ht, "hf_frac": hf,
                     "reduction_ratio": (mf / hf) if (mf and hf) else None}
    issues = []
    for tag, r in rows.items():
        if r["hf_frac"] is None or r["main_frac"] is None:
            issues.append("%s 判定总数缺失" % tag)
        elif not (r["hf_frac"] < r["main_frac"]):
            issues.append("%s hf capped 占比 %.5f%% 未低于主实验 %.5f%%"
                          % (tag, 100.0 * r["hf_frac"], 100.0 * r["main_frac"]))
        elif r["main_frac"] > 0 and r["hf_frac"] > 0.5 * r["main_frac"]:
            issues.append("%s hf capped 占比 %.5f%% 未显著低于主实验 %.5f%%（降幅<50%%）"
                          % (tag, 100.0 * r["hf_frac"], 100.0 * r["main_frac"]))
    ck.sub("6.4", "hf capped 占比显著低于 cap%r" % (cap_main,),
           "FAIL" if issues else "PASS",
           "；".join("%s: 主实验 %.5f%% → hf %.5f%%" %
                     (t, 100.0 * r["main_frac"], 100.0 * r["hf_frac"])
                     for t, r in rows.items()) if not issues else "；".join(issues),
           {"compare": rows})

    # 6.5 对比指标（结构数/最大原子数/≥39 原子数量）
    compare = {}
    issues = []
    for tag, mainC, hfC, mainName, hfName in (
            ("A", cA, hA, "cap40", "cap60"),
            ("B", cB, hB, "cap40", "cap60")):
        compare[tag] = {
            "main": {"formula_species": mainC["n_formula"],
                     "max_atoms": mainC["max_atoms"],
                     "n_ge39": mainC["count_ge39"]},
            "hf": {"formula_species": hfC["n_formula"],
                   "max_atoms": hfC["max_atoms"],
                   "n_ge39": hfC["count_ge39"]}}
        if hfC["max_atoms"] > cap_hf:
            issues.append("%s hf 最大原子数 %d > cap%r"
                          % (tag, hfC["max_atoms"], cap_hf))
    ck.sub("6.5", "cap40 vs cap60 终态结构数/最大原子数/≥39 原子数量对比",
           "FAIL" if issues else "PASS",
           "；".join("%s: 主实验 species=%d max=%d ≥39=%d；hf species=%d max=%d ≥39=%d"
                     % (t, compare[t]["main"]["formula_species"],
                        compare[t]["main"]["max_atoms"],
                        compare[t]["main"]["n_ge39"],
                        compare[t]["hf"]["formula_species"],
                        compare[t]["hf"]["max_atoms"],
                        compare[t]["hf"]["n_ge39"])
                     for t in ("A", "B")),
           {"compare": compare, "issues": issues})

    # 6.6 hf top 结构合法性
    issues = []
    for tag, hf in (("hfA", HFA), ("hfB", HFB)):
        for f, t in hf["top"].items():
            probs = validate_structure(f, t["atoms"], t["edges"], cap_hf)
            if probs:
                issues.append("%s %s: %s" % (tag, f, "; ".join(probs[:3])))
    ck.sub("6.6", "hf top 结构合法（价数填满/原子与公式一致）",
           "FAIL" if issues else "PASS",
           "全部合法（hfA %d 个，hfB %d 个）"
           % (len(HFA["top"]), len(HFB["top"]))
           if not issues else "；".join(issues[:8]),
           {"issues": issues[:8]})

    # 6.7 可选 hf state 文件一致性
    if SAh is None:
        ck.sub("6.7", "hf stateA 与 hf phaseA 结果一致（可选）", "INFO",
               "t62_stateA_hf.json 不存在，跳过（不在任务必需输入内）")
    else:
        st, det, vals = state_match(SAh, HFA["comp"], HFA["summary"])
        ck.sub("6.7", "hf stateA 与 hf phaseA 结果一致（可选）", st, det, vals)
    if SBh is None:
        ck.sub("6.8", "hf stateB 与 hf phaseB 结果一致（可选）", "INFO",
               "t62_stateB_hf.json 不存在，跳过（不在任务必需输入内）")
    else:
        st, det, vals = state_match(SBh, HFB["comp"], HFB["summary"])
        ck.sub("6.8", "hf stateB 与 hf phaseB 结果一致（可选）", st, det, vals)


def check_group7(ck, RA, RB, SA, SB):
    ck.begin(7, "终态表 sanity")
    if not RA:
        ck.skip_rest("phaseA 结果缺失")
        return

    # 7.1 final_composition atoms 字段
    issues = []
    vals = {}
    for tag, R in (("phaseA", RA), ("phaseB", RB)):
        if R is None:
            vals[tag] = {"pending": True}
            continue
        c = comp_stats(R["comp"])
        vals[tag] = {"n_formula": c["n_formula"],
                     "atoms_none": len(c["atoms_none"]),
                     "atoms_field_mismatch": len(c["atoms_field_mismatch"]),
                     "parse_errors": len(c["parse_errors"])}
        if c["atoms_field_mismatch"] or c["parse_errors"]:
            issues.append("%s 字段不一致=%d 解析错误=%d"
                          % (tag, len(c["atoms_field_mismatch"]),
                             len(c["parse_errors"])))
    pending = any(isinstance(v, dict) and v.get("pending")
                  for v in vals.values())
    status = "FAIL" if issues else ("PENDING" if pending else "PASS")
    det = "一致" if not issues else "；".join(issues)
    if pending:
        det += "；phaseB 数据 PENDING（待补验）"
    ck.sub("7.1", "final_composition.atoms 与公式原子数一致", status, det,
           {"phases": vals})

    # 7.2 top 结构合法性
    issues = []
    vals = {}
    for tag, R in (("phaseA", RA), ("phaseB", RB)):
        if R is None:
            vals[tag] = {"pending": True}
            continue
        cap = R["config"].get("max_reaction_atoms")
        bad = []
        for f, t in R["top"].items():
            problems = validate_structure(f, t["atoms"], t["edges"], cap)
            if problems:
                bad.append({"formula": f, "problems": problems[:3]})
        vals[tag] = {"n_top": len(R["top"]), "bad": bad}
        if bad:
            issues.append("%s top 非法结构 %d 个" % (tag, len(bad)))
    pending = any(isinstance(v, dict) and v.get("pending")
                  for v in vals.values())
    status = "FAIL" if issues else ("PENDING" if pending else "PASS")
    det = ("全部合法（phaseA %d 个，phaseB %d 个）"
           % (len(RA["top"]), len(RB["top"]) if RB else 0)
           if not issues else "；".join(issues))
    if pending:
        det += "；phaseB 数据 PENDING（待补验）"
    ck.sub("7.2", "final_top_structures atoms/edges 合法（价数填满、无重复原子/边）",
           status, det, {"phases": vals})

    # 7.3 state 全结构合法性
    issues = []
    vals = {}
    for tag, st in (("stateA", SA), ("stateB", SB)):
        if st is None:
            vals[tag] = {"pending": True}
            continue
        bad = []
        for m in st["molecules"]:
            problems = validate_structure(m["formula"], m["atoms"], m["edges"])
            if problems:
                bad.append({"formula": m["formula"], "problems": problems[:3]})
        vals[tag] = {"n_structures": len(st["molecules"]), "bad": bad[:8]}
        if bad:
            issues.append("%s 非法结构 %d 个" % (tag, len(bad)))
    pending = any(isinstance(v, dict) and v.get("pending")
                  for v in vals.values())
    if issues:
        status = "FAIL"
    elif pending:
        status = "PENDING"
    elif vals:
        status = "PASS"
    else:
        status = "SKIP"
    det = ("全部合法（stateA %d 种，stateB %d 种）"
           % (vals.get("stateA", {}).get("n_structures", 0),
              vals.get("stateB", {}).get("n_structures", 0))
           if status == "PASS" else
           ("；".join(issues) if issues else "state 文件 PENDING（待补验）"))
    ck.sub("7.3", "stateA/stateB 全部结构合法（atoms/edges/价数）", status,
           det, {"phases": vals})

    # 7.4 top 公式 ⊆ final_composition
    issues = []
    for tag, R in (("phaseA", RA), ("phaseB", RB)):
        if R is None:
            continue
        missing = [f for f in R["top"] if f not in R["comp"]]
        if missing:
            issues.append("%s top 中存在 final_composition 未收录公式: %s"
                          % (tag, missing[:5]))
    ck.sub("7.4", "top 结构公式均在 final_composition 中",
           "FAIL" if issues else ("PENDING" if RB is None else "PASS"),
           ("一致" if not issues else "；".join(issues))
           + ("；phaseB 数据 PENDING（待补验）" if RB is None else ""),
           {"issues": issues[:5]})

    # 7.5 未重建结构（atoms=None）计数
    none_cnt = {}
    for tag, R in (("phaseA", RA), ("phaseB", RB)):
        if R is None:
            continue
        c = comp_stats(R["comp"])
        none_cnt[tag] = {"n_formula": c["n_formula"],
                         "atoms_none": len(c["atoms_none"]),
                         "formulas": c["atoms_none"][:5]}
    ck.sub("7.5", "final_composition 无未重建结构（atoms=None）", "INFO",
           "；".join("%s: atoms=None %d/%d" %
                     (t, v["atoms_none"], v["n_formula"])
                     for t, v in none_cnt.items()), {"phases": none_cnt})


# ================================================================ 主流程
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="T62 独立验证脚本（只读 JSON，输出 t62_verify.json）")
    D = lambda name: os.path.join(BASE, name)
    ap.add_argument("--loads", default=D("t62_loads.json"))
    ap.add_argument("--a", "--phaseA", dest="a",
                    default=D("t62_phaseA_result.json"))
    ap.add_argument("--stateA", dest="stateA", default=D("t62_stateA.json"))
    ap.add_argument("--b", "--phaseB", dest="b",
                    default=D("t62_phaseB_result.json"))
    ap.add_argument("--stateB", dest="stateB", default=D("t62_stateB.json"))
    ap.add_argument("--control", default=D("t62_control_A.json"))
    ap.add_argument("--a_hf", "--phaseA_hf", dest="a_hf",
                    default=D("t62_phaseA_hf_result.json"))
    ap.add_argument("--b_hf", "--phaseB_hf", dest="b_hf",
                    default=D("t62_phaseB_hf_result.json"))
    ap.add_argument("--stateA_hf", dest="stateA_hf",
                    default=D("t62_stateA_hf.json"))
    ap.add_argument("--stateB_hf", dest="stateB_hf",
                    default=D("t62_stateB_hf.json"))
    ap.add_argument("--out", default=D("t62_verify.json"))
    ap.add_argument("--cap-main", type=int, default=40)
    ap.add_argument("--cap-hf", type=int, default=60)
    ap.add_argument("--val-tol-pp", type=float, default=1.0)
    ap.add_argument("--elem-tol-pp", type=float, default=1.0)
    ap.add_argument("--control-min", type=float, default=500.0)
    ap.add_argument("--control-frac", type=float, default=0.9999)
    ap.add_argument("--no-events-scan", action="store_true",
                    help="跳过 event_samples 逐条扫描（仅调试加速用）")
    args = ap.parse_args(argv)

    t0 = datetime.now()
    print("T62 独立验证开始", iso_now())
    print("BASE =", BASE)
    paths = [
        ("loads", args.loads), ("phaseA", args.a), ("stateA", args.stateA),
        ("phaseB", args.b), ("stateB", args.stateB),
        ("control_A", args.control),
        ("phaseA_hf", args.a_hf), ("phaseB_hf", args.b_hf),
        ("stateA_hf", args.stateA_hf), ("stateB_hf", args.stateB_hf),
    ]
    inputs = {name: file_meta(p) for name, p in paths}
    for name, meta in inputs.items():
        print("  %-10s %-8s %s" % (name, "OK" if meta["exists"] else "MISSING",
                                   meta["path"]))

    scan_ev = not args.no_events_scan
    print("加载数据（%s event_samples 扫描）..." %
          ("含" if scan_ev else "不含"), flush=True)
    loads = None
    if inputs["loads"]["exists"]:
        with open(args.loads, encoding="utf-8") as fh:
            loads = json.load(fh)
    RA = load_result_compact(args.a, scan_ev)
    SA = load_state_compact(args.stateA)
    RB = load_result_compact(args.b, scan_ev)
    SB = load_state_compact(args.stateB)
    CTL = load_control_compact(args.control)
    HFA = load_result_compact(args.a_hf, scan_ev)
    HFB = load_result_compact(args.b_hf, scan_ev)
    SAh = load_state_compact(args.stateA_hf)
    SBh = load_state_compact(args.stateB_hf)
    print("数据加载完成，耗时 %.1fs" % (datetime.now() - t0).total_seconds(),
          flush=True)

    ck = Checker()
    group_fns = [
        (1, lambda: check_group1(ck, loads, args.val_tol_pp, args.elem_tol_pp)),
        (2, lambda: check_group2(ck, loads, RA, SA, RB, SB)),
        (3, lambda: check_group3(ck, loads, RA, RB)),
        (4, lambda: check_group4(ck, loads, CTL, args.control_min,
                                 args.control_frac)),
        (5, lambda: check_group5(ck, RA, RB, args.cap_main)),
        (6, lambda: check_group6(ck, loads, RA, RB, HFA, HFB, SAh, SBh,
                                 args.cap_main, args.cap_hf)),
        (7, lambda: check_group7(ck, RA, RB, SA, SB)),
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

    required = {1, 2, 3, 4, 5, 7}
    statuses = [s["status"] for g in ck.groups for s in g["subchecks"]]
    counts = {k: statuses.count(k)
              for k in ("PASS", "FAIL", "SKIP", "INFO", "PENDING")}
    groups_pending = [g["id"] for g in ck.groups if g["status"] == "PENDING"]
    overall = "PASS"
    if counts["FAIL"]:
        overall = "FAIL"
    elif counts["PENDING"] or groups_pending or \
            any(g["id"] in required and g["status"] == "SKIP" for g in ck.groups):
        overall = "INCOMPLETE"

    pending = [{"group": g["id"], "id": s["id"], "name": s["name"],
                "detail": s["detail"]}
               for g in ck.groups for s in g["subchecks"]
               if s["status"] == "PENDING"]
    out = {
        "script": "t62_verify.py",
        "description": "T62 独立验证：投料等量性/守恒/价数/对照/判定自洽/cap对比/终态表",
        "generated_at": iso_now(),
        "elapsed_s": round((datetime.now() - t0).total_seconds(), 1),
        "base_dir": BASE,
        "args": {k: v for k, v in vars(args).items()},
        "tolerances": {"valence_dev_pp": args.val_tol_pp,
                       "element_dev_pp": args.elem_tol_pp,
                       "control_min": args.control_min,
                       "control_fraction_ge_500": args.control_frac,
                       "capped_frac_max": 0.01,
                       "cap_main": args.cap_main, "cap_hf": args.cap_hf,
                       "event_reservoir": EVENT_RESERVOIR},
        "inputs": inputs,
        "groups": ck.groups,
        "summary": counts,
        "overall": overall,
        "pending": pending,
        "notes": [],
    }
    # 记录关键跳过/待补原因
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
