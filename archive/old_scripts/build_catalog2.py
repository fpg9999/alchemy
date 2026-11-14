# -*- coding: utf-8 -*-
"""build_catalog2：用"实测分类"结果构建 511 类别目录（最终版）。

输入：all511_classified.json / catalog_raw_compact.json / families_empirical.json(或 families_full.json)
输出：catalog2_subsets.json / catalog2_composition.json / catalog2_minimal.json / catalog2_stats.json
"""
import itertools
import json
import sys
from collections import defaultdict

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
MAXN = 16


def sig(elems):
    return "/".join(sorted(elems, key=lambda e: P.ORDER.index(e)))


def zh_elems(elems):
    return "、".join(f"{e}{P.CN[e]}" for e in sorted(elems, key=lambda x: P.ORDER.index(x)))


def load(name, default=None):
    try:
        return json.load(open(BASE + "\\" + name, encoding="utf-8"))
    except Exception:
        return default


def main():
    raw = load("catalog_raw_compact.json")
    cls = load("all_classified_final.json")
    stats0 = load("all_classified_stats.json")
    fams = load("families_full.json") or load("families_empirical.json") or {}
    print("目录条数", len(raw), "类别", len(cls), flush=True)
    minimal = [set(s.split("/")) for s in stats0["minimal"]]
    # 合并多批实测证据（3 元组来自 classify_staged；6 个中证据来自 medium_test）
    ev = {}
    try:
        st = load("all_classified_raw.json") or {}
        for k, v in (st.get("sets") or {}).items():
            ev[k] = max(ev.get(k, 0), v.get("max", 0))
    except Exception:
        pass
    try:
        mt = load("medium_test.json") or {}
        for k, d in mt.items():
            for T, v in d.items():
                ev[k] = max(ev.get(k, 0), v.get("max", 0))
    except Exception:
        pass
    groups = defaultdict(list)
    for x in raw:
        groups[frozenset(x["atoms"])].append(x)

    def count_by_N(items):
        ns = [x["natoms"] for x in items]
        return {str(N): sum(1 for n in ns if n <= N) for N in range(2, MAXN + 1)}

    comp_out = {}
    for E, items in groups.items():
        items.sort(key=lambda x: (x["natoms"], x["formula"]))
        cores = [sig(m) for m in minimal if m <= E]
        comp_out[sig(E)] = {
            "elems": sorted(E, key=lambda e: P.ORDER.index(e)),
            "zh": zh_elems(E), "infinite": bool(cores), "cores": cores,
            "count_le16": len(items), "count_by_N": count_by_N(items),
            "max_natoms": max(x["natoms"] for x in items),
            "substances": [{"formula": x["formula"], "natoms": x["natoms"], "zh": P.zh_of(x["atoms"])} for x in items],
        }

    sub_out = []
    for r in range(1, 10):
        for c in itertools.combinations(P.ORDER, r):
            S = list(c)
            ck = sig(S)
            c = cls.get(ck)
            items = []
            for E, its in groups.items():
                if E <= set(S):
                    items.extend(its)
            items.sort(key=lambda x: (x["natoms"], x["formula"]))
            cores = c["cores"] if c else []
            entry = {
                "elems": S, "zh": zh_elems(S), "elements_zh": P.zh_of(S), "n_elems": len(S),
                "infinite": c["infinite"], "cores": cores,
                "direct_evidence": bool(max(c.get("max", 0), ev.get(ck, 0)) >= 17),
                "evidence_T": c.get("T"), "evidence_max": max(c.get("max", 0), ev.get(ck, 0)),
                "evidence_info": c.get("info"),
                "count_le16": len(items), "count_by_N": count_by_N(items),
                "max_natoms": max((x["natoms"] for x in items), default=0),
                "formulas_le16": [x["formula"] for x in items],
                "reps": [{"formula": x["formula"], "zh": P.zh_of(x["atoms"]), "natoms": x["natoms"]} for x in items[:3]],
            }
            sub_out.append(entry)
    sub_out.sort(key=lambda e: (e["n_elems"], [P.ORDER.index(x) for x in e["elems"]]))

    min_out = []
    for m in minimal:
        allitems = [x for E, its in groups.items() if E <= m for x in its]
        min_out.append({
            "elems": sorted(m, key=lambda e: P.ORDER.index(e)),
            "count_le16": len(allitems), "count_by_N": count_by_N(allitems),
            "families": fams.get(sig(m), {}).get("families", []),
            "evidence_T": cls[sig(m)].get("T"), "evidence_max": max(cls[sig(m)].get("max", 0), ev.get(sig(m), 0)),
        })
    min_out.sort(key=lambda x: (len(x["elems"]), [P.ORDER.index(e) for e in x["elems"]]))

    st = {
        "catalog_size": len(raw),
        "n_pool_categories": len(sub_out),
        "n_finite": sum(1 for x in sub_out if not x["infinite"]),
        "n_infinite": sum(1 for x in sub_out if x["infinite"]),
        "n_direct_evidence": sum(1 for x in sub_out if x["direct_evidence"]),
        "n_minimal": len(minimal),
        "minimal": [sig(m) for m in minimal],
        "infinite_by_size": {r: sum(1 for x in sub_out if x["infinite"] and x["n_elems"] == r) for r in range(1, 10)},
        "finite_by_size": {r: sum(1 for x in sub_out if not x["infinite"] and x["n_elems"] == r) for r in range(1, 10)},
    }
    json.dump(sub_out, open(BASE + r"\catalog2_subsets.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(comp_out, open(BASE + r"\catalog2_composition.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(min_out, open(BASE + r"\catalog2_minimal.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(st, open(BASE + r"\catalog2_stats.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(st, ensure_ascii=False, indent=1)[:1600])
    print("saved catalog2_*.json")


if __name__ == "__main__":
    main()
