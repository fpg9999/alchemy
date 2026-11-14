# -*- coding: utf-8 -*-
"""T13 grow：以「最大产物分子尺寸」为目标做爬山搜索（继续找 >140 的大分子）。

策略：
  轮 0：V140 细密缩放扫描 t∈[1.35,2.65]，+ 取整变体，+ 「大组件自身的分子式作为投料」
        （若父投料产出 217+27 两块，则试只喂 217 那一块的向量）
  轮 k ：围绕当前 max 最大的若干投料向量做 ±原子 / 重分配 / 整块缩放扰动
输出追加到 t13_results_grow.jsonl（phase="grow"）。
用法：python t13_grow.py [--workers 14] [--rounds 6]
"""
import sys, os, json, time, argparse, random

HERE = r"G:\AI work\deepseek\work1\alchemy"
sys.path.insert(0, HERE)
import t13_search as S
from pot_all import ORDER, parse_formula, formula_of

RESULTS = os.path.join(HERE, "t13_results.jsonl")
GROW_OUT = os.path.join(HERE, "t13_results_grow.jsonl")
V140 = S.V140


def load_all():
    recs = []
    if not os.path.exists(RESULTS):
        return recs
    for line in open(RESULTS, encoding="utf-8"):
        try:
            recs.append(json.loads(line))
        except Exception:
            pass
    return recs


def scale_vec(v, t):
    return tuple(int(round(x * t)) for x in v)


def round0_cands(recs, rng):
    cands = []

    def add(label, v):
        cands.append((label, S.fix_parity(tuple(v), rng)))

    # 细密缩放
    t = 1.35
    while t <= 2.66:
        add(f"g_scale_{t:.2f}", scale_vec(V140, t))
        t = round(t + 0.05, 2)
    # 取整变体：t=1.5/1.75/2.0 附近向上/向下取整 + 少量元素平衡
    for t in (1.45, 1.5, 1.55, 1.6, 1.65, 1.7, 1.75, 1.8, 1.85, 1.9, 2.0, 2.1, 2.2):
        v = [x * t for x in V140]
        for d in (0.0, 0.5, -0.5):
            vv = [max(0, int(x + d)) for x in v]
            add(f"g_floor_{t:.2f}_{d:+.1f}", tuple(vv))
    # 大组件自身分子式作为投料
    big = sorted([r for r in recs if r["ok"] and r["max"] > 140],
                 key=lambda r: -r["max"])[:8]
    seen_f = set()
    for r in big:
        f = r.get("formula")
        if not f or f in seen_f:
            continue
        seen_f.add(f)
        add(f"g_selffeed_{r['max']}", parse_formula(f))
    return cands


def perturb(seed, rng, tag, j):
    v = list(seed)
    mode = rng.random()
    if mode < 0.45:
        k = rng.randint(1, 8)
        for _ in range(k):
            i = rng.randrange(9)
            v[i] += 1
    elif mode < 0.75:
        k = rng.randint(1, 8)
        nz = [i for i in range(9) if v[i] >= 1]
        for _ in range(k):
            i = rng.choice(nz)
            if v[i] > 0:
                v[i] -= 1
    elif mode < 0.9:
        nz = [i for i in range(9) if v[i] >= 2]
        if len(nz) >= 2:
            a, b = rng.sample(nz, 2)
            m = rng.randint(1, min(10, v[a]))
            v[a] -= m
            v[b] += m
    else:
        # 按比例整体放大 2%~8%
        m = rng.uniform(1.02, 1.08)
        v = [int(round(x * m)) for x in v]
    return (tag, S.fix_parity(tuple(v), rng))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--seed", type=int, default=777)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    import multiprocessing as mp
    recs = load_all()
    seen = set(tuple(r["vec"]) for r in recs)
    ok = [r for r in recs if r["ok"]]
    ok.sort(key=lambda r: -r["max"])
    print(f"[grow] base records={len(recs)} ok={len(ok)} best={ok[0]['max'] if ok else 0}", flush=True)

    pool = mp.Pool(args.workers)
    t_start = time.time()
    try:
        seeds = [(tuple(r["vec"]), r["max"], r["label"]) for r in ok[:6]]
        cur_best = ok[0]["max"] if ok else 0
        for rnd in range(args.rounds):
            if rnd == 0:
                cands = round0_cands(recs, rng)
            else:
                cands = []
                for si, (sv, mx, lab) in enumerate(seeds[:5]):
                    for j in range(3):
                        cands.append(perturb(sv, rng, f"g{si}_{mx}", j))
            uniq, seen_u = [], set()
            for lab, v in cands:
                if any(x < 0 for x in v) or sum(v) == 0 or v in seen or v in seen_u:
                    continue
                seen_u.add(v)
                uniq.append((lab, v))
            if not uniq:
                print(f"[grow] round {rnd}: no new candidates", flush=True)
                break
            t0 = time.time()
            recs_out = pool.map(S.sim_task, [v for _, v in uniq])
            new_best = cur_best
            hits = []
            with open(GROW_OUT, "a", encoding="utf-8") as f:
                for (lab, v), rec in zip(uniq, recs_out):
                    seen.add(v)
                    rec["phase"] = "grow"
                    rec["label"] = lab
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    if rec["ok"]:
                        if rec["max"] > new_best:
                            new_best = rec["max"]
                        if rec["max"] > 140:
                            hits.append((rec["max"], rec["nmols"], lab, list(v), rec["formula"]))
            hits.sort(key=lambda h: -h[0])
            print(f"[grow] round {rnd}: {len(uniq)} sims {time.time()-t0:.0f}s "
                  f"best_round={max((r['max'] for r in recs_out if r['ok']), default=0)} "
                  f"global_best={new_best} >140_hits={len(hits)} {hits[:3]}", flush=True)
            cur_best = new_best
            # 更新种子：用本轮最好的 ok 记录
            allok = [r for r in recs_out if r["ok"]] + [
                {"vec": list(sv), "max": mx, "label": lab, "n": sum(sv)}
                for sv, mx, lab in seeds]
            allok.sort(key=lambda r: -r["max"])
            seeds = [(tuple(r["vec"]), r["max"], r["label"]) for r in allok[:6]]
            if rnd > 0 and new_best == cur_best and not hits:
                pass
    finally:
        pool.close()
        pool.join()


if __name__ == "__main__":
    main()
