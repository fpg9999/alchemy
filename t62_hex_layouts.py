# -*- coding: utf-8 -*-
"""t62_hex_layouts.py —— T62 两阶段实验（A/B）终态中所有大分子（≥5 原子）的六边形棋盘格严格摆放

做法沿用 T61（见 docs/T61_HEX_LARGE.md、t61_hex_layouts.py）：
  * 跨阶段按结构去重（pot_all.mol_label），收集 T62A / T62B 终态所有 ≥5 原子结构；
  * 用 pot_v2.embed_mol2 严格摆放（回溯搜索），失败时用随机原子标号重排再试
    （embed_mol2_perm_seed0/1/...），最后用 pot_v2.validate_place 严格复核；
  * 输出 t62_hex_layouts.json：summary + items
    （formula/n_atoms/atoms/edges/place/bonds/bbox/valid/layout_method/counts/occurrences）。

数据结构来源（优先级）：
  1) t62_phaseA_result.json / t62_phaseB_result.json 的 final_composition（formula/atoms/count）
     与 final_top_structures（该公式代表结构的 atoms/edges）；
  2) t62_analysis.json 的 structures.top30（formula/atoms/count/structure）；
  3) 必要时用 natural_engine.complete_products 重建结构（完全大锅反应）。

用法：
  python t62_hex_layouts.py                     # 正式：读 T62 数据，写 t62_hex_layouts.json
  python t62_hex_layouts.py --source t59 --out %TEMP%\\t62_hex_layouts_test.json --max-items 12
                                                # 自测：用 T59 数据渲染到临时目录
"""
import argparse
import json
import os
import random
import sys
import time

BASE = r"G:\AI work\deepseek\work1\alchemy"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import natural_engine as E
import pot_all as P
import pot_v2

E.set_fast(True)

SOURCES = {
    "t62": {
        "exp_label": "T62",
        "phases": [("T62A", "t62_phaseA_result.json"),
                   ("T62B", "t62_phaseB_result.json")],
        "analysis": "t62_analysis.json",
    },
    "t59": {
        "exp_label": "T59",
        "phases": [("T59A", "t59_phaseA_result.json"),
                   ("T59B", "t59_phaseB_result.json")],
        "analysis": "t59_analysis.json",
    },
}


# ---------------------------------------------------------------- 数据读取/结构重建
def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _struct_from_rec(rec):
    """从分析/top 结构记录里取 (atoms, edges)；兼容多种字段布局。"""
    if not isinstance(rec, dict):
        return None
    for key in ("structure", None):
        src = rec.get(key) if key else rec
        if not isinstance(src, dict):
            continue
        at, ed = src.get("atoms"), src.get("edges")
        if isinstance(at, list) and isinstance(ed, list) and at:
            return list(at), [tuple(e) for e in ed]
    return None


def rebuild_struct(formula):
    """用 natural_engine.complete_products 重建该公式的代表结构。"""
    try:
        mols = E.complete_products(tuple(P.parse_formula(formula)))
    except Exception as exc:  # 数据异常时不要中断整个任务
        print("[warn] complete_products %s: %r" % (formula, exc), flush=True)
        return None
    if not mols:
        return None
    for m in mols:
        if m.get("formula") == formula:
            return list(m["atoms"]), [tuple(e) for e in m["edges"]]
    return None


def collect(source, max_items=None):
    """收集 A/B 终态所有 ≥5 原子结构（跨阶段按 mol_label 去重）。"""
    cfg = SOURCES[source]
    merged = {}          # mol_label -> rec
    missing = []         # (exp, formula) 找不到结构的
    phase_results = []
    for exp, fn in cfg["phases"]:
        d = load_json(os.path.join(BASE, fn))
        if d is None:
            print("[warn] 缺少阶段结果文件: %s" % fn, flush=True)
            continue
        phase_results.append((exp, d))
    if not phase_results:
        raise SystemExit("没有可用的阶段结果文件（source=%s）" % source)

    analysis = load_json(os.path.join(BASE, cfg["analysis"])) or {}
    ast = analysis.get("structures") or {}
    top30 = ast.get("top30") or []
    amap = {}
    for s in top30:
        f = s.get("formula")
        if f:
            amap[f] = s
    # 分析文件里可能还带独立的大分子结构清单（T59/T62 分析脚本的扩展字段）
    extra_structs = []
    for key in ("big_structures", "giant_structures", "big_molecules_top"):
        v = ast.get(key)
        if isinstance(v, list):
            extra_structs.extend(x for x in v if isinstance(x, dict))

    # ---- 1) 阶段终态组成 -------------------------------------------------
    for exp, d in phase_results:
        comp = d.get("final_composition") or {}
        tops = d.get("final_top_structures") or {}
        for f, v in comp.items():
            natoms = int(v.get("atoms") or 0)
            if natoms < 5:
                continue
            st = _struct_from_rec(tops.get(f)) or _struct_from_rec(amap.get(f))
            if st is None:
                st = rebuild_struct(f)
            if st is None:
                missing.append((exp, f))
                print("[warn] NO STRUCT %s %s" % (exp, f), flush=True)
                continue
            atoms, edges = st
            if len(atoms) != natoms:
                print("[warn] 原子数不一致 %s %s: comp=%d struct=%d"
                      % (exp, f, natoms, len(atoms)), flush=True)
            label = P.mol_label(atoms, edges)
            rec = merged.get(label)
            if rec is None:
                rec = {"key": label, "formula": f, "atoms": list(atoms),
                       "edges": [list(e) for e in edges],
                       "n_atoms": len(atoms), "occurrences": {}, "counts": {}}
                merged[label] = rec
            if exp in rec["counts"] and rec["formula"] != f:
                print("[warn] 同结构多公式 %s: %s / %s"
                      % (label, rec["formula"], f), flush=True)
            rec["counts"][exp] = rec["counts"].get(exp, 0) + int(v.get("count") or 0)
            rec["occurrences"][exp] = len(atoms)

    # ---- 2) 分析文件 top30 / 扩展清单里额外的大分子结构 -----------------
    n_from_analysis = 0
    seen_labels = set(merged.keys())
    for s in top30 + extra_structs:
        f = s.get("formula")
        if not f:
            continue
        natoms = s.get("atoms")
        if isinstance(natoms, list):
            natoms = len(natoms)
        try:
            natoms = int(natoms or 0)
        except (TypeError, ValueError):
            natoms = 0
        if natoms < 5:
            continue
        st = _struct_from_rec(s)
        if st is None:
            st = rebuild_struct(f)
        if st is None:
            continue
        atoms, edges = st
        label = P.mol_label(atoms, edges)
        if label in seen_labels:
            rec = merged[label]
            if s.get("count") is not None:
                rec.setdefault("analysis_count", int(s["count"]))
            continue
        rec = {"key": label, "formula": f, "atoms": list(atoms),
               "edges": [list(e) for e in edges], "n_atoms": len(atoms),
               "occurrences": {}, "counts": {},
               "analysis_count": int(s.get("count") or 0),
               "count_source": "analysis.total"}
        merged[label] = rec
        seen_labels.add(label)
        n_from_analysis += 1

    items = list(merged.values())
    # 排序：跨阶段总数量降序（与 T61 一致），同数量优先原子数多的
    items.sort(key=lambda r: (-max(r["counts"].values()) if r["counts"] else
                              -r.get("analysis_count", 0),
                              -r["n_atoms"], r["formula"]))
    if max_items:
        items = items[:max_items]
    print("收集到大分子结构（去重后）%d 种（其中分析文件新增 %d）"
          % (len(merged), n_from_analysis), flush=True)
    return items, missing, [exp for exp, _ in phase_results], cfg["exp_label"]


# ---------------------------------------------------------------- 严格摆放
def place_mol(atoms, edges, max_nodes=2_000_000, perm_seeds=12,
              perm_max_nodes=1_500_000, big_nodes=20_000_000):
    """严格摆放：embed_mol2 → 随机标号重排 embed_mol2_perm_seed* → 大预算/pot_all。

    返回 (pos, method, seconds, attempts)；失败时 pos=None。
    """
    t0 = time.time()
    n = len(atoms)
    attempts = []

    def ok_pos(place):
        if place is None:
            return None
        ok, msg = pot_v2.validate_place(place, atoms, edges)
        if not ok:
            attempts.append("validate:%s" % msg)
            return None
        return [tuple(place[k]) for k in range(n)]

    # 1) 原始原子顺序，严格 embed_mol2
    place = pot_v2.embed_mol2(atoms, edges, max_nodes=max_nodes)
    pos = ok_pos(place)
    if pos is not None:
        return pos, "embed_mol2", round(time.time() - t0, 3), attempts
    attempts.append("embed_mol2:no-solution")

    # 2) 随机原子标号重排（embed_mol2_perm_seed0/1/...）
    for seed in range(perm_seeds):
        rng = random.Random(seed)
        perm = list(range(n))
        rng.shuffle(perm)
        new_atoms = [atoms[perm[i]] for i in range(n)]
        old_to_new = {perm[i]: i for i in range(n)}
        new_edges = [(old_to_new[a], old_to_new[b], m) for (a, b, m) in edges]
        p = pot_v2.embed_mol2(new_atoms, new_edges, max_nodes=perm_max_nodes)
        if p is None:
            attempts.append("perm_seed%d:no-solution" % seed)
            continue
        ok, msg = pot_v2.validate_place(p, new_atoms, new_edges)
        if not ok:
            attempts.append("perm_seed%d:invalid(%s)" % (seed, msg))
            continue
        back = {perm[i]: p[i] for i in range(n)}
        pos = [tuple(back[j]) for j in range(n)]
        # 回映射到原编号后再严格复核一次
        ok, msg = pot_v2.validate_place({i: pos[i] for i in range(n)}, atoms, edges)
        if not ok:
            attempts.append("perm_seed%d:backmap-invalid(%s)" % (seed, msg))
            continue
        return pos, "embed_mol2_perm_seed%d" % seed, round(time.time() - t0, 3), attempts

    # 3) 大预算、原顺序再试一次
    place = pot_v2.embed_mol2(atoms, edges, max_nodes=big_nodes)
    pos = ok_pos(place)
    if pos is not None:
        return pos, "embed_mol2_%dM" % (big_nodes // 1_000_000), \
            round(time.time() - t0, 3), attempts
    attempts.append("embed_mol2_%dM:no-solution" % (big_nodes // 1_000_000))

    # 4) pot_all.embed_mol 兜底（T61 同款），仍严格复核
    try:
        p2 = P.embed_mol(atoms, edges, max_nodes=big_nodes)
    except Exception:
        p2 = None
    pos = ok_pos(p2)
    if pos is not None:
        return pos, "pot_all.embed_mol_%dM" % (big_nodes // 1_000_000), \
            round(time.time() - t0, 3), attempts
    attempts.append("pot_all.embed_mol:no-solution")

    return None, "failed", round(time.time() - t0, 3), attempts


def layout_item(rec, max_nodes=2_000_000, perm_seeds=12):
    atoms = rec["atoms"]
    edges = [tuple(e) for e in rec["edges"]]
    pos, method, sec, attempts = place_mol(
        atoms, edges, max_nodes=max_nodes, perm_seeds=perm_seeds)
    rec["layout_method"] = method
    rec["layout_seconds"] = sec
    if pos is None:
        rec["place"] = None
        rec["bonds"] = None
        rec["bbox"] = None
        rec["valid"] = False
        rec["failed_attempts"] = attempts[-8:]
        return rec
    bonds = []
    for (a, b, m) in edges:
        d = (pos[b][0] - pos[a][0], pos[b][1] - pos[a][1])
        typ = P.classify_offset(d)
        mid = None
        if typ == "L":
            mid = (pos[a][0] + d[0] // 2, pos[a][1] + d[1] // 2)
        bonds.append({"a": a, "b": b, "m": m, "type": typ,
                      "mid": list(mid) if mid else None})
    xs = [p[0] for p in pos]
    ys = [p[1] for p in pos]
    rec["place"] = pos
    rec["bonds"] = bonds
    rec["bbox"] = [min(xs), min(ys), max(xs), max(ys)]
    rec["valid"] = True
    return rec


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="t62", choices=["t62", "t59"])
    ap.add_argument("--out", default=os.path.join(BASE, "t62_hex_layouts.json"))
    ap.add_argument("--max-items", type=int, default=None,
                    help="只摆放排序后的前 N 种（自测用；正式生成不要设置）")
    ap.add_argument("--max-nodes", type=int, default=2_000_000)
    ap.add_argument("--perm-seeds", type=int, default=12)
    args = ap.parse_args()

    t0 = time.time()
    items, missing, phase_labels, exp_label = collect(args.source, args.max_items)
    print("开始严格摆放 %d 种结构 ..." % len(items), flush=True)
    out = []
    for i, rec in enumerate(items):
        out.append(layout_item(rec, max_nodes=args.max_nodes,
                               perm_seeds=args.perm_seeds))
        if (i + 1) % 10 == 0 or (i + 1) == len(items):
            print("  embedded %d/%d elapsed %.1fs"
                  % (i + 1, len(items), time.time() - t0), flush=True)
        if out[-1]["valid"]:
            print("   [%d] %s n=%d %s %.3fs"
                  % (i + 1, rec["formula"], rec["n_atoms"],
                     out[-1]["layout_method"], out[-1]["layout_seconds"]),
                  flush=True)
        else:
            print("   [%d] %s n=%d FAILED %.1fs"
                  % (i + 1, rec["formula"], rec["n_atoms"],
                     out[-1]["layout_seconds"]), flush=True)

    bad = [r for r in out if not r["valid"]]
    methods = {}
    for r in out:
        m = r["layout_method"]
        methods[m] = methods.get(m, 0) + 1
    n_med = sum(1 for r in out if 5 <= r["n_atoms"] <= 18)
    n_giant = sum(1 for r in out if r["n_atoms"] >= 19)
    summary = {
        "source": args.source,
        "exp_label": exp_label,
        "phases": phase_labels,
        "source_files": [fn for (_, fn) in SOURCES[args.source]["phases"]]
                        + [SOURCES[args.source]["analysis"]],
        "n_big_distinct": len(out),
        "n_valid": len(out) - len(bad),
        "n_invalid": len(bad),
        "invalid": [r["formula"] for r in bad],
        "invalid_detail": [{"formula": r["formula"], "n_atoms": r["n_atoms"],
                            "attempts": r.get("failed_attempts")} for r in bad],
        "n_medium_5_18": n_med,
        "n_giants_ge19": n_giant,
        "n_phases": {exp: sum(1 for r in out if exp in r["counts"])
                     for exp in phase_labels},
        "layout_methods": methods,
        "n_need_perm_or_extra": sum(1 for r in out
                                    if r["layout_method"] not in ("embed_mol2",)),
        "n_from_analysis": sum(1 for r in out if not r["counts"]),
        "n_missing_struct": len(missing),
        "missing_struct": ["%s:%s" % (e, f) for (e, f) in missing],
        "seconds": round(time.time() - t0, 1),
        "max_nodes": args.max_nodes,
        "perm_seeds": args.perm_seeds,
        "note": ("大分子定义: 原子数>=5；跨阶段按 pot_all.mol_label 去重；"
                 "place 为轴向坐标 (q,r)，与 atoms 下标一一对应；"
                 "counts 记录该结构在各阶段终态的分子数，"
                 "occurrences 记录该结构在各阶段终态的原子数；"
                 "严格摆放流程 embed_mol2 -> 随机原子标号重排 embed_mol2_perm_seed* "
                 "-> 大预算 -> pot_all.embed_mol，全部经 pot_v2.validate_place 复核"),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"summary": summary, "items": out}, fh,
                  ensure_ascii=False, indent=1)
    print("[saved] %s (%d bytes)" % (args.out, os.path.getsize(args.out)),
          flush=True)
    print(json.dumps(summary, ensure_ascii=False, indent=1), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
