# -*- coding: utf-8 -*-
"""t12c_pure.py —— 补充采样：纯大类对（目录随机采样中几乎抽不到，因为纯大类物质极少）。

- 纯大类物质（元素只属同一大类）：聚 30、动 30、散 30（目录中）。
- 同大类内全部 i<j 对（435×3）+ 异大类两两（30×30×3=2700）；
- 用 pot_v3（规则1~9）+ pot_v2 严格校验（3M 节点）计算反应；
- 输出 t12c_pure.json，用于补充「聚/动/散」类别组合的跨元素统计，
  并与 T11（规则1~8，聚素 29 种 435 对：成功432/失败3/惰性87/单产物40/多产物305）对照。
"""
import json, sys, os, time
from collections import Counter

BASE = r"G:\AI work\deepseek\work1\alchemy"
sys.path.insert(0, BASE)
import pot_all as P
import pot_v2
import pot_v3

ORDER = list(P.ORDER)
CAT = P.CAT
CATS = ["聚", "动", "散"]
EMBED_CAP = 3_000_000
_CACHE = {}


def check(m):
    k = (tuple(m["atoms"]), tuple(sorted((min(a, b), max(a, b), mult) for a, b, mult in m["edges"])))
    if k not in _CACHE:
        _CACHE[k] = pot_v2.embed_mol2(m["atoms"], m["edges"], max_nodes=EMBED_CAP) is not None
    return _CACHE[k]


def react(va, vb):
    v = tuple(a + b for a, b in zip(va, vb))
    atoms = [e for e, c in zip(ORDER, v) for _ in range(c)]
    mols = pot_v3.simulate(atoms)
    if mols is None:
        return {"status": "fail_rem", "prods": None, "nmol": 0, "maxmol": 0}
    ok = all(check(m) for m in mols)
    prods = sorted(P.formula_of(m["atoms"]) for m in mols)
    return {"status": "ok" if ok else "fail_embed", "prods": prods,
            "nmol": len(mols), "maxmol": max(len(m["atoms"]) for m in mols)}


def main():
    t0 = time.time()
    cat = json.load(open(os.path.join(BASE, "t4_catalog_all_validated.json"), encoding="utf-8"))
    pure = {c: [] for c in CATS}
    for d in cat:
        v = P.parse_formula(d["formula"])
        s = set(CAT[ORDER[i]] for i in range(9) if v[i])
        if len(s) == 1:
            pure[list(s)[0]].append({"formula": d["formula"], "vec": tuple(v)})
    print("纯大类物质数:", {c: len(pure[c]) for c in CATS}, flush=True)
    rows = []
    # 同大类全部 i<j 对
    for c in CATS:
        items = pure[c]
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                r = react(a["vec"], b["vec"])
                rows.append({"combo": c, "type": "same", "A": a["formula"], "B": b["formula"],
                             "n": sum(a["vec"]) + sum(b["vec"]), **r})
    # 异大类两两（纯物质×纯物质）
    for ci in range(3):
        for cj in range(ci + 1, 3):
            ca, cb = CATS[ci], CATS[cj]
            combo = ca + cb
            for a in pure[ca]:
                for b in pure[cb]:
                    r = react(a["vec"], b["vec"])
                    rows.append({"combo": combo, "type": "cross", "A": a["formula"], "B": b["formula"],
                                 "n": sum(a["vec"]) + sum(b["vec"]), **r})
    json.dump({"pure_counts": {c: len(pure[c]) for c in CATS}, "rows": rows},
              open(os.path.join(BASE, "t12c_pure.json"), "w", encoding="utf-8"), ensure_ascii=False)
    # 统计
    print(f"\n共 {len(rows)} 对，用时 {time.time()-t0:.1f}s", flush=True)
    for combo in ["聚", "动", "散", "聚动", "聚散", "动散"]:
        rs = [r for r in rows if r["combo"] == combo]
        n = len(rs)
        ok = [r for r in rs if r["status"] == "ok"]
        fail = [r for r in rs if r["status"] != "ok"]
        inert = [r for r in ok if sorted(r["prods"]) == sorted([r["A"], r["B"]])]
        single = [r for r in ok if len(r["prods"]) == 1]
        multi = [r for r in ok if len(r["prods"]) > 1 and r not in inert]
        print(f"{combo}: {n} 对 | 成功 {len(ok)} 失败 {len(fail)}"
              f"（剩键 {sum(1 for r in fail if r['status']=='fail_rem')} / 摆放 {sum(1 for r in fail if r['status']=='fail_embed')}）"
              f" | 惰性 {len(inert)} 单产物 {len(single)} 多产物 {len(multi)}"
              f" | 平均最大产物 {sum(r['maxmol'] for r in ok)/len(ok):.1f}" if ok else "", flush=True)


if __name__ == "__main__":
    main()
