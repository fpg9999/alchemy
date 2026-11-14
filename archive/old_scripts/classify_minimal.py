# -*- coding: utf-8 -*-
"""classify_minimal：找"最小无限元素集合"。
口径（允许池）：只用子集 S 里的元素投料，若存在任意大的分子（实测 T=28 时最大分子 >= 18），
则 S 无限；由于元素只增不减，S 的超集也无限。用递增规模搜索最小无限集合。

阶段：3 元组(84) T=24/28 全枚举 → 4 元组(不含无限 3 元组) T=24 全枚举 →
      5 元组(不含无限 3/4 元组) T=20 随机抽样。
"""
import itertools
import json
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
THRESH = 18  # 有限块实测封顶 16；>=18 视为无限证据


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


def best_for(scope_elems, vecs):
    """两阶段：先模拟找最大的若干候选，再对候选做（有预算的）几何判定。
    返回 (max_atoms, formula, feed) —— 成功反应（全部产物可摆）中最大分子。"""
    cands = []
    for v in vecs:
        atoms = P.vec_to_atoms(v, P.ORDER)
        if sum(P.VAL[e] for e in atoms) % 2:
            continue
        mols = P.simulate(atoms)
        if not mols:
            continue
        mx = max(len(m["atoms"]) for m in mols)
        if mx < THRESH:
            continue
        cands.append((mx, v, mols))
    cands.sort(key=lambda t: -t[0])
    best = (0, None, None)
    for mx, v, mols in cands[:60]:
        ok = True
        for m in mols:
            if P.embed_mol(m["atoms"], m["edges"], max_nodes=120000) is None:
                ok = False
                break
        if not ok:
            continue
        m = [x for x in mols if len(x["atoms"]) == mx][0]
        best = (mx, P.formula_of(m["atoms"]), list(v))
        break
    return best


def enum_task(args):
    elems, T = args
    vecs = [vec_full(c, elems) for c in gen_compositions(T, len(elems))]
    return elems, T, best_for(elems, vecs)


def rand_task(args):
    elems, T, n = args
    rng = random.Random(hash(tuple(elems)) & 0xffffffff)
    vecs = []
    for _ in range(n):
        cuts = sorted(rng.sample(range(T + len(elems) - 1), len(elems) - 1))
        out, prev = [], -1
        for c in cuts + [T + len(elems) - 1]:
            out.append(c - prev - 1)
            prev = c
        vecs.append(vec_full(out, elems))
    return elems, T, best_for(elems, vecs)


def run(pool, fn, tasks, label):
    out = {}
    for elems, T, best in pool.map(fn, tasks):
        key = tuple(elems)
        if key not in out or best[0] > out[key][0]:
            out[key] = best
    print(f"[{label}] 完成 {len(tasks)} 个任务", flush=True)
    return out


def main():
    jobs = max(4, (os.cpu_count() or 8) - 2)
    results = {}
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        # Phase A: 3 元组，T=24 与 T=28
        triples = list(itertools.combinations(P.ORDER, 3))
        for T in (24, 28):
            res = run(pool, enum_task, [(list(t), T) for t in triples], f"3元组 T={T}")
            for k, v in res.items():
                old = results.get(k)
                if old is None or v[0] > old[0]:
                    results[k] = (v[0], v[1], v[2], T)
        inf3 = {k for k, v in results.items() if v[0] >= THRESH}
        print(f"无限 3 元组: {len(inf3)} 个", flush=True)
        for k in sorted(inf3):
            print("  ", "/".join(k), results[k][0], results[k][1], flush=True)

        # Phase B: 4 元组（不含无限 3 元组），T=24 全枚举
        fours = [c for c in itertools.combinations(P.ORDER, 4)
                 if not any(set(t) <= set(c) for t in inf3)]
        print(f"待测 4 元组: {len(fours)} 个", flush=True)
        res4 = run(pool, enum_task, [(list(c), 24) for c in fours], "4元组 T=24")
        inf4 = set()
        for k, v in res4.items():
            if v[0] >= THRESH:
                inf4.add(k)
                results[k] = (v[0], v[1], v[2], 24)
        print(f"无限 4 元组: {len(inf4)} 个", flush=True)
        for k in sorted(inf4):
            print("  ", "/".join(k), results[k][0], results[k][1], flush=True)

        # Phase C: 5 元组（不含无限 3/4 元组），T=20 随机抽样
        fives = [c for c in itertools.combinations(P.ORDER, 5)
                 if not any(set(t) <= set(c) for t in inf3)
                 and not any(set(t) <= set(c) for t in inf4)]
        print(f"待测 5 元组: {len(fives)} 个", flush=True)
        res5 = run(pool, rand_task, [(list(c), 20, 4000) for c in fives], "5元组 T=20 抽样")
        inf5 = set()
        for k, v in res5.items():
            if v[0] >= 17:  # T=20 时有限封顶 <=16
                inf5.add(k)
                results[k] = (v[0], v[1], v[2], 20)
        print(f"无限 5 元组: {len(inf5)} 个", flush=True)
        for k in sorted(inf5):
            print("  ", "/".join(k), results[k][0], results[k][1], flush=True)

    minimal = [k for k in results if results[k][0] >= (THRESH if len(k) <= 4 else 17)]
    out = {
        "threshold": THRESH,
        "inf3": ["/".join(k) for k in sorted(inf3)],
        "inf4": ["/".join(k) for k in sorted(inf4)],
        "inf5": ["/".join(k) for k in sorted(inf5)],
        "minimal": ["/".join(k) for k in sorted(minimal)],
        "evidence": {"/".join(k): {"max": v[0], "formula": v[1], "feed": v[2], "T": v[3]}
                     for k, v in results.items()},
    }
    json.dump(out, open(BASE + r"\minimal_infinite.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved minimal_infinite.json; 最小无限集合(去超集):")
    mins = []
    for k in minimal:
        if not any(set(m) < set(k) and m in minimal for m in minimal):
            mins.append(k)
    for k in sorted(mins):
        print("  最小:", "/".join(k))


if __name__ == "__main__":
    main()
