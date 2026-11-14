# -*- coding: utf-8 -*-
"""T13 dump：把指定投料的最大产物分子结构 dump 成 json（供 lead embed 使用）。
投料向量从 t13_results.jsonl 按 label 精确读取（含 fix_parity 后的真实投料）。
"""
import sys, os, json, time
HERE = r"G:\AI work\deepseek\work1\alchemy"
sys.path.insert(0, HERE)
import pot_v3
from pot_all import vec_to_atoms, ORDER, formula_of

LABELS = ["scale_1.75", "scale_2.0", "scale_1.5"]
feeds = {}
for line in open(os.path.join(HERE, "t13_results.jsonl"), encoding="utf-8"):
    r = json.loads(line)
    if r.get("label") in LABELS:
        feeds[r["label"]] = tuple(r["vec"])

out = {}
for name in LABELS:
    vec = feeds.get(name)
    if vec is None:
        print(name, "not found", flush=True)
        continue
    t0 = time.time()
    mols = pot_v3.simulate(vec_to_atoms(vec, ORDER))
    dt = time.time() - t0
    if not mols:
        print(f"{name}: sim fail", flush=True)
        continue
    big = max(mols, key=lambda m: len(m["atoms"]))
    out[name] = {"feed_vec": list(vec), "feed_n": sum(vec),
                 "mol_n": len(big["atoms"]), "formula": formula_of(big["atoms"]),
                 "nmols": len(mols), "sizes": sorted((len(m["atoms"]) for m in mols), reverse=True),
                 "atoms": big["atoms"], "edges": big["edges"], "t_sim": round(dt, 1)}
    print(f"{name}: feed_n={sum(vec)} mols={len(mols)} max={len(big['atoms'])} "
          f"{formula_of(big['atoms'])} t={dt:.1f}s", flush=True)
with open(os.path.join(HERE, "t13_big_struct_lead.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False)
print("saved t13_big_struct_lead.json", flush=True)
