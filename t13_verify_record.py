# -*- coding: utf-8 -*-
"""T13 verify record：对已验证纪录的「整个投料」做全产物严格校验。

对 t13_embed.json 中 status=ok 的纪录投料：重新 simulate，对**每个**产物分子
调用 pot_v2.embed_mol2(20M) + validate_place，确认整锅反应合法（不只是最大分子）。
输出 t13_record_full_verify.json。
"""
import sys, os, json, time

HERE = r"G:\AI work\deepseek\work1\alchemy"
sys.path.insert(0, HERE)
import pot_v3, pot_v2
from pot_all import vec_to_atoms, ORDER, formula_of

EMBED = os.path.join(HERE, "t13_embed.json")
SCREEN = os.path.join(HERE, "t13_embed_screen.json")
OUT = os.path.join(HERE, "t13_record_full_verify.json")
BUDGET = 2_000_000
MIN_MAX = 150


def main():
    feeds = []
    for p in (EMBED, SCREEN):
        if not os.path.exists(p):
            continue
        for d in json.load(open(p, encoding="utf-8")):
            if d.get("status") == "ok" and d.get("max", 0) >= MIN_MAX:
                feeds.append((d["max"], d.get("formula"), tuple(d["vec"])))
    # 去重（同一投料）
    seen, uniq = set(), []
    for mx, f, v in sorted(feeds, key=lambda x: -x[0]):
        if v in seen:
            continue
        seen.add(v)
        uniq.append((mx, f, v))
    rows = []
    for mx, f, vec in uniq:
        t0 = time.time()
        mols = pot_v3.simulate(vec_to_atoms(vec, ORDER))
        if not mols:
            rows.append({"feed": list(vec), "feed_n": sum(vec), "ok": False,
                         "reason": "sim_fail"})
            continue
        allok = True
        detail = []
        for m in sorted(mols, key=lambda m: -len(m["atoms"])):
            t1 = time.time()
            place = pot_v2.embed_mol2(m["atoms"], m["edges"], max_nodes=BUDGET)
            ok, msg = pot_v2.validate_place(place, m["atoms"], m["edges"])
            detail.append({"n": len(m["atoms"]), "formula": formula_of(m["atoms"]),
                           "embed": place is not None, "valid": bool(ok),
                           "t_embed": round(time.time() - t1, 2), "msg": msg})
            allok = allok and bool(ok)
        rows.append({"feed": list(vec), "feed_n": sum(vec), "max_mol": mx,
                     "n_products": len(mols), "all_valid": allok,
                     "products": detail, "t_total": round(time.time() - t0, 1)})
        print(f"feed_n={sum(vec)} max={mx} products={len(mols)} all_valid={allok} "
              f"t={rows[-1]['t_total']}s", flush=True)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
    print("wrote", OUT, flush=True)


if __name__ == "__main__":
    main()
