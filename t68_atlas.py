# -*- coding: utf-8 -*-
"""t68_atlas.py —— T68 形状语言图鉴页

输出：
  images/t68_glyphs.png      元素字形 / 键型 / 0 级键 / 角色样式 说明页
  images/t68_families.png    7 种骨架家族容器 + 真实 6 级块示例
  images/t68_library38.png   38 形态库（level-6 骨架块）全图鉴
  images/t68_connect.png     连接语法：融合 / S 焊桥 / C 铰接桥 / L 浮空桥 / 支臂 / 端帽
"""
import json
import math
import os

import pot_all as P
import t68_shapes as S

BASE = S.BASE
OUT = os.path.join(BASE, "images")


def load_forms():
    with open(os.path.join(BASE, "t8_forms.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def edge_type(place, i, j):
    dq = place[j][0] - place[i][0]
    dr = place[j][1] - place[i][1]
    return P.classify_offset((dq, dr))


def form_place(f):
    pl = f["place"]
    n = len(f["atoms"])
    if isinstance(pl, dict):
        out = []
        for i in range(n):
            if i in pl:
                out.append(tuple(pl[i]))
            else:
                out.append(tuple(pl[str(i)]))
        return out
    return [tuple(p) for p in pl]


def draw_form(cv, box, form, letters=True, max_s=None, container=True,
              label_size=0, drawn=None):
    """画一个 38 库形态（atoms+edges+place），返回 (s, pos)。"""
    atoms = form["atoms"]
    place = form_place(form)
    edges = form["edges"]
    s, ox, oy = S.fit_layout(place, box, margin=1.25)
    if max_s:
        s = min(s, max_s)
    pos = []
    for (q, r) in place:
        x, y = S.center_of((q, r), s)
        pos.append((x + ox, y + oy))
    key, tint = S.fam_tint(atoms)
    d = cv.d
    if container:
        hull = S.pad_hull(pos, max(2.2, 0.62 * s))
        d.polygon(hull, fill=S.lighten(tint, 0.84), outline=tint,
                  width=max(1, int(s * 0.06)))
    kk = max(1, sum(1 for a in atoms if a == "K"))
    polys = [S.atom_poly(el, pos[i][0], pos[i][1], s, kk)
             for i, el in enumerate(atoms)]
    # 键：多重度用平行线，类型决定颜色
    for (i, j, m) in edges:
        t = edge_type(place, i, j)
        col = S.BONDC.get(t, "#7f8c8d")
        p1 = S.ray_exit(polys[i], pos[i], pos[j])
        p2 = S.ray_exit(polys[j], pos[j], pos[i])
        if p1 is None or p2 is None:
            continue
        w = max(1, int(s * 0.10))
        if t == "L":
            for k in range(m):
                off = (k - (m - 1) / 2) * max(2.0, s * 0.14)
                a, b = S.offset_line(p1, p2, off)
                S.dashed(d, a, b, col, w, max(4, int(s * 0.22)),
                         max(3, int(s * 0.16)))
            mid = ((place[i][0] + place[j][0]) / 2.0,
                   (place[i][1] + place[j][1]) / 2.0)
            mx, my = S.center_of(mid, s)
            S.dashed_poly(d, S.hex_pts(mx + ox, my + oy, s), "#b3b3b3", 1, 4, 4)
        else:
            for k in range(m):
                off = (k - (m - 1) / 2) * max(2.2, s * 0.16)
                a, b = S.offset_line(p1, p2, off)
                d.line([a, b], fill=col, width=w)
    for i, el in enumerate(atoms):
        S.draw_atom(d, el, polys[i], pos[i][0], pos[i][1], s, "skel", kk)
    if drawn is not None:
        drawn.update({"s": s, "pos": pos, "tint": tint, "key": key})
    return s, pos


# ------------------------------------------------------------------ 字形页
def page_glyphs():
    W, H = 1600, 900
    cv = S.Canvas(W, H)
    d = cv.d
    cv.txt(40, 24, "T68 形状语言 · 元素字形与键型", 36, True, "#1c2833")
    cv.txt(40, 70, "三价元素（骨架层）用「三角形 / 圆形 / 正方形或多角形」；"
           "二价（连接层）与一价（终端层）用不同六边形 / 小点。", 15, False,
           "#566573")
    d.line([(40, 98), (W - 40, 98)], fill="#bdc3c7", width=2)

    # A. 9 元素字形
    y0 = 112
    cv.txt(40, y0, "A. 九元素字形（价数 = 该原子最多成键数）", 20, True,
           "#1c2833")
    info = {
        "O": ("秩", 3, "骨架", "三角形：最锐利，代表秩序与几何"),
        "P": ("势", 3, "骨架", "圆形：最饱满，代表势与能量"),
        "K": ("散", 3, "骨架", "正方形起，角数=3+骨架内K数（更多角）"),
        "X": ("晶", 2, "连接", "尖六边形：刚性，S 短键为主"),
        "W": ("流", 2, "连接", "圆角六边形：铰接，C 角键为主"),
        "A": ("气", 2, "连接", "虚线六边形：软连接，L 长键为主"),
        "C": ("冰", 1, "终端", "小菱形：冷端帽"),
        "L": ("电", 1, "终端", "小圆点：电荷端帽"),
        "F": ("焰", 1, "终端", "小三角形：火端帽"),
    }
    cellw = (W - 80) / 9
    for i, el in enumerate(S.ORDER):
        cx = 40 + cellw * (i + 0.5)
        zh, val, role, desc = info[el]
        kk = {"O": 1, "P": 1, "K": 2}.get(el, 1)
        poly = S.atom_poly(el, cx, y0 + 86, 54, kk)
        S.draw_atom(d, el, poly, cx, y0 + 86, 54, "skel", kk)
        cv.txt(cx, y0 + 146, "%s %s" % (zh, el), 18, True, "#1c2833", "ma")
        cv.txt(cx, y0 + 170, "%d 价 · %s层" % (val, role), 12, False,
               "#566573", "ma")
        for k, line in enumerate(cv.wrap(desc, cellw - 34, 10, False)[:2]):
            cv.txt(cx, y0 + 190 + k * 14, line, 10, False, "#95a5a6", "ma")
        if el == "K":
            cv.txt(cx, y0 + 224, "图中 K 数=2 → 五边形", 10, True, "#c0392b",
                   "ma")

    # B. 键型
    y1 = 400
    cv.txt(40, y1, "B. 键型（S 短键 / C 角键 / L 长键；每对元素最多 3 根平行键）",
           20, True, "#1c2833")
    specs = [("S", 1, "共享边：刚性最短，聚素"), ("S", 2, "双键"),
             ("S", 3, "三键"), ("C", 1, "共享顶点：可转动的角键"),
             ("C", 2, "双键"), ("L", 1, "隔一格：长键 + 中点空格"),
             ("L", 2, "双键")]
    bx = 60
    for t, m, note in specs:
        w = 200
        pa = (bx + 56, y1 + 84)
        pb = (bx + 56 + 100, y1 + 84)
        ga = S.atom_poly("P", pa[0], pa[1], 28, 1)
        gb = S.atom_poly("P", pb[0], pb[1], 28, 1)
        for g, p in ((ga, pa), (gb, pb)):
            d.polygon(g, fill=S.lighten(S.ELEMCOL["P"], 0.35),
                      outline="#1c2833", width=2)
            S.text_center(d, p[0], p[1], "P", 14, "#111")
        col = S.BONDC[t]
        p1 = S.ray_exit(ga, pa, pb)
        p2 = S.ray_exit(gb, pb, pa)
        if t == "L":
            for k in range(m):
                off = (k - (m - 1) / 2) * 5
                a, b = S.offset_line(p1, p2, off)
                S.dashed(d, a, b, col, 3, 6, 5)
            mid = ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)
            S.dashed_poly(d, S.hex_pts(mid[0], mid[1], 24), "#b3b3b3", 1, 4, 4)
        else:
            for k in range(m):
                off = (k - (m - 1) / 2) * 5
                a, b = S.offset_line(p1, p2, off)
                d.line([a, b], fill=col, width=3)
        cv.txt(bx, y1 + 124, "%s ×%d 键" % (S.BONDZH[t], m), 15, True, col)
        for k, line in enumerate(cv.wrap(note, 185, 10, False)[:2]):
            cv.txt(bx, y1 + 146 + k * 13, line, 10, False, "#5d6d7e")
        bx += w

    # C. 0 级同类键 = 焊接
    y2 = 580
    cv.txt(40, y2, "C. 0 级同类键 = 焊接（同一元素的三价原子之间才可能出现）",
           20, True, "#1c2833")
    pa = (150, y2 + 100)
    pb = (330, y2 + 100)
    ga = S.atom_poly("P", pa[0], pa[1], 30, 1)
    gb = S.atom_poly("P", pb[0], pb[1], 30, 1)
    for g, p in ((ga, pa), (gb, pb)):
        d.polygon(g, fill=S.lighten(S.ELEMCOL["P"], 0.35), outline="#1c2833",
                  width=2)
        S.text_center(d, p[0], p[1], "P", 15, "#111")
    p1 = S.ray_exit(ga, pa, pb)
    p2 = S.ray_exit(gb, pb, pa)
    for a, b in (S.offset_line(p1, p2, -3), S.offset_line(p1, p2, 3)):
        d.line([a, b], fill="#34495e", width=4)
    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    d.line([(mx, my - 15), (mx, my + 15)], fill="#e67e22", width=3)
    cv.txt(mx + 16, my - 28, "焊刻痕（橙）", 12, True, "#d35400")
    desc_c = ("两个 6 级骨架块之间若出现同类三价键（0 级），即判定为融合："
              "图形上把两块轮廓用深色双线焊条 + 橙色刻痕连接，并在图中标「融合」。")
    for k, line in enumerate(cv.wrap(desc_c, 720, 12, False)):
        cv.txt(40, y2 + 160 + k * 18, line, 12, False, "#566573")

    # D. 角色样式
    rx = 840
    cv.txt(rx, y2, "D. 原子在分子图里的角色样式", 20, True, "#1c2833")
    samples = [("skel", "P", "骨架原子：高饱和 + 深描边"),
               ("bridge", "X", "桥原子：二价连接层，中饱和"),
               ("intra", "X", "骨架内桥：同骨架两原子间的二价焊点"),
               ("arm", "W", "支臂原子：骨架伸出的二价链段"),
               ("mono", "C", "一价端帽：小字形 + 浅色"),
               ("free", "A", "游离装饰：最浅，只作陪衬")]
    yy = y2 + 36
    for role, el, txt in samples:
        poly = S.atom_poly(el, rx + 26, yy + 17, 21, 1)
        S.draw_atom(d, el, poly, rx + 26, yy + 17, 21, role, 1)
        cv.txt(rx + 58, yy + 7, txt, 13, False, "#566573")
        yy += 36
    cv.save(os.path.join(OUT, "t68_glyphs.png"))


# ------------------------------------------------------------------ 家族页
def page_families():
    forms = load_forms()
    W, H = 1600, 1080
    cv = S.Canvas(W, H)
    d = cv.d
    cv.txt(40, 26, "T68 形状语言 · 骨架家族的 7 种外形容器", 36, True, "#1c2833")
    cv.txt(40, 72, "按骨架里出现的三价元素集合决定外形；颜色为该家族专属色。"
           "容器只是轮廓，骨架内部的原子字形（△○■）与键型仍然给出唯一形态。",
           15, False, "#566573")
    d.line([(40, 100), (W - 40, 100)], fill="#bdc3c7", width=2)
    groups = [("O", "纯秩", "只含 O：三角形"),
              ("P", "纯势", "只含 P：圆形"),
              ("K", "纯散", "只含 K：3+K数 边形"),
              ("OP", "秩势", "O+P：拱形（三角 ∪ 圆）"),
              ("OK", "秩散", "O+K：盾形（三角 ∪ 方）"),
              ("PK", "势散", "P+K：圆角方（方圆超椭圆）"),
              ("OPK", "秩势散", "O+P+K：六边形（最复杂的一类）")]
    y = 120
    for key, zh, desc in groups:
        fam = S.FAMILY[key]
        col = fam["col"]
        d.rounded_rectangle([40, y, W - 40, y + 122], radius=12,
                            fill=S.lighten(col, 0.93), outline=S.lighten(col, 0.5),
                            width=1)
        poly = S.fam_shape(key, 120, y + 61, 46, 46, 2)
        d.polygon(poly, fill=S.lighten(col, 0.72), outline=col, width=3)
        cv.txt(190, y + 18, "家族 %s（%s）" % (zh, key), 19, True, S.lighten(
            col, 0.25) if col != "#2c3e50" else "#2c3e50")
        cv.txt(190, y + 46, desc, 13, False, "#566573")
        ex = [f for f in forms if S.fam_key(f["atoms"]) == key]
        cv.txt(190, y + 72, "38 库内含 %d 个形态：%s" % (
            len(ex), "、".join(f["formula"] for f in ex[:12]) +
            ("…" if len(ex) > 12 else "")), 11, False, "#7f8c8d")
        # 两个真实例子
        for j, f in enumerate(ex[:2]):
            box = (760 + j * 400, y + 4, 330, 100)
            draw_form(cv, box, f, max_s=28, label_size=0)
            cv.txt(760 + j * 400 + 165, y + 110, "例：#%d %s" % (
                forms.index(f) + 1, f["formula"]), 11, False, "#566573", "ma")
        y += 132
    cv.save(os.path.join(OUT, "t68_families.png"))


# ------------------------------------------------------------------ 38 库图鉴
def _formula_w(d, text, size):
    f = S.font(size, True)
    w = 0.0
    for ch in text:
        w += f.getlength(ch) * (0.64 if ch.isdigit() else 1.0)
    return w


def page_library():
    forms = load_forms()
    cols, rows = 8, 5
    cellw, cellh = 198, 224
    W = 40 * 2 + cols * cellw
    H = 120 + rows * cellh + 60
    cv = S.Canvas(W, H)
    d = cv.d
    cv.txt(40, 26, "T68 形态图鉴 · 38 个 level-6 骨架块（每种形态一种图形）",
           34, True, "#1c2833")
    cv.txt(40, 70, "全部 36 个大分子的骨架块都落在这 38 个形态内（已验证：库外块 0）。"
           "编号 #1–#38 为 38 库序号；外框颜色 = 家族色。", 14, False, "#566573")
    d.line([(40, 100), (W - 40, 100)], fill="#bdc3c7", width=2)
    for i, f in enumerate(forms):
        r, c = divmod(i, cols)
        x0 = 40 + c * cellw
        y0 = 118 + r * cellh
        key, tint = S.fam_tint(f["atoms"])
        d.rectangle([x0, y0, x0 + cellw - 8, y0 + cellh - 8],
                    fill="#ffffff", outline=S.lighten(tint, 0.55), width=2)
        box = (x0 + 12, y0 + 24, cellw - 36, 112)
        draw_form(cv, box, f, max_s=22)
        cv.txt(x0 + 10, y0 + 6, "#%d" % (i + 1), 14, True,
               S.lighten(tint, 0.2) if tint != "#2c3e50" else "#2c3e50")
        fw = _formula_w(d, f["formula"], 16)
        S.draw_formula(d, x0 + cellw - 22 - fw, y0 + 12, f["formula"], 16,
                       "#1c2833", True, center=False)
        # 家族小图标
        S_raw = None
        poly = S.fam_shape(key, x0 + cellw - 26, y0 + 158, 12, 12, 2)
        d.polygon(poly, fill=S.lighten(tint, 0.70), outline=tint, width=2)
        cv.txt(x0 + 10, y0 + 150, "%s 家族 · %d 原子" % (
            S.FAMILY[key]["zh"], len(f["atoms"])), 11, False, "#7f8c8d")
        cv.txt(x0 + 10, y0 + 168, "键 %d 根" % len(f["edges"]), 11, False,
               "#7f8c8d")
        cv.txt(x0 + 10, y0 + 186, "类型 %s" % "+".join(
            sorted(set(edge_type(form_place(f), e0, e1)
                       for (e0, e1, m) in f["edges"]))), 11, False, "#7f8c8d")
    cv.save(os.path.join(OUT, "t68_library38.png"))


# ------------------------------------------------------------------ 连接语法页
def page_connect():
    W, H = 1600, 1300
    cv = S.Canvas(W, H)
    d = cv.d
    cv.txt(40, 26, "T68 形状语言 · 骨架之间怎么连", 36, True, "#1c2833")
    cv.txt(40, 72, "两个骨架块之间：(1) 若出现 0 级同类三价键 → 融合焊接；"
           "(2) 否则经二价连接层成桥：S 短键=刚性焊条，C 角键=可转关节，"
           "L 长键=浮空软链；桥原子本身还可以再挂一价端帽/支臂。", 15, False,
           "#566573")
    d.line([(40, 108), (W - 40, 108)], fill="#bdc3c7", width=2)

    def two_blocks(bx, by, s=26, key1="OP", key2="PK"):
        """用两个家族容器示意图表示两个骨架。"""
        c1 = (bx + 120, by + 110)
        c2 = (bx + 360, by + 110)
        for c, key in ((c1, key1), (c2, key2)):
            col = S.FAMILY[key]["col"]
            poly = S.fam_shape(key, c[0], c[1], 86, 62, 2)
            d.polygon(poly, fill=S.lighten(col, 0.85), outline=col, width=3)
        return c1, c2

    # 1 融合
    cv.txt(40, 130, "1. 融合（0 级同类三价键）", 20, True, "#1c2833")
    c1, c2 = two_blocks(180, 150)
    x1, y1 = c1
    x2, y2 = c2
    pa = (x1 + 60, y1 + 6)
    pb = (x2 - 62, y2 + 6)
    ga = S.atom_poly("P", pa[0], pa[1], 26, 1)
    gb = S.atom_poly("P", pb[0], pb[1], 26, 1)
    for g, p in ((ga, pa), (gb, pb)):
        d.polygon(g, fill=S.lighten(S.ELEMCOL["P"], 0.35), outline="#1c2833",
                  width=2)
        S.text_center(d, p[0], p[1], "P", 13, "#111")
    p1 = S.ray_exit(ga, pa, pb)
    p2 = S.ray_exit(gb, pb, pa)
    for a, b in (S.offset_line(p1, p2, -3), S.offset_line(p1, p2, 3)):
        d.line([a, b], fill="#34495e", width=4)
    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    d.line([(mx, my - 15), (mx, my + 15)], fill="#e67e22", width=3)
    cv.txt(mx + 16, my - 8, "融合", 13, True, "#d35400")
    cv.txt(40, 344, "两个 6 级块之间出现同类三价键（0 级）。图形上把两个容器轮廓看成"
           "「焊在一起」，双线焊条 + 橙色刻痕即融合标记。", 12, False, "#566573")
    cv.txt(40, 366, "实例：G13 的骨架② = OP4K ⊕ OP4K（1 根 P–P 0 级键）→ O2P8K2。",
           12, True, "#5d6d7e")

    # 2 S / C / L 桥
    cv.txt(40, 408, "2. 二价桥的三种键型（桥原子 X/W/A 决定）", 20, True,
           "#1c2833")
    rows = [("S 短键 → 刚性焊桥", "X 晶", "焊板：骨架上贴小方板，桥身短而直，两骨架相对固定"),
            ("C 角键 → 铰接桥", "W 流", "关节：桥原子外套圆环，可绕骨架转动/折叠"),
            ("L 长键 → 浮空软桥", "A 气", "软链：虚线 + 中点空格六边形，两骨架隔空相连")]
    yy = 432
    for i, (title, note1, note2) in enumerate(rows):
        t = "SCL"[i]
        col = S.BONDC[t]
        c1, c2 = two_blocks(180 + 0, yy, key1="OP", key2="OPK")
        # 用桥原子连两个容器
        bx = (c1[0] + c2[0]) / 2
        by = yy + 110
        el = {"S": "X", "C": "W", "L": "A"}[t]
        poly = S.atom_poly(el, bx, by, 30, 1)
        d.polygon(poly, fill=S.lighten(S.ELEMCOL[el], 0.45), outline="#1c2833",
                  width=2)
        S.text_center(d, bx, by, el, 14, "#111")
        # 两条键：bridge → 两骨架
        for cx, cy in (c1, c2):
            ex = S.ray_exit(poly, (bx, by), (cx, cy))
            if i == 2:
                S.dashed(d, (bx, by), (cx, cy), col, 3, 6, 5)
                S.dashed_poly(d, S.hex_pts((bx + cx) / 2, (by + cy) / 2, 20),
                              "#b3b3b3", 1, 4, 4)
            else:
                d.line([(bx, by), (cx, cy)], fill=col, width=3)
        if t == "S":
            for (cx, cy) in (c1, c2):
                S_plate(d, bx, by, cx, cy, 28)
        if t == "C":
            d.ellipse([bx - 22, by - 22, bx + 22, by + 22], outline=col, width=3)
        cv.txt(700, yy + 40, title, 19, True, col)
        cv.txt(700, yy + 70, "桥原子：%s" % note1, 13, True, "#5d6d7e")
        for k, line in enumerate(cv.wrap(note2, 420, 12, False)):
            cv.txt(700, yy + 92 + k * 18, line, 12, False, "#566573")
        # 实例计数
        cv.txt(700, yy + 150, {"S": "36 个分子中 S 焊桥 9 条",
                               "C": "C 铰接桥 45 条",
                               "L": "L 浮空桥 4 条"}[t], 12, False, "#95a5a6")
        yy += 200

    # 3 支臂 / 端帽 / 骨架内桥
    cv.txt(40, yy + 14, "3. 骨架上的装饰：支臂、端帽、骨架内桥", 20, True,
           "#1c2833")
    bx, by = 300, yy + 128
    poly = S.fam_shape("OP", bx, by, 105, 74, 2)
    d.polygon(poly, fill=S.lighten(S.FAMILY["OP"]["col"], 0.86),
              outline=S.FAMILY["OP"]["col"], width=3)
    # 支臂：骨架原子 → W → C 端帽
    ax, ay = bx + 100, by - 30
    cx2, cy2 = ax + 60, ay - 34
    S.text_center(d, ax, ay, "W", 13, "#111")
    d.ellipse([ax - 20, ay - 20, ax + 20, ay + 20],
              fill=S.lighten(S.ELEMCOL["W"], 0.45), outline="#1c2833", width=2)
    S.text_center(d, ax, ay, "W", 13, "#111")
    d.line([(bx + 70, by - 20), (ax - 16, ay + 8)], fill="#95a5a6", width=3)
    d.line([(ax + 8, ay - 16), (cx2 - 10, cy2 + 6)], fill="#95a5a6", width=3)
    d.ellipse([cx2 - 15, cy2 - 15, cx2 + 15, cy2 + 15],
              fill=S.lighten(S.ELEMCOL["C"], 0.4), outline="#7f8c8d", width=2)
    S.text_center(d, cx2, cy2, "C", 11, "#111")
    cv.txt(cx2 + 30, cy2 - 8, "端帽", 13, True, "#5d6d7e")
    cv.txt(ax - 20, ay - 46, "支臂", 13, True, "#5d6d7e")
    # 骨架内桥：骨架内两个原子间一个 X（画在容器里）
    ix, iy = bx - 30, by + 20
    d.ellipse([ix - 20, iy - 20, ix + 20, iy + 20],
              fill=S.lighten(S.ELEMCOL["X"], 0.5), outline="#1c2833", width=2)
    S.text_center(d, ix, iy, "X", 13, "#111")
    cv.txt(ix + 26, iy + 4, "骨架内桥（加固）", 12, False, "#5d6d7e")
    # 端帽双键（鳍/刺）
    cv.txt(700, yy + 90,
           "支臂 = 骨架 – 二价 – 一价端帽；端帽 = 一价原子直接封端；"
           "骨架内桥 = 同一骨架上两个原子之间的二价焊点，图形画在容器内部。",
           13, False, "#566573")
    cv.txt(700, yy + 130, "在 36 个分子中共出现：支臂 12 例、骨架内桥 13 例、"
           "一价端帽约 150 个。", 12, False, "#95a5a6")
    cv.save(os.path.join(OUT, "t68_connect.png"))


def S_plate(d, bx, by, cx, cy, s):
    """S 焊板示意：骨架上朝桥方向贴小方板。"""
    dx, dy = bx - cx, by - cy
    L = math.hypot(dx, dy) or 1
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    px, py = cx + ux * s * 0.9, cy + uy * s * 0.9
    h = s * 0.16
    d.line([(px - nx * h - ux * h, py - ny * h - uy * h),
            (px + nx * h - ux * h, py + ny * h - uy * h),
            (px + nx * h + ux * h, py + ny * h + uy * h),
            (px - nx * h + ux * h, py - ny * h + uy * h),
            (px - nx * h - ux * h, py - ny * h - uy * h)],
           fill=S.BONDC["S"], width=3)


if __name__ == "__main__":
    page_glyphs()
    page_families()
    page_library()
    page_connect()
    forms = load_forms()
    labels = [P.mol_label(f["atoms"], [tuple(e) for e in f["edges"]])
              for f in forms]
    print("forms:", len(forms), "distinct mol_label:", len(set(labels)))
    fam_cnt = {}
    for f in forms:
        fam_cnt[S.fam_key(f["atoms"])] = fam_cnt.get(S.fam_key(f["atoms"]), 0) + 1
    print("families:", fam_cnt)
