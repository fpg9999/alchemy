# -*- coding: utf-8 -*-
"""t19a_big_level6.py：从超大分子中提取 6 级骨架块（带边），找出不在 T8 38 库中的形态"""
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


def main():
    structs = load_structs()
    forms = {}
    used = 0
    for name, rec in structs:
        atoms = rec["atoms"]
        level6, final, ok, bond6 = simulate_record(atoms, return_bond=True)
        if level6 is None:
            continue
        used += 1
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
            in_t8 = k in lib
            if k not in forms:
                forms[k] = {"atoms": ats, "edges": [list(e) for e in es],
                            "size": len(ats), "examples": [name],
                            "example_formula": "".join(f"{s}{ats.count(s)}" for s in "OPK" if ats.count(s)),
                            "in_t8": in_t8, "count": 0}
            forms[k]["count"] += 1
            if name not in forms[k]["examples"] and len(forms[k]["examples"]) < 5:
                forms[k]["examples"].append(name)
    allf = list(forms.values())
    newf = [f for f in allf if not f["in_t8"]]
    print(f"参与分子 {used}；不同 6 级块形态 {len(allf)}；其中不在 T8 库 {len(newf)}")
    from collections import Counter
    print("按大小分布:", dict(sorted(Counter(f['size'] for f in newf).items())))
    # 打印新形态（按大小排序，最多 40 个）
    newf.sort(key=lambda f: (f["size"], f["example_formula"]))
    for f in newf[:40]:
        print(f"size={f['size']:2d} 组成={f['example_formula']:10s} 边={f['edges']} 例={f['examples'][:2]}")
    json.dump([{k: v for k, v in f.items() if k != "examples"} | {"examples": f["examples"]}
               for f in newf],
              open(BASE + r"\t19_big_new_forms.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    print("saved t19_big_new_forms.json")


if __name__ == "__main__":
    main()
