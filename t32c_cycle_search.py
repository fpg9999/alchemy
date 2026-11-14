# -*- coding: utf-8 -*-
"""t32c_cycle_search.py：在"反应→自分解→再反应"循环中搜索固定点/周期轨道
确定性转移：按顺序找第一个能发生（公式改变）的 2 或 3 分子子集；
不稳定分子全部立即自分解（q=1 的极限）。
"""
import json
import random
import sys
from itertools import combinations
from collections import Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v3
from t28_rule_v2 import react_v2, formula

BASE = r"G:\AI work\deepseek\work1\alchemy"
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
pool = [r for r in cat if 2 <= len(r["atoms"]) <= 4 and r.get("place")]
rng = random.Random(7171)

_fc = {}


def F(mol):
    key = tuple(sorted(mol["atoms"]))
    if key in _fc:
        return _fc[key]
    mols = pot_v3.simulate(list(mol["atoms"]))
    if mols is None:
        _fc[key] = []
    else:
        _fc[key] = [{"atoms": list(m["atoms"]), "edges": [tuple(e) for e in m["edges"]],
                     "formula": formula(m["atoms"])} for m in mols]
    return _fc[key]


def stable(mol):
    prods = F(mol)
    return len(prods) == 1 and prods[0]["formula"] == mol["formula"]


def decay_all(state):
    out = []
    for m in state:
        if stable(m):
            out.append(m)
        else:
            out += [dict(p) for p in F(m)]
    return out


def key(state):
    return tuple(sorted(m["formula"] for m in state))


def step(state):
    n = len(state)
    for k in (2, 3):
        for idx in combinations(range(n), k):
            system = [(state[i]["atoms"], state[i]["edges"]) for i in idx]
            r = react_v2(system, use_valence=True, check_geometry=False)
            if not r["changed"]:
                continue
            fin = sorted(state[i]["formula"] for i in idx)
            fout = sorted(p["formula"] for p in r["products"])
            if fout == fin:
                continue
            newstate = [m for j, m in enumerate(state) if j not in idx]
            newstate += [{"atoms": list(p["atoms"]), "edges": [tuple(e) for e in p["edges"]],
                          "formula": p["formula"]} for p in r["products"]]
            return newstate, {"type": "react", "inputs": [state[i]["formula"] for i in idx],
                              "products": fout, "class": r["class"]}
    return state, None


def trajectory(init, max_steps=40):
    state = [dict(m) for m in init]
    hist = [key(state)]
    events = []
    for t in range(max_steps):
        state2, ev = step(state)
        if ev:
            events.append(ev)
        # 全部不稳定立即衰变
        state3 = decay_all(state2)
        # 记录衰变事件
        if key(state3) != key(state2):
            events.append({"type": "decay", "from": key(state2), "to": key(state3)})
        state = state3
        k = key(state)
        if k in hist:
            return {"history": hist + [k], "events": events, "state": state,
                    "outcome": "cycle", "cycle_start": hist.index(k)}
        hist.append(k)
        if key(state2) == key(state) and ev is None and len(events) < 1:
            return {"history": hist, "events": events, "state": state, "outcome": "fixed"}
    return {"history": hist, "events": events, "state": state, "outcome": "max"}


def main():
    stats = Counter()
    cycles = []
    chains = []
    for t in range(2000):
        k = rng.choice([2, 2, 3, 3, 4])
        recs = rng.sample(pool, k)
        init = [{"atoms": list(r["atoms"]), "edges": [tuple(e) for e in r["edges"]],
                 "formula": r["formula"]} for r in recs]
        r = trajectory(init)
        stats[r["outcome"]] += 1
        if r["outcome"] == "cycle":
            period = len(r["history"]) - 1 - r["cycle_start"]
            stats[f"period_{period}"] += 1
            if len(cycles) < 40:
                cycles.append({"init": [m["formula"] for m in init],
                               "history": r["history"], "period": period,
                               "events": r["events"]})
        # 链式：至少 1 次反应 + 1 次衰变 + 再反应
        reacts = sum(1 for e in r["events"] if e["type"] == "react")
        decays = sum(1 for e in r["events"] if e["type"] == "decay")
        if reacts >= 2 and decays >= 1 and len(chains) < 40:
            chains.append({"init": [m["formula"] for m in init],
                           "events": r["events"], "history": r["history"]})
    print("统计:", dict(stats))
    print("周期轨道数:", len(cycles))
    for c in cycles[:10]:
        print(" init", c["init"], "period", c["period"])
        print("  events", [(e["type"], e.get("inputs"), e.get("products") if e["type"]=="react" else e.get("to")) for e in c["events"][:8]])
    print("链式轨迹数:", len(chains))
    for c in chains[:5]:
        print(" chain init", c["init"])
        for e in c["events"][:8]:
            print("   ", e)
    json.dump({"stats": dict(stats), "cycles": cycles, "chains": chains},
              open(BASE + r"\t32c_cycles.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t32c_cycles.json")


if __name__ == "__main__":
    main()
