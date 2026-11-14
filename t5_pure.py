# -*- coding: utf-8 -*-
"""t5_pure：子引理 L2 的计算检验 —— 纯大类（同一大类 3 价/2 价/1 价各一种）子反应的组件上界。

对纯大类池 P={3价,2价,1价}，穷举三种原子的计数 (n3,n2,n1)，跑完整反应（级别 2,1,0），
统计最大分子与模板。纯大类之间仅元素符号不同，结构同构，故只算聚素即可。
"""
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
CATS = {"聚": ("O", "X", "C"), "动": ("P", "W", "L"), "散": ("K", "A", "F")}


def pure_case(args):
    n3, n2, n1, catname = args
    e3, e2, e1 = CATS[catname]
    atoms = [e3] * n3 + [e2] * n2 + [e1] * n1
    mols = P.simulate(atoms)
    if not mols:
        return (0, [], None)
    sizes = sorted((len(m["atoms"]) for m in mols), reverse=True)
    forms = tuple(sorted(P.formula_of(m["atoms"]) for m in mols))
    return (sizes[0], sizes, forms)


def work(args):
    n3, NMAX, catname = args
    out = {}
    mx = 0
    ex = None
    shapes = Counter()
    for n2 in range(NMAX + 1):
        for n1 in range(NMAX + 1):
            m, sizes, forms = pure_case((n3, n2, n1, catname))
            if m > mx:
                mx, ex = m, (n3, n2, n1, sizes[:10], forms)
            for s in sizes:
                shapes[s] += 1
            out[f"{n3},{n2},{n1}"] = [m, sizes[:6]]
    return n3, out, mx, ex, shapes


def main():
    catname = sys.argv[1] if len(sys.argv) > 1 else "聚"
    NMAX = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    jobs = int(sys.argv[3]) if len(sys.argv) > 3 else max(2, (os.cpu_count() or 4) - 2)
    results = {}
    gmax = 0
    gex = None
    shapes = Counter()
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        for n3, out, mx, e, sh in ex.map(work, [(n3, NMAX, catname) for n3 in range(NMAX + 1)]):
            results.update(out)
            shapes.update(sh)
            if mx > gmax:
                gmax, gex = mx, e
    report = {"category": catname, "NMAX": NMAX, "max_molecule": gmax, "max_example": gex,
              "n_cases": len(results), "component_size_histogram": dict(sorted(shapes.items()))}
    json.dump(report, open(BASE + rf"\t5_pure_{catname}.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(catname, "NMAX", NMAX, "cases", len(results), "max_molecule", gmax, "example", gex)
    print("component size histogram:", report["component_size_histogram"])


if __name__ == "__main__":
    main()
