# -*- coding: utf-8 -*-
"""t19a2：列出超大分子的全部 6 级块形态（并与 T8 库对比）"""
import json
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from t17b_history_fusion import simulate_record
from t15_forms_examples import wl_key

BASE = r"G:\AI work\deepseek\work1\alchemy"
lib = {}
t8 = json.load(open(BASE + r"\t8_forms.json", encoding="utf-8"))
for f in t8:
    lib[wl_key(f["atoms"], [tuple(e) for e in f["edges"]])] = f["formula"]


def load_structs():
    out = []
    for fn in ["t12c_big140.json", "t12c_big108.json", "t13_new_record.json",
               "t13_scale3.json", "t13_scale4.json"]:
        try:
            d = json.load(open(BASE + "\\" + fn, encoding="utf-8"))
        except Exception:
            continue
        rec = d[0] if isinstance(d, list) else d
        if isinstance(rec, dict) and rec.get("atoms"):
            out.append((fn, rec))
    try:
        d = json.load(open(BASE + r"\t13_big_struct_lead.json", encoding="utf-8"))
        if isinstance(d, dict):
            for k, v in d.items():
                if isinstance(v, dict) and v.get("atoms"):
                    out.append(("big_struct:" + str(k), v))
        elif isinstance(d, list):
            for i, v in enumerate(d):
                if isinstance(v, dict) and v.get("atoms"):
                    out.append((f"big_struct:{i}", v))
    except Exception:
        pass
    return out


forms = {}
for name, rec in load_structs():
    atoms = rec["atoms"]
    level6, final, ok, bond6 = simulate_record(atoms, return_bond=True)
    if level6 is None:
        continue
    for b in level6:
        mem = sorted(b)
        idx = {v: k for k, v in enumerate(mem)}
        ats = [atoms[v] for v in mem]
        es = []
        for x in range(len(mem)):
            for y in range(x + 1, len(mem)):
                m = bond6[mem[x]][mem[y]]
                if m:
                    es.append((x, y, m))
        k = wl_key(ats, es)
        if k not in forms:
            forms[k] = {"atoms": ats, "edges": [list(e) for e in es],
                        "size": len(ats), "formula": "".join(f"{s}{ats.count(s)}" for s in "OPK" if ats.count(s)),
                        "in_t8": k in lib, "t8_name": lib.get(k, ""), "count": 0}
        forms[k]["count"] += 1
allf = list(forms.values())
allf.sort(key=lambda f: (f["size"], f["formula"]))
print(f"超大分子的 6 级块形态: {len(allf)} 种")
for f in allf:
    print(f"  size={f['size']:2d} {f['formula']:10s} in_T8={f['in_t8']} count={f['count']} edges={f['edges']}")
json.dump(allf, open(BASE + r"\t19_big_forms.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=0)

# T8 全部 38 形态清单
print("\nT8 38 库清单:")
for f in t8:
    print(f"  {f['formula']:10s} size={len(f['atoms']):2d} edges={f['edges']}")
