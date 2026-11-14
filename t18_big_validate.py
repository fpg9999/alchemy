# -*- coding: utf-8 -*-
"""t18_big_validate.py：用超大分子验证「骨架 = 自身 6 级块 + 0 级同类键融合」分类方式
输入：t12c_big140.json(140)、t12c_big108.json(108)、t13_new_record.json(155)、
      t13_big_struct_lead.json(215/217/156)、t13_scale3.json(258)、t13_scale4.json(346)
输出：t18_big.json
"""
import json
import sys
import time
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from t17b_history_fusion import simulate_record, TRI
from t15_forms_examples import wl_key

BASE = r"G:\AI work\deepseek\work1\alchemy"
TRI = {"O", "P", "K"}

# T8 库 keys
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
    # t13_big_struct_lead.json：可能是 dict of structures
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
    print("structures:", [(n, len(r["atoms"])) for n, r in structs], flush=True)
    results = []
    for name, rec in structs:
        atoms = rec["atoms"]
        n = len(atoms)
        t0 = time.time()
        level6, final, ok = simulate_record(atoms)
        dt = time.time() - t0
        if level6 is None:
            results.append({"name": name, "n": n, "status": "odd/fail", "seconds": dt})
            continue
        # 6 级块形态归属
        block_info = []
        for b in level6:
            ats = [atoms[i] for i in b]
            k = wl_key(ats, [])
            block_info.append({"size": len(b), "in_t8": k in lib,
                               "formula": lib.get(k, "")})
        # final 连通块 -> 由哪些 6 级块组成
        comps = []
        for fc in final:
            blocks = [j for j, b in enumerate(level6) if b <= fc]
            comps.append({"size": len(fc), "blocks": blocks,
                          "cover_ok": set().union(*[set(level6[j]) for j in blocks]) == set(fc) if blocks else False})
        bad = sum(1 for c in comps if not c["cover_ok"])
        results.append({"name": name, "n": n, "status": "ok",
                        "seconds": round(dt, 1),
                        "n_level6_blocks": len(level6),
                        "level6_sizes": sorted(len(b) for b in level6),
                        "all_blocks_in_t8": all(b["in_t8"] for b in block_info),
                        "t8_hits": sum(1 for b in block_info if b["in_t8"]),
                        "n_final_triv_components": len(comps),
                        "fusion_arity": sorted(set(len(c["blocks"]) for c in comps)),
                        "cover_bad": bad})
        print(name, "n=", n, "ok", ok, "6级块:", len(level6),
              "T8命中:", sum(1 for b in block_info if b["in_t8"]),
              "终态块:", len(comps), "融合度:", sorted(set(len(c['blocks']) for c in comps)),
              "cover_bad:", bad, f"{dt:.1f}s", flush=True)
    json.dump(results, open(BASE + r"\t18_big.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t18_big.json")


if __name__ == "__main__":
    main()
