# -*- coding: utf-8 -*-
"""t12c_retry.py —— 对主采样中 status=fail_embed 的唯一总向量，用更大 embedding 节点预算重试，
判断「3M 预算超限」中有多少其实是可摆放的合法产物；更新 t12c_vectors.json。
用法: python t12c_retry.py 10000000 18
"""
import json, sys, os, time
from collections import Counter

BASE = r"G:\AI work\deepseek\work1\alchemy"
sys.path.insert(0, BASE)
import pot_all as P
import pot_v2
import pot_v3

ORDER = list(P.ORDER)
CAP = int(sys.argv[1]) if len(sys.argv) > 1 else 10_000_000
NPROC = int(sys.argv[2]) if len(sys.argv) > 2 else 18


def atoms_of(v):
    return [e for e, c in zip(ORDER, v) for _ in range(c)]


def parse_key(k):
    return tuple(int(x) for x in k.split(","))


def _work(k):
    v = parse_key(k)
    t0 = time.time()
    mols = pot_v3.simulate(atoms_of(v))
    if mols is None:
        return k, {"status": "fail_rem", "prods": None, "nmol": 0, "maxmol": 0,
                   "embed_s": round(time.time() - t0, 3)}
    t1 = time.time()
    ok = True
    per = []
    for m in mols:
        r = pot_v2.embed_mol2(m["atoms"], m["edges"], max_nodes=CAP)
        per.append({"n": len(m["atoms"]), "ok": r is not None})
        if r is None:
            ok = False
    embed_s = time.time() - t1
    prods = sorted(P.formula_of(m["atoms"]) for m in mols)
    return k, {"status": "ok" if ok else "fail_embed_cap",
               "prods": prods, "nmol": len(mols),
               "maxmol": max(len(m["atoms"]) for m in mols),
               "embed_s": round(embed_s, 3), "per_mol": per, "cap": CAP,
               "n": sum(v)}


def main():
    t0 = time.time()
    vecs = json.load(open(os.path.join(BASE, "t12c_vectors.json"), encoding="utf-8"))
    todo = [k for k, x in vecs.items() if x["status"] == "fail_embed"]
    print(f"待重试 {len(todo)} 个总向量，cap={CAP:,}，进程 {NPROC}", flush=True)
    from multiprocessing import Pool
    out = {}
    done = 0
    with Pool(NPROC) as pool:
        for k, r in pool.imap_unordered(_work, todo, chunksize=1):
            out[k] = r
            done += 1
            if done % 10 == 0 or done == len(todo):
                el = time.time() - t0
                print(f"  {done}/{len(todo)} elapsed={el:.0f}s eta={(el/done)*(len(todo)-done):.0f}s "
                      f"stat={r['status']} n={r.get('n')} maxmol={r.get('maxmol')}", flush=True)
    n_ok = sum(1 for r in out.values() if r["status"] == "ok")
    print(f"重试结果：{n_ok}/{len(todo)} 变为可摆放（原 3M 预算失败）", flush=True)
    # 合并回主记录
    for k, r in out.items():
        old = vecs[k]
        old["orig_status"] = old["status"]
        old["retried_cap"] = CAP
        if r["status"] == "ok":
            old["status"] = "ok"
            old["prods"] = r["prods"]
            old["nmol"] = r["nmol"]
            old["maxmol"] = r["maxmol"]
            old["sim_s"] = old["sim_s"]
            old["embed_s"] = old["embed_s"] + r["embed_s"]
            old["embed_fail"] = []
        else:
            old["embed_s"] = old["embed_s"] + r["embed_s"]
            old["embed_fail_cap"] = r.get("per_mol")
    json.dump(vecs, open(os.path.join(BASE, "t12c_vectors.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    json.dump(out, open(os.path.join(BASE, "t12c_retry.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    print(f"已更新 t12c_vectors.json；落盘 t12c_retry.json；用时 {(time.time()-t0)/60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
