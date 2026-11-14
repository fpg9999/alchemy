# -*- coding: utf-8 -*-
"""t32_cycles.py：自然环境完整循环模拟
循环：
  不完全反应（随机 k=2~3 个分子）→ 可能产生不稳定物质
  不稳定物质每个时间步以概率 q 自分解（M -> F(v_M)）为稳定物质
  再次进入不完全反应……
统计：固定点 / 循环 / 长轨迹；收集有趣的循环示例。
"""
import json
import random
import sys
from collections import Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v3
from t28_rule_v2 import react_v2, formula

BASE = r"G:\AI work\deepseek\work1\alchemy"
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
pool = [r for r in cat if 2 <= len(r["atoms"]) <= 4 and r.get("place")]
rng = random.Random(2026)
DECAY_Q = 0.5


def atoms_of_formula(f):
    return P.vec_to_atoms(P.parse_formula(f), P.ORDER)


def pot_products(atoms):
    mols = pot_v3.simulate(atoms)
    if mols is None:
        print("F_FAIL", atoms, flush=True)
        return []
    out = []
    for m in mols:
        out.append({"atoms": list(m["atoms"]), "edges": [tuple(e) for e in m["edges"]],
                    "formula": formula(m["atoms"])})
    return out


_fcache = {}


def is_unstable(mol):
    f = mol["formula"]
    if f not in _fcache:
        prods = pot_products(mol["atoms"])
        _fcache[f] = prods
    prods = _fcache[f]
    if not prods:
        return False
    return not (len(prods) == 1 and prods[0]["formula"] == f)


def decay(mol):
    f = mol["formula"]
    if f not in _fcache:
        _fcache[f] = pot_products(mol["atoms"])
    return _fcache[f]


def state_key(state):
    return tuple(sorted(m["formula"] for m in state))


def simulate(initial, max_steps=25, subset_max=3, q=DECAY_Q):
    state = [dict(m) for m in initial]
    history = [state_key(state)]
    events = []
    for step in range(max_steps):
        # 1) 随机尝试不完全反应
        changed = False
        for attempt in range(6):
            k = min(rng.choice([2, 2, 3]), len(state))
            if k < 2:
                break
            idx = sorted(rng.sample(range(len(state)), k))
            system = [(state[i]["atoms"], state[i]["edges"]) for i in idx]
            r = react_v2(system, use_valence=True, check_geometry=False)
            if not r["changed"]:
                continue
            forms_in = sorted(state[i]["formula"] for i in idx)
            forms_out = sorted(p["formula"] for p in r["products"])
            if forms_out == forms_in:
                continue
            events.append({"type": "react", "step": step,
                           "inputs": [state[i]["formula"] for i in idx],
                           "products": [dict(p) for p in r["products"]],
                           "class": r["class"]})
            newstate = [m for j, m in enumerate(state) if j not in idx]
            newstate += [{"atoms": list(p["atoms"]), "edges": [tuple(e) for e in p["edges"]],
                          "formula": p["formula"]} for p in r["products"]]
            state = newstate
            changed = True
            break
        # 2) 不稳定物质按概率自分解
        decayed = False
        newstate = []
        for m in state:
            if is_unstable(m) and rng.random() < q:
                prods = decay(m)
                events.append({"type": "decay", "step": step, "from": m["formula"],
                               "to": [p["formula"] for p in prods]})
                newstate += prods
                decayed = True
            else:
                newstate.append(m)
        state = newstate
        if not changed and not decayed:
            break
        key = state_key(state)
        if key in history:
            return {"history": history + [key], "events": events, "state": state,
                    "cycle_start": history.index(key), "outcome": "cycle"}
        history.append(key)
    return {"history": history, "events": events, "state": state,
            "cycle_start": None, "outcome": "max"}


def init_system():
    k = rng.choice([2, 2, 3, 3, 4])
    recs = rng.sample(pool, k)
    return [{"atoms": list(r["atoms"]), "edges": [tuple(e) for e in r["edges"]],
             "formula": r["formula"]} for r in recs]


def main():
    stats = Counter()
    cycles = []
    catalyst_examples = []
    for t in range(500):
        init = init_system()
        r = simulate(init)
        stats[r["outcome"]] += 1
        if r["outcome"] == "cycle":
            period = len(r["history"]) - 1 - r["cycle_start"]
            stats[f"period_{period}"] += 1
            # 催化剂：某个分子式在所有状态中都存在
            common = set(r["history"][0])
            for h in r["history"]:
                common &= set(h)
            if len(cycles) < 30:
                cycles.append({"init": [m["formula"] for m in init],
                               "history": r["history"],
                               "period": period,
                               "events": r["events"],
                               "common_formulas": sorted(common)})
            if common and len(catalyst_examples) < 10:
                catalyst_examples.append({"init": [m["formula"] for m in init],
                                          "common": sorted(common),
                                          "history": r["history"]})
    print("统计:", dict(stats))
    print("循环示例数:", len(cycles))
    for c in cycles[:8]:
        print("  init", c["init"], "period", c["period"], "common", c["common_formulas"])
        print("   states:", c["history"][:8])
    json.dump({"stats": dict(stats), "cycles": cycles,
               "catalysts": catalyst_examples},
              open(BASE + r"\t32_cycles.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t32_cycles.json")


if __name__ == "__main__":
    main()
