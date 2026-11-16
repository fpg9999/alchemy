# -*- coding: utf-8 -*-
"""t47_scan_ambiguity.py：在规则 1~11 下扫描「是否还存在骨架/最终结构歧义」。

骨架歧义 = 同一投料经不同并列裁决，得到不同（非同构）的 6 级块组合；
最终歧义 = 不同最终分子结构。
"""
import sys
import time

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import t45_rules1011 as T

MAX_T = int(sys.argv[1]) if len(sys.argv) > 1 else 9
START_T = int(sys.argv[2]) if len(sys.argv) > 2 else 1
USE10 = True
USE11 = True
MODE = "A"

t0 = time.time()
bad_block = []
bad_final = []
total_comps = 0
cap_hit = 0
for total in range(START_T, MAX_T + 1):
    t1 = time.time()
    for nO in range(total + 1):
        for nP in range(total - nO + 1):
            nK = total - nO - nP
            if nO == nP == nK == 0:
                continue
            total_comps += 1
            r = T.enumerate_outcomes((nO, nP, nK), USE10, USE11, MODE, cap=3_000_000)
            if r is None:
                continue
            if r.get("cap"):
                cap_hit += 1
                continue
            if r["distinct_block_classes"] > 1:
                bad_block.append(((nO, nP, nK), r))
            if r["distinct_final_classes"] > 1:
                bad_final.append(((nO, nP, nK), r))
    print(f"total={total} done {time.time()-t1:.0f}s  "
          f"block_amb={len(bad_block)} final_amb={len(bad_final)} cap={cap_hit}", flush=True)
print("=" * 90)
print("compositions:", total_comps, "seconds:", round(time.time() - t0, 1))
print("block ambiguity counts:", bad_block)
print("final ambiguity counts:", bad_final)
