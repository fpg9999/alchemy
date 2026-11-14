# -*- coding: utf-8 -*-
"""T13 更大分子搜索：投料向量 → pot_v3.simulate → 记录最大产物分子尺寸（先不 embed）。

用法：
    python t13_search.py seed     # V140 种子：±原子 / 配比扰动 / t-缩放
    python t13_search.py rand     # 随机大投料（120~500，含均衡族/偏斜族）
    python t13_search.py adapt    # 自适应爬山：围绕当前最大单分子向量扰动
输出：t13_results.jsonl（逐条追加，含 phase/label/vec/n/ok/nmols/max/top/formula/t）
"""
import sys, os, json, time, random, argparse

HERE = r"G:\AI work\deepseek\work1\alchemy"
sys.path.insert(0, HERE)
import pot_v3
from pot_all import vec_to_atoms, ORDER, VAL, formula_of

OUT = os.path.join(HERE, "t13_results.jsonl")
V140 = (28, 27, 0, 47, 1, 0, 11, 20, 6)   # ORDER: O X C P W L K A F
ODD = [i for i, e in enumerate(ORDER) if VAL[e] % 2 == 1]


# ------------------------------------------------------------------ worker
def sim_task(vec):
    t0 = time.time()
    atoms = vec_to_atoms(vec, ORDER)
    mols = pot_v3.simulate(atoms)
    dt = time.time() - t0
    n = len(atoms)
    rec = {"vec": list(vec), "n": n, "t": round(dt, 2)}
    if mols is None:
        rec.update(ok=False, parity=(sum(v for i, v in enumerate(vec) if i in ODD) % 2 == 1),
                   nmols=0, max=0, top=[], formula=None)
        return rec
    sizes = sorted((len(m["atoms"]) for m in mols), reverse=True)
    big = max(mols, key=lambda m: len(m["atoms"]))
    rec.update(ok=True, nmols=len(mols), max=sizes[0], top=sizes[:5],
               formula=formula_of(big["atoms"]))
    return rec


# ------------------------------------------------------------------ helpers
def n_odd(v):
    return sum(v[i] for i in ODD)


def fix_parity(v, rng):
    v = list(v)
    if n_odd(v) % 2 == 1:
        if all(x >= 0 for x in v):
            opts = []
            for i in ODD:
                opts.append((1, i))
                if v[i] > 0:
                    opts.append((-1, i))
            s, i = rng.choice(opts)
            v[i] += s
    return tuple(v)


def total(v):
    return sum(v)


def vec_of(d):
    return tuple(d.get(e, 0) for e in ORDER)


def gen_seed(rng):
    """种子族：±原子、单元素±k、配比重分配、t-缩放。"""
    cands = []  # (label, vec)

    def add(label, v):
        cands.append((label, fix_parity(v, rng)))

    add("base_V140", V140)
    # t-缩放
    for t in (1.05, 1.1, 1.15, 1.2, 1.25, 1.33, 1.5, 1.75, 2.0):
        add(f"scale_{t}", tuple(int(round(x * t)) for x in V140))
    # 随机 ±k 原子（k=1..8，正负各半，多元素分散）
    for k in range(1, 9):
        for j in range(8):
            sign = 1 if j % 2 == 0 else -1
            v = list(V140)
            for i in rng.choices(range(9), k=k):
                if sign > 0:
                    v[i] += 1
                elif v[i] > 0:
                    v[i] -= 1
            add(f"pm_k{k}_{'p' if sign>0 else 'm'}_{j}", tuple(v))
    # 单元素 ±k
    for i, e in enumerate(ORDER):
        for k in (1, 2, 3, 5, 8):
            v = list(V140)
            v[i] += k
            add(f"add_{e}{k}", tuple(v))
            if V140[i] >= k:
                v = list(V140)
                v[i] -= k
                add(f"sub_{e}{k}", tuple(v))
    # 配比重分配（总量不变）：从元素 a 移 m 个到元素 b
    for m in (1, 2, 3, 5, 8, 12, 16):
        for j in range(10):
            a, b = rng.sample([i for i in range(9) if V140[i] >= m], 2)
            v = list(V140)
            v[a] -= m
            v[b] += m
            add(f"realloc_{m}_{j}", tuple(v))
    # 定向重分配：O/P/K/F 之间互换（大分子关键元素）
    key = [0, 3, 6, 8, 1, 2]  # O P K F X C
    for m in (2, 4, 8, 16):
        for a in key:
            for b in key:
                if a != b and V140[a] >= m:
                    v = list(V140)
                    v[a] -= m
                    v[b] += m
                    add(f"move_{ORDER[a]}{m}to{ORDER[b]}", tuple(v))
    return cands


def gen_rand(rng):
    """随机大投料：均匀 9 维 / 均衡族 / 偏斜族，总原子 120~500。"""
    cands = []

    def add(label, v):
        cands.append((label, fix_parity(v, rng)))

    # 均匀随机 9 维（不含 0 强制，允许 0）
    n_list = [120, 130, 140, 150, 160, 170, 180, 190, 200, 215, 230, 245,
              260, 280, 300, 320, 345, 370, 400]
    for rep in range(4):
        for n in n_list:
            v = [0] * 9
            for _ in range(n):
                v[rng.randrange(9)] += 1
            add(f"unif{rep}_n{n}", tuple(v))
    # 超高投料（每个只 1 组，simulate 很贵）
    for n in (440, 500):
        v = [0] * 9
        for _ in range(n):
            v[rng.randrange(9)] += 1
        add(f"unif_hi_n{n}", tuple(v))
    # 均衡族：各元素计数相近
    for n in (126, 135, 144, 153, 162, 180, 198, 216, 252, 288, 351, 432):
        base = n // 9
        rem = n - base * 9
        v = [base] * 9
        for _ in range(rem):
            v[rng.randrange(9)] += 1
        for _ in range(6):
            vv = list(v)
            for _ in range(rng.randint(0, 4)):
                a = rng.randrange(9)
                if vv[a] > 1:
                    vv[a] -= 1
                    vv[rng.randrange(9)] += 1
            add(f"bal_n{n}", tuple(vv))
    # 偏斜族：某元素占 55~75%
    for n in (120, 150, 180, 210, 240, 280, 330, 400, 460):
        for _ in range(3):
            e = rng.randrange(9)
            v = [0] * 9
            v[e] = int(n * rng.uniform(0.55, 0.75))
            for _ in range(n - v[e]):
                v[rng.randrange(9)] += 1
            add(f"skew_{ORDER[e]}_n{n}", tuple(v))
    return cands


def gen_adapt(seeds, rng, per_seed=3):
    """围绕给定种子向量生成扰动（±原子 + 重分配）。"""
    out = []

    def add(label, v):
        out.append((label, fix_parity(v, rng)))

    for si, (seed_vec, seed_n, tag) in enumerate(seeds):
        for j in range(per_seed):
            v = list(seed_vec)
            mode = rng.random()
            if mode < 0.55:
                k = rng.randint(1, 6)
                for _ in range(k):
                    i = rng.randrange(9)
                    if v[i] > 0 and rng.random() < 0.4:
                        v[i] -= 1
                    else:
                        v[i] += 1
            elif mode < 0.85:
                # 重分配
                nz = [i for i in range(9) if v[i] >= 2]
                if len(nz) >= 2:
                    a, b = rng.sample(nz, 2)
                    m = rng.randint(1, min(8, v[a]))
                    v[a] -= m
                    v[b] += m
            else:
                # 加一小块「同族」原子（保持大类比例）
                k = rng.randint(1, 10)
                for _ in range(k):
                    v[rng.randrange(9)] += 1
            add(f"adapt_{tag}_s{si}_j{j}", tuple(v))
    return out


# ------------------------------------------------------------------ driver
def run_phase(phase, cands, pool, budget_s=None):
    seen = set()
    uniq = []
    for label, v in cands:
        if any(x < 0 for x in v) or total(v) == 0:
            continue
        if v in seen:
            continue
        seen.add(v)
        uniq.append((label, v))
    print(f"[{phase}] candidates={len(uniq)} (raw {len(cands)})", flush=True)
    t0 = time.time()
    results = []
    B = 24
    with open(OUT, "a", encoding="utf-8") as f:
        for s in range(0, len(uniq), B):
            chunk = uniq[s:s + B]
            recs = pool.map(sim_task, [v for _, v in chunk])
            for (label, v), rec in zip(chunk, recs):
                rec["phase"] = phase
                rec["label"] = label
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                results.append(rec)
            f.flush()
            best = max((r["max"] for r in results if r["ok"]), default=0)
            n1 = sum(1 for r in results if r["ok"] and r["nmols"] == 1)
            print(f"  [{phase}] {len(results)}/{len(uniq)} best_max={best} single_mol={n1} "
                  f"elapsed={time.time()-t0:.0f}s", flush=True)
            if budget_s and time.time() - t0 > budget_s:
                print(f"  [{phase}] budget {budget_s}s reached, stop", flush=True)
                break
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phases", nargs="+", default=["seed"])
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--seed", type=int, default=20261113)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    import multiprocessing as mp
    if "adapt" in args.phases:
        phases = [p for p in args.phases if p != "adapt"]
        print("[init] 先跑", phases, flush=True)
        for ph in phases:
            _run(ph, rng, args.workers)
        _run_adapt(rng, args.workers)
        return
    for ph in args.phases:
        _run(ph, rng, args.workers)


def _run(phase, rng, workers):
    import multiprocessing as mp
    gens = {"seed": gen_seed, "rand": gen_rand}
    cands = gens[phase](rng)
    pool = mp.Pool(workers)
    try:
        run_phase(phase, cands, pool)
    finally:
        pool.close()
        pool.join()


def _run_adapt(rng, workers):
    import multiprocessing as mp
    # 读已有结果，取最大的单分子向量作为种子
    hits = []
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("ok") and r.get("nmols") == 1:
                hits.append(r)
    if not hits:
        print("[adapt] no single-molecule hit yet, seed from V140", flush=True)
        seeds = [(V140, 140, "V140")]
    else:
        hits.sort(key=lambda r: -r["max"])
        seeds = [(tuple(h["vec"]), h["n"], f"n{h['n']}") for h in hits[:8]]
    pool = mp.Pool(workers)
    try:
        seen = set()
        if os.path.exists(OUT):
            for line in open(OUT, encoding="utf-8"):
                try:
                    seen.add(tuple(json.loads(line)["vec"]))
                except Exception:
                    pass
        best_hist = []
        for rnd in range(14):
            cands = gen_adapt(seeds, rng, per_seed=2)
            cands = [(l, v) for l, v in cands if v not in seen]
            if not cands:
                print(f"[adapt] round {rnd}: no new candidates, stop", flush=True)
                break
            t0 = time.time()
            recs = pool.map(sim_task, [v for _, v in cands])
            for (label, v), rec in zip(cands, recs):
                seen.add(v)
                rec["phase"] = "adapt"
                rec["label"] = f"r{rnd}_" + label
                with open(OUT, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                if rec["ok"] and rec["nmols"] == 1:
                    best_hist.append((rec["max"], rec["n"], label, tuple(rec["vec"])))
            best_hist.sort(key=lambda x: -x[0])
            hits_now = [h for h in best_hist if h[0] > 140]
            print(f"[adapt] round {rnd}: {len(recs)} sims, {time.time()-t0:.0f}s, "
                  f"best={best_hist[0][0] if best_hist else 0}, "
                  f"records>140={len(hits_now)}", flush=True)
            # 更新种子：最大单分子
            if best_hist:
                seeds = [(h[3], h[1], f"n{h[1]}") for h in best_hist[:8]]
    finally:
        pool.close()
        pool.join()


if __name__ == "__main__":
    main()
