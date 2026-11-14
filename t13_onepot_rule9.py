# -*- coding: utf-8 -*-
"""t13_onepot_rule9：检验规则 9 新目录的一锅复现性：
  对目录中每个物质，按它自身的元素组成投料，用 pot_v3（规则 1~9）应恰好得到该物质一个分子。"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v3

BASE = r"G:\AI work\deepseek\work1\alchemy"


def check(chunk):
    bad = []
    ok = 0
    for item in chunk:
        atoms = P.vec_to_atoms(tuple(item["vec"]), P.ORDER)
        mols = pot_v3.simulate(atoms)
        if not mols:
            bad.append((item["formula"], "sim_fail"))
            continue
        forms = [P.formula_of(m["atoms"]) for m in mols]
        if len(forms) == 1 and forms[0] == item["formula"]:
            ok += 1
        else:
            bad.append((item["formula"], sorted(forms)))
    return ok, bad


def main():
    data = json.load(open(BASE + r"\t4_catalog_le16_rule9.json", encoding="utf-8"))
    jobs = int(sys.argv[1]) if len(sys.argv) > 1 else max(2, (os.cpu_count() or 4) - 2)
    CH = 500
    tasks = [data[i:i + CH] for i in range(0, len(data), CH)]
    ok_total = 0
    bad_all = []
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for ok, bad in ex.map(check, tasks):
            ok_total += ok
            bad_all.extend(bad)
    print(f"one-pot: {ok_total}/{len(data)} OK, bad={len(bad_all)}")
    for b in bad_all[:20]:
        print("BAD", b)
    json.dump({"total": len(data), "ok": ok_total, "bad": bad_all[:200]},
              open(BASE + r"\t13_onepot_rule9.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
