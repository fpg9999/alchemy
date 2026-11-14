# -*- coding: utf-8 -*-
"""T13 embed：对最大产物 >140 的候选做 pot_v2 严格摆放校验。

- 重跑 pot_v3.simulate 取最大产物分子
- pot_v2.embed_mol2(max_nodes=budget) + pot_v2.validate_place 严格校验
- 结果逐条写 t13_embed.json；成功（>140）写 t13_new_record.json
用法：python t13_embed.py [--workers 8] [--budget 20000000] [--min-size 141]
"""
import sys, os, json, time, argparse

HERE = r"G:\AI work\deepseek\work1\alchemy"
sys.path.insert(0, HERE)
import pot_v3
import pot_v2
from pot_all import vec_to_atoms, ORDER, formula_of

RESULTS = os.path.join(HERE, "t13_results.jsonl")
EMBED_OUT = os.path.join(HERE, "t13_embed.json")
RECORD_OUT = os.path.join(HERE, "t13_new_record.json")


def embed_task(item):
    """item: {label, vec, max, budget}"""
    label, vec, budget = item["label"], tuple(item["vec"]), item["budget"]
    t0 = time.time()
    atoms = vec_to_atoms(vec, ORDER)
    mols = pot_v3.simulate(atoms)
    t_sim = time.time() - t0
    if mols is None:
        return {"label": label, "vec": list(vec), "n": len(atoms), "max": 0,
                "status": "sim_fail", "t_sim": round(t_sim, 2), "t_embed": 0}
    big = max(mols, key=lambda m: len(m["atoms"]))
    na = len(big["atoms"])
    t1 = time.time()
    place = pot_v2.embed_mol2(big["atoms"], big["edges"], max_nodes=budget)
    t_embed = time.time() - t1
    ok, msg = pot_v2.validate_place(place, big["atoms"], big["edges"])
    rec = {"label": label, "vec": list(vec), "n": len(atoms), "max": na,
           "formula": formula_of(big["atoms"]), "nmols": len(mols),
           "status": "ok" if (place is not None and ok) else "fail",
           "msg": msg, "valid": bool(ok), "budget": budget,
           "t_sim": round(t_sim, 2), "t_embed": round(t_embed, 2),
           "birth": label, "phase": item.get("phase")}
    if place is not None and ok:
        rec["structure"] = {"atoms": big["atoms"], "edges": big["edges"],
                            "place": {str(k): list(v) for k, v in place.items()}}
    return rec


def candidate_list(min_size, budget_map):
    recs = [json.loads(l) for l in open(RESULTS, encoding="utf-8")]
    out = {}
    for r in recs:
        if not r.get("ok") or r["max"] < min_size:
            continue
        # 同尺寸同分子式只试一次（同分异构可能不同，但优先省时间；异构另见 jsonl）
        key = (r["max"], r.get("formula"))
        if key in out:
            continue
        out[key] = {"label": r["label"], "vec": list(r["vec"]), "max": r["max"],
                    "formula": r.get("formula"), "phase": r.get("phase"),
                    "budget": budget_map(r["max"])}
    cands = sorted(out.values(), key=lambda c: (c["max"], c["label"]))
    return cands


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--budget", type=int, default=20_000_000)
    ap.add_argument("--min-size", type=int, default=141)
    ap.add_argument("--deadline-min", type=float, default=60)
    args = ap.parse_args()

    def budget_map(mx):
        # 小分子用 20M；>=180 原子（很大且很可能不可摆放）仍给 20M 但排队在后
        return args.budget

    cands = candidate_list(args.min_size, budget_map)
    done = []
    if os.path.exists(EMBED_OUT):
        try:
            done = json.load(open(EMBED_OUT, encoding="utf-8"))
        except Exception:
            done = []
    done_labels = {(d["label"], d["max"]) for d in done}
    cands = [c for c in cands if (c["label"], c["max"]) not in done_labels]
    print(f"[embed] candidates={len(cands)} workers={args.workers} budget={args.budget}", flush=True)

    import multiprocessing as mp
    t_start = time.time()
    pool = mp.Pool(args.workers)
    try:
        B = args.workers
        for s in range(0, len(cands), B):
            batch = cands[s:s + B]
            t0 = time.time()
            recs = pool.map(embed_task, batch)
            done.extend(recs)
            with open(EMBED_OUT, "w", encoding="utf-8") as f:
                json.dump(done, f, ensure_ascii=False, indent=1)
            for r in recs:
                print(f"  {r['max']:4d} {r['status']:9s} valid={r.get('valid')} "
                      f"{r['label']:20s} @{r.get('budget',0)//1000}k "
                      f"t_embed={r.get('t_embed',0)}s t_sim={r.get('t_sim',0)}s "
                      f"msg={r.get('msg','')[:40]}", flush=True)
            ok140 = [d for d in done if d.get("status") == "ok" and d["max"] > 140]
            print(f"[embed] {len(done)}/{len(cands)} done, batch {time.time()-t0:.0f}s, "
                  f"total {time.time()-t_start:.0f}s, records={[(d['max'], d['label']) for d in ok140]}",
                  flush=True)
            # 保存新纪录
            if ok140:
                best = max(ok140, key=lambda d: d["max"])
                with open(RECORD_OUT, "w", encoding="utf-8") as f:
                    json.dump(best, f, ensure_ascii=False, indent=1)
            if (time.time() - t_start) / 60 > args.deadline_min:
                print(f"[embed] deadline {args.deadline_min}min reached, stop", flush=True)
                break
    finally:
        pool.close()
        pool.join()


if __name__ == "__main__":
    main()
