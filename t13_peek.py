# -*- coding: utf-8 -*-
"""T13 小工具：查看 t13_results.jsonl 中 max>140 的候选与单分子命中。"""
import json, sys, os
HERE = r"G:\AI work\deepseek\work1\alchemy"
recs = [json.loads(l) for l in open(os.path.join(HERE, "t13_results.jsonl"), encoding="utf-8")]
print("records:", len(recs))
phases = {}
for r in recs:
    phases[r.get("phase")] = phases.get(r.get("phase"), 0) + 1
print("phases:", phases)
ok = [r for r in recs if r["ok"]]
print("ok:", len(ok), "fail:", len(recs) - len(ok))
big = [r for r in recs if r["max"] > 140]
print("\nmax>140 count:", len(big))
for r in sorted(big, key=lambda r: -r["max"]):
    print(f"{r['max']:4d} n={r['n']:3d} nmols={r['nmols']:2d} {r.get('phase','?'):5s} {r['label']:22s} t={r['t']:6.2f}s {r['formula']}")
print("\nsingle-molecule hits:")
for r in sorted([r for r in ok if r["nmols"] == 1], key=lambda r: -r["max"]):
    print(f"{r['max']:4d} n={r['n']:3d} {r.get('phase','?'):5s} {r['label']:22s} {r['formula']}")
