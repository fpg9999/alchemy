# -*- coding: utf-8 -*-
"""final_pot_dong：动素（P/W/L，角键 C）全量扫描 + 可达闭包 + 结构导出。

对应聚素的 final_pot4.py；规则 1~8 同构，仅键几何换成角键 C（偶数方向）。
导出 substances_dong.json（含 place 轴向坐标 + place_xy 用户坐标 + 每根键的方向号）。
"""
import json
import random
import sys
from collections import Counter

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_dong as P

CN = {"P": "势", "W": "流", "L": "电"}
BASE = r"G:\AI work\deepseek\work1\alchemy"


def atoms_of(v):
    return ["P"] * v[0] + ["W"] * v[1] + ["L"] * v[2]


def vec_of_formula(f):
    v = {"P": 0, "W": 0, "L": 0}
    i = 0
    while i < len(f):
        e = f[i]
        i += 1
        num = ""
        while i < len(f) and f[i].isdigit():
            num += f[i]
            i += 1
        v[e] += int(num) if num else 1
    return (v["P"], v["W"], v["L"])


def run(v, rng=None):
    mols = P.simulate(atoms_of(v), rng)
    if mols is None:
        return None, "剩键"
    if not P.embed_all(mols):
        return None, "摆不出来"
    return mols, "ok"


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


N = 36
rng = random.Random(2025)

# 1) 全量扫描（确定性）+ 并列敏感性
formula_example = {}
reasons = Counter()
maxsize = 0
amb_inputs = []
for total in range(1, N + 1):
    for a in range(total + 1):
        for b in range(total - a + 1):
            c = total - a - b
            if c < 0 or (a + c) % 2:
                continue
            v = (a, b, c)
            mols, why = run(v)
            if mols is None:
                reasons[why] += 1
                continue
            reasons["ok"] += 1
            base_sig = P.signature(mols)
            outs = {base_sig}
            for _ in range(2):
                aa = atoms_of(v)
                rng.shuffle(aa)
                m2 = P.simulate(aa, rng)
                if m2 is not None and P.embed_all(m2):
                    outs.add(P.signature(m2))
            if len(outs) > 1:
                amb_inputs.append((v, list(outs)))
            for x in mols:
                maxsize = max(maxsize, len(x["atoms"]))
                formula_example.setdefault(P.formula_of(x["atoms"]), v)
print("扫描完成: 失败", dict(reasons), "公式数", len(formula_example), "最大原子", maxsize,
      "并列敏感输入", len(amb_inputs))
for v, outs in amb_inputs[:5]:
    print("  并列:", v, len(outs), "种")

# 2) 可达闭包（单质 P2 / W2 / L2 起）
known = {"P2": (2, 0, 0), "W2": (0, 2, 0), "L2": (0, 0, 2)}
example = dict(known)
for it in range(8):
    vecs = sorted(semigroup(list(known.values()), N))
    new = 0
    for v in vecs:
        mols, why = run(v)
        if mols is None:
            continue
        for x in mols:
            f = P.formula_of(x["atoms"])
            if f not in known:
                known[f] = vec_of_formula(f)
                example[f] = v
                new += 1
    print(f"闭包 iter {it}: 可达向量={len(vecs)} 已知={len(known)} 新增={new}")
    if new == 0:
        break

# 3) 导出结构（place 用轴向坐标；place_xy 用用户坐标 X=q, Y=q+2r；dir 为角键方向号）
out = []
for f in sorted(known, key=lambda s: (len(vec_of_formula(s)), vec_of_formula(s))):
    v = example[f]
    mols, why = run(v)
    target = None
    for x in mols:
        if P.formula_of(x["atoms"]) == f:
            target = x
            break
    place = P.embed_place(target["atoms"], target["edges"])
    place_xy = {str(k): [q, q + 2 * r] for k, (q, r) in place.items()}
    dirs = []
    for (i, j, m) in target["edges"]:
        qi, ri = place[i]
        qj, rj = place[j]
        dirs.append(P.dir_of(qj - qi, rj - ri))
    out.append({
        "formula": f,
        "vec": list(known[f]),
        "feed": list(v),
        "atoms": target["atoms"],
        "edges": [list(e) for e in target["edges"]],
        "dirs": dirs,
        "bond": "C",
        "place": {str(k): list(c) for k, c in place.items()},
        "place_xy": place_xy,
        "zh": "".join(CN[e] + (str(target["atoms"].count(e)) if target["atoms"].count(e) > 1 else "")
                      for e in ["P", "W", "L"] if target["atoms"].count(e)),
        "natoms": len(target["atoms"]),
    })

with open(BASE + r"\substances_dong.json", "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)

print("\n最终清单:", len(out), "种")
for it in out:
    print(f"  {it['formula']:8s} {it['zh']:8s} 原子={it['natoms']} 例投料={tuple(it['feed'])}"
          f" 方向={it['dirs']}")
