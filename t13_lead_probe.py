# -*- coding: utf-8 -*-
"""lead 快检：140 纪录投料的放大/扰动变体，看是否出现 >140 原子的产物（不 embed）"""
import json
import sys
import time
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_v3

BASE = r"G:\AI work\deepseek\work1\alchemy"
ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]
prod = json.load(open(BASE + r"\t12c_big140.json", encoding="utf-8"))[0]
atoms = prod["atoms"]
v = [0] * 9
for a in atoms:
    v[ORDER.index(a)] += 1
print("V140 =", v, "总原子=", sum(v))


def run(vec, name):
    atoms = [s for s, c in zip(ORDER, vec) for _ in range(c)]
    t0 = time.time()
    mols = pot_v3.simulate(atoms)
    dt = time.time() - t0
    if mols is None:
        print(f"{name}: 失败 ({dt:.1f}s)")
        return
    sizes = sorted((len(m["atoms"]) for m in mols), reverse=True)
    print(f"{name}: 总原子={sum(vec)} 产物数={len(mols)} 最大={sizes[:3]} 用时={dt:.1f}s", flush=True)


run(v, "V140")
run([x * 2 for x in v], "V140 x2")
# 加 20 个 WA（每次 2 原子）
wa = [0, 0, 0, 0, 20, 0, 0, 20, 0]
run([a + b for a, b in zip(v, wa)], "V140 + 20WA")
# 加 20 个 X2C2
add = [0, 40, 40, 0, 0, 0, 0, 0, 0]
run([a + b for a, b in zip(v, add)], "V140 + 20X2C2")
