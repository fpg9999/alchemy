# -*- coding: utf-8 -*-
"""t17c：用物质自身的原子多重集重跑反应（这才是它自己的形成历史），
检验终态三价组件 = 6 级中间态骨架块的融合。
"""
import json
import random
import sys
from collections import Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from t17b_history_fusion import simulate_record, TRI

BASE = r"G:\AI work\deepseek\work1\alchemy"


def main():
    cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
    rng = random.Random(7)
    # 分层抽样：每个三价类型各若干 + 小分子全量
    bytype = {}
    for r in cat:
        trs = frozenset(a for a in r["atoms"] if a in TRI)
        bytype.setdefault(trs, []).append(r)
    picks = []
    for trs, lst in bytype.items():
        picks += rng.sample(lst, min(40, len(lst)))
    picks += [r for r in cat if len(r["atoms"]) <= 6][:800]
    print("samples:", len(picks), flush=True)
    stats = Counter()
    fusion = Counter()
    block_sizes = Counter()
    examples = []
    bad = []
    for r in picks:
        atoms = r["atoms"]
        try:
            level6, final, ok = simulate_record(atoms)
        except Exception:
            stats["error"] += 1
            continue
        if level6 is None:
            stats["odd"] += 1
            continue
        bad_n = 0
        for fc in final:
            blocks = [b for b in level6 if b <= fc]
            cover = set()
            for b in blocks:
                cover |= b
            if not blocks or cover != set(fc):
                bad_n += 1
            fusion[len(blocks)] += 1
        for b in level6:
            block_sizes[len(b)] += 1
        stats["ok" if bad_n == 0 else "bad"] += 1
        if bad_n:
            bad.append(r["formula"])
        if r["formula"] in ("O3P", "O2CK", "O2K4", "O2K6", "O2P6", "O5P5K2",
                            "O3KA2", "CP2K3", "O2X2C4", "O4X9P19W4K5") and len(examples) < 20:
            examples.append({"formula": r["formula"], "atoms": atoms,
                             "level6": [sorted(b) for b in level6],
                             "final": [sorted(f) for f in final],
                             "fusion_arity": dict(Counter(
                                 len([b for b in level6 if b <= fc]) for fc in final))})
    print("stats:", dict(stats))
    print("融合度分布（终态组件由几个 6 级块融合）:", dict(fusion))
    print("6 级块大小分布:", dict(sorted(block_sizes.items())))
    print("bad:", bad[:5], "..." if len(bad) > 5 else "")
    json.dump({"stats": dict(stats), "fusion": dict(fusion),
               "block_sizes": dict(block_sizes), "examples": examples},
              open(BASE + r"\t17_history.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved t17_history.json")


if __name__ == "__main__":
    main()
