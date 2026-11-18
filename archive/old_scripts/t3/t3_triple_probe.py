# -*- coding: utf-8 -*-
"""t3_triple_probe：对争议/确认的 3 元组做更大 T 范围全枚举 + 最大分子候选校验。

阶段1（并行，只模拟）：对每个 (triple, T) 全枚举总原子=T 的投料，记录反应成功的最大单分子（原始值）。
阶段2（并行，逐锅校验）：对每个 (triple,T) 的最大候选整锅 embed 校验，得到 validated max。
输出 t3_triple_probe_raw.json / t3_triple_probe_val.json
"""
import itertools
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"


def gen_compositions(total, k, prefix=()):
    if k == 1:
        yield prefix + (total,)
        return
    for x in range(total + 1):
        yield from gen_compositions(total - x, k - 1, prefix + (x,))


def work(task):
    elems, T = task
    best = None
    ok = 0
    for counts in gen_compositions(T, len(elems)):
        atoms = P.vec_to_atoms(counts, elems)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        mols = P.simulate(atoms)
        if not mols:
            continue
        ok += 1
        mx = max(len(m["atoms"]) for m in mols)
        if best is None or mx > best[0]:
            m = [x for x in mols if len(x["atoms"]) == mx][0]
            best = (mx, P.formula_of(m["atoms"]), list(counts),
                    [list(m["atoms"]), [list(e) for e in m["edges"]]])
    return "/".join(elems), T, best, ok


def check_pot(task):
    key, T, feed, budget = task
    elems = key.split("/")
    atoms = P.vec_to_atoms(tuple(feed), elems)
    mols = P.simulate(atoms)
    if not mols:
        return key, T, None
    sizes = sorted((len(m["atoms"]) for m in mols), reverse=True)
    okall = True
    for m in mols:
        if P.embed_mol(m["atoms"], m["edges"], max_nodes=budget) is None:
            okall = False
            break
    return key, T, {"raw": sizes[0], "pot_ok": okall, "sizes": sizes,
                    "formula": P.formula_of([m["atoms"] for m in mols if len(m["atoms"]) == sizes[0]][0])}


CONFIRMED = ["O/X/P", "O/X/K", "O/P/W", "O/P/A", "O/W/K", "O/K/A", "X/P/K", "P/W/K", "P/K/A"]


def main():
    Ts = [int(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else [36, 40, 44, 48, 52, 56, 60, 64, 72, 80]
    disputed = ["O/X/A", "O/X/W", "X/P/W", "X/K/A", "P/W/A", "W/K/A", "O/P/K", "O/W/A", "X/P/A", "X/W/K"]
    if len(sys.argv) > 2:
        triples = [c.split("/") for c in sys.argv[2].split(",")]
    else:
        triples = [c.split("/") for c in CONFIRMED + disputed]
    jobs = max(2, (os.cpu_count() or 4) // 2 - 2)
    tasks = [(t, T) for t in triples for T in Ts]
    raw = {}
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for key, T, best, ok in ex.map(work, tasks):
            raw.setdefault(key, {})[str(T)] = {"max": best[0], "formula": best[1],
                                               "feed": best[2], "mol": best[3], "ok": ok}
            print(f"RAW {key:8s} T={T:2d} max={best[0]:2d} {best[1]}", flush=True)
    json.dump(raw, open(BASE + r"\t3_triple_probe_raw.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("phase1 saved, validating...", flush=True)

    budget = 200000
    tasks2 = []
    for key, byT in raw.items():
        for T, rec in byT.items():
            tasks2.append((key, int(T), rec["feed"], budget))
    val = {}
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for key, T, res in ex.map(check_pot, tasks2):
            if res is None:
                continue
            val.setdefault(key, {})[str(T)] = res
            print(f"VAL {key:8s} T={T:>2s} raw={res['raw']:2d} pot_ok={res['pot_ok']} sizes={res['sizes']}", flush=True)
    json.dump(val, open(BASE + r"\t3_triple_probe_val.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved")


if __name__ == "__main__":
    main()
