# -*- coding: utf-8 -*-
"""t51_pot_v4_embed_check.py：检查 pot_v4 产物（规则 1~11）是否可严格摆放。
抽样：目录中「pot_v4 结构 != 目录结构」的物质 + 随机未变化物质；有界 max_nodes。
"""
import json
import random
import sys
import time

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v2
import pot_v4

BASE = r"G:\AI work\deepseek\work1\alchemy"
MAX_NODES = 2_000_000


def main():
    t0 = time.time()
    cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
    rng = random.Random(9)
    sample = rng.sample(cat, 1200)
    stats = {"checked": 0, "changed": 0, "embed_ok": 0,
             "embed_none": 0, "timeout_or_none": 0, "examples_bad": []}
    for rec in sample:
        atoms = list(rec["atoms"])
        m4 = pot_v4.simulate(atoms)
        if m4 is None or len(m4) != 1:
            continue
        m = m4[0]
        lab_cat = P.mol_label(atoms, [tuple(e) for e in rec["edges"]])
        lab_new = P.mol_label(m["atoms"], [tuple(e) for e in m["edges"]])
        stats["checked"] += 1
        changed = lab_new != lab_cat
        if changed:
            stats["changed"] += 1
        t1 = time.time()
        place = pot_v2.embed_mol2(m["atoms"], [tuple(e) for e in m["edges"]],
                                  max_nodes=MAX_NODES)
        dt = time.time() - t1
        if place is None:
            stats["embed_none"] += 1
            if dt >= 1.0:
                stats["timeout_or_none"] += 1
            if len(stats["examples_bad"]) < 10:
                stats["examples_bad"].append({"formula": P.formula_of(m["atoms"]),
                                              "seconds": round(dt, 2)})
        else:
            stats["embed_ok"] += 1
    stats["seconds"] = round(time.time() - t0, 1)
    json.dump(stats, open(BASE + r"\t51_pot_v4_embed_check.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(stats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
