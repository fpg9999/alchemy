# -*- coding: utf-8 -*-
"""t4_validate_search：对 merged catalog 中 source=="search" 的物质，重新校验其整锅（所有产物可摆）。
不合格的删除。输出 t4_catalog_all_validated.json。
"""
import json
import sys

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v2

BASE = r"G:\AI work\deepseek\work1\alchemy"


def main():
    cat = json.load(open(BASE + r"\t4_catalog_all.json", encoding="utf-8"))
    keep = []
    drop = []
    for x in cat:
        if x.get("source") != "search":
            keep.append(x)
            continue
        feed = x.get("feed")
        elems = list(P.ORDER) if len(feed) == 9 else sorted(set(x["atoms"]))
        # feed 是 9 元向量；若 feed 长度 9 则直接算
        if len(feed) != 9:
            keep.append(x)
            continue
        atoms = P.vec_to_atoms(tuple(feed), P.ORDER)
        mols = P.simulate(atoms)
        if not mols:
            drop.append(x["formula"])
            continue
        ok = True
        for m in mols:
            pl = pot_v2.embed_mol2(m["atoms"], m["edges"], max_nodes=4_000_000)
            good, _ = pot_v2.validate_place(pl, m["atoms"], m["edges"])
            if not good:
                ok = False
                break
        if not ok:
            drop.append(x["formula"])
            continue
        # 记录该物质本体的合法摆放
        for m in mols:
            if P.formula_of(m["atoms"]) == x["formula"]:
                pl = pot_v2.embed_mol2(m["atoms"], m["edges"], max_nodes=4_000_000)
                x["place"] = {str(k): list(v) for k, v in pl.items()}
                break
        keep.append(x)
    json.dump(keep, open(BASE + r"\t4_catalog_all_validated.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"kept {len(keep)}, dropped {len(drop)}")
    print("dropped:", drop[:40])


if __name__ == "__main__":
    main()
