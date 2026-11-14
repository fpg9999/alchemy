# -*- coding: utf-8 -*-
"""T13 screen：对所有搜索结果中「最大产物 > 当前纪录」的候选做严格摆放校验。

两档预算：
  pass 1  screen: max_nodes=2,000,000（≈20s 上限，筛掉明显不可摆放的）
  pass 2  deep  : max_nodes=20,000,000（仅对 pass1 失败且 max 最大的若干候选）
输出 t13_embed_screen.json；最优纪录写 t13_new_record.json。
"""
import sys, os, json, time, argparse

HERE = r"G:\AI work\deepseek\work1\alchemy"
sys.path.insert(0, HERE)
from t13_embed import embed_task

RES_FILES = ["t13_results.jsonl", "t13_results_grow.jsonl", "t13_results_target.jsonl",
             "t13_results_grow2.jsonl"]
OLD = os.path.join(HERE, "t13_embed.json")
OUT = os.path.join(HERE, "t13_embed_screen.json")
RECORD = os.path.join(HERE, "t13_new_record.json")


def collect(min_size):
    tried = set()
    if os.path.exists(OLD):
        for d in json.load(open(OLD, encoding="utf-8")):
            tried.add((d.get("max"), d.get("formula")))
    if os.path.exists(OUT):
        for d in json.load(open(OUT, encoding="utf-8")):
            tried.add((d.get("max"), d.get("formula")))
    cands, seen = [], set()
    for fn in RES_FILES:
        p = os.path.join(HERE, fn)
        if not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if not r.get("ok") or r.get("max", 0) < min_size:
                continue
            key = (r["max"], r.get("formula"))
            if key in tried or key in seen:
                continue
            seen.add(key)
            cands.append({"label": f"{r.get('phase')}:{r['label']}", "vec": r["vec"],
                          "max": r["max"], "formula": r["formula"], "budget": None})
    return cands


def save_all(rows):
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)


def update_record(rows):
    ok = [d for d in rows if d.get("status") == "ok" and d.get("valid") and d["max"] > 140]
    if not ok:
        return None
    best = max(ok, key=lambda d: (d["max"], -d.get("t_embed", 1e9)))
    with open(RECORD, "w", encoding="utf-8") as f:
        json.dump(best, f, ensure_ascii=False, indent=1)
    return best


def run_pass(cands, budget, workers, rows, tag):
    import multiprocessing as mp
    if not cands:
        print(f"[{tag}] nothing to do", flush=True)
        return rows
    print(f"[{tag}] {len(cands)} candidates budget={budget} workers={workers}", flush=True)
    pool = mp.Pool(workers)
    t0 = time.time()
    try:
        B = workers
        for s in range(0, len(cands), B):
            batch = [dict(c, budget=budget) for c in cands[s:s + B]]
            recs = pool.map(embed_task, batch)
            rows.extend(recs)
            save_all(rows)
            for r in recs:
                print(f"  [{tag}] {r['max']:4d} {r['status']:9s} valid={r.get('valid')} "
                      f"t_embed={r.get('t_embed')}s {r['label'][:40]}", flush=True)
            best = update_record(rows)
            print(f"[{tag}] {len(rows)} total, elapsed {time.time()-t0:.0f}s, "
                  f"record={best['max'] if best else None}", flush=True)
    finally:
        pool.close()
        pool.join()
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-size", type=int, default=144)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--screen-budget", type=int, default=2_000_000)
    ap.add_argument("--deep-workers", type=int, default=8)
    ap.add_argument("--deep-budget", type=int, default=20_000_000)
    ap.add_argument("--deep-max", type=int, default=8, help="pass1 失败后深试的最大候选数")
    ap.add_argument("--deadline-min", type=float, default=25)
    args = ap.parse_args()

    rows = []
    if os.path.exists(OUT):
        try:
            rows = json.load(open(OUT, encoding="utf-8"))
        except Exception:
            rows = []
    cands = collect(args.min_size)
    # 小尺寸优先（更可能摆得出来、更快出纪录）
    cands.sort(key=lambda c: (c["max"], c["label"]))
    t_start = time.time()
    rows = run_pass(cands, args.screen_budget, args.workers, rows, "screen")
    # pass 2：screen 失败者按尺寸从大到小深试
    fails = [r for r in rows if r.get("status") == "fail" and r.get("budget") == args.screen_budget
             and r["max"] >= args.min_size]
    fails.sort(key=lambda r: -r["max"])
    deep = [{"label": r["label"], "vec": r["vec"], "max": r["max"]} for r in fails[:args.deep_max]]
    if deep and time.time() - t_start < args.deadline_min * 60:
        rows = run_pass(deep, args.deep_budget, args.deep_workers, rows, "deep")
    best = update_record(rows)
    print(f"[screen] done. verified records: "
          f"{sorted([(r['max'], r['formula']) for r in rows if r.get('status')=='ok' and r.get('valid')], reverse=True)[:6]}",
          flush=True)
    print(f"[screen] best={best['max'] if best else None}", flush=True)


if __name__ == "__main__":
    main()
