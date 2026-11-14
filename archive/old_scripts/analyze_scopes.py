# -*- coding: utf-8 -*-
"""analyze_scopes：按"元素子集"给跨类物质分族（有限块 vs 无限族成员），并找最小例子。"""
import json
import sys
from collections import defaultdict

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
PURE = {"聚": ["O", "X", "C"], "动": ["P", "W", "L"], "散": ["K", "A", "F"]}
BASE29 = ["O2", "X2", "C2", "X3", "O2X", "O2X2", "O2X3", "O2X4", "O2X5", "O2X6", "O2X7",
          "OC3", "O2C2", "O2C4", "O3C3", "O3C5", "XC2", "X2C2", "X3C2",
          "OXC", "OX2C", "OX3C", "O2XC2", "O2XC4", "O2X2C4", "O2X3C4", "O3XC", "O3XC3", "O3X2C"]


def map29(cat):
    tr = {"聚": {"O": "O", "X": "X", "C": "C"},
          "动": {"O": "P", "X": "W", "C": "L"},
          "散": {"O": "K", "X": "A", "C": "F"}}[cat]
    return set("".join(tr.get(ch, ch) for ch in f) for f in BASE29)


# 各范围的最小无限核心（元素三元组）：不同大类的两个 3 价 + 一个 2 价
CORES = {
    3: [{"O", "X", "K"}, {"O", "K", "A"}],
    4: [{"O", "X", "P"}, {"O", "P", "W"}],
    5: [{"P", "W", "K"}, {"P", "K", "A"}],
    6: [{"O", "X", "K"}, {"O", "K", "A"}, {"O", "X", "P"}, {"O", "P", "W"},
        {"P", "W", "K"}, {"P", "K", "A"}],
}
SCOPE_EL = {3: ["O", "X", "C", "K", "A", "F"], 4: ["O", "X", "C", "P", "W", "L"],
            5: ["P", "W", "L", "K", "A", "F"], 6: P.ORDER}


def main():
    for sid in (3, 4, 5, 6):
        data = json.load(open(BASE + rf"\substances_league_s{sid}.json", encoding="utf-8"))
        cores = CORES[sid]
        finite, inf = [], []
        for x in data:
            es = set(x["atoms"])
            (inf if any(c <= es for c in cores) else finite).append(x)
        print(f"\n=== 范围{sid} (扫描 N=16 截断, 共 {len(data)} 种) ===")
        for cat in ("聚", "动", "散"):
            syms = set(PURE[cat])
            if not syms <= set(SCOPE_EL[sid]):
                continue
            ps = [x for x in data if set(x["atoms"]) <= syms]
            want = map29(cat)
            extra = [x["formula"] for x in ps if x["formula"] not in want]
            print(f"  纯{cat}: {len(ps)} 种" + (f"（额外扫描产物 {extra}，投料凑不出，剔除）" if extra else ""))
        tc = [x for x in data if x["cats"] == "聚-动-散"] if sid == 6 else []
        print(f"  有限块物质: {len(finite)} 种, 最大 {max((x['natoms'] for x in finite), default=0)} 原子")
        print(f"  无限族成员: {len(inf)} 种, 最大 {max((x['natoms'] for x in inf), default=0)} 原子")
        if tc:
            print(f"  其中三类同时出现: {len(tc)} 种, 最大 {max(x['natoms'] for x in tc)} 原子")
        for core in cores:
            cand = [x for x in inf if core <= set(x["atoms"])]
            if not cand:
                print(f"  核心 {'/'.join(sorted(core))}: 无例子")
                continue
            m = min(cand, key=lambda x: x["natoms"])
            print(f"  核心 {'/'.join(sorted(core))}: 已含 {len(cand)} 种，最小例子 {m['formula']} "
                  f"({m['natoms']}原子, 投料={tuple(m['feed'])})")
        fsets = defaultdict(int)
        for x in finite:
            fsets[" ".join(sorted(set(x["atoms"])))] += 1
        print(f"  有限块涉及的元素子集: {len(fsets)} 个")
        for k, v in sorted(fsets.items(), key=lambda kv: -kv[1])[:12]:
            print(f"    {k:18s} {v}")


if __name__ == "__main__":
    main()
