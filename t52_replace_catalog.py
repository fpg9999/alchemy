# -*- coding: utf-8 -*-
"""t52_replace_catalog.py：把目录中「pot_v4 产物结构不同」的记录直接替换为 pot_v4 结构。

按用户要求：先不做额外合法性校验；只做结构替换。
  * 未变化记录：原样保留（含 place）；
  * 变化记录：atoms/edges 换成 pot_v4 产物；place 用 pot_v2.embed_mol2 尽力计算
    （仅为了目录数据完整，不作为筛选；若失败则记为 None 并计数）。
输出：
  1) 覆盖写回 t4_catalog_all_validated.json（原文件；旧版本在 git 历史里）
  2) t52_replace_catalog.json（统计）
"""
import json
import sys
import time

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import pot_v2
import pot_v4

BASE = r"G:\AI work\deepseek\work1\alchemy"
ORDER = P.ORDER


def main():
    t0 = time.time()
    path = BASE + r"\t4_catalog_all_validated.json"
    cat = json.load(open(path, encoding="utf-8"))
    stats = {"records": len(cat), "unchanged": 0, "replaced": 0,
             "place_computed": 0, "place_none": 0, "sim_fail": 0,
             "single_product": 0, "other": 0}
    for i, rec in enumerate(cat):
        atoms = list(rec["atoms"])
        edges_old = [tuple(e) for e in rec["edges"]]
        lab_old = P.mol_label(atoms, edges_old)
        m4 = pot_v4.simulate(atoms)
        if m4 is None or len(m4) != 1:
            stats["sim_fail"] += 1
            continue
        stats["single_product"] += 1
        m = m4[0]
        lab_new = P.mol_label(m["atoms"], [tuple(e) for e in m["edges"]])
        if lab_new == lab_old:
            stats["unchanged"] += 1
            continue
        # 替换
        rec["atoms"] = list(m["atoms"])
        rec["edges"] = [list(e) for e in m["edges"]]
        place = pot_v2.embed_mol2(m["atoms"], [tuple(e) for e in m["edges"]],
                                  max_nodes=2_000_000)
        if place is None:
            rec["place"] = None
            stats["place_none"] += 1
        else:
            rec["place"] = {str(k): list(v) for k, v in place.items()}
            stats["place_computed"] += 1
        stats["replaced"] += 1
        if i % 10000 == 0:
            print(f"  {i} ... replaced={stats['replaced']} {time.time()-t0:.0f}s", flush=True)
    stats["seconds"] = round(time.time() - t0, 1)
    json.dump(cat, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump(stats, open(BASE + r"\t52_replace_catalog.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    print("saved catalog + t52_replace_catalog.json")


if __name__ == "__main__":
    main()
