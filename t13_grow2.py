# -*- coding: utf-8 -*-
"""T13 grow2：第二轮定向生长——从「已验证可摆放」的分子式出发继续加原子。

种子：t13_embed.json + t13_embed_screen.json 中 status=ok 的(投料向量, 分子式向量)。
族群：
  mol + e_k（e=O/X/A/W/K/P/F，k=1..10）
  mol + 随机 ±k（k=1..8，2 变体）
  feed + e_k
  mol + (A/W/O combo)
输出 t13_results_grow2.jsonl（phase="grow2"）。
"""
import sys, os, json, time, argparse, random

HERE = r"G:\AI work\deepseek\work1\alchemy"
sys.path.insert(0, HERE)
import t13_search as S
from pot_all import ORDER, parse_formula

V140 = S.V140
OUT = os.path.join(HERE, "t13_results_grow2.jsonl")
EXIST = ["t13_results.jsonl", "t13_results_grow.jsonl",
         "t13_results_target.jsonl", "t13_results_grow2.jsonl"]


def load_verified():
    out = []
    for fn in ("t13_embed.json", "t13_embed_screen.json"):
        p = os.path.join(HERE, fn)
        if not os.path.exists(p):
            continue
        for d in json.load(open(p, encoding="utf-8")):
            if d.get("status") == "ok" and d.get("valid") and d.get("max", 0) > 140:
                out.append(d)
    # 去重 by (max, formula)
    seen, uniq = set(), []
    for d in sorted(out, key=lambda d: -d["max"]):
        key = (d["max"], d.get("formula"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(d)
    return uniq


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=13)
    ap.add_argument("--top-mols", type=int, default=4)
    ap.add_argument("--seed", type=int, default=31337)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    recs = load_verified()
    print(f"[grow2] verified records={len(recs)}: "
          f"{[(r['max'], r.get('formula')) for r in recs[:6]]}", flush=True)
    seeds = []
    for d in recs[:args.top_mols]:
        if d.get("formula"):
            seeds.append((f"mol{d['max']}", parse_formula(d["formula"])))
        seeds.append((f"rec{d['max']}", tuple(d["vec"])))
    # 追加 V140 基线
    seeds.append(("V140", V140))

    cands = []

    def add(label, v):
        v = S.fix_parity(tuple(v), rng)
        if any(x < 0 for x in v) or sum(v) == 0:
            return
        cands.append((label, v))

    for lab, v in seeds:
        if lab.startswith("mol"):
            for e in ("O", "X", "A", "W", "K", "P", "F"):
                for k in range(1, 11):
                    vv = list(v)
                    vv[ORDER.index(e)] += k
                    add(f"{lab}_add_{e}{k}", tuple(vv))
            for k in range(1, 9):
                for j in range(2):
                    vv = list(v)
                    for i in rng.choices(range(9), k=k):
                        if vv[i] > 0 and j == 1:
                            vv[i] -= 1
                        else:
                            vv[i] += 1
                    add(f"{lab}_pm{k}_{j}", tuple(vv))
            # 大原子组合：O+X / O+A / X+A / O+X+A 各加少量
            for (a, b) in (("O", "X"), ("O", "A"), ("X", "A"), ("O", "K"), ("P", "A")):
                for k in (2, 4, 6):
                    vv = list(v)
                    vv[ORDER.index(a)] += k
                    vv[ORDER.index(b)] += k
                    add(f"{lab}_combo_{a}{b}{k}", tuple(vv))
        else:
            for e in ("O", "X", "A", "W", "K", "P"):
                for k in (1, 2, 3, 5, 8, 10):
                    vv = list(v)
                    vv[ORDER.index(e)] += k
                    add(f"{lab}_add_{e}{k}", tuple(vv))

    seen = set()
    for fn in EXIST:
        p = os.path.join(HERE, fn)
        if os.path.exists(p):
            for line in open(p, encoding="utf-8"):
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
    print(f"[grow2] candidates={len(uniq)} (raw {len(cands)})", flush=True)

    import multiprocessing as mp
    pool = mp.Pool(args.workers)
    t0 = time.time()
    try:
        B = 26
        done = 0
        for s in range(0, len(uniq), B):
            chunk = uniq[s:s + B]
            rs = pool.map(S.sim_task, [v for _, v in chunk])
            with open(OUT, "a", encoding="utf-8") as f:
                for (lab, v), r in zip(chunk, rs):
                    r["phase"] = "grow2"
                    r["label"] = lab
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            done += len(chunk)
            hi = [(r["max"], r["label"]) for r in rs if r["ok"] and r["max"] > 149]
            best = max((r["max"] for r in rs if r["ok"]), default=0)
            print(f"[grow2] {done}/{len(uniq)} best={best} >149={hi[:5]} "
                  f"elapsed={time.time()-t0:.0f}s", flush=True)
    finally:
        pool.close()
        pool.join()


if __name__ == "__main__":
    main()
