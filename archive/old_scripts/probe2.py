# -*- coding: utf-8 -*-
"""对 N<=20 扫描里的代表投料做并列敏感性测试"""
import random
import sys
from collections import Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot2 as P
from probe_ties import simulate_rng


def atoms_of(v):
    return ["O"] * v[0] + ["X"] * v[1] + ["C"] * v[2]


def sig(mols):
    if mols is None:
        return "FAIL(剩键)"
    if not P.embed_all(mols):
        return "FAIL(摆不出来)"
    return " + ".join(sorted(P.mol_label(m) for m in mols))


def forms(s):
    # 从签名里粗略取公式
    out = []
    for part in s.split(" + "):
        if "|" not in part:
            continue
        at = part.split("|")[0]
        cnt = Counter(at)
        f = "".join(e + (str(cnt[e]) if cnt[e] > 1 else "") for e in ["O", "X", "C"] if cnt[e])
        out.append(f)
    return out


CASES = [(2, 5, 0), (2, 6, 0), (2, 7, 0), (3, 0, 5), (0, 3, 2), (2, 1, 4),
         (3, 1, 3), (2, 2, 4), (2, 3, 4), (3, 2, 5), (3, 3, 5), (4, 3, 2),
         (2, 4, 2), (4, 2, 4), (3, 0, 3), (3, 2, 1), (2, 2, 2), (4, 4, 4)]
rng = random.Random(123)
for v in CASES:
    outs = Counter()
    for _ in range(120):
        a = atoms_of(v)
        rng.shuffle(a)
        outs[sig(simulate_rng(a, rng))] += 1
    print(f"\n投料 {v}:")
    for s, c in outs.most_common():
        print(f"   {c:3d}/120  {s}")
