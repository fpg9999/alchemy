# -*- coding: utf-8 -*-
"""T13 bench: simulate 速度基准 + V140 口径确认。
只读，不写数据文件。
"""
import sys, time, random
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_v3
from pot_all import vec_to_atoms, ORDER, formula_of

V140 = {"O": 28, "X": 27, "P": 47, "K": 11, "W": 1, "A": 20, "F": 6, "C": 0, "L": 0}


def vec_to_list(v):
    a = []
    for e in ORDER:
        a.extend([e] * v.get(e, 0))
    return a


def run(name, atoms):
    t0 = time.time()
    mols = pot_v3.simulate(atoms)
    dt = time.time() - t0
    if mols is None:
        print(f"{name}: n={len(atoms)} FAIL None  t={dt:.2f}s", flush=True)
        return
    sizes = sorted((len(m["atoms"]) for m in mols), reverse=True)
    print(f"{name}: n={len(atoms)} mols={len(mols)} max={sizes[0]} top5={sizes[:5]} t={dt:.2f}s", flush=True)
    return mols


print("=== V140 direct feed (口径确认: 应为单分子 140 原子) ===", flush=True)
mols = run("V140", vec_to_list(V140))
if mols:
    for m in sorted(mols, key=lambda m: -len(m["atoms"]))[:3]:
        print("   formula:", formula_of(m["atoms"]), "n=", len(m["atoms"]))

print("\n=== 尺寸/耗时基准 ===", flush=True)
rng = random.Random(20261113)
for n in (140, 200, 260, 320, 400, 500):
    for kind in ("rand9", "skewO"):
        if kind == "rand9":
            v = {"O": 0, "X": 0, "P": 0, "K": 0, "W": 0, "A": 0, "F": 0, "C": 0, "L": 0}
            for _ in range(n):
                v[rng.choice(ORDER)] += 1
        else:
            v = {e: 0 for e in ORDER}
            v["O"] = n - 8 * (n // 40)
            rest = n - v["O"]
            for _ in range(rest):
                v[rng.choice(ORDER)] += 1
        vol = sum({"O": 3, "X": 2, "C": 1, "P": 3, "W": 2, "L": 1, "K": 3, "A": 2, "F": 1}[e] * c for e, c in v.items())
        if vol % 2 == 0:
            run(f"{kind}{n}", vec_to_list(v))
