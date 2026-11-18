# -*- coding: utf-8 -*-
"""t3_max_search：搜索"全 9 元素"范围内最大可产出单分子，判断是否存在无界增长。

步骤：
1) 随机大投料（T=40/48/56/64/80）若干样本，找最大单分子（只模拟）。
2) 从最好的投料出发做爬山：随机增删少量原子，最大化最大单分子尺寸；一直加到 T 上限。
3) 对每个新纪录做整锅 embed 校验。
输出 t3_max_search.json
"""
import json
import random
import sys
import time

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
ORDER = P.ORDER


def outcome(feed):
    atoms = P.vec_to_atoms(tuple(feed), ORDER)
    if not atoms or sum(P.VAL[e] for e in atoms) % 2:
        return None
    mols = P.simulate(atoms)
    if not mols:
        return None
    sizes = sorted((len(m["atoms"]) for m in mols), reverse=True)
    return sizes, mols


def score(feed):
    o = outcome(feed)
    if o is None:
        return (-1, 999)
    sizes, mols = o
    return (sizes[0], len(sizes))


def rand_feed(T, rng):
    cuts = sorted(rng.sample(range(T + 8), 8))
    out, prev = [], -1
    for c in cuts + [T + 8]:
        out.append(c - prev - 1)
        prev = c
    return out


def validate(feed, budget=600000):
    o = outcome(feed)
    if o is None:
        return None
    sizes, mols = o
    ok = True
    for m in mols:
        if P.embed_mol(m["atoms"], m["edges"], max_nodes=budget) is None:
            ok = False
            break
    big = [m for m in mols if len(m["atoms"]) == sizes[0]][0]
    return {"max": sizes[0], "sizes": sizes, "pot_ok": ok,
            "formula": P.formula_of(big["atoms"]), "feed": list(feed),
            "elements": sorted(set(big["atoms"]))}


def main():
    rng = random.Random(20261112)
    records = []
    best = (-1, None)
    t0 = time.time()
    # 1) 随机搜索
    for T in (40, 48, 56, 64, 80):
        for _ in range(150):
            f = rand_feed(T, rng)
            sc = score(f)
            if sc[0] > best[0]:
                best = (sc[0], list(f))
                rec = validate(f)
                records.append({"stage": "random", "T": T, **rec})
                print(f"[random T={T}] new best max={rec['max']} {rec['formula']} "
                      f"pot_ok={rec['pot_ok']} elems={rec['elements']} ({time.time()-t0:.1f}s)", flush=True)
    print("random search done, best", best[0], flush=True)

    # 2) 爬山：不断增加原子 / 微调比例
    cur = list(best[1])
    cur_sc = score(cur)
    for it in range(600):
        cand = list(cur)
        mode = rng.random()
        if mode < 0.5:
            # 加几个原子
            for _ in range(rng.randint(1, 4)):
                cand[rng.randrange(9)] += 1
        elif mode < 0.8:
            # 转移原子
            i, j = rng.randrange(9), rng.randrange(9)
            if cand[i] > 0:
                cand[i] -= 1
                cand[j] += 1
        else:
            # 大规模加原子
            for _ in range(rng.randint(4, 12)):
                cand[rng.randrange(9)] += 1
        if sum(cand) > 150:
            continue
        sc = score(cand)
        if sc > cur_sc:
            cur, cur_sc = cand, sc
            rec = validate(cand)
            if rec and rec["max"] >= 40:
                records.append({"stage": "hill", "it": it, **rec})
                print(f"[hill {it}] T={sum(cand)} max={rec['max']} {rec['formula']} "
                      f"pot_ok={rec['pot_ok']} elems={rec['elements']} nmols={len(rec['sizes'])}", flush=True)
        elif rng.random() < 0.02:
            # 偶尔接受较差解（跳出局部）
            cur, cur_sc = cand, sc
    records.sort(key=lambda r: r.get("max", 0))
    json.dump({"records": records}, open(BASE + r"\t3_max_search.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved; top records:")
    for r in records[-8:]:
        print(" ", r["max"], r["formula"], "T=", sum(r["feed"]), "pot_ok=", r["pot_ok"], "elems=", r["elements"])


if __name__ == "__main__":
    main()
