# -*- coding: utf-8 -*-
"""T13 target：在「已验证可摆放的大分子盆地」里做定向搜索。

种子 = 已验证纪录投料（141/142/143）+ V140，围绕它们做：
  - V140 + A(k) / + W(k) 系列（k=6..15，A/W 为 2 价，前面成功过）
  - 各元素单元素 ±k
  - 随机 ±k 原子（k=1..8）
  - 重分配
  - 已验证分子式本身 + 小幅扰动（含 217/215 大组件分子式）
输出 t13_results_target.jsonl（phase="target"）。
"""
import sys, os, json, time, argparse, random

HERE = r"G:\AI work\deepseek\work1\alchemy"
sys.path.insert(0, HERE)
import t13_search as S
from pot_all import ORDER, parse_formula, formula_of

V140 = S.V140
RESULTS = os.path.join(HERE, "t13_results.jsonl")
EMBED = os.path.join(HERE, "t13_embed.json")
OUT = os.path.join(HERE, "t13_results_target.jsonl")


def vec_add(v, e, k):
    v = list(v)
    v[ORDER.index(e)] += k
    return tuple(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--seed", type=int, default=4242)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    # 已验证的纪录投料 + 最大分子分子式
    seeds = []
    if os.path.exists(EMBED):
        try:
            for d in json.load(open(EMBED, encoding="utf-8")):
                if d.get("status") == "ok" and d.get("max", 0) > 140:
                    seeds.append((f"rec{d['max']}", tuple(d["vec"])))
                    if d.get("formula"):
                        seeds.append((f"mol{d['max']}", parse_formula(d["formula"])))
        except Exception:
            pass
    seeds.append(("V140", V140))
    # 去重
    seen_s, sd = set(), []
    for lab, v in seeds:
        if v not in seen_s:
            seen_s.add(v)
            sd.append((lab, v))
    seeds = sd
    print("[target] seeds:", [(l, sum(v)) for l, v in seeds], flush=True)

    cands = []

    def add(label, v):
        v = S.fix_parity(tuple(v), rng)
        if any(x < 0 for x in v) or sum(v) == 0:
            return
        cands.append((label, v))

    # 1) V140 + A(k) / + W(k) / + X(k) 系列
    for e in ("A", "W", "X", "K", "P", "O"):
        for k in range(1, 16):
            add(f"t_{e}{k}", vec_add(V140, e, k))
    # 2) 每种子：单元素 ±k
    for lab, v in seeds:
        for e in ORDER:
            for k in (1, 2, 3, 5):
                add(f"{lab}_add_{e}{k}", vec_add(v, e, k))
                i = ORDER.index(e)
                if v[i] >= k:
                    vv = list(v)
                    vv[i] -= k
                    add(f"{lab}_sub_{e}{k}", tuple(vv))
    # 3) 每种子：随机 ±k（k=1..8）
    for lab, v in seeds:
        for k in range(1, 9):
            for j in range(2):
                vv = list(v)
                for i in rng.choices(range(9), k=k):
                    if vv[i] > 0 and (j == 1):
                        vv[i] -= 1
                    else:
                        vv[i] += 1
                add(f"{lab}_pm{k}_{j}", tuple(vv))
    # 4) 每种子：重分配
    for lab, v in seeds:
        for j in range(8):
            nz = [i for i in range(9) if v[i] >= 2]
            if len(nz) < 2:
                continue
            a, b = rng.sample(nz, 2)
            m = rng.randint(1, min(10, v[a]))
            vv = list(v)
            vv[a] -= m
            vv[b] += m
            add(f"{lab}_realloc{j}", tuple(vv))
    # 5) 已验证大分子式 + 「补几个小原子」（试图让产物更大）
    for lab, v in seeds:
        if sum(v) < 160:
            for k in (6, 10):
                for e in ("A", "W", "F", "K", "X"):
                    add(f"{lab}_grow_{e}{k}", vec_add(v, e, k))

    # 去重 & 排除已跑过的向量
    seen = set()
    for path in (RESULTS, OUT):
        if os.path.exists(path):
            for line in open(path, encoding="utf-8"):
                try:
                    seen.add(tuple(json.loads(line)["vec"]))
                except Exception:
                    pass
    uniq, us = [], set()
    for lab, v in cands:
        if v in seen or v in us:
            continue
        us.add(v)
        uniq.append((lab, v))
    print(f"[target] candidates={len(uniq)} (raw {len(cands)})", flush=True)

    import multiprocessing as mp
    pool = mp.Pool(args.workers)
    t0 = time.time()
    try:
        B = 28
        done = 0
        for s in range(0, len(uniq), B):
            chunk = uniq[s:s + B]
            recs = pool.map(S.sim_task, [v for _, v in chunk])
            with open(OUT, "a", encoding="utf-8") as f:
                for (lab, v), rec in zip(chunk, recs):
                    rec["phase"] = "target"
                    rec["label"] = lab
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            done += len(chunk)
            big = [(r["max"], r["label"]) for r in recs if r["ok"] and r["max"] > 143]
            best = max((r["max"] for r in recs if r["ok"]), default=0)
            print(f"[target] {done}/{len(uniq)} batch best={best} >143={big[:5]} "
                  f"elapsed={time.time()-t0:.0f}s", flush=True)
    finally:
        pool.close()
        pool.join()


if __name__ == "__main__":
    main()
