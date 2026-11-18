# -*- coding: utf-8 -*-
"""verify_selfprod_all：验证目录里每个物质都可用"自身组成"直接投料复现（并行）。"""
import json
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def check(formula):
    vec = P.parse_formula(formula)
    atoms = P.vec_to_atoms(vec, P.ORDER)
    mols = P.simulate(atoms)
    if not mols:
        return formula, "剩键"
    for m in mols:
        if P.formula_of(m["atoms"]) == formula:
            if P.embed_mol(m["atoms"], m["edges"], max_nodes=60000) is None:
                return formula, "摆不出"
            return formula, "ok"
    return formula, "没产出"


def main():
    cat = json.load(open(BASE + r"\catalog_raw_compact.json", encoding="utf-8"))
    for name in ("extended_finite.json", "extended_finite2.json", "extended_finite3.json",
                 "extended_finite4.json", "extended_finite_merged.json"):
        try:
            ext = json.load(open(BASE + "\\" + name, encoding="utf-8"))
            for v in ext.values():
                cat += [{"formula": x["formula"], "natoms": x["natoms"]} for x in v["substances"]]
        except Exception:
            pass
    formulas = sorted({x["formula"] for x in cat})
    print("待验证物质:", len(formulas), flush=True)
    import os
    jobs = max(4, (os.cpu_count() or 8) - 4)
    bad = 0
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for formula, status in pool.map(check, formulas, chunksize=300):
            if status != "ok":
                bad += 1
                print("FAIL", formula, status, flush=True)
    print(f"完成: {len(formulas)} 个，失败 {bad}")


if __name__ == "__main__":
    main()
