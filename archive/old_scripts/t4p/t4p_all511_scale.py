# -*- coding: utf-8 -*-
"""t4p_all511_scale：对全部 511 个非空元素子集做"按比例放大投料"实验：
T = 24 / 48 / 96 的均衡投料，记录最大分子大小。
目的：为"每类有限（最大分子有上界）"提供全子集范围的数值证据，并搜索可能的无界增长。
输出 t4p_all511_scale.json；单进程运行（避免与其它重计算抢 CPU）。
"""
import json
import sys
import time
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
TS = (24, 48, 96)


def balanced_feed(elems, T):
    """尽量均衡分配 T 个原子；若总价数为奇，把它补成偶数（补在奇价元素上）。"""
    k = len(elems)
    feed = [T // k] * k
    for i in range(T % k):
        feed[i] += 1
    for _ in range(4):
        tot = sum(P.VAL[e] * c for e, c in zip(elems, feed))
        if tot % 2 == 0:
            return feed
        odd = [i for i, e in enumerate(elems) if P.VAL[e] % 2 == 1]
        if not odd:
            return feed
        feed[odd[0]] += 1
    return feed


def run_one(elems, T):
    feed = balanced_feed(elems, T)
    atoms = P.vec_to_atoms(tuple(feed), elems)
    mols = P.simulate(atoms)
    if mols is None:
        return {"T": T, "feed": feed, "ok": False}
    sizes = sorted((len(m["atoms"]) for m in mols), reverse=True)
    return {"T": T, "feed": feed, "ok": True, "maxcomp": sizes[0], "nmols": len(mols)}


def main():
    subsets = []
    for mask in range(1, 512):
        subsets.append([P.ORDER[i] for i in range(9) if mask >> i & 1])
    t0 = time.time()
    out = []
    for idx, elems in enumerate(subsets):
        row = {"elems": elems, "runs": []}
        for T in TS:
            row["runs"].append(run_one(elems, T))
        out.append(row)
        if (idx + 1) % 25 == 0:
            el = time.time() - t0
            print(f"  {idx+1}/511 用时 {el:.0f}s (ETA {el/(idx+1)*(511-idx-1):.0f}s)", flush=True)
            json.dump(out, open(BASE + r"\t4p_all511_scale.json", "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(out, open(BASE + r"\t4p_all511_scale.json", "w", encoding="utf-8"), ensure_ascii=False)
    # 汇总
    grow = []
    for row in out:
        ms = [r.get("maxcomp", 0) for r in row["runs"]]
        if ms[-1] > max(ms[0], ms[1]) + 2:
            grow.append((row["elems"], ms))
    print(f"\n完成，{len(out)} 子集。有明显增长(96 比 24/48 大 >2)的子集: {len(grow)}")
    for g in grow[:80]:
        print("  ", g)
    stats = {T: {} for T in TS}
    for row in out:
        for r in row["runs"]:
            T = r["T"]
            if r["ok"]:
                stats[T][r["maxcomp"]] = stats[T].get(r["maxcomp"], 0) + 1
    for T in TS:
        hist = stats[T]
        print(f"T={T}: 最大分子分布 top: {sorted(hist.items(), reverse=True)[:12]}, 失败锅数={sum(1 for row in out for r in row['runs'] if r['T']==T and not r['ok'])}")


if __name__ == "__main__":
    main()
