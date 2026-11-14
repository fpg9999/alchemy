# -*- coding: utf-8 -*-
"""scan_growth2：逐 N 跑范围增长计数并落盘（含分类计数），避免一锅端被 kill 掉。"""
import json
import sys
import time
from collections import defaultdict

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P
import scan_all as S

BASE = r"G:\AI work\deepseek\work1\alchemy"


def classify(f):
    cats = set()
    for ch in f:
        if ch in P.CAT:
            cats.add(P.CAT[ch])
    return "-".join(c for c in ["聚", "动", "散"] if c in cats)


def main():
    sid = int(sys.argv[1])
    Ns = [int(x) for x in sys.argv[2].split(",")]
    out = {"scope": sid, "data": {}}
    for N in Ns:
        t = time.time()
        res = S.run_scope(sid, N, verbose=True)
        fs = [x["formula"] for x in res["formulas"]]
        stat = defaultdict(int)
        for f in fs:
            stat[classify(f)] += 1
        out["data"][N] = {
            "count": len(fs),
            "maxatoms": max((x["natoms"] for x in res["formulas"]), default=0),
            "catstat": dict(stat),
            "formulas": fs,
            "secs": round(time.time() - t, 1),
        }
        print(f"scope{sid} N={N}: 公式数={len(fs)} 最大原子={out['data'][N]['maxatoms']} "
              f"分类={dict(stat)} 用时={out['data'][N]['secs']}s", flush=True)
        json.dump(out, open(BASE + rf"\scope{sid}_growth2.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
