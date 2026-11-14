# -*- coding: utf-8 -*-
"""t12_struct：规则 9e 的结构化压力测试——
对“同元素对大量并列”的投料（如 K/A、O/X、P/W 混合，纯大类堆叠，放大族）检查产物是否唯一。
"""
import json
import os
import random
import sys
import time

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
from t12_rule9e import simulate_rule9e

BASE = r"G:\AI work\deepseek\work1\alchemy"


def test(counts, runs=8, seed=0):
    atoms = P.vec_to_atoms(tuple(counts), P.ORDER)
    if sum(P.VAL[e] for e in atoms) % 2:
        return "odd", None
    rng = random.Random(seed)
    outs = set()
    for _ in range(runs):
        r = simulate_rule9e(atoms, rng)
        if r is None:
            return "invalid", None
        outs.add(r)
    return len(outs), [list(x) for x in list(outs)[:3]]


def main():
    rng = random.Random(2026)
    cases = []
    # 两元素/三元素组合，较大规模
    combos = [
        ("O", "K"), ("X", "K"), ("O", "X"), ("K", "A"), ("P", "W"),
        ("O", "A"), ("X", "F"), ("O", "P"), ("C", "K"), ("W", "L"),
    ]
    for a, b in combos:
        for T in (12, 24, 40, 60):
            k = rng.randint(T // 4, T // 2)
            counts = [0] * 9
            counts[P.ORDER.index(a)] = k
            counts[P.ORDER.index(b)] = T - k
            cases.append((f"{a}{b}_T{T}_k{k}", counts))
    # 三元素
    for combo in (("O", "X", "K"), ("C", "K", "A"), ("P", "W", "L"), ("O", "K", "A")):
        for T in (18, 36, 60):
            counts = [0] * 9
            for _ in range(T):
                counts[P.ORDER.index(rng.choice(combo))] += 1
            cases.append(("tri_" + "_".join(combo) + f"_T{T}", counts))
    # 纯大类堆叠
    for combo in (("O", "X", "C"), ("P", "W", "L"), ("K", "A", "F")):
        for T in (18, 36, 60):
            counts = [0] * 9
            for _ in range(T):
                counts[P.ORDER.index(rng.choice(combo))] += 1
            cases.append(("pure_" + "_".join(combo) + f"_T{T}", counts))
    results = {}
    t0 = time.time()
    for name, counts in cases:
        n, outs = test(counts, runs=8, seed=hash(name) & 0xFFFF)
        results[name] = (n, outs)
        if n != 1:
            print("AMBIG/OTHER:", name, counts, n, outs, flush=True)
    ambiguous = {k: v for k, v in results.items() if v[0] != 1}
    print(f"cases={len(cases)} ambiguous={len(ambiguous)} time={time.time()-t0:.1f}s")
    json.dump({k: {"n_outcomes": v[0], "outcomes": v[1]} for k, v in results.items()},
              open(BASE + r"\t12_rule9e_struct.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
