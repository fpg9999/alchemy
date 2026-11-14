# -*- coding: utf-8 -*-
"""t32g_prep.py：准备完整循环示例（链式：反应→衰变→再反应）的结构/坐标"""
import json
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v3
import pot_v2
from t28_rule_v2 import react_v2, formula

BASE = r"G:\AI work\deepseek\work1\alchemy"
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
by = {r["formula"]: r for r in cat}


def attach_place(mol):
    f = mol["formula"]
    if f in by and by[f].get("place"):
        mol["place"] = by[f]["place"]
        return mol
    place = pot_v2.embed_mol2(mol["atoms"], [tuple(e) for e in mol["edges"]], max_nodes=300000)
    mol["place"] = {str(k): list(v) for k, v in place.items()} if place else None
    return mol


def mol_from_formula(f):
    r = by[f]
    return {"formula": f, "atoms": list(r["atoms"]),
            "edges": [list(e) for e in r["edges"]], "place": r["place"]}


def react(mols):
    out = react_v2([(m["atoms"], m["edges"]) for m in mols],
                   use_valence=True, check_geometry=False)
    assert out["changed"], "reaction failed"
    prods = [{"formula": p["formula"], "atoms": list(p["atoms"]),
              "edges": [list(e) for e in p["edges"]]} for p in out["products"]]
    return [attach_place(p) for p in prods], out["class"]


def F(mol):
    mols = pot_v3.simulate(list(mol["atoms"]))
    prods = [{"formula": formula(m["atoms"]), "atoms": list(m["atoms"]),
              "edges": [list(e) for e in m["edges"]]} for m in mols]
    return [attach_place(p) for p in prods]


def run_sequence(init_formulas, steps):
    """steps: list of ('react', [indices]) / ('decay', index) operating on current list"""
    cur = [mol_from_formula(f) for f in init_formulas]
    states = [cur]
    log = []
    for kind, arg in steps:
        if kind == "react":
            sub = [cur[i] for i in arg]
            prods, cls = react(sub)
            rest = [m for j, m in enumerate(cur) if j not in arg]
            cur = rest + prods
            log.append({"type": "react", "inputs": [m["formula"] for m in sub],
                        "products": [m["formula"] for m in prods], "class": cls})
        else:
            m = cur[arg]
            prods = F(m)
            cur = [x for j, x in enumerate(cur) if j != arg] + prods
            log.append({"type": "decay", "from": m["formula"],
                        "to": [p["formula"] for p in prods]})
        states.append(cur)
    return states, log


examples = []
# A: 三段链
states, log = run_sequence(["OX2C", "KA2F", "PL2F"],
                           [("react", [0, 1]), ("decay", 1), ("react", [0, 2, 3])])
examples.append({"name": "A", "init": ["OX2C", "KA2F", "PL2F"], "states": states, "log": log})
# B: 两段链
states, log = run_sequence(["OWF", "CWK"], [("react", [0, 1]), ("decay", 0)])
examples.append({"name": "B", "init": ["OWF", "CWK"], "states": states, "log": log})
# C: 两段链 + 小碎片再反应
states, log = run_sequence(["LKF2", "CPLF"], [("react", [0, 1]), ("decay", 0), ("react", [0, 1])])
examples.append({"name": "C", "init": ["LKF2", "CPLF"], "states": states, "log": log})
# D: CF 再生成链（有旁观者）
states, log = run_sequence(["OCPK", "CA2F", "WLF", "X2CF"],
                           [("react", [1, 3]), ("decay", 2), ("react", [2, 3])])
examples.append({"name": "D", "init": ["OCPK", "CA2F", "WLF", "X2CF"],
                 "states": states, "log": log})
json.dump(examples, open(BASE + r"\t32_cycle_examples.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
for e in examples:
    print(e["name"], "init", e["init"])
    for s in e["states"]:
        print("  state:", [m["formula"] for m in s])
    for l in e["log"]:
        print("  ", l)
print("saved t32_cycle_examples.json")
