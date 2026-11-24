# -*- coding: utf-8 -*-
"""三素相互作用（方案 1：元素配对 + 分族强度/覆盖半径）
================================================================
三个维度（与质量/物态/温度并存，不改内核）：

  聚素 = 吸引力强度   O=3 点、X=2 点、C=1 点
  散素 = 覆盖范围     K=3 点、A=2 点、F=1 点
  动素 = 排斥力强度   P=3 点、W=2 点、L=1 点

单分子量
--------
  点数和   P = 3·n_O + 2·n_X + 1·n_C        （聚素点数）
           Q = 3·n_K + 2·n_A + 1·n_F        （散素点数，决定半径）
           S = 3·n_P + 2·n_W + 1·n_L        （动素点数）
  强度轴   A = P/(n_O+n_X+n_C)  缺族 → 0     （0~3 的族内平均点）
           B = Q/(n_K+n_A+n_F)  缺族 → 0
           D = S/(n_P+n_W+n_L)  缺族 → 0
  覆盖半径（方阵 8 邻域，半径 1 = 相邻一圈 8 格；切比雪夫距离）
     连续规则（T96 起，与 ChemLab `_radius_of_q` 一致）：
           r_att = clamp(Q, 1, R_MAX)                  （Q 点即半径格数）
           r_rep = clamp(round(0.7·Q), 1, R_MAX)       （排斥落后 0.7 倍点数）
     Q = 0/1/2/3/…/12 对应 1/1/2/3/…/12，R_MAX 默认 12；世界脚本
     以自身 force_r（扫描窗口）作为 r_max 传入，使半径封顶 == 力扫描窗口。

双分子（i, j，格距 d = max(|dx|,|dy|)，环面）
--------------------------------------------
  组成重叠（只与同种元素配对，无任何额外可调参数）
      组成 Jaccard：J_att = Σ_e min(n_i^e, n_j^e) / Σ_e max(n_i^e, n_j^e)
      动素同理：    J_rep = Σ_e min(s_i^e, s_j^e) / Σ_e max(s_i^e, s_j^e)
      （同式 = 1；异式 = 共享元素原子数 / 并集原子数）
  距离衰减
      F(d, r) = 1                       d = 1
              = (r + 1 - d) / r        1 < d ≤ r
              = 0                      d > r
  半径合成：r_att,ij = max(r_att,i, r_att,j)；r_rep,ij = max(r_rep,i, r_rep,j)
  力
      Att_ij(d) = K_A · sqrt(A_i·A_j)/3 · J_att · F(d, r_att,ij)
      Rep_ij(d) = K_R · sqrt(D_i·D_j)/3 · J_rep · F(d, r_rep,ij)
      w_ij(d)   = Att − Rep
  能量单位 E*：K_A=2.5（S 短键的 κ0）、K_R=0.5；同式 A=3 时 Att=2.5。

判定（**粘附语义，不是化学键**）
---------------------------------
  w ≥ +1.0   强粘 = 粘附锁：锁住两分子的相对位置（拉不开），
             不生成化学键、不改变分子式、不占用价键位点；粘附强度 = w
  +0.2 ≤ w    弱粘 = 可逆接触（可断，不锁死）
  |w| < 0.2   几乎无作用
  w ≤ −0.2   排斥（沿连线推开）

  化学键（S 短键/C 角键/L 长键）只由反应规则 1~11 的 F(v) 产生，与三素无关。

纯标准库；本模块只读，不修改内核，也不改世界。
"""
from __future__ import annotations

import math

PTS = {"O": 3, "X": 2, "C": 1, "K": 3, "A": 2, "F": 1, "P": 3, "W": 2, "L": 1}
FAM = {
    "O": "att", "X": "att", "C": "att",
    "K": "rng", "A": "rng", "F": "rng",
    "P": "rep", "W": "rep", "L": "rep",
}
ATT_ELS = ("O", "X", "C")
RNG_ELS = ("K", "A", "F")
REP_ELS = ("P", "W", "L")

R_MAX = 12           # 半径封顶默认值（= ChemLab r_cap 默认 12）；世界脚本用 force_r 覆盖
UNIT = 10.0          # 旧「10 点 = 1 档」单位；T96 起不再参与半径计算，保留供历史脚本读取
K_A = 2.5            # 吸引系数（= S 短键 κ0）
K_R = 0.5            # 排斥系数
W_STRONG = 1.0
W_WEAK = 0.2
N_RING = 8           # 方阵 8 邻域


def parse_formula(formula):
    """'O2X3' -> {'O':2,'X':3}；纯元素字母（无数字）= 1 个。"""
    out = {}
    i = 0
    n = len(formula)
    while i < n:
        ch = formula[i]
        if not ("A" <= ch <= "Z"):
            i += 1
            continue
        j = i + 1
        num = ""
        while j < n and formula[j].isdigit():
            num += formula[j]
            j += 1
        out[ch] = out.get(ch, 0) + (int(num) if num else 1)
        i = j
    return out


def points(comp):
    """返回 (P, Q, S, N)：聚/散/动素点数与原子总数。"""
    p = q = s = 0
    for el, c in comp.items():
        w = PTS.get(el, 0) * c
        f = FAM.get(el)
        if f == "att":
            p += w
        elif f == "rng":
            q += w
        elif f == "rep":
            s += w
    return p, q, s, sum(comp.values())


def radii(q, r_max=None):
    """覆盖半径（连续规则，T96 起）：吸引 clamp(Q,1,R_MAX)，排斥 clamp(round(0.7Q),1,R_MAX)。

    r_max 为封顶半径；缺省用模块常量 R_MAX=12（= ChemLab r_cap 默认值）。
    世界脚本传入自身 force_r，保证「半径封顶 == 力扫描窗口」。
    """
    cap = R_MAX if r_max is None else int(r_max)
    if cap < 1:
        cap = 1
    r_att = min(cap, max(1, int(q)))
    # 0.7Q 取整用 half-up：与 ChemLab GDScript round()（half away from zero）一致。
    # Python 内置 round 是银行家舍入，Q=15 时会得 10 而 ChemLab 得 11。
    r_rep = min(cap, max(1, int(math.floor(0.7 * float(q) + 0.5))))
    return r_att, r_rep


def scores(comp, r_max=None):
    """单分子三分 + 点数和 + 半径（r_max 为半径封顶，缺省 R_MAX）。"""
    p, q, s, n = points(comp)
    n_att = sum(c for el, c in comp.items() if FAM.get(el) == "att")
    n_rng = sum(c for el, c in comp.items() if FAM.get(el) == "rng")
    n_rep = sum(c for el, c in comp.items() if FAM.get(el) == "rep")
    a = p / n_att if n_att else 0.0
    b = q / n_rng if n_rng else 0.0
    d = s / n_rep if n_rep else 0.0
    r_att, r_rep = radii(q, r_max)
    return {
        "natoms": n, "P": p, "Q": q, "S": s,
        "A": a, "B": b, "D": d,
        "n_att": n_att, "n_rng": n_rng, "n_rep": n_rep,
        "r_att": r_att, "r_rep": r_rep,
    }


def overlap(comp_i, comp_j):
    """组成同一性 J（0~1，全元素原子数 Jaccard），同式=1。

    配对只反映“是不是同一种/组成多接近”，不含额外的匹配度变量。
    """
    num = sum(min(comp_i.get(e, 0), comp_j.get(e, 0)) for e in PTS)
    den = sum(max(comp_i.get(e, 0), comp_j.get(e, 0)) for e in PTS)
    j = num / den if den else 0.0
    return j, j


def decay(d, r):
    """距离衰减：F=1（贴邻），线性降到 0（r 处）。"""
    if d <= 0:
        return 0.0
    if d == 1:
        return 1.0
    if d > r:
        return 0.0
    return (r + 1 - d) / r


def pair_force(comp_i, comp_j, d=1, k_a=None, k_r=None, r_max=None):
    """两分子间在格距 d 的吸引/排斥/净力（r_max 为半径封顶，缺省 R_MAX）。

    返回 dict：att, rep, w, j_att, j_rep, r_att, r_rep, d。
    """
    ka = K_A if k_a is None else k_a
    kr = K_R if k_r is None else k_r
    si = scores(comp_i, r_max)
    sj = scores(comp_j, r_max)
    r_att = max(si["r_att"], sj["r_att"])
    r_rep = max(si["r_rep"], sj["r_rep"])
    j_att, j_rep = overlap(comp_i, comp_j)
    att = ka * ((si["A"] * sj["A"]) ** 0.5) / 3.0 * j_att * decay(d, r_att)
    rep = kr * ((si["D"] * sj["D"]) ** 0.5) / 3.0 * j_rep * decay(d, r_rep)
    return {
        "att": att, "rep": rep, "w": att - rep,
        "j_att": j_att, "j_rep": j_rep,
        "r_att": r_att, "r_rep": r_rep, "d": d,
    }


def classify(w):
    """w → 强粘/弱粘/无作用/排斥。"""
    if w >= W_STRONG:
        return "strong"
    if w >= W_WEAK:
        return "weak"
    if w > -W_WEAK:
        return "none"
    return "repel"


if __name__ == "__main__":
    # 手算自检（也可 `python alchemy/three_su.py`）
    demo = ["O2", "X2", "C2", "XA", "WA", "K2", "LF", "P2", "OXCPWKA", "C3K3F2", "C2K2", "CKF2"]
    print("%-10s %6s %6s %6s %4s %4s  %8s %8s %8s" % (
        "formula", "A", "B", "D", "rA", "rR", "att_self", "rep_self", "w_self"))
    for f in demo:
        c = parse_formula(f)
        s = scores(c)
        pf = pair_force(c, c, 1)
        print("%-10s %6.2f %6.2f %6.2f %4d %4d  %8.2f %8.2f %8.2f" % (
            f, s["A"], s["B"], s["D"], s["r_att"], s["r_rep"],
            pf["att"], pf["rep"], pf["w"]))
    print()
    cross = [("O2", "K2"), ("O2", "O2X3"), ("XA", "CF"), ("WA", "LF"), ("O2", "X3"), ("CKF2", "C2K2")]
    print("%-6s %-8s %8s %8s %8s  %s" % ("i", "j", "att", "rep", "w", "class"))
    for a, b in cross:
        pf = pair_force(parse_formula(a), parse_formula(b), 1)
        print("%-6s %-8s %8.2f %8.2f %8.2f  %s" % (a, b, pf["att"], pf["rep"], pf["w"], classify(pf["w"])))

    print()
    print("半径规则（T96 连续）：Q -> (r_att, r_rep) | 默认封顶 12 | 世界 force_r=2 封顶")
    for q in range(0, 25):
        a12, r12 = radii(q)
        a2, r2 = radii(q, 2)
        print("Q=%2d -> (%2d, %2d) | (%d, %d)" % (q, a12, r12, a2, r2))
    # 形状自检：Q=0/1 取 1、连续增长、封顶生效、排斥落后 0.7 倍
    assert radii(0) == (1, 1)
    assert radii(1) == (1, 1)
    assert radii(2) == (2, 1)
    assert radii(15) == (12, 11)      # ChemLab round(10.5)=11（half away）；Python round 会给 10
    assert radii(15, 2) == (2, 2)
    assert radii(100) == (12, 12)
    for q in range(0, 40):
        pa, pr = radii(q, 6)
        assert 1 <= pa <= 6 and 1 <= pr <= 6
    print("半径规则自检 OK")
