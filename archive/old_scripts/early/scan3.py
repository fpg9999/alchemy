# -*- coding: utf-8 -*-
"""规则6=并集后的全量扫描 + 并列敏感性 + 可达闭包"""
import random
import sys
from collections import Counter, defaultdict
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot2 as P
from probe_ties import simulate_rng


def atoms_of(v):
    return ["O"] * v[0] + ["X"] * v[1] + ["C"] * v[2]


def sig(mols):
    if mols is None:
        return "FAIL(剩键)"
    if not P.embed_all(mols):
        return "FAIL(摆出来)"
    return " + ".join(sorted(P.mol_label(m) for m in mols))


def formulas_of(mols):
    return sorted(P.formula_of(m["atoms"]) for m in mols)


def vec_of_formula(f):
    v = {"O": 0, "X": 0, "C": 0}
    i = 0
    while i < len(f):
        e = f[i]
        i += 1
        num = ""
        while i < len(f) and f[i].isdigit():
            num += f[i]
            i += 1
        v[e] += int(num) if num else 1
    return (v["O"], v["X"], v["C"])


def semigroup(vectors, N):
    reach = set()
    stack = [(0, 0, 0)]
    seen = {(0, 0, 0)}
    while stack:
        o, x, c = stack.pop()
        reach.add((o, x, c))
        for (do, dx, dc) in vectors:
            n = (o + do, x + dx, c + dc)
            if sum(n) <= N and n not in seen:
                seen.add(n)
                stack.append(n)
    return reach


def main(N):
    rng = random.Random(2024)
    ok_formula = {}     # 公式 -> 一个稳定输入的产物
    amb_inputs = []
    amb_formulas = set()
    maxsize = 0
    reasons = Counter()
    checked = 0
    for total in range(1, N + 1):
        for a in range(total + 1):
            for b in range(total - a + 1):
                c = total - a - b
                if c < 0 or (a + c) % 2:
                    continue
                v = (a, b, c)
                checked += 1
                at = atoms_of(v)
                mols = P.simulate(at)
                if mols is None:
                    reasons["剩键"] += 1
                    continue
                if not P.embed_all(mols):
                    reasons["摆不出来"] += 1
                    continue
                reasons["ok"] += 1
                base_sig = sig(mols)
                # 并列敏感性
                outs = {base_sig}
                for _ in range(4):
                    aa = at[:]
                    rng.shuffle(aa)
                    outs.add(sig(simulate_rng(aa, rng)))
                if len(outs) > 1:
                    amb_inputs.append((v, outs))
                for f in formulas_of(mols):
                    maxsize = max(maxsize, 0)
                    ok_formula.setdefault(f, v)
    print(f"N={N}: 输入数={checked}, 稳定公式(确定性口径)={len(ok_formula)}, 并列敏感输入数={len(amb_inputs)}, 最大原子?? ")
    print("失败统计:", dict(reasons))
    print("\n=== 并列敏感输入 ===")
    for v, outs in amb_inputs[:12]:
        print(" ", v, len(outs), "种")
        for s in list(outs)[:4]:
            print("     ", s)
    print("\n=== 公式（确定性口径） ===")
    for f in sorted(ok_formula, key=lambda s: (len(vec_of_formula(s)), vec_of_formula(s))):
        print(f"  {f:10s} vec={vec_of_formula(f)} 例:{ok_formula[f]}")
    print("\n含 O4X3C2 ?", "O4X3C2" in ok_formula)
    return ok_formula


if __name__ == "__main__":
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 22
    main(N)
