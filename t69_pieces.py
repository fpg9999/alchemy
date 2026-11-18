# -*- coding: utf-8 -*-
"""T69 形状语言：无元素剪影 + 连接件 + 端帽触肢的绘制库。

层次顺序（画图时由 t69_cards 控制）：
  1) 连接件与支臂先画（会被骨架剪影盖住一部分 → 看起来"嵌进"骨架）
  2) 骨架剪影（浅色填充 + 白色隔离晕 + 只留外轮廓）
  3) 焊缝（融合处，贴着剪影内部画）
  4) 端帽触肢 / 铆钉（画在表面）
  5) 徽章与文字标注
"""
import math
import json
import os

from PIL import Image, ImageDraw, ImageFilter, ImageChops

import t68_shapes as S

HERE = os.path.dirname(os.path.abspath(__file__))

INK = (37, 51, 63)
INK2 = (104, 120, 133)
WELD = (44, 62, 80)
SS = 2
GLYPH_SCALE = 1.16
BOND_W = 0.74
STROKE_K = 9

FAM = S.FAMILY
EDGE_NEI = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]


# ------------------------------------------------------------------ 基础
def font(size, bold=False):
    return S.font(size, bold)


def light(col, f):
    return S.lighten(col, f)


def norm(v):
    L = math.hypot(v[0], v[1])
    if L < 1e-9:
        return (0.0, -1.0)
    return (v[0] / L, v[1] / L)


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def mul(a, k):
    return (a[0] * k, a[1] * k)


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def perp(v):
    return (-v[1], v[0])


def rot(v, ang):
    c, s_ = math.cos(ang), math.sin(ang)
    return (v[0] * c - v[1] * s_, v[0] * s_ + v[1] * c)


def centroid(pts):
    if not pts:
        return (0, 0)
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def is_nei(c1, c2):
    return (c2[0] - c1[0], c2[1] - c1[1]) in EDGE_NEI


def text_bg(cv, x, y, s, size=13, bold=False, fill="#22303c",
            bg=(255, 255, 255, 228), pad=(6, 3), anchor="la"):
    f = cv.f(size, bold)
    d = cv.d
    box = d.textbbox((x, y), s, font=f, anchor=anchor)
    x0, y0, x1, y1 = box
    lay = Image.new("RGBA", (cv.W, cv.H), (0, 0, 0, 0))
    dl = ImageDraw.Draw(lay)
    dl.rounded_rectangle([x0 - pad[0], y0 - pad[1], x1 + pad[0], y1 + pad[1]],
                         radius=5, fill=bg)
    cv.img.paste(lay, (0, 0), lay)
    cv.d = ImageDraw.Draw(cv.img)
    cv.d.text((x, y), s, font=f, fill=fill, anchor=anchor)


# ------------------------------------------------------------------ 剪影
class _Mask:
    def __init__(self, W, H):
        self.W, self.H = W, H
        self.img = Image.new("L", (W * SS, H * SS), 0)
        self.d = ImageDraw.Draw(self.img)

    def poly(self, pts):
        self.d.polygon([(p[0] * SS, p[1] * SS) for p in pts], fill=255)

    def capsule(self, p1, p2, w):
        r = max(1.0, w / 2.0)
        d = self.d
        d.line([(p1[0] * SS, p1[1] * SS), (p2[0] * SS, p2[1] * SS)],
               fill=255, width=max(1, int(2 * r * SS)))
        for p in (p1, p2):
            d.ellipse([(p[0] - r) * SS, (p[1] - r) * SS,
                       (p[0] + r) * SS, (p[1] + r) * SS], fill=255)

    def final(self):
        return self.img.resize((self.W, self.H), Image.BILINEAR)


def draw_body(cv, polys, caps, fill, stroke, halo=True):
    """并集剪影：浅填充 + 白色隔离晕 + 外轮廓。"""
    m = _Mask(cv.W, cv.H)
    for pts in polys:
        m.poly(pts)
    for (p1, p2, w) in caps:
        m.capsule(p1, p2, w)
    small = m.final()
    fm = small.point(lambda v: 255 if v >= 108 else 0)
    k = STROKE_K if STROKE_K % 2 else STROKE_K + 1
    dil = fm.filter(ImageFilter.MaxFilter(k))
    band = ImageChops.subtract(dil, fm)
    if halo:
        dil2 = fm.filter(ImageFilter.MaxFilter(k + 8))
        cv.img.paste((255, 255, 255), (0, 0), ImageChops.subtract(dil2, fm))
    cv.img.paste(fill, (0, 0), fm)
    cv.img.paste(stroke, (0, 0), band)
    cv.d = ImageDraw.Draw(cv.img)
    return fm, band


def repaint_strokes(cv, bands):
    for (band, stroke) in bands:
        cv.img.paste(stroke, (0, 0), band)
    cv.d = ImageDraw.Draw(cv.img)


# ------------------------------------------------------------------ 融合贴边
def _seed_segs(pairs, s):
    segs = []
    for a, b in pairs:
        pa = S.center_of(a, s)
        pb = S.center_of(b, s)
        mid = lerp(pa, pb, 0.5)
        t = perp(norm(sub(pb, pa)))
        segs.append((add(mid, mul(t, s * 0.5)), add(mid, mul(t, -s * 0.5))))
    return segs


def _longest_run(segs):
    key = lambda p: (round(p[0], 2), round(p[1], 2))
    n = len(segs)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    ends = [set([key(a), key(b)]) for (a, b) in segs]
    for i in range(n):
        for j in range(i + 1, n):
            if ends[i] & ends[j]:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[ri] = rj
    cnt = {}
    for i in range(n):
        r = find(i)
        cnt[r] = cnt.get(r, 0) + 1
    return max(cnt.values()) if cnt else 0


def flush_shift(cells1, cells2, blocked=None, s=30.0):
    """把 block2 平移成与 block1 至少两条边完整贴合（焊死），位移尽量小。

    返回 (dq, dr, seam_segments_axial)。
    """
    c1 = set(map(tuple, cells1))
    c2 = [tuple(c) for c in cells2]
    blocked = set(map(tuple, blocked)) if blocked else set()
    best = None
    for dq in range(-4, 5):
        for dr in range(-4, 5):
            moved = [(q + dq, r + dr) for (q, r) in c2]
            if set(moved) & c1 or set(moved) & blocked:
                continue
            pairs = [(a, b) for a in c1 for b in moved if is_nei(a, b)]
            if len(pairs) < 2:
                continue
            segs = _seed_segs(pairs, s)
            run = _longest_run(segs)
            if run < 2:
                continue
            cost = math.hypot(dq, dr)
            score = (cost, -run, -len(pairs), abs(dq) + abs(dr))
            if best is None or score < best[0]:
                best = (score, dq, dr, segs)
    if best is None:
        return 0, 0, []
    _, dq, dr, segs = best
    return dq, dr, segs


def draw_weld(cv, segs, s):
    """焊缝：贴合处画粗焊道 + 两侧双线 + 斜刻痕。"""
    d = cv.d
    w = max(3, int(s * 0.115))
    for (a, b) in segs:
        d.line([a, b], fill=WELD, width=w)
        for p in (a, b):
            d.ellipse([p[0] - w / 2.0, p[1] - w / 2.0,
                       p[0] + w / 2.0, p[1] + w / 2.0], fill=WELD)
    for (a, b) in segs:
        n = perp(norm(sub(b, a)))
        for sgn in (-1, 1):
            d.line([add(a, mul(n, sgn * s * 0.075)),
                    add(b, mul(n, sgn * s * 0.075))],
                   fill=WELD, width=max(1, int(s * 0.03)))
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        n_t = max(2, int(L / max(5.0, s * 0.20)))
        for i in range(n_t + 1):
            p = lerp(a, b, i / float(n_t))
            d.line([add(p, mul(n, s * 0.12)), add(p, mul(n, -s * 0.12))],
                   fill=WELD, width=max(1, int(s * 0.028)))


# ------------------------------------------------------------------ 连接件
def draw_x_wedge(cv, ca, cb, s, gap=None):
    """晶 X：最短最粗的三角楔块，尖端深深插入 A 侧骨架，底边顶死 B 侧。"""
    d = cv.d
    u = norm(sub(cb, ca))
    n = perp(u)
    L = math.hypot(cb[0] - ca[0], cb[1] - ca[1])
    L = gap if gap else L
    L = max(L, s * 1.0)
    apex = add(ca, mul(u, -0.50 * s))            # 深插进 A 骨架
    base = add(cb, mul(u, 0.55 * s))             # 越过 B 侧接触原子
    half = max(0.30 * L, 0.52 * s)
    tri = [apex, add(base, mul(n, half)), add(base, mul(n, -half))]
    d.polygon(tri, fill=(225, 231, 236), outline=WELD)
    d.line([tri[0], tri[1]], fill=WELD, width=max(2, int(s * 0.10)))
    d.line([tri[0], tri[2]], fill=WELD, width=max(2, int(s * 0.10)))
    d.line([tri[1], tri[2]], fill=WELD, width=max(4, int(s * 0.14)))
    # 三角块内三条肋（沿 apex→底边）
    for f in (0.38, 0.62, 0.86):
        p = lerp(apex, lerp(tri[1], tri[2], 0.5), f)
        d.line([p, lerp(tri[1], tri[2], f)], fill=(150, 163, 174),
               width=max(1, int(s * 0.03)))
    # B 侧焊板
    bc = add(cb, mul(u, 0.18 * s))
    plate = [add(add(bc, mul(n, half * 1.02)), mul(u, s * 0.20)),
             add(add(bc, mul(n, -half * 1.02)), mul(u, s * 0.20)),
             add(add(bc, mul(n, -half * 1.02)), mul(u, -s * 0.14)),
             add(add(bc, mul(n, half * 1.02)), mul(u, -s * 0.14))]
    d.polygon(plate, fill=(206, 214, 221), outline=WELD)
    for i in range(3):
        t = (i + 1) / 4.0
        d.line([lerp(plate[0], plate[3], t), lerp(plate[1], plate[2], t)],
               fill=WELD, width=max(1, int(s * 0.028)))


def draw_w_tendon(cv, ca, cb, s, gap=None):
    """流 W：可拉伸肌腱——两端窄、中间鼓，带张力纤维。"""
    d = cv.d
    u = norm(sub(cb, ca))
    n = perp(u)
    L = math.hypot(cb[0] - ca[0], cb[1] - ca[1])
    L = max(gap if gap else L, s * 1.1)
    start = add(ca, mul(u, -0.30 * s))
    end = add(cb, mul(u, 0.30 * s))
    span = math.hypot(end[0] - start[0], end[1] - start[1])
    up, dn = [], []
    steps = 18
    for i in range(steps + 1):
        t = i / float(steps)
        p = lerp(start, end, t)
        w = max(0.10 * span, 0.22 * s) * (0.45 + 0.55 * math.sin(math.pi * t))
        up.append(add(p, mul(n, w)))
        dn.append(add(p, mul(n, -w)))
    poly = up + list(reversed(dn))
    d.polygon(poly, fill=(226, 240, 249), outline=(33, 82, 122))
    d.line(poly + [poly[0]], fill=(33, 82, 122), width=max(2, int(s * 0.085)))
    for k in (-0.45, 0.0, 0.45):
        p1 = add(add(start, mul(u, 0.16 * span)), mul(n, 0.10 * span * k))
        p2 = add(add(end, mul(u, -0.16 * span)), mul(n, 0.10 * span * k))
        mid = add(lerp(p1, p2, 0.5), mul(n, 0.07 * span))
        d.line([p1, mid, p2], fill=(112, 154, 184), width=max(1, int(s * 0.028)))


def draw_a_membrane(cv, ca, cb, s, gap=None):
    """气 A：长条薄膜横置，长边贴着两侧骨架。"""
    d = cv.d
    u = norm(sub(cb, ca))
    n = perp(u)
    L = math.hypot(cb[0] - ca[0], cb[1] - ca[1])
    L = max(gap if gap else L, s * 1.0)
    mid = lerp(ca, cb, 0.5)
    hl = max(0.62 * L, 1.25 * s)
    ht = max(0.30 * L, 0.45 * s)
    rect = [add(add(mid, mul(n, hl)), mul(u, ht)),
            add(add(mid, mul(n, -hl)), mul(u, ht)),
            add(add(mid, mul(n, -hl)), mul(u, -ht)),
            add(add(mid, mul(n, hl)), mul(u, -ht))]
    d.polygon(rect, fill=(226, 244, 238), outline=(20, 112, 96))
    d.line(rect + [rect[0]], fill=(20, 112, 96), width=max(2, int(s * 0.08)))
    for f in (-0.36, 0.36):
        d.line([add(add(mid, mul(n, hl)), mul(u, ht * f)),
                add(add(mid, mul(n, -hl)), mul(u, ht * f))],
               fill=(116, 176, 160), width=max(1, int(s * 0.03)))


def draw_link(cv, ca, cb, elems, s):
    """多元素桥组合规则：沿 A→B 轴按原子数切槽，同元素相邻槽合并；
    楔块负责两端（端部楔块最粗，把骨架焊死），腱与膜负责中段。"""
    if not elems:
        return
    u = norm(sub(cb, ca))
    n = perp(u)
    L = math.hypot(cb[0] - ca[0], cb[1] - ca[1])
    L = max(L, s * 1.0)
    groups = []
    for e in elems:
        if groups and groups[-1][0] == e:
            groups[-1][1] += 1
        else:
            groups.append([e, 1])
    total = float(sum(g[1] for g in groups))
    t0 = 0.0
    for gi, (e, cnt) in enumerate(groups):
        f0 = t0 / total
        f1 = (t0 + cnt) / total
        t0 += cnt
        p0 = add(ca, mul(u, L * f0))
        p1 = add(ca, mul(u, L * f1))
        gap = L * (f1 - f0)
        first, last = (gi == 0), (gi == len(groups) - 1)
        if e == "X":
            draw_x_wedge(cv, p0, p1, s, gap=max(gap, 0.9 * s))
        elif e == "W":
            draw_w_tendon(cv, p0, p1, s, gap=gap)
        else:
            draw_a_membrane(cv, p0, p1, s, gap=gap)


# ------------------------------------------------------------------ 端帽触肢
def draw_terminal(cv, base, direction, el, s, idx=0):
    """冰 C：尖三角触肢；焰 F：四边形软触肢；电 L：细长椭圆软触肢。"""
    d = cv.d
    u = norm(direction)
    n = perp(u)
    if el == "C":
        ln = s * (1.35 + 0.16 * (idx % 2))
        half = s * 0.36
        tip = add(base, mul(u, ln))
        if idx % 2 == 0:      # 正三角（宽底在外）
            tri = [add(base, mul(n, half)), add(base, mul(n, -half)),
                   add(tip, mul(n, half * 0.35))]
        else:                 # 倒三角（宽底在内，尖端在外）
            mid = add(base, mul(u, ln * 0.40))
            tri = [add(mid, mul(n, half)), add(mid, mul(n, -half)), tip]
        d.polygon(tri, fill=(231, 239, 246), outline=(34, 62, 90))
        d.line(tri + [tri[0]], fill=(34, 62, 90), width=max(2, int(s * 0.075)))
        d.line([lerp(tri[0], tri[2], 0.45), lerp(tri[1], tri[2], 0.45)],
               fill=(126, 148, 168), width=max(1, int(s * 0.028)))
    elif el == "F":
        ln = s * 1.45
        curve = mul(n, s * 0.26 * (1 if idx % 2 else -1))
        up, dn = [], []
        steps = 12
        for i in range(steps + 1):
            t = i / float(steps)
            p = add(add(base, mul(u, ln * t)), mul(curve, t * t * 0.9))
            w = s * (0.42 * (1 - t) ** 0.65 + 0.05)
            up.append(add(p, mul(n, w)))
            dn.append(add(p, mul(n, -w)))
        poly = up + list(reversed(dn))
        d.polygon(poly, fill=(246, 236, 231), outline=(118, 62, 44))
        d.line(poly + [poly[0]], fill=(118, 62, 44), width=max(2, int(s * 0.07)))
        d.line([add(base, mul(u, s * 0.12)),
                add(add(base, mul(u, ln * 0.92)), mul(curve, 0.7))],
               fill=(160, 96, 76), width=max(1, int(s * 0.028)))
    else:  # L 电
        ln = s * 1.75
        half = s * 0.18
        start = add(base, mul(u, s * 0.10))
        tip = add(base, mul(u, ln))
        poly = []
        steps = 14
        for i in range(steps + 1):
            t = i / float(steps)
            p = lerp(start, tip, t)
            w = half * (0.55 + 0.45 * math.sin(math.pi * t))
            poly.append(add(p, mul(n, w)))
        for i in range(steps, -1, -1):
            t = i / float(steps)
            p = lerp(start, tip, t)
            w = half * (0.55 + 0.45 * math.sin(math.pi * t))
            poly.append(add(p, mul(n, -w)))
        d.polygon(poly, fill=(252, 243, 231), outline=(140, 90, 40))
        d.line(poly + [poly[0]], fill=(140, 90, 40), width=max(2, int(s * 0.06)))
        d.line([add(start, mul(u, s * 0.06)), add(tip, mul(u, -s * 0.16))],
               fill=(190, 140, 86), width=max(1, int(s * 0.028)))


def draw_rivet(cv, p, s):
    """骨架内桥：铆钉 / 焊点。"""
    d = cv.d
    r = max(2.0, s * 0.17)
    d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r],
              fill=(232, 237, 241), outline=WELD, width=max(1, int(s * 0.045)))
    d.line([(p[0] - r * 0.62, p[1]), (p[0] + r * 0.62, p[1])], fill=WELD,
           width=max(1, int(s * 0.035)))
    d.line([(p[0], p[1] - r * 0.62), (p[0], p[1] + r * 0.62)], fill=WELD,
           width=max(1, int(s * 0.035)))


def draw_arm(cv, pts, elems, s):
    """支臂：从骨架伸出的二价触须（管状），按元素给纹理。"""
    d = cv.d
    if len(pts) < 2:
        return
    elems = list(elems or ["W"] * (len(pts) - 1))
    n = len(pts) - 1
    for i in range(n):
        e = elems[min(i, len(elems) - 1)]
        w = s * (0.30 - 0.05 * i)
        col = {"X": (222, 228, 234), "W": (230, 242, 249),
               "A": (232, 247, 242)}.get(e, (235, 240, 243))
        d.line([pts[i], pts[i + 1]], fill=col, width=max(3, int(w * 2)))
        d.line([pts[i], pts[i + 1]], fill=(70, 88, 104),
               width=max(1, int(w * 0.16)))
    for i in range(n):
        e = elems[min(i, len(elems) - 1)]
        a, b = pts[i], pts[i + 1]
        u = norm(sub(b, a))
        t = perp(u)
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if e == "X":
            for f in (0.28, 0.56, 0.84):
                p = lerp(a, b, f)
                d.line([add(p, mul(t, s * 0.13)), add(p, mul(t, -s * 0.13))],
                       fill=(96, 110, 124), width=max(1, int(s * 0.026)))
        elif e == "W":
            prev = None
            for j in range(7):
                f = j / 6.0
                p = add(lerp(a, b, f),
                        mul(t, s * 0.055 * math.sin(f * math.pi * 2)))
                if prev:
                    d.line([prev, p], fill=(96, 140, 170),
                           width=max(1, int(s * 0.024)))
                prev = p
        else:
            p = add(lerp(a, b, 0.5), mul(t, s * 0.06))
            d.line([p, add(p, mul(u, s * 0.12))], fill=(96, 150, 130),
                   width=max(1, int(s * 0.026)))


# ------------------------------------------------------------------ 标注
def badge(cv, p, text, r=14, fill="#ffffff", ink=INK, size=13):
    d = cv.d
    d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r],
              fill=fill, outline=ink, width=2)
    d.text(p, text, font=font(size, True), fill=ink, anchor="mm")


def elem_comp(atoms):
    order = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]
    zh = S.CN
    cnt = {}
    for a in atoms:
        cnt[a] = cnt.get(a, 0) + 1
    out = []
    for e in order:
        if cnt.get(e):
            n = cnt[e]
            out.append("%s%s%s" % (zh.get(e, e), e, "" if n == 1 else "×%d" % n))
    return " ".join(out)


def short_comp(atoms):
    order = ["O", "X", "C", "P", "W", "L", "K", "A", "F"]
    cnt = {}
    for a in atoms:
        cnt[a] = cnt.get(a, 0) + 1
    out = ""
    for e in order:
        if cnt.get(e):
            n = cnt[e]
            out += e + ("" if n == 1 else str(n))
    return out


def load_data():
    with open(os.path.join(HERE, "t68_data.json"), encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------------------------------------------ 焊口（骨架长出的焊嘴）
BOSS_H = {"X": 0.50, "W": 0.80, "A": 1.15}


def boss_h(elems):
    """连接件两侧焊口之间预留的半间隙（单位 s）。"""
    if len(elems) == 1:
        return BOSS_H.get(elems[0], 0.7)
    return 0.42 + 0.26 * len(elems)


def boss_geom(p_atom, p_partner, s, h):
    """返回 (tip 点, 是否有效)。tip 从原子中心朝对方伸出，止于半间隙处。"""
    u = norm(sub(p_partner, p_atom))
    D = math.hypot(p_partner[0] - p_atom[0], p_partner[1] - p_atom[1])
    tip_len = D * 0.5 - h * s
    return add(p_atom, mul(u, max(tip_len, 0.0))), tip_len


def boss_poly(p_atom, p_partner, s, h):
    """焊口多边形（从骨架原子向外伸出的梯形焊嘴）；太短则返回 None。"""
    u = norm(sub(p_partner, p_atom))
    D = math.hypot(p_partner[0] - p_atom[0], p_partner[1] - p_atom[1])
    tip_len = D * 0.5 - h * s
    if tip_len < 0.22 * s:
        return None
    n = perp(u)
    base_h = 1.02 * s
    tip_h = 0.62 * s
    tip = add(p_atom, mul(u, tip_len))
    p0 = add(p_atom, mul(n, base_h))
    p1 = add(p_atom, mul(n, -base_h))
    t0 = add(tip, mul(n, tip_h))
    t1 = add(tip, mul(n, -tip_h))
    return [p0, t0, t1, p1]
