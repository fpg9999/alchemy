# -*- coding: utf-8 -*-
"""t61_hex_layouts.py —— T59 最后两次实验（A/B）中所有大分子（≥5 原子）的六边形棋盘格严格摆放

输出 t61_hex_layouts.json：每个大分子物质的原子/键/place/键型/出现实验与数量/摆放是否有效。
"""
import json
import sys
import time

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import natural_engine as E
import pot_all as P
import pot_v2

E.set_fast(True)
BASE = r"G:\AI work\deepseek\work1\alchemy"
FILES = [("T59A", "t59_phaseA_result.json"), ("T59B", "t59_phaseB_result.json")]


def get_struct(f, tops):
    if f in tops:
        t = tops[f]
        return list(t["atoms"]), [tuple(e) for e in t["edges"]]
    mols = E.complete_products(tuple(P.parse_formula(f)))
    if not mols:
        return None
    for m in mols:
        if m["formula"] == f:
            return list(m["atoms"]), [tuple(e) for e in m["edges"]]
    return None


def place_mol(atoms, edges):
    """先严格 embed_mol2；失败再试 pot_all.embed_mol（并严格校验）。"""
    t0 = time.time()
    place = pot_v2.embed_mol2(atoms, edges, max_nodes=2_000_000)
    method = "embed_mol2"
    if place is not None:
        ok, msg = pot_v2.validate_place(place, atoms, edges)
        if not ok:
            place = None
    if place is None:
        try:
            p2 = P.embed_mol(atoms, edges, max_nodes=5_000_000)
        except Exception:
            p2 = None
        if p2 is not None:
            ok, msg = pot_v2.validate_place(p2, atoms, edges)
            if ok:
                place = p2
                method = "pot_all.embed_mol"
    return place, method, round(time.time() - t0, 3)


def main():
    merged = {}
    for exp, fn in FILES:
        d = json.load(open(BASE + "\\" + fn, encoding="utf-8"))
        comp = d["final_composition"]
        tops = d.get("final_top_structures", {}) or {}
        for f, v in comp.items():
            if v["atoms"] < 5:
                continue
            st = get_struct(f, tops)
            if st is None:
                print("NO STRUCT", f)
                continue
            atoms, edges = st
            label = P.mol_label(atoms, edges)
            key = label
            rec = merged.get(key)
            if rec is None:
                rec = {"key": key, "formula": f, "atoms": atoms,
                       "edges": [list(e) for e in edges],
                       "n_atoms": len(atoms), "occurrences": {}, "counts": {}}
                merged[key] = rec
            rec["occurrences"][exp] = v["atoms"]
            rec["counts"][exp] = v["count"]
    print("merged big distinct", len(merged))
    out = []
    t0 = time.time()
    for i, rec in enumerate(sorted(merged.values(),
                                    key=lambda r: (-max(r["counts"].values()), -r["n_atoms"]))):
        atoms = rec["atoms"]
        edges = [tuple(e) for e in rec["edges"]]
        place, method, sec = place_mol(atoms, edges)
        valid = place is not None
        if valid:
            pos = [tuple(place[k]) for k in range(len(atoms))]
            occ = set(pos)
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
            bbox = [min(xs), min(ys), max(xs), max(ys)]
        else:
            pos, bonds, bbox = None, None, None
        out.append({**rec, "place": pos, "bonds": bonds, "bbox": bbox,
                    "valid": valid, "layout_method": method,
                    "layout_seconds": sec})
        if (i + 1) % 10 == 0:
            print("embedded", i + 1, "/", len(merged), "elapsed", round(time.time() - t0, 1))
    bad = [r for r in out if not r["valid"]]
    summary = {
        "n_big_distinct": len(out),
        "n_valid": len(out) - len(bad),
        "n_invalid": len(bad),
        "invalid": [r["formula"] for r in bad],
        "n_A": sum(1 for r in out if "T59A" in r["counts"]),
        "n_B": sum(1 for r in out if "T59B" in r["counts"]),
        "seconds": round(time.time() - t0, 1),
        "note": "大分子定义: 原子数>=5；结构按 mol_label 去重；occurrences 记录该结构在各实验中的原子数，counts 记录该结构在各实验中的分子数",
    }
    json.dump({"summary": summary, "items": out},
              open(BASE + r"\t61_hex_layouts.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
