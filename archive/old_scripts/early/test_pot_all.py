# -*- coding: utf-8 -*-
"""test_pot_all：通用模拟器回归测试 + 三类纯大类闭包 + 混类小投料探针。"""
import json
import sys
import time
from collections import defaultdict

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_all as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
PURE = {"聚": ["O", "X", "C"], "动": ["P", "W", "L"], "散": ["K", "A", "F"]}
RENAME = {"聚": ("O", "X", "C"), "动": ("P", "W", "L"), "散": ("K", "A", "F")}


def atoms_of_vec(v, elems):
    return P.vec_to_atoms(v, elems)


def semigroup(vecs, N):
    reach = set()
    stack = [(0,) * len(vecs[0])]
    seen = set(stack)
    while stack:
        cur = stack.pop()
        reach.add(cur)
        for v in vecs:
            nxt = tuple(a + b for a, b in zip(cur, v))
            if sum(nxt) <= N and nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return reach


def run_vec(v, elems, rng=None, use_embed=True):
    mols = P.simulate(atoms_of_vec(v, elems), rng)
    if mols is None:
        return None, "剩键"
    if use_embed and not P.embed_all(mols):
        return None, "摆不出来"
    return mols, "ok"


def parse_in(f, elems):
    cnt = defaultdict(int)
    i = 0
    while i < len(f):
        e = f[i]
        i += 1
        num = ""
        while i < len(f) and f[i].isdigit():
            num += f[i]
            i += 1
        cnt[e] += int(num) if num else 1
    return tuple(cnt[e] for e in elems)


def closure(elems, seeds, N, verbose=True):
    known = {f: parse_in(f, elems) for f in seeds}
    it = 0
    while True:
        vecs = semigroup(list(known.values()), N)
        new = 0
        for v in vecs:
            mols, why = run_vec(v, elems)
            if mols is None:
                continue
            for m in mols:
                f = P.formula_of(m["atoms"])
                if f not in known:
                    known[f] = parse_in(f, elems)
                    new += 1
        it += 1
        if verbose:
            print(f"  closure iter {it}: 可达向量={len(vecs)} 已知={len(known)} 新增={new}")
        if new == 0:
            break
    return known


def translate(f, src, dst):
    mp = {RENAME[src][i]: RENAME[dst][i] for i in range(3)}
    return "".join(mp.get(ch, ch) for ch in f)


def compositions(total, k, prefix=()):
    if k == 1:
        yield prefix + (total,)
        return
    for x in range(total + 1):
        yield from compositions(total - x, k - 1, prefix + (x,))


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL") + " " + msg)
    return cond


def main():
    t0 = time.time()

    # ---------- 1) HANDOFF 第 5 节已知案例 ----------
    print("\n[1] HANDOFF 已知案例（聚素）")
    cases = [
        ((2, 2, 2), ["OXC", "OXC"]),
        ((2, 4, 0), ["O2X4"]),
        ((4, 3, 2), ["O2X2", "O2XC2"]),
        ((3, 3, 5), ["O2X2C4", "OXC"]),
        ((3, 5, 5), ["O2X2C4", "OX3C"]),
    ]
    for v, exp in cases:
        mols, why = run_vec(v, PURE["聚"])
        got = sorted(P.formula_of(m["atoms"]) for m in mols) if mols else [why]
        check(got == sorted(exp), f"{v} -> {got}  (期望 {exp})")

    # ---------- 2) 纯大类闭包（应各 29 种） ----------
    results = {}
    for cat, elems in PURE.items():
        print(f"\n[2] {cat}素闭包（生成元 {elems[0]}2 {elems[1]}2 {elems[2]}2，总原子≤36）")
        t = time.time()
        known = closure(elems, [elems[0] + "2", elems[1] + "2", elems[2] + "2"], 36)
        results[cat] = set(known)
        check(len(known) == 29, f"{cat}素物质数 {len(known)}（期望 29） 用时 {time.time()-t:.1f}s")

    print("\n[2b] 三套公式符号替换后应完全相同")
    base = {translate(f, "聚", "动") for f in results["聚"]}
    check(base == results["动"], "聚→动 映射一致")
    base = {translate(f, "聚", "散") for f in results["聚"]}
    check(base == results["散"], "聚→散 映射一致")

    # ---------- 3) 混类小投料探针 ----------
    print("\n[3] 混类小投料探针（总原子 ≤7，全 9 元素）")
    t = time.time()
    cnt = 0
    formulas = defaultdict(set)
    for total in range(1, 8):
        for v in compositions(total, 9):
            cnt += 1
            mols, why = run_vec(v, P.ORDER)
            if mols is None:
                continue
            for m in mols:
                cats = tuple(sorted(set(P.CAT[e] for e in m["atoms"]), key=lambda c: "聚动散".index(c)))
                formulas[cats].add(P.formula_of(m["atoms"]))
    print(f"  投料向量 {cnt} 个，用时 {time.time()-t:.1f}s")
    for cats in sorted(formulas):
        fs = sorted(formulas[cats])
        print(f"  {'-'.join(cats):8s} : {len(fs):3d} 种  " + " ".join(fs[:14]) +
              (" ..." if len(fs) > 14 else ""))
    print(f"\n总用时 {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
