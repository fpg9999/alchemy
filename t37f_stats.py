# -*- coding: utf-8 -*-
"""t37f_stats.py：统计并列事件发生在中间态骨架之前/之后，以及是否存在块内候选"""
import json
import random
import sys
from collections import Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all
import t37_tie_analysis as T

BASE = r"G:\AI work\deepseek\work1\alchemy"
cat = json.load(open(BASE + r"\t4_catalog_all_validated.json", encoding="utf-8"))
pool = [r for r in cat if 2 <= len(r["atoms"]) <= 10]
rng = random.Random(9876)
sample = rng.sample(pool, min(400, len(pool)))
stats = Counter()
for rec in sample:
    r = T.run(list(rec["atoms"]), policy="first", collect_ties=True)
    if not r or not r["ties"]:
        continue
    stats["有并列的分子"] += 1
    for t in r["ties"]:
        stats["并列事件"] += 1
        if not t["blocks_ready"]:
            stats["骨架前并列"] += 1
        else:
            if t["intra"]:
                stats["骨架后且有块内候选"] += 1
            else:
                stats["骨架后但无块内候选"] += 1
print(dict(stats))
