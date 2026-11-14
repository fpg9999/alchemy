# -*- coding: utf-8 -*-
"""t20_render.py：二价元素存在形式示意图（两张图）
图1：8 种存在形式（真桥/骨架内桥/链段/支臂/链端/端帽双键/二价二聚/二价环/双帽夹心）
图2：同一桥位置，X/W/A 三种二价元素的连接几何（S 刚性 / C 铰接 / L 软连接）
"""
import json
import math
import sys
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
from PIL import Image, ImageDraw
import t8_render_forms as R

BASE = r"G:\AI work\deepseek\work1\alchemy"
FONT = R.FONT
FONT_B = R.FONT_B
font = R.font
text_center = R.text_center
TWO_COL = {"X": (240, 160, 75), "W": (201, 162, 39), "A": (143, 214, 192)}
ONE_COL = {"C": (127, 182, 232), "L": (255, 224, 102), "F": (224, 90, 79)}
TCOL = (107, 191, 107)
BONDC = {"S": "#c0392b", "C": "#1e8449", "L": "#6c3483"}


def tri(d, x, y, r, label="T"):
    pts = [(x + r * math.cos(math.radians(-90 + 120 * k)),
            y + r * math.sin(math.radians(-90 + 120 * k))) for k in range(3)]
    d.polygon(pts, fill=TCOL, outline="#2d5a2d", width=2)
    text_center(d, x, y + 3, label, font(FONT_B, int(r * 0.9)), "#0b3d0b")


def hexn(d, x, y, r, col, label):
    pts = R.hex_pts(x, y, r)
    d.polygon(pts, fill=col, outline="#333", width=2)
    text_center(d, x, y, label, font(FONT_B, int(r * 0.75)), "#111")


def cap(d, x, y, r, col, label):
    d.ellipse([x - r, y - r, x + r, y + r], fill=col, outline="#333", width=2)
    text_center(d, x, y, label, font(FONT_B, int(r * 0.75)), "#111")


def bond(d, *args):
    """兼容两种调用：bond(d, (x1,y1),(x2,y2),kind,mult) 或 bond(d,x1,y1,x2,y2,kind,mult)"""
    if len(args) == 4:
        p1, p2, kind, mult = args
    elif len(args) == 6:
        p1 = (args[0], args[1])
        p2 = (args[2], args[3])
        kind = args[4]
        mult = args[5]
    else:
        raise TypeError("bond args: %r" % (args,))
    ux, uy = p2[0] - p1[0], p2[1] - p1[1]
    L = math.hypot(ux, uy)
    nx, ny = -uy / L, ux / L
    col = BONDC[kind]
    width = 3 if kind != "L" else 2
    if kind == "L":
        R.dashed(d, p1, p2, col, width, 8, 6)
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        d.rectangle([mx - 4, my - 4, mx + 4, my + 4], outline=col, width=1)
    else:
        for k in range(mult):
            off = (k - (mult - 1) / 2) * 5
            d.line([(p1[0] + nx * off, p1[1] + ny * off),
                    (p2[0] + nx * off, p2[1] + ny * off)], fill=col, width=width)
            if kind == "C":
                mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
                d.ellipse([mx - 3, my - 3, mx + 3, my + 3], fill="#1e8449")


def panel(img, d, box, title, draw_fn):
    x0, y0, w, h = box
    d.rectangle([x0, y0, x0 + w, y0 + h], outline="#dddddd", width=1)
    d.text((x0 + 10, y0 + 8), title, font=font(FONT_B, 19), fill="#111")
    draw_fn(d, x0, y0, w, h)


def main():
    roles = json.load(open(BASE + r"\t20_roles.json", encoding="utf-8"))
    W, H = 1680, 1180
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((24, 14), "二价元素（晶 X / 流 W / 气 A）的存在形式（全部 84,225 种物质统计）",
           font=font(FONT_B, 28), fill="#111")
    d.text((24, 52), "2 价原子恒有 2 根键 → 只能做\"连接\"；但它可以以 9 种方式出现。绿色三角=三价骨架原子，彩色六边形=二价原子，小圆=一价端帽。",
           font=font(FONT, 16), fill="#555")
    d.text((24, 78), "红=短键S（刚性），绿=角键C（铰接），紫虚线=长键L（软/远距）；平行线=多重键。",
           font=font(FONT, 16), fill="#888")

    pw, ph, left, top = 545, 255, 24, 118

    # 1 真桥
    def p1(d, x, y, w, h):
        c = TCOL
        tri(d, x + 130, y + 90, 26)
        tri(d, x + 410, y + 90, 26)
        hexn(d, x + 270, y + 90, 24, TWO_COL["X"], "X")
        bond(d, x + 154, y + 90, x + 246, y + 90, "S", 1)
        bond(d, x + 294, y + 90, x + 386, y + 90, "S", 1)
        d.text((x + 155, y + 150), "两端接不同骨架块", font=font(FONT, 14), fill="#555")
    # 2 骨架内桥
    def p2(d, x, y, w, h):
        tri(d, x + 120, y + 100, 26)
        tri(d, x + 380, y + 100, 26)
        hexn(d, x + 250, y + 200, 22, TWO_COL["W"], "W")
        bond(d, x + 140, y + 118, x + 232, y + 182, "C", 1)
        bond(d, x + 268, y + 182, x + 360, y + 118, "C", 1)
        d.text((x + 60, y + 230), "同一骨架块的两处被 2 价原子拉成环/加固", font=font(FONT, 14), fill="#555")
    # 3 链段
    def p3(d, x, y, w, h):
        tri(d, x + 90, y + 110, 26)
        hexn(d, x + 220, y + 110, 22, TWO_COL["A"], "A")
        hexn(d, x + 350, y + 110, 22, TWO_COL["A"], "A")
        d.text((x + 385, y + 100), "…", font=FONT_B and font(FONT_B, 30), fill="#333")
        bond(d, x + 114, y + 110, x + 198, y + 110, "L", 1)
        bond(d, x + 242, y + 110, x + 328, y + 110, "L", 1)
    # 4 支臂（骨架—二价—端帽）
    def p4(d, x, y, w, h):
        tri(d, x + 120, y + 110, 26)
        hexn(d, x + 260, y + 110, 22, TWO_COL["X"], "X")
        cap(d, x + 385, y + 110, 14, ONE_COL["C"], "C")
        bond(d, x + 144, y + 110, x + 238, y + 110, "S", 1)
        bond(d, x + 282, y + 110, x + 371, y + 110, "S", 1)
    # 5 链端（二价—端帽）
    def p5(d, x, y, w, h):
        hexn(d, x + 130, y + 110, 22, TWO_COL["W"], "W")
        hexn(d, x + 270, y + 110, 22, TWO_COL["W"], "W")
        cap(d, x + 400, y + 110, 14, ONE_COL["L"], "L")
        bond(d, x + 152, y + 110, x + 248, y + 110, "C", 1)
        bond(d, x + 292, y + 110, x + 386, y + 110, "C", 1)
    # 6 端帽双键（同一三价原子 ×2）
    def p6(d, x, y, w, h):
        tri(d, x + 180, y + 110, 28)
        hexn(d, x + 340, y + 110, 24, TWO_COL["X"], "X")
        bond(d, x + 205, y + 110, x + 316, y + 110, "S", 2)
        d.text((x + 210, y + 150), "双键挂在同一骨架原子上（端基）", font=font(FONT, 14), fill="#555")
    # 7 二价二聚
    def p7(d, x, y, w, h):
        hexn(d, x + 240, y + 110, 24, TWO_COL["A"], "A")
        hexn(d, x + 400, y + 110, 24, TWO_COL["A"], "A")
        bond(d, x + 264, y + 110, x + 376, y + 110, "L", 2)
    # 8 二价环
    def p8(d, x, y, w, h):
        cx, cy, r = x + 270, y + 120, 62
        pts = []
        for k in range(3):
            ang = math.radians(-90 + 120 * k)
            pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
        for k in range(3):
            hexn(d, pts[k][0], pts[k][1], 20, TWO_COL["X"], "X")
        for k in range(3):
            bond(d, pts[k], pts[(k + 1) % 3], "S", 1)
    # 9 双帽夹心
    def p9(d, x, y, w, h):
        cap(d, x + 160, y + 110, 14, ONE_COL["F"], "F")
        hexn(d, x + 300, y + 110, 22, TWO_COL["A"], "A")
        cap(d, x + 440, y + 110, 14, ONE_COL["C"], "C")
        bond(d, x + 174, y + 110, x + 278, y + 110, "L", 1)
        bond(d, x + 322, y + 110, x + 426, y + 110, "L", 1)

    panels = [
        ("① 真桥（跨不同骨架块） 59,621", p1),
        ("② 骨架内桥（同块内成环/加固） 46,287", p2),
        ("③ 链段（2价—2价—…串联） 128,922*", p3),
        ("④ 支臂（骨架—2价—1价端帽） 33,331", p4),
        ("⑤ 链端（2价—1价端帽） 22,834", p5),
        ("⑥ 端帽双键（同一骨架原子×2） 51,991", p6),
        ("⑦ 二价二聚（2价=2价） 12", p7),
        ("⑧ 二价小环（3~5 元） 19 种物质", p8),
        ("⑨ 双帽夹心（1价—2价—1价） 18", p9),
    ]
    for k, (title, fn) in enumerate(panels):
        r, c = divmod(k, 3)
        panel(img, d, (left + c * pw, top + r * ph, pw - 8, ph - 8), title, fn)
    img.save(BASE + r"\images\t20_divalent_forms.png")
    print("saved images/t20_divalent_forms.png")

    # 图2：三种二价元素的桥接几何
    W2, H2 = 1680, 620
    img2 = Image.new("RGB", (W2, H2), "white")
    d2 = ImageDraw.Draw(img2)
    d2.text((24, 14), "同一种桥位置，三种二价元素 → 三种机械性质", font=font(FONT_B, 28), fill="#111")
    d2.text((24, 52), "X 晶：62.9% 用短键 S（刚性焊接）；W 流：71.1% 用角键 C（铰链/可旋转）；A 气：64.3% 用长键 L（隔格软连接）。",
            font=font(FONT, 16), fill="#555")
    specs = [
        ("X 晶（聚，2价）：短键 S → 刚性焊接", "X", "S", "两骨架共享边、整块受力；装甲板/支撑梁"),
        ("W 流（动，2价）：角键 C → 铰链", "W", "C", "两骨架角对角接触、可绕点旋转；腿/钳/翻盖"),
        ("A 气（散，2价）：长键 L → 软连接", "A", "L", "两骨架隔一格、弹性系带；浮空/鞭击/拖曳"),
    ]
    for k, (title, el, kind, desc) in enumerate(specs):
        x0 = 24 + k * 550
        y0 = 100
        d2.rounded_rectangle([x0, y0, x0 + 530, y0 + 480], radius=12, outline="#ddd", width=2)
        d2.text((x0 + 16, y0 + 10), title, font=font(FONT_B, 19), fill="#111")
        cx = x0 + 265
        tri(d2, cx - 150, y0 + 150, 30)
        tri(d2, cx + 150, y0 + 150, 30)
        hexn(d2, cx, y0 + 150, 26, TWO_COL[el], el)
        bond(d2, cx - 122, y0 + 150, cx - 28, y0 + 150, kind, 1)
        bond(d2, cx + 28, y0 + 150, cx + 122, y0 + 150, kind, 1)
        d2.text((x0 + 20, y0 + 250), desc, font=font(FONT, 15), fill="#444")
        cnt = {"X": "S 62.9% / C 19.4% / L 17.7%", "W": "C 71.1% / S 15.3% / L 13.6%",
               "A": "L 64.3% / C 17.6% / S 18.0%"}[el]
        d2.text((x0 + 20, y0 + 300), "实测键型占比：" + cnt, font=font(FONT, 14), fill="#b8860b")
    img2.save(BASE + r"\images\t20_bridge_types.png")
    print("saved images/t20_bridge_types.png")


if __name__ == "__main__":
    main()
