# -*- coding: utf-8 -*-
"""t13_scale_3.py：V140×t（t=3,4）产物的最大分子尺寸（只 simulate，不 embed）"""
import json
import sys
import time
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_v3

BASE = r"G:\AI work\deepseek\work1\alchemy"
ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]
prod = json.load(open(BASE + r"\t12c_big140.json", encoding="utf-8"))[0]
v = [0] * 9
for a in prod["atoms"]:
    v[ORDER.index(a)] += 1

out = {}
for t in (3, 4):
    vec = [x * t for x in v]
    atoms = [s for s, c in zip(ORDER, vec) for _ in range(c)]
    t0 = time.time()
    mols = pot_v3.simulate(atoms)
    dt = time.time() - t0
    if mols is None:
        print(f"t={t} 总原子={len(atoms)}: 失败 {dt:.1f}s", flush=True)
        out[t] = {"ok": False}
        continue
    sizes = sorted((len(m["atoms"]) for m in mols), reverse=True)
    print(f"t={t} 总原子={len(atoms)}: 产物数={len(mols)} top={sizes[:5]} 用时={dt:.1f}s", flush=True)
    out[t] = {"ok": True, "sizes": sizes[:10]}
    # 保存最大产物结构
    big = max(mols, key=lambda m: len(m["atoms"]))
    rec = {"formula": "".join(f"{s}{big['atoms'].count(s)}" for s in ORDER if big["atoms"].count(s)),
           "atoms": big["atoms"], "edges": [list(e) for e in big["edges"]]}
    json.dump([rec], open(BASE + rf"\t13_scale{t}.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    print("  saved", rec["formula"], len(rec["atoms"]), flush=True)
json.dump(out, open(BASE + r"\t13_scale_results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("done")
