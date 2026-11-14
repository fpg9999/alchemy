# -*- coding: utf-8 -*-
"""t12b_merge.py —— 合并全量计算结果（pot_all 主口径）：vecparts + timeout 高上限复核。
输出 t12b_results.json  {vecs, res}  res=[status, products]
status: 0=成功, 1=剩键失败, 2=摆放失败, 3=未判定（超时）
"""
import json
import os
from collections import Counter

BASE = r"G:\AI work\deepseek\work1\alchemy"
PARTS = BASE + r"\t12b_vecparts"


def main():
    uniq = None
    res = None
    for f in sorted(os.listdir(PARTS)):
        if not (f.startswith("part_") and f.endswith(".json")):
            continue
        s = int(f[5:11])
        part = json.load(open(os.path.join(PARTS, f), encoding="utf-8"))
        if res is None:
            # 先确定 nv
            pass
        if res is None:
            res = {}
        for k, r in enumerate(part):
            res[s + k] = r
    nv = max(res) + 1
    out = [res.get(i) for i in range(nv)]
    assert all(x is not None for x in out), "缺块"
    S = json.load(open(BASE + r"\t12b_S.json", encoding="utf-8"))
    vecs = [tuple(d["vec"]) for d in S]
    n = len(vecs)
    seen = set()
    for i in range(n):
        vi = vecs[i]
        seen.add((vi[0] * 2, vi[1] * 2, vi[2] * 2, vi[3] * 2, vi[4] * 2,
                  vi[5] * 2, vi[6] * 2, vi[7] * 2, vi[8] * 2))
        for j in range(i + 1, n):
            vj = vecs[j]
            seen.add((vi[0] + vj[0], vi[1] + vj[1], vi[2] + vj[2],
                      vi[3] + vj[3], vi[4] + vj[4], vi[5] + vj[5],
                      vi[6] + vj[6], vi[7] + vj[7], vi[8] + vj[8]))
    uniq = sorted(seen)
    assert len(uniq) == nv, (len(uniq), nv)
    # timeout 复核
    fn = BASE + r"\t12b_timeout_fix.json"
    if os.path.exists(fn):
        fix = json.load(open(fn, encoding="utf-8"))
        fixed = 0
        for k in range(nv):
            if out[k][0] == 3:
                v = fix.get(str(k))
                if v is not None:
                    out[k] = v
                    fixed += 1
        print(f"timeout 复核应用 {fixed} 条", flush=True)
    c = Counter(r[0] for r in out)
    print("状态分布:", dict(c), flush=True)
    json.dump({"vecs": [list(v) for v in uniq], "res": out},
              open(BASE + r"\t12b_results.json", "w", encoding="utf-8"),
              separators=(",", ":"))
    print(f"saved t12b_results.json nv={nv}", flush=True)


if __name__ == "__main__":
    main()
