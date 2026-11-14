# -*- coding: utf-8 -*-
"""t3_classify_triples：84 个三元组全枚举（恰好 T 个原子）判无限/有限 + 封顶。

任务粒度: (subset, T)。每个任务枚举该子集内所有总原子=T 的投料向量，求成功反应中最大单分子。
输出 t3_triples.json
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
    best = (0, None, None)
    ok = 0
    for counts in gen_compositions(T, len(elems)):
        atoms = P.vec_to_atoms(counts, elems)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        mols = P.simulate(atoms)
        if not mols:
            continue
        mx = max(len(m["atoms"]) for m in mols)
        m = [x for x in mols if len(x["atoms"]) == mx][0]
        if P.embed_mol(m["atoms"], m["edges"], max_nodes=200000) is None:
            continue
        if not P.embed_all(mols):
            continue
        ok += 1
        if mx > best[0]:
            best = (mx, P.formula_of(m["atoms"]), list(counts))
    return tuple(elems), T, best, ok


def main():
    Ts = [20, 24, 28, 32, 40, 48, 56, 64, 80]
    if len(sys.argv) > 1:
        Ts = [int(x) for x in sys.argv[1].split(",")]
    triples = [list(t) for t in itertools.combinations(P.ORDER, 3)]
    jobs = max(2, (os.cpu_count() or 4) - 2)
    tasks = [(t, T) for t in triples for T in Ts]
    out = {}
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for elems, T, best, ok in ex.map(work, tasks):
            out.setdefault("/".join(elems), {})[str(T)] = {"max": best[0], "formula": best[1],
                                                           "feed": best[2], "ok": ok}
            print(f"{'/'.join(elems):10s} T={T:2d} max={best[0]:2d} {best[1]}", flush=True)
    json.dump(out, open(BASE + r"\t3_triples.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 汇总
    print("\n== 汇总 ==")
    inf = []
    for k, d in out.items():
        m = {int(T): v["max"] for T, v in d.items()}
        # 无限：T=80 时最大分子 >= 40（有限类封顶远小于此）
        isinf = m[80] >= 40
        if isinf:
            inf.append(k)
        print(f"{k:10s} " + " ".join(f"{T}:{m[T]:2d}" for T in sorted(m)))
    print("无限三元组:", len(inf), inf)
    json.dump({"infinite": inf, "data": out}, open(BASE + r"\t3_triples_summary.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
