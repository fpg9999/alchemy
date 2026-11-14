# -*- coding: utf-8 -*-
"""t16_decompose.py
检验：695 种"终态新骨架"能否拆成 45 库骨架（单类型 7 模块 + T8 35 形态）的并集，
其中各部分之间的边就是"直接融合键"（不经二价桥）。
方法：对每个形态做精确覆盖/贪心：选不相交的子图，每个子图与库中某形态同构；
最大化被库骨架覆盖的顶点数（允许剩余单原子）。
"""
import itertools
import json
from collections import Counter

BASE = r"G:\AI work\deepseek\work1\alchemy"
TRI = {"O", "P", "K"}


def canon(atoms, edges):
    """带元素标签的多重图规范形（n 小，暴力置换）"""
    n = len(atoms)
    best = None
    for p in itertools.permutations(range(n)):
        s = []
        for a in range(n):
            for b in range(a + 1, n):
                # 找 p 中 a,b 对应的原顶点
                pass
        # 简化：直接用排列重排
        m = [[0] * n for _ in range(n)]
        for (i, j, k) in edges:
            m[i][j] = m[j][i] = k
        s = []
        for a in range(n):
            for b in range(a + 1, n):
                if m[p[a]][p[b]]:
                    s.append((a, b, m[p[a]][p[b]]))
        key = (tuple(atoms[p[i]] for i in range(n)), tuple(sorted(s)))
        if best is None or key < best:
            best = key
    return best


def normalize_single(atoms, edges):
    if len(set(atoms)) == 1:
        return canon(["A"] * len(atoms), edges)
    return canon(atoms, edges)


# 库
lib = set()
mod = {
    "单原子": (["A"], []),
    "单键二聚体": (["A", "A"], [(0, 1, 1)]),
    "双键二聚体": (["A", "A"], [(0, 1, 2)]),
    "三键二聚体": (["A", "A"], [(0, 1, 3)]),
    "三元链": (["A", "A", "A"], [(0, 1, 1), (1, 2, 1)]),
    "三元环(全单键)": (["A", "A", "A"], [(0, 1, 1), (1, 2, 1), (0, 2, 1)]),
    "三元环(含双键)": (["A", "A", "A"], [(0, 1, 1), (0, 2, 2), (1, 2, 1)]),
}
lib_names = {}
for name, (atoms, edges) in mod.items():
    k = canon(atoms, edges)
    lib.add(k)
    lib_names[k] = name
t8 = json.load(open(BASE + r"\t8_forms.json", encoding="utf-8"))
for f in t8:
    if len(f["atoms"]) == 1:
        continue
    k = canon(f["atoms"], [tuple(e) for e in f["edges"]])
    lib.add(k)
    lib_names.setdefault(k, "T8:" + f["formula"])
print("库形态数:", len(lib))


def sub_key(atoms, edges, verts):
    idx = {v: k for k, v in enumerate(verts)}
    ats = [atoms[v] for v in verts]
    es = []
    for (i, j, m) in edges:
        if i in idx and j in idx:
            es.append((idx[i], idx[j], m))
    return normalize_single(ats, es)


def decompose(n, atoms, edges, max_exact=10):
    """返回 (covered, parts, leftover_singletons)；n>max_exact 用贪心"""
    verts = list(range(n))
    # 所有子集 -> 是否库形态
    if n <= max_exact:
        good = []
        for mask in range(1, 1 << n):
            vs = [i for i in range(n) if mask >> i & 1]
            if len(vs) < 2:
                continue
            k = sub_key(atoms, edges, vs)
            if k in lib:
                good.append((mask, len(vs)))
        # 精确 DP：最大覆盖（优先多覆盖；同等取更少部分）
        best = {0: (0, 0, [])}  # mask -> (covered, parts, chosen)
        states = {0: (0, 0, [])}
        for mask in range(1, 1 << n):
            pass
        # 用记忆化 DFS
        from functools import lru_cache
        @lru_cache(maxsize=None)
        def f(rem_mask):
            if rem_mask == 0:
                return (0, 0, ())
            # 取最低位顶点，选择包含它的库子集或不覆盖
            low = rem_mask & -rem_mask
            i = low.bit_length() - 1
            best_c, best_p, best_seq = 0, 0, ()
            # 不覆盖 i
            c, p, seq = f(rem_mask & ~low)
            best_c, best_p, best_seq = c, p, seq
            # 覆盖 i 的库子集
            for mask, sz in good:
                if mask & low and (mask & ~rem_mask) == 0:
                    c2, p2, seq2 = f(rem_mask & ~mask)
                    c2 += sz
                    p2 += 1
                    # 优先覆盖多，其次部分少
                    if (c2, -p2) > (best_c, -best_p):
                        best_c, best_p = c2, p2
                        best_seq = (mask,) + seq2
            return (best_c, best_p, best_seq)
        c, p, seq = f((1 << n) - 1)
        return c, p, seq
    else:
        # 贪心：随机顺序找库子集
        covered = set()
        parts = []
        for size in (5, 4, 3, 2):
            for comb in itertools.combinations(range(n), size):
                if any(v in covered for v in comb):
                    continue
                k = sub_key(atoms, edges, comb)
                if k in lib:
                    parts.append(comb)
                    covered.update(comb)
        return len(covered), len(parts), [tuple(p) for p in parts]


def main():
    d = json.load(open(BASE + r"\t15_forms.json", encoding="utf-8"))
    print("新形态数:", len(d), flush=True)
    full = 0
    by_n = Counter()
    results = []
    for x in d:
        atoms = x["atoms"]
        edges = [tuple(e) for e in x["edges"]]
        n = len(atoms)
        c, p, seq = decompose(n, atoms, edges)
        frac = c / n
        results.append({"example": x["example"], "n": n, "covered": c,
                        "parts": p, "frac": frac,
                        "parts_desc": [tuple(atoms[i] for i in part) for part in seq]})
        if c == n:
            full += 1
        by_n[(n, c == n)] += 1
    print(f"完全可拆（所有顶点都被库骨架覆盖，无剩余）: {full}/{len(d)}")
    # 覆盖率分布
    fr = Counter(round(r["frac"], 2) for r in results)
    for k in sorted(fr):
        print(f"  覆盖率 {k}: {fr[k]} 种")
    # 例子
    for target in ["O3P", "O2CK", "O3KA2", "CP2K3", "O2K4", "O2K6", "O2P6", "O5P5K2"]:
        r = next((q for q in results if q["example"] == target), None)
        if r:
            print(f"\n{target}（n={r['n']}）覆盖率 {r['covered']}/{r['n']}，库骨架块 {r['parts']} 个:")
            for part in r["parts_desc"]:
                print("   ", "".join(part))
    json.dump(results, open(BASE + r"\t16_decompose.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=0, default=str)
    print("\nsaved t16_decompose.json")


if __name__ == "__main__":
    main()
