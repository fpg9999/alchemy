# -*- coding: utf-8 -*-
"""verify_dong：验证动素结果
1) 公式集合与聚素 29 种一一对应（P↔O, W↔X, L↔C）；
2) 每种物质的抽象结构（元素标号 + 键数多重图）与聚素对应物完全相同；
3) 几何合法：坐标互不重合、每根键偏置落在角键 C 的偶数方向表里、价数守恒、连通。
"""
import json
import sys

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import pot_dong as P

BASE = r"G:\AI work\deepseek\work1\alchemy"
MAP = {"P": "O", "W": "X", "L": "C"}

ju = json.load(open(BASE + r"\substances.json", encoding="utf-8"))
dong = json.load(open(BASE + r"\substances_dong.json", encoding="utf-8"))


def canon(atoms, edges):
    """与 pot4.mol_label 相同的规范形，用作跨文件结构比对（元素统一成聚素符号）。"""
    n = len(atoms)
    mat = [[0] * n for _ in range(n)]
    for (i, j, k) in edges:
        mat[i][j] = mat[j][i] = k
    import itertools
    from collections import defaultdict
    groups = defaultdict(list)
    for i, e in enumerate(atoms):
        groups[e].append(i)
    keys = sorted(groups)
    perms = [list(itertools.permutations(groups[k])) for k in keys]
    best = None
    for combo in itertools.product(*perms):
        p = []
        for part in combo:
            p.extend(part)
        s = "".join(atoms[i] for i in p) + "|"
        for a in range(n):
            for b in range(a + 1, n):
                s += str(mat[p[a]][p[b]])
        if best is None or s < best:
            best = s
    return best


# 1) + 2) 公式与结构一一对应
ju_by_f = {x["formula"]: x for x in ju}
print("聚素", len(ju), "种；动素", len(dong), "种")
ok = 0
for it in dong:
    f = it["formula"]
    jf = "".join(MAP[e] + (str(f.count(e)) if f.count(e) > 1 else "")
                 for e in ["P", "W", "L"] if e in f)
    # 上面写法对 P2 之类可行，但需按次数展开：直接用 vec 更稳
    p, w, l = it["vec"]
    jf = "".join(e + (str(c) if c > 1 else "") for e, c in [("O", p), ("X", w), ("C", l)] if c)
    assert jf in ju_by_f, ("聚素缺对应物", f, jf)
    ref = ju_by_f[jf]
    # 结构 sig：把动素原子换成聚素符号后比较
    dong_sig = canon([MAP[e] for e in it["atoms"]], it["edges"])
    ju_sig = canon(ref["atoms"], [tuple(e) for e in ref["edges"]])
    if dong_sig != ju_sig:
        print("!! 结构不一致", f, "vs", jf)
    else:
        ok += 1
print(f"结构完全同构: {ok}/{len(dong)}")

# 3) 几何合法性独立检查
bad = 0
for it in dong:
    atoms = it["atoms"]
    edges = [tuple(e) for e in it["edges"]]
    place = {int(k): tuple(v) for k, v in it["place"].items()}
    xy = {int(k): tuple(v) for k, v in it["place_xy"].items()}
    n = len(atoms)
    # a) 坐标唯一
    if len(set(place.values())) != n:
        print("!! 坐标重合", it["formula"]); bad += 1
    # b) 每根键偏置 = 角键偶数方向
    for (i, j, m) in edges:
        dq = place[j][0] - place[i][0]
        dr = place[j][1] - place[i][1]
        d = P.dir_of(dq, dr)
        assert d in (2, 4, 6, 8, 10, 12)
        # 用户坐标也一致
        dx = xy[j][0] - xy[i][0]
        dy = xy[j][1] - xy[i][1]
        expect = {2: (1, 3), 4: (2, 0), 6: (1, -3),
                  8: (-1, -3), 10: (-2, 0), 12: (-1, 3)}[d]
        assert (dx, dy) == expect, ("XY 偏置不符", it["formula"], (dx, dy), expect)
        # c) 用户坐标格点合法（X、Y 同奇偶）
        for k in range(n):
            assert (xy[k][0] - xy[k][1]) % 2 == 0, ("不是合法格点", it["formula"], xy[k])
    # d) 价数守恒 + 连通
    deg = [0] * n
    for (i, j, m) in edges:
        deg[i] += m
        deg[j] += m
    for k, e in enumerate(atoms):
        assert deg[k] == P.VAL[e], ("价数不符", it["formula"], k, deg[k], P.VAL[e])
    seen = {0}
    st = [0]
    adj = [[] for _ in range(n)]
    for (i, j, m) in edges:
        adj[i].append(j)
        adj[j].append(i)
    while st:
        u = st.pop()
        for v in adj[u]:
            if v not in seen:
                seen.add(v)
                st.append(v)
    assert len(seen) == n, ("不连通", it["formula"])
print("几何合法性检查完成，问题数:", bad)
