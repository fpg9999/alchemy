# -*- coding: utf-8 -*-
"""t33_threshold_example.py：寻找温度阈值示例
条件：T >= c(A)（A 完全阈值）且 T < c(B)（B 未达完全），且 T >= i(A), i(B)（双方不完全阈值）。
要求：不完全反应可发生，且结果与完全大锅反应不同。
"""
import json
import random
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_v3
import pot_all as P
from t28_rule_v2 import react_v2, formula, wake, select_class, VAL
from collections import Counter

BASE = r"G:\AI work\deepseek\work1\alchemy"
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
small = [r for r in cat if 2 <= len(r["atoms"]) <= 6 and r.get("place")]
rng = random.Random(1234)


def bonds_count(rec):
    return sum(e[2] for e in rec["edges"])


def i_count(rec, cls, atoms_all, edges_all, offset, dt):
    """该分子在该全局类下要断的键数（每元素对 1 根）"""
    atoms = list(rec["atoms"])
    bond = [[0] * len(atoms) for _ in range(len(atoms))]
    for e in rec["edges"]:
        bond[e[0]][e[1]] = bond[e[1]][e[0]] = e[2]
    d, negm, v = cls
    mclass = -negm
    cnt = 0
    for x in range(len(atoms)):
        for y in range(x + 1, len(atoms)):
            if bond[x][y] == mclass:
                # 距离与价数需匹配全局类
                dd = P.ptable_dist(atoms[x], atoms[y])
                vv = min(VAL[atoms[x]], VAL[atoms[y]])
                if dd == d and vv == v:
                    cnt += 1
    return cnt


def main():
    found = []
    for _ in range(30000):
        A, B = rng.sample(small, 2)
        if len(A["atoms"]) + len(B["atoms"]) > 10:
            continue
        cA, cB = bonds_count(A), bonds_count(B)
        if cA >= cB:
            continue
        # 先跑不完全反应拿 class
        r = react_v2([(list(A["atoms"]), [tuple(e) for e in A["edges"]]),
                      (list(B["atoms"]), [tuple(e) for e in B["edges"]])],
                     use_valence=True, check_geometry=False)
        if not r["changed"]:
            continue
        f0 = sorted([A["formula"], B["formula"]])
        if sorted(p["formula"] for p in r["products"]) == f0:
            continue
        cls = r["class"]
        iA = i_count(A, cls, None, None, 0, None)
        iB = i_count(B, cls, None, None, 0, None)
        if iA < 1 or iB < 1:
            continue
        T = max(cA, iA, iB)
        if not (T >= cA and T < cB and T >= iA and T >= iB):
            continue
        # 几何合法的不完全反应
        rg = react_v2([(list(A["atoms"]), [tuple(e) for e in A["edges"]]),
                       (list(B["atoms"]), [tuple(e) for e in B["edges"]])],
                      use_valence=True, check_geometry=True)
        if not rg["changed"]:
            continue
        inc = sorted(p["formula"] for p in rg["products"])
        if inc == sorted([A["formula"], B["formula"]]):
            continue
        atoms = list(A["atoms"]) + list(B["atoms"])
        mols = pot_v3.simulate(atoms)
        if mols is None:
            continue
        comp = sorted(formula(m["atoms"]) for m in mols)
        if inc == comp:
            continue
        found.append({"A": A["formula"], "B": B["formula"],
                      "cA": cA, "cB": cB, "iA": iA, "iB": iB, "T": T,
                      "class": cls, "incomplete": inc, "complete": comp,
                      "atoms": len(atoms)})
        if len(found) >= 6:
            break
    print("找到", len(found), "个示例")
    for f in found:
        print(json.dumps(f, ensure_ascii=False))
    json.dump(found, open(BASE + r"\t33_threshold_examples.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
