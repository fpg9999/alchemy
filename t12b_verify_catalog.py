# -*- coding: utf-8 -*-
"""t12b_verify_catalog.py —— 验证「不在 ≤16 完备目录中的产物」确实可严格摆放。

用途：T12B 结果里发现 212 种产物分子式不在 t4_catalog_all_validated.json 中；
本脚本用 pot_v2（严格 validate_place）在更高节点上限下复核它们，
判断是「目录 embedding 预算不足漏收」还是「我们的校验过宽」。

输出 t12b_catalog_gap.json
"""
import json
import sys
import time
from multiprocessing import Pool

BASE = r"G:\AI work\deepseek\work1\alchemy"
sys.path.insert(0, BASE)
import pot_all as P
import pot_v2

ORDER = P.ORDER
NPROC = 8


def work(f):
    v = P.parse_formula(f)
    atoms = [s for s, c in zip(ORDER, v) for _ in range(c)]
    mols = P.simulate(atoms)
    if mols is None:
        return f, {"simfail": True}
    info = []
    for cap in (400_000, 3_000_000, 12_000_000):
        ok = True
        need = cap
        for m in mols:
            pl = pot_v2.embed_mol2(m["atoms"], m["edges"], max_nodes=cap)
            if pl is None:
                ok = False
                break
            good, msg = pot_v2.validate_place(pl, m["atoms"], m["edges"])
            if not good:
                return f, {"bad_place": msg, "cap": cap}
        if ok:
            return f, {"ok": True, "cap": cap,
                       "sizes": [len(m["atoms"]) for m in mols]}
    return f, {"ok": False, "cap": None, "sizes": [len(m["atoms"]) for m in mols]}


def main():
    t0 = time.time()
    S = json.load(open(BASE + r"\t12b_summary.json", encoding="utf-8"))
    forms = list(S["single_product"]["not_in_catalog_products"].keys())
    print(f"待复核产物分子式 {len(forms)} 个", flush=True)
    out = {}
    with Pool(NPROC) as pool:
        for k, (f, info) in enumerate(pool.imap_unordered(work, forms, chunksize=2), 1):
            out[f] = info
            if k % 20 == 0 or k == len(forms):
                print(f"  {k}/{len(forms)} {time.time()-t0:.1f}s", flush=True)
    caps = {}
    bad = [f for f, d in out.items() if not d.get("ok")]
    for f, d in out.items():
        if d.get("ok"):
            caps[str(d["cap"])] = caps.get(str(d["cap"]), 0) + 1
    print(f"可严格摆放: {len(out)-len(bad)}/{len(out)}；按所需节点上限: {caps}", flush=True)
    print(f"仍失败: {bad[:10]}{'...' if len(bad) > 10 else ''}", flush=True)
    json.dump({"checked": len(forms), "caps": caps, "n_fail": len(bad),
               "fail_examples": bad[:10], "detail": out},
              open(BASE + r"\t12b_catalog_gap.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"done {time.time()-t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
