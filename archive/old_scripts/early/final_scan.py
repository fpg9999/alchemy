# -*- coding: utf-8 -*-
import itertools
import random
import sys
from collections import defaultdict, Counter
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot2 as P


def atoms_of(v):
    o, x, c = v
    return ["O"] * o + ["X"] * x + ["C"] * c


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


def run(v, opts=None, diag=None):
    mols = P.simulate(atoms_of(v), opts, diag)
    if mols is None:
        return None, "剩键"
    if not P.embed_all(mols):
        return None, "摆不出来"
    return mols, "ok"


def main():
    N = 18
    print("=== A. 全量扫描：总原子数 <= %d 的所有 (a,b,c) ===" % N)
    formula_examples = {}
    reasons = Counter()
    maxsize = 0
    bad_det = []
    r7 = 0
    r7_examples = []
    for total in range(1, N + 1):
        for a in range(total + 1):
            for b in range(total - a + 1):
                c = total - a - b
                if c < 0 or (a + c) % 2:
                    continue
                v = (a, b, c)
                diag = {}
                mols, why = run(v, diag=diag)
                reasons[why] += 1
                if diag.get("index_tie"):
                    r7 += diag["index_tie"]
                    if len(r7_examples) < 5:
                        r7_examples.append(v)
                if mols is None:
                    continue
                for m in mols:
                    f = P.formula_of(m["atoms"])
                    maxsize = max(maxsize, len(m["atoms"]))
                    if f not in formula_examples:
                        formula_examples[f] = v
                # 确定性：换原子顺序再跑
                base = P.signature(mols)
                for _ in range(2):
                    at = atoms_of(v)
                    random.shuffle(at)
                    m2 = P.simulate(at)
                    if m2 is None or not P.embed_all(m2):
                        s2 = "FAIL"
                    else:
                        s2 = P.signature(m2)
                    if s2 != base:
                        bad_det.append((v, base, s2))
    print("  出现过的公式数:", len(formula_examples))
    print("  最大分子原子数:", maxsize)
    print("  失败统计:", dict(reasons))
    print("  下标并列(规则7兜底)次数:", r7, "例子输入:", r7_examples)
    print("  顺序打乱后结果不同的输入数:", len(bad_det))
    for v, a, b in bad_det[:5]:
        print("    ", v, "\n      A:", a, "\n      B:", b)

    print("\n=== B. 规则 5/6/7 关掉后结果变化（总原子<=11） ===")
    base_set = set()
    for total in range(1, 12):
        for a in range(total + 1):
            for b in range(total - a + 1):
                c = total - a - b
                if c < 0 or (a + c) % 2:
                    continue
                mols, wh = run((a, b, c))
                if mols:
                    base_set |= {P.formula_of(m["atoms"]) for m in mols}
    print("  基线公式:", sorted(base_set, key=lambda s: (len(vec_of_formula(s)), s)))
    for name, opts in [("关C5", {"c5": False}), ("关C6", {"c6": False}), ("关C7", {"c7": False}),
                       ("只留1~2", {"c5": False, "c6": False, "c7": False})]:
        s = set()
        for total in range(1, 12):
            for a in range(total + 1):
                for b in range(total - a + 1):
                    c = total - a - b
                    if c < 0 or (a + c) % 2:
                        continue
                    mols, wh = run((a, b, c), opts)
                    if mols:
                        s |= {P.formula_of(m["atoms"]) for m in mols}
        extra = s - base_set
        miss = base_set - s
        print(f"  {name}: 公式数={len(s)} 多出={sorted(extra)} 少了={sorted(miss)}")

    print("\n=== C. 可达性闭包（N=%d）===" % N)
    known = {"O2": (2, 0, 0), "X2": (0, 2, 0), "C2": (0, 0, 2)}
    example = {"O2": (2, 0, 0), "X2": (0, 2, 0), "C2": (0, 0, 2)}
    for it in range(8):
        vecs = sorted(semigroup(list(known.values()), N))
        new = 0
        for v in vecs:
            mols, why = run(v)
            if mols is None:
                continue
            for m in mols:
                f = P.formula_of(m["atoms"])
                if f not in known:
                    known[f] = vec_of_formula(f)
                    example[f] = v
                    new += 1
        print(f"  iter {it}: 可达向量={len(vecs)} 已知公式={len(known)} 新增={new}")
        if new == 0:
            break

    print("\n=== 最终清单 ===")
    order = ["O2", "X2", "C2"]
    for f in sorted(known, key=lambda s: (len(vec_of_formula(s)), vec_of_formula(s))):
        print(f"  {f:8s}  vec={known[f]}  例:投入{example[f]}")


if __name__ == "__main__":
    main()
