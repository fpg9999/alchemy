# -*- coding: utf-8 -*-
"""t19c_extend_enum.py：扩展枚举 6 级中间态骨架形态
- 网格：nO,nP,nK ∈ 0..64 步长 8（729 组）
- 随机大计数：200 组（各 0..120，偏斜）
- 模板放大：35 个多原子形态 × t=2,3,4
收集所有连通块的带标签形态，与 T8 的 38 库对比，检查是否出现新形态。
"""
import itertools
import json
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from t8_level6_forms import level6_components
from t15_forms_examples import wl_key

BASE = r"G:\AI work\deepseek\work1\alchemy"
T8 = json.load(open(BASE + r"\t8_forms.json", encoding="utf-8"))
LIB = {wl_key(f["atoms"], [tuple(e) for e in f["edges"]]): f["formula"] for f in T8}


def collect(counts_list):
    out = {}
    for c in counts_list:
        comps = level6_components(tuple(c))
        for x in comps:
            k = wl_key(x["atoms"], [tuple(e) for e in x["edges"]])
            if k not in out:
                out[k] = {"atoms": x["atoms"], "edges": [list(e) for e in x["edges"]],
                          "size": len(x["atoms"]), "counts": list(c), "count": 0}
            out[k]["count"] += 1
    return out


def worker(args):
    nO, step, N = args
    combos = []
    for nP in range(0, N + 1, step):
        for nK in range(0, N + 1, step):
            combos.append((nO, nP, nK))
    return collect(combos)


def main():
    N, step = 64, 8
    combos_grid = list(range(0, N + 1, step))
    print("grid values:", combos_grid, flush=True)
    merged = {}
    with ProcessPoolExecutor(max_workers=16) as ex:
        for out in ex.map(worker, [(nO, step, N) for nO in combos_grid]):
            for k, v in out.items():
                if k not in merged:
                    merged[k] = dict(v, count=0)
                merged[k]["count"] += v["count"]
    print("网格后形态数:", len(merged), flush=True)

    # 随机大计数
    rng = random.Random(2027)
    rand_combos = []
    for _ in range(200):
        c = [rng.randint(0, 120), rng.randint(0, 120), rng.randint(0, 120)]
        rand_combos.append(c)
    # 模板放大
    for f in T8:
        cnt = [f["atoms"].count(e) for e in ("O", "P", "K")]
        if sum(cnt) < 2:
            continue
        for t in (2, 3, 4):
            rand_combos.append([x * t for x in cnt])
    print("随机/放大 combo 数:", len(rand_combos), flush=True)
    chunk = 40
    with ProcessPoolExecutor(max_workers=12) as ex:
        for out in ex.map(collect, [rand_combos[i:i + chunk] for i in range(0, len(rand_combos), chunk)]):
            for k, v in out.items():
                if k not in merged:
                    merged[k] = dict(v, count=0)
                merged[k]["count"] += v["count"]
    print("总形态数:", len(merged), flush=True)
    new = {k: v for k, v in merged.items() if k not in LIB}
    print("不在 T8 库中的形态:", len(new))
    for k, v in new.items():
        print("   NEW size", v["size"], "atoms", v["atoms"], "edges", v["edges"], "counts", v["counts"])
    json.dump({"n_forms": len(merged),
               "forms": [{"atoms": v["atoms"], "edges": v["edges"], "size": v["size"],
                          "counts": v["counts"], "count": v["count"],
                          "in_t8": k in LIB, "t8_name": LIB.get(k, "")}
                         for k, v in merged.items()],
               "n_outside": len(new),
               "outside": [{"atoms": v["atoms"], "edges": v["edges"], "size": v["size"],
                            "counts": v["counts"]} for v in new.values()]},
              open(BASE + r"\t19_extended_forms.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    from collections import Counter as C2
    print("形态大小分布:", dict(sorted(C2(v["size"] for v in merged.values()).items())))
    print("saved t19_extended_forms.json")


if __name__ == "__main__":
    main()
