# -*- coding: utf-8 -*-
"""extend_incremental：对"有限但封顶>16"的类别，只枚举尚未覆盖的高原子数档，
补齐完整物质清单；并判断是否到达封顶（某档不再出现新分子）。

ext1 覆盖：3 元组 N≤24、4 元组 N≤22、5 元组 N≤20、6 元组 N≤18。
本脚本：4→总原子 23~26；5→21~24；6→19~22（若仍贴边再手动加档）。
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
START = {3: 25, 4: 23, 5: 21, 6: 19}
END = {3: 26, 4: 26, 5: 24, 6: 22}


def gen_compositions(total, k, prefix=()):
    if k == 1:
        yield prefix + (total,)
        return
    for x in range(total + 1):
        yield from gen_compositions(total - x, k - 1, prefix + (x,))


def vec_full(partial, elems):
    v = [0] * 9
    for e, c in zip(elems, partial):
        v[P.ORDER.index(e)] = c
    return tuple(v)


def scan(args):
    elems, t0, t1 = args
    found = {}
    for total in range(t0, t1 + 1):
        for comp in gen_compositions(total, len(elems)):
            v = vec_full(comp, elems)
            atoms = P.vec_to_atoms(v, P.ORDER)
            if sum(P.VAL[e] for e in atoms) % 2:
                continue
            mols = P.simulate(atoms)
            if not mols:
                continue
            ok = True
            for m in mols:
                if P.embed_mol(m["atoms"], m["edges"], max_nodes=40000) is None:
                    ok = False
                    break
            if not ok:
                continue
            for m in mols:
                f = P.formula_of(m["atoms"])
                if f not in found:
                    found[f] = {"formula": f, "natoms": len(m["atoms"]),
                                "zh": P.zh_of(m["atoms"]), "feed": list(v),
                                "atoms": list(m["atoms"])}
    return "/".join(elems), t0, t1, found


def main():
    rec = json.load(open(BASE + r"\recheck_finite.json", encoding="utf-8"))
    cats = [k for k, v in rec.items() if v["max"] > 16]
    jobs = max(4, (os.cpu_count() or 8) - 6)
    tasks = [(c.split("/"), START[len(c.split("/"))], END[len(c.split("/"))]) for c in cats]
    print("增量扩展类别:", len(tasks), flush=True)
    out = {}
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for key, t0, t1, found in pool.map(scan, tasks):
            mx = max((x["natoms"] for x in found.values()), default=0)
            out[key] = {"t0": t0, "t1": t1, "substances": list(found.values()), "max": mx,
                        "hit_bound": mx >= t1 - 1}
            print(f"  {key} 新增档 {t0}~{t1}: 新物质 {len(found)}, 最大 {mx}, 可能贴边={out[key]['hit_bound']}", flush=True)
            json.dump(out, open(BASE + r"\extended_finite2.json", "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
    print("saved extended_finite2.json")


if __name__ == "__main__":
    main()
