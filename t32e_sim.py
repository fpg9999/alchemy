# -*- coding: utf-8 -*-
"""t32e_sim.py：自然环境完整循环的随机模拟（低反应概率 + 半衰期衰减）
每步：以 p_react 尝试一次 k=2/3 分子不完全反应；随后每个不稳定分子以 q 概率自分解。
统计：轨迹类型（固定/循环/长）、反应-衰变链长度、常见稳定终点、再生分子。
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
rng = random.Random(4321)
P_REACT = 0.30
Q_DECAY = 0.30
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
    p = F(mol)
    return len(p) == 1 and p[0]["formula"] == mol["formula"]


def key(state):
    return tuple(sorted(m["formula"] for m in state))


def step(state):
    events = []
    # 反应
    if len(state) >= 2 and rng.random() < P_REACT:
        order = list(range(len(state)))
        rng.shuffle(order)
        done = False
        for k in (2, 3):
            for _ in range(3):
                if len(order) < k:
                    continue
                idx = sorted(rng.sample(order, k))
                sub = [state[i] for i in idx]
                r = react_v2([(m["atoms"], m["edges"]) for m in sub],
                             use_valence=True, check_geometry=False)
                if not r["changed"]:
                    continue
                if sorted(p["formula"] for p in r["products"]) == sorted(m["formula"] for m in sub):
                    continue
                newstate = [m for j, m in enumerate(state) if j not in idx]
                newstate += [{"atoms": list(p["atoms"]), "edges": [tuple(e) for e in p["edges"]],
                              "formula": p["formula"]} for p in r["products"]]
                events.append({"type": "react", "inputs": [m["formula"] for m in sub],
                               "products": [p["formula"] for p in r["products"]],
                               "class": r["class"]})
                state = newstate
                done = True
                break
            if done:
                break
    # 衰变
    newstate = []
    for m in state:
        if not stable(m) and rng.random() < Q_DECAY:
            prods = F(m)
            events.append({"type": "decay", "from": m["formula"],
                           "to": [p["formula"] for p in prods]})
            newstate += [dict(p) for p in prods]
        else:
            newstate.append(m)
    return newstate, events


def run(init, max_steps=80):
    state = [dict(m) for m in init]
    hist = [key(state)]
    events = []
    for t in range(max_steps):
        state, ev = step(state)
        events += ev
        k = key(state)
        if k in hist:
            return {"history": hist + [k], "events": events, "outcome": "cycle",
                    "cycle_start": hist.index(k), "state": state}
        hist.append(k)
        if len(events) == 0 and t > 2:
            return {"history": hist, "events": events, "outcome": "fixed", "state": state}
    return {"history": hist, "events": events, "outcome": "max", "state": state}


def main():
    stats = Counter()
    chains = []
    for _ in range(600):
        k = rng.choice([2, 2, 3, 3, 4])
        recs = rng.sample(pool, k)
        init = [{"atoms": list(r["atoms"]), "edges": [tuple(e) for e in r["edges"]],
                 "formula": r["formula"]} for r in recs]
        r = run(init)
        stats[r["outcome"]] += 1
        reacts = sum(1 for e in r["events"] if e["type"] == "react")
        decays = sum(1 for e in r["events"] if e["type"] == "decay")
        stats[f"reacts_{reacts}"] += 1
        if r["outcome"] == "cycle":
            stats[f"period_{len(r['history'])-1-r['cycle_start']}"] += 1
        if reacts >= 1:
            if len(chains) < 30:
                chains.append({"init": [m["formula"] for m in init],
                               "events": r["events"][:15],
                               "history": r["history"][:15],
                               "outcome": r["outcome"],
                               "final": list(key(r["state"]))})
    print("统计:", dict(stats))
    print("链示例数:", len(chains))
    # 打印最长的链
    chains.sort(key=lambda c: -len(c["events"]))
    for c in chains[:6]:
        print("INIT", c["init"], "outcome", c["outcome"], "final", c["final"])
        for e in c["events"][:10]:
            print("  ", e)
    json.dump({"stats": dict(stats), "chains": chains},
              open(BASE + r"\t32e_sim.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t32e_sim.json")


if __name__ == "__main__":
    main()
