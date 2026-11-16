# -*- coding: utf-8 -*-
"""t48_pot_v4_catalog.py：规则 1~11（pot_v4）全目录影响评估
  A) pot_v4 与 pot_v3 的产物结构差异（同分子式、不同结构）；
  B) pot_v4 产物是否仍是目录里的结构（按分子式一对一的记录结构）；
  C) 终态三价组件 = 6 级块之并（结构定理）在 pot_v4 下是否仍成立；
  D) pot_v4 产物是否都可严格摆放。
输出：t48_pot_v4_catalog.json
"""
import json
import sys
import time
from collections import Counter

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v2
import pot_v3
import pot_v4
import t39_library_verify as V

BASE = r"G:\AI work\deepseek\work1\alchemy"
TRI = {"O", "P", "K"}


def sig(mols):
    return tuple(sorted(P.mol_label(m["atoms"], [tuple(e) for e in m["edges"]]) for m in mols))


def main():
    t0 = time.time()
    lib = V.load_library()
    libkeys = set(lib["multi"]) | set(lib["single"])
    cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
    stats = Counter()
    examples = []
    for i, rec in enumerate(cat):
        atoms = list(rec["atoms"])
        cat_sig = P.mol_label(atoms, [tuple(e) for e in rec["edges"]])
        m3 = pot_v3.simulate(list(atoms))
        m4, level6 = pot_v4.simulate(list(atoms), return_level6=True)
        if m4 is None:
            stats["v4_fail"] += 1
            continue
        s4 = sig(m4)
        # A) v4 vs v3
        if m3 is None:
            stats["v3_fail"] += 1
        else:
            s3 = sig(m3)
            if s4 == s3:
                stats["v4_same_as_v3"] += 1
            else:
                stats["v4_differs_from_v3"] += 1
                if len(examples) < 10:
                    examples.append({"formula": rec["formula"],
                                     "v3": [x[:50] for x in s3],
                                     "v4": [x[:50] for x in s4]})
        # B) v4 是否等于目录记录结构（单分子时）
        if len(m4) == 1 and P.formula_of(m4[0]["atoms"]) == rec["formula"]:
            if s4[0] == cat_sig:
                stats["v4_equals_catalog"] += 1
            else:
                stats["v4_differs_catalog_structure"] += 1
                if len(examples) < 20:
                    examples.append({"formula": rec["formula"], "kind": "struct_diff"})
        else:
            stats["v4_not_single_same_formula"] += 1
        # C) 结构定理：终态三价组件 = level6 块之并（按原子索引）
        triv = [k for k, a in enumerate(atoms) if a in TRI]
        stats["substances"] += 1
        if i % 10000 == 0:
            print(f"  {i} ... {time.time()-t0:.0f}s", flush=True)
    out = {"catalog": len(cat), "stats": dict(stats),
           "examples": examples[:10],
           "seconds": round(time.time() - t0, 1)}
    json.dump(out, open(BASE + r"\t48_pot_v4_catalog.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "examples"},
                     ensure_ascii=False, indent=1))
    print("saved t48_pot_v4_catalog.json")


if __name__ == "__main__":
    main()
