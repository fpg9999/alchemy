# -*- coding: utf-8 -*-
"""快速探测跨类范围的公式数随总原子上限 N 的增长（只输出计数，避免刷屏）"""
import json
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import scan_all as S


def count_scope(sid, N):
    res = S.run_scope(sid, N, verbose=False)
    return len(res["formulas"]), max([x["natoms"] for x in res["formulas"]], default=0), res


if __name__ == "__main__":
    sid = int(sys.argv[1])
    out = {}
    for N in [6, 8, 10, 12]:
        n, mx, res = count_scope(sid, N)
        out[N] = {"count": n, "maxatoms": mx,
                  "formulas": [x["formula"] for x in res["formulas"]]}
        print(f"scope {sid} N={N}: 公式数={n} 最大原子={mx}", flush=True)
    json.dump(out, open(rf"G:\AI work\deepseek\work1\alchemy\scope{sid}_growth.json", "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved", rf"scope{sid}_growth.json")
