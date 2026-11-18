# -*- coding: utf-8 -*-
"""T70 生成式形状语言：骨架 / 桥梁 / 端帽都由"数据 → 函数"生成，而不是手工指派的固定多边形。

设计原则
--------
1) 同一条规则族：所有骨架图形都来自同一个"超公式晶核"函数，只是输入不同（元素计数、度数谱、键角）。
   → 同类骨架看起来像同一种东西（规律性），不同骨架又各不相同（涌现性）。
2) 数据驱动：K 数决定对称瓣数、P 比例决定圆润度、O 比例决定锐度、度数谱决定瓣的相位与晶脉。
3) 桥梁与端帽也走"数据 → 曲线"：桥链长度决定编织/褶皱数，键型 S/C/L 决定收束与张力，
   一价原子所在骨架的锐度决定尖刺层数。
"""
import hashlib
import math

from PIL import Image, ImageDraw, ImageFilter

import t68_shapes as S

TAU = math.pi * 2.0


def hexa(col, a):
    if isinstance(col, (tuple, list)):
        t = tuple(int(v) for v in col[:3])
        return t + (a,)
    h = str(col).lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


# ---------------------------------------------------------------- 基础工具
def hash_seed(text):
    h = hashlib.md5(text.encode("utf-8")).hexdigest()
    return int(h[:8], 16) / float(0xFFFFFFFF)


def unit(v, frm=(0.0, 0.0)):
    dx, dy = v[0] - frm[0], v[1] - frm[1]
    m = math.hypot(dx, dy) or 1.0
    return (dx / m, dy / m)


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def polar_curve(cx, cy, r, rf, k=240, rot=0.0):
    pts = []
    for i in range(k):
        th = TAU * i / k
        rr = r * rf(th)
        pts.append((cx + math.cos(th + rot) * rr, cy + math.sin(th + rot) * rr))
    return pts


# ---------------------------------------------------------------- 骨架图形
def block_params(atoms, edges, label=""):
    """从块数据算出画图参数（这就是"涌现"的来源）。"""
    n = len(atoms)
    cnt = {"O": atoms.count("O"), "P": atoms.count("P"), "K": atoms.count("K")}
    deg = [0] * n
    for (i, j, m) in edges:
        deg[i] += m
        deg[j] += m
    dmax = max(deg) if deg and max(deg) > 0 else 1
    dsorted = sorted(deg, reverse=True)
    seed = hash_seed(label or "".join(sorted(atoms)))
    # 对称瓣数：K 每多一个多一瓣；纯 P 退化为 2 瓣柔圆；纯 O 为 3 瓣
    if cnt["K"] == 0 and cnt["P"] > 0 and cnt["O"] == 0:
        m_basic = 2
    else:
        m_basic = 3 + cnt["K"]
    # 圆润度 n1：P 越多越圆；O、K 越多越锐
    n1 = 0.42 + 1.55 * (cnt["P"] / float(n)) + 0.30 * (cnt["O"] / float(n))
    # 尖刺量：O 给出三棱锐边，K 给出多边形硬角
    n2 = 0.75 + 0.85 * (cnt["O"] / float(n)) + 0.55 * (cnt["K"] / float(n))
    n3 = 0.75 + 0.85 * (cnt["P"] / float(n))
    # 有机扰动：由哈希种子给相位，幅度很小，只让每个个体有唯一"指纹"
    wob = 0.030 + 0.022 * ((seed * 7.0) % 1.0)
    rot = TAU * seed * 0.62
    ph = TAU * ((dsorted[0] if dsorted else 1) / float(dmax + 1))
    return {"n": n, "cnt": cnt, "deg": deg, "dmax": dmax, "dsorted": dsorted,
            "m": m_basic, "n1": n1, "n2": n2, "n3": n3, "wob": wob,
            "rot": rot, "ph": ph, "seed": seed}


def skeleton_rf(p, scale=1.0):
    """超公式 + 谐波扰动：同一函数生成全部 38 个骨架外形。"""
    m, n1, n2, n3, wob = p["m"], p["n1"], p["n2"], p["n3"], p["wob"]
    ph = p["ph"]

    def rf(th):
        t = m * th / 4.0
        c, s = abs(math.cos(t)), abs(math.sin(t))
        c = max(c, 1e-6)
        s = max(s, 1e-6)
        base = (c ** n2 + s ** n3) ** (-1.0 / n1)
        base = base / 1.35                      # 归一到 1 附近
        organic = (1.0 + wob * math.cos((m + 3) * th + ph)
                   + 0.55 * wob * math.cos((2 * m + 1) * th - ph * 0.7))
        return scale * base * organic
    return rf


def draw_skeleton(cv, cx, cy, r, atoms, edges, key, label="", alpha=255, veins=True, rings=3):
    """骨架图形：超公式晶核 + 生长纹 + 晶脉 + 柔光。"""
    p = block_params(atoms, edges, label)
    col = S.FAMILY[key]["col"]
    rgb = hexa(col, 255)[:3]
    rf = skeleton_rf(p)
    d = cv.d
    pts = polar_curve(cx, cy, r, rf, k=260, rot=p["rot"])
    # 柔和投影
    sh = Image.new("RGBA", cv.img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).polygon(pts, fill=hexa(col, 26))
    sh = sh.filter(ImageFilter.GaussianBlur(max(2.0, r * 0.08)))
    if cv.img.mode == "RGBA":
        cv.img.alpha_composite(sh)
    else:
        cv.img.paste(sh, (0, 0), sh)
    d = cv.d
    # 由浅到深的层叠填充（芯部最浅）
    for i in range(4, 0, -1):
        rr = r * (0.34 + 0.165 * i)
        q = polar_curve(cx, cy, rr, rf, k=200, rot=p["rot"])
        d.polygon(q, fill=hexa(S.lighten(col, 0.30 + 0.16 * i), 255))
    # 外轮廓
    dark = tuple(max(0, int(v * 0.62)) for v in rgb)
    d.line(pts + [pts[0]], fill=hexa(dark, 255),
           width=max(2, int(r * 0.045)), joint="curve")
    # 生长纹（同一函数缩半径，越向外越淡）
    for i in range(rings, 0, -1):
        rr = r * (0.30 + 0.20 * i)
        q = polar_curve(cx, cy, rr, rf, k=180, rot=p["rot"])
        d.line(q + [q[0]], fill=hexa(S.lighten(col, 0.10), int(96 - 20 * i)), width=1)
    if veins:
        # 晶脉：从每条瓣尖向内收，度数越大越亮越粗
        mv = max(2, p["m"])
        for k in range(mv):
            th = p["rot"] + TAU * (k / float(mv)) + p["ph"] * 0.0
            outer = r * rf(th) * 0.92
            inner = outer * (0.26 + 0.10 * ((k + p["dsorted"][0]) % 3))
            c1 = (cx + math.cos(th) * inner, cy + math.sin(th) * inner)
            c2 = (cx + math.cos(th) * outer, cy + math.sin(th) * outer)
            d.line([c1, c2], fill=hexa(S.lighten(col, 0.05), 120), width=max(1, int(r * 0.02)))
            d.ellipse([c2[0] - 1.7, c2[1] - 1.7, c2[0] + 1.7, c2[1] + 1.7],
                      fill=hexa(rgb, 210))
    return p


def block_glyph(cv, cx, cy, r, atoms, edges, key, label=""):
    return draw_skeleton(cv, cx, cy, r, atoms, edges, key, label)


# ---------------------------------------------------------------- 桥梁图形
def draw_bridge_x(cv, a, b, s, mult=1, plate=True):
    """晶 X：焊核（钝三角 + 放射焊纹 + 两侧焊板），多重键加厚。"""
    d = cv.d
    u = unit(b, a)
    n = (-u[1], u[0])
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    half = max(5.0, min(0.62 * s, 0.30 * L + 0.24 * s)) * (1.0 + 0.14 * (mult - 1))
    tip = (mid[0] - u[0] * half * 1.25, mid[1] - u[1] * half * 1.25)
    base = (mid[0] + u[0] * half * 0.80, mid[1] + u[1] * half * 0.80)
    tri = [tip, (base[0] + n[0] * half * 1.02, base[1] + n[1] * half * 1.02),
           (base[0] - n[0] * half * 1.02, base[1] - n[1] * half * 1.02)]
    d.polygon(tri, fill=(206, 218, 230), outline=(46, 62, 82))
    # 内芯高光
    small = [lerp(tip, base, 0.18),
             lerp((base[0] + n[0] * half * 0.62, base[1] + n[1] * half * 0.62), tip, 0.12),
             lerp((base[0] - n[0] * half * 0.62, base[1] - n[1] * half * 0.62), tip, 0.12)]
    d.polygon(small, fill=(238, 245, 251))
    d.line(tri + [tri[0]], fill=(30, 44, 62), width=max(2, int(half * 0.11)))
    for k in range(3 + 2 * (mult - 1)):
        t = 0.30 + 0.20 * k
        if t > 0.96:
            break
        p = lerp(tip, base, t)
        wf = half * (1.0 - 0.22 * k) * 0.92
        d.line([(p[0] + n[0] * wf, p[1] + n[1] * wf), (p[0] - n[0] * wf, p[1] - n[1] * wf)],
               fill=(146, 166, 186), width=1)
    if plate:
        for f in (-1.0, 1.0):
            pc = (mid[0] + u[0] * half * 1.55 * f, mid[1] + u[1] * half * 1.55 * f)
            hh = half * 0.86
            th = half * 0.14
            rect = [(pc[0] + n[0] * hh + u[0] * th, pc[1] + n[1] * hh + u[1] * th),
                    (pc[0] - n[0] * hh + u[0] * th, pc[1] - n[1] * hh + u[1] * th),
                    (pc[0] - n[0] * hh - u[0] * th, pc[1] - n[1] * hh - u[1] * th),
                    (pc[0] + n[0] * hh - u[0] * th, pc[1] + n[1] * hh - u[1] * th)]
            d.polygon(rect, fill=(96, 110, 128), outline=(52, 66, 84))


def draw_bridge_w(cv, a, b, s, ncross=1):
    """流 W：双股肌腱编织（交叉数随链长）。先铺腱鞘，再压编织线。"""
    d = cv.d
    u = unit(b, a)
    n = (-u[1], u[0])
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    steps = 120
    amp = max(5.0, min(0.40 * s, 0.16 * L + 0.12 * s))
    env = []
    for i in range(steps + 1):
        t = i / float(steps)
        p = lerp(a, b, t)
        e = math.sin(math.pi * t) ** 0.45
        env.append((p[0] + n[0] * amp * e * 1.30, p[1] + n[1] * amp * e * 1.30))
    for i in range(steps, -1, -1):
        t = i / float(steps)
        p = lerp(a, b, t)
        e = math.sin(math.pi * t) ** 0.45
        env.append((p[0] - n[0] * amp * e * 1.30, p[1] - n[1] * amp * e * 1.30))
    d.polygon(env, fill=(196, 224, 244))
    for phase, col, wd in ((0.0, (24, 82, 128), 4), (math.pi, (24, 82, 128), 4)):
        pts = []
        for i in range(steps + 1):
            t = i / float(steps)
            p = lerp(a, b, t)
            e = math.sin(math.pi * t) ** 0.45
            off = amp * e * math.sin(TAU * ncross * t + phase)
            pts.append((p[0] + n[0] * off, p[1] + n[1] * off))
        d.line(pts, fill=col, width=wd, joint="curve")
        d.line(pts, fill=(168, 212, 240), width=1, joint="curve")


def draw_bridge_a(cv, a, b, s, pleats=1):
    """气 A：褶皱薄膜（横向展开的薄幕，长边贴着两侧骨架）。"""
    d = cv.d
    u = unit(b, a)
    n = (-u[1], u[0])
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    hl = max(0.85 * s, min(1.15 * s, 0.55 * L + 0.62 * s))
    ht = max(0.11 * s, min(0.17 * s, 0.08 * L + 0.07 * s))
    # 幕面：整片浅青，两端微微内收
    poly = [(mid[0] + n[0] * hl + u[0] * ht, mid[1] + n[1] * hl + u[1] * ht),
            (mid[0] - n[0] * hl + u[0] * ht, mid[1] - n[1] * hl + u[1] * ht),
            (mid[0] - n[0] * hl - u[0] * ht, mid[1] - n[1] * hl - u[1] * ht),
            (mid[0] + n[0] * hl - u[0] * ht, mid[1] + n[1] * hl - u[1] * ht)]
    d.polygon(poly, fill=(178, 226, 214), outline=(10, 78, 66))
    d.line(poly + [poly[0]], fill=(8, 64, 54), width=2)
    # 褶：沿幕高方向等距的短折线（明暗交替）
    nf = max(4, pleats * 3 + 1)
    for k in range(1, nf):
        t = -1.0 + 2.0 * k / nf
        p = (mid[0] + n[0] * t * hl, mid[1] + n[1] * t * hl)
        shade = (140, 206, 192) if k % 2 == 0 else (108, 186, 170)
        d.line([(p[0] + u[0] * ht, p[1] + u[1] * ht),
                (p[0] - u[0] * ht, p[1] - u[1] * ht)],
               fill=shade, width=max(2, int(ht * 0.75)))
    # 两条长边（贴着两侧骨架的边）再压一道
    for f in (-1.0, 1.0):
        p0 = (mid[0] + u[0] * ht * 0.98 * f, mid[1] + u[1] * ht * 0.98 * f)
        d.line([(p0[0] + n[0] * hl, p0[1] + n[1] * hl),
                (p0[0] - n[0] * hl, p0[1] - n[1] * hl)],
               fill=(8, 60, 50), width=2)


def draw_bridge_chain(cv, a, b, s, elems):
    """多元素桥：沿同一条轴线分段，接缝打结。"""
    groups = []
    for e in elems:
        if groups and groups[-1][0] == e:
            groups[-1][1] += 1
        else:
            groups.append([e, 1])
    n = len(groups)
    a0 = lerp(a, b, 0.10)
    b0 = lerp(a, b, 0.90)
    d = cv.d
    for i, (e, cnt) in enumerate(groups):
        p = lerp(a0, b0, i / float(n))
        q = lerp(a0, b0, (i + 1) / float(n))
        if e == "X":
            draw_bridge_x(cv, p, q, s, mult=cnt, plate=(i == n - 1 or i == 0))
        elif e == "W":
            draw_bridge_w(cv, p, q, s, ncross=max(1, cnt))
        elif e == "A":
            draw_bridge_a(cv, p, q, s, pleats=max(1, cnt))
        if i < n - 1:
            knot = lerp(a0, b0, (i + 1) / float(n))
            u = unit(b0, a0)
            nn = (-u[1], u[0])
            r = max(2.6, 0.09 * s)
            d.ellipse([knot[0] - r, knot[1] - r, knot[0] + r, knot[1] + r],
                      fill=(248, 251, 254), outline=(52, 72, 92), width=2)


# ---------------------------------------------------------------- 端帽图形
def draw_terminal_c(cv, base, direction, size, depth=2):
    """冰 C：冰晶尖刺（一根主冰锥 + 两对侧刺，depth 控制侧刺层数）。"""
    d = cv.d
    u = unit((base[0] + direction[0], base[1] + direction[1]), base)
    L = size * 2.10
    w0 = size * 0.30

    def spike(p, dirv, ln, wd, fill, outline):
        nn = (-dirv[1], dirv[0])
        tip = (p[0] + dirv[0] * ln, p[1] + dirv[1] * ln)
        poly = [tip, (p[0] + nn[0] * wd, p[1] + nn[1] * wd), (p[0] - nn[0] * wd, p[1] - nn[1] * wd)]
        d.polygon(poly, fill=fill, outline=outline)
        d.line(poly + [poly[0]], fill=outline, width=2)

    # 侧刺先画（在后面）
    if depth >= 1:
        for i, t in enumerate((0.40, 0.66)):
            p = (base[0] + u[0] * L * t, base[1] + u[1] * L * t)
            for sgn in (1.0, -1.0):
                ang = sgn * 0.95
                ca, sa = math.cos(ang), math.sin(ang)
                dv = (u[0] * ca - u[1] * sa, u[0] * sa + u[1] * ca)
                spike(p, dv, L * (0.42 - 0.10 * i), w0 * 0.55, (222, 234, 250), (76, 98, 136))
    # 主冰锥
    spike(base, u, L, w0, (232, 242, 253), (52, 74, 110))


def draw_terminal_f(cv, base, direction, size, waves=2):
    """焰 F：软四边形飘带（迎风起伏的宽带）。"""
    d = cv.d
    u = unit((base[0] + direction[0], base[1] + direction[1]), base)
    n = (-u[1], u[0])
    steps = 40
    L = size * 2.1
    up, dn = [], []
    for i in range(steps + 1):
        t = i / float(steps)
        p = (base[0] + u[0] * L * t, base[1] + u[1] * L * t)
        w = (0.20 + 0.34 * math.sin(math.pi * min(1.0, t * 1.15))) * size * (1.0 - 0.35 * t)
        wob = math.sin(math.pi * waves * t) * size * 0.26 * t
        up.append((p[0] + n[0] * (w + wob) + u[0] * wob * 0.4,
                   p[1] + n[1] * (w + wob) + u[1] * wob * 0.4))
        dn.append((p[0] - n[0] * (w - wob) + u[0] * wob * 0.4,
                   p[1] - n[1] * (w - wob) + u[1] * wob * 0.4))
    poly = up + list(reversed(dn))
    d.polygon(poly, fill=(252, 232, 208), outline=(166, 96, 44))
    d.line(poly + [poly[0]], fill=(140, 74, 30), width=2)
    # 内焰纹
    mid = [(a[0] * 0.5 + b[0] * 0.5, a[1] * 0.5 + b[1] * 0.5) for a, b in zip(up, dn)]
    d.line([mid[i * 4] for i in range(len(mid) // 4)], fill=(200, 132, 70), width=2, joint="curve")


def draw_terminal_l(cv, base, direction, size, turns=1):
    """电 L：双股螺旋丝（弹簧状细触肢）。"""
    d = cv.d
    u = unit((base[0] + direction[0], base[1] + direction[1]), base)
    n = (-u[1], u[0])
    steps = 160
    L = size * 2.6
    amp = size * 0.30
    for phase in (0.0, math.pi):
        pts = []
        for i in range(steps + 1):
            t = i / float(steps)
            p = (base[0] + u[0] * L * t, base[1] + u[1] * L * t)
            w = amp * math.sin(math.pi * t) ** 0.4
            off = w * math.sin(TAU * (turns + 0.5) * t + phase)
            pts.append((p[0] + n[0] * off, p[1] + n[1] * off))
        d.line(pts, fill=(88, 56, 132), width=3, joint="curve")
        d.line(pts, fill=(176, 150, 216), width=1, joint="curve")


# ---------------------------------------------------------------- 骨架块库
KIND_ZH = {"X": "晶 X 焊核", "W": "流 W 编织腱", "A": "气 A 褶皱膜"}


def library_blocks():
    """读 38 库，返回 [(formula, atoms, edges, family, label)]。"""
    import json
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    forms = json.load(open(os.path.join(here, "t8_forms.json"), encoding="utf-8"))
    out = []
    for idx, f in enumerate(forms):
        atoms = list(f["atoms"])
        edges = [tuple(e) for e in f["edges"]]
        if not atoms:
            continue
        key = S.fam_key([a for a in atoms if a in ("O", "P", "K")]) or "O"
        label = f["formula"] + "|" + str(idx)
        out.append((f["formula"], atoms, edges, key, label))
    return out
