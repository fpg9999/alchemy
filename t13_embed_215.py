# -*- coding: utf-8 -*-
"""t13_embed_215.py：把 V140×2 反应中最大的产物（215 原子）尝试严格摆放。
若成功则刷新区最大合法分子纪录（215 > 140）。
"""
import json
import sys
import time
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_v3
import pot_v2

BASE = r"G:\AI work\deepseek\work1\alchemy"
ORDER = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]
prod = json.load(open(BASE + r"\t12c_big140.json", encoding="utf-8"))[0]
v = [0] * 9
for a in prod["atoms"]:
    v[ORDER.index(a)] += 1
vec = [x * 2 for x in v]
atoms = [s for s, c in zip(ORDER, vec) for _ in range(c)]
print("投料总原子", len(atoms), flush=True)
t0 = time.time()
mols = pot_v3.simulate(atoms)
print(f"simulate {time.time()-t0:.1f}s；产物数 {len(mols) if mols else None}", flush=True)
if mols is None:
    sys.exit(0)
mols = sorted(mols, key=lambda m: -len(m["atoms"]))
big = mols[0]
print("最大产物原子数:", len(big["atoms"]), flush=True)
rec = {"formula": "".join(f"{s}{big['atoms'].count(s)}" for s in ORDER if big["atoms"].count(s)),
       "atoms": big["atoms"], "edges": [list(e) for e in big["edges"]],
       "natoms": len(big["atoms"])}
json.dump([rec], open(BASE + r"\t13_lead_215.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)
print("saved structure", rec["formula"], "natoms", rec["natoms"], flush=True)

t1 = time.time()
place = pot_v2.embed_mol2(rec["atoms"], [tuple(e) for e in rec["edges"]], max_nodes=20_000_000)
dt = time.time() - t1
if place is None:
    print(f"embed FAIL after {dt:.1f}s", flush=True)
    json.dump({"formula": rec["formula"], "natoms": rec["natoms"], "embed": "FAIL",
               "seconds": dt}, open(BASE + r"\t13_lead_215_result.json", "w", encoding="utf-8"))
else:
    ok, msg = pot_v2.validate_place(place, rec["atoms"], [tuple(e) for e in rec["edges"]])
    print(f"embed OK {dt:.1f}s validate={ok} {msg}", flush=True)
    rec["place"] = {str(k): list(v) for k, v in place.items()}
    json.dump([rec], open(BASE + r"\t13_lead_215.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    json.dump({"formula": rec["formula"], "natoms": rec["natoms"], "embed": "OK",
               "validate": ok, "seconds": dt},
              open(BASE + r"\t13_lead_215_result.json", "w", encoding="utf-8"))
