# -*- coding: utf-8 -*-
"""T81 三素相互作用 图：全目录校准 + 动态世界验证
输出 images/t81_su.png
"""
from __future__ import annotations

import io
import json
import math
import os

from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
FONT = r"C:\Windows\Fonts\msyh.ttc"
FONTB = r"C:\Windows\Fonts\msyhbd.ttc"
W, H = 1800, 1240

C_BG = (255, 255, 255)
C_FRAME = (90, 90, 90)
C_TXT = (40, 40, 40)
C_GRID = (226, 226, 226)
C_ATT = (196, 84, 62)
C_REP = (58, 102, 160)
C_LINE = (44, 116, 176)
C_LINE2 = (214, 96, 40)
C_GREEN = (46, 132, 88)
C_GREY = (130, 130, 130)

_fonts = {}


def fnt(sz, bold=False):
    key = (sz, bold)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(FONTB if bold else FONT, sz)
    return _fonts[key]


def text(d, xy, s, sz=16, bold=False, fill=C_TXT):
    d.text(xy, s, font=fnt(sz, bold), fill=fill)


def frame(d, box, title=None, xlab=None, ylab=None):
    x0, y0, x1, y1 = box
    d.rectangle(box, outline=C_FRAME, width=1)
    if title:
        text(d, (x0 + 6, y0 + 4), title, 17, True)
    if xlab:
        text(d, ((x0 + x1) / 2 - len(xlab) * 6, y1 + 6), xlab, 14)
    if ylab:
        text(d, (x0 + 2, y0 + 26), ylab, 14)


def axes_box(box, pad_l=62, pad_r=16, pad_t=34, pad_b=44):
    x0, y0, x1, y1 = box
    return x0 + pad_l, y0 + pad_t, x1 - pad_r, y1 - pad_b


def yticks(d, ax, vmax, n=4, fmt="%.1f"):
    x0, y0, x1, y1 = ax
    for k in range(n + 1):
        v = vmax * k / n
        y = y1 - (y1 - y0) * k / n
        d.line([(x0, y), (x1, y)], fill=C_GRID, width=1)
        text(d, (x0 - 44, y - 9), fmt % v, 13)


def xticks(d, ax, vals, labels=None, fmt="%g"):
    x0, y0, x1, y1 = ax
    for i, v in enumerate(vals):
        x = x0 + (x1 - x0) * (i / max(1, len(vals) - 1))
        d.line([(x, y0), (x, y1)], fill=C_GRID, width=1)
        lab = labels[i] if labels else (fmt % v)
        text(d, (x - 16, y1 + 6), lab, 12)


def poly(d, pts, color, width=2, dash=None):
    if not pts:
        return
    if dash is None:
        d.line(pts, fill=color, width=width)
        return
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        if i % dash[1] == 0:
            d.line([(x0, y0), (x1, y1)], fill=color, width=width)


def main():
    cal = json.load(io.open(os.path.join(BASE, "t81_calibration.json"), encoding="utf-8"))
    wd = json.load(io.open(os.path.join(BASE, "t81_world_full.json"), encoding="utf-8"))
    d = ImageDraw.Draw(img := Image.new("RGB", (W, H), C_BG))

    text(d, (28, 18), "T81 三素相互作用：聚素=吸引、散素=覆盖半径、动素=排斥", 30, True)
    text(d, (28, 58), "全目录 84,225 分子校准（κA=2.5, κR=0.5, J=原子组成Jaccard）＋ 方阵环面动态世界验证", 16)

    # ---- A 校准 ----
    box = (28, 92, 700, 400)
    frame(d, box, "A 全目录配对校准（84,225 分子，10 万随机异种对）")
    ax = axes_box(box, pad_l=70, pad_b=60)
    yticks(d, ax, 100.0, 4, "%.0f%%")
    items = [
        ("同种净吸引", 100.0 * cal["same"]["net_attract"] / cal["meta"]["catalog"], C_ATT),
        ("同种强粘\n(w≥1)", 100.0 * cal["same"]["strong_10"] / cal["meta"]["catalog"], C_ATT),
        ("异种双弱\n(att,rep<0.5)", cal["cross"]["double_weak_05"], C_REP),
        ("异种双弱\n(att,rep<1.0)", cal["cross"]["double_weak_10"], C_REP),
        ("异种强吸\n(att≥1)", cal["cross"]["strong_att_10"], (150, 150, 150)),
    ]
    x0, y0, x1, y1 = ax
    bw = (x1 - x0) / (len(items) * 1.6)
    for i, (lab, v, col) in enumerate(items):
        cx = x0 + (i + 0.5) * (x1 - x0) / len(items)
        h = (y1 - y0) * v / 100.0
        d.rectangle([cx - bw / 2, y1 - h, cx + bw / 2, y1], fill=col)
        text(d, (cx - 22, y1 - h - 18), "%.1f%%" % v, 13, True)
        for j, ln in enumerate(lab.split("\n")):
            text(d, (cx - len(ln) * 6, y1 + 6 + j * 15), ln, 12)
    text(d, (x0, y0 - 22), "占比", 12)

    # ---- B 半径 ----
    box = (724, 92, 1180, 400)
    frame(d, box, "B 覆盖半径分布（散素点数和 Q 决定）")
    ax = axes_box(box, pad_l=70, pad_b=60, pad_t=56)
    x0, y0, x1, y1 = ax
    ra = cal["radii"]["r_att"]
    rr = cal["radii"]["r_rep"]
    n = cal["meta"]["catalog"]
    bars = [("吸引半径", [ra["1"], ra["2"], ra["3"]], [C_ATT, (222, 142, 120), (240, 190, 178)]),
            ("排斥半径", [rr["1"], rr["2"], rr["3"]], [C_REP, (120, 158, 205), (188, 210, 234)])]
    for gi, (lab, vals, cols) in enumerate(bars):
        cy0 = y0 + gi * ((y1 - y0) / 2 + 8)
        cy1 = cy0 + (y1 - y0) / 2 - 12
        left = x0
        tot = sum(vals)
        for k, v in enumerate(vals):
            w = (x1 - x0) * v / tot
            d.rectangle([left, cy0, left + w, cy1], fill=cols[k], outline=C_BG)
            if w > 60:
                text(d, (left + 6, cy0 + 6), "r=%d  %.1f%%" % (k + 1, 100.0 * v / tot), 13, True, (255, 255, 255))
            left += w
        text(d, (x0, cy0 - 20), lab, 14, True)

    # ---- C E1 聚集：键数（力 vs 无力） ----
    box = (28, 412, 900, 900)
    frame(d, box, "C 同种聚集（40 个/世界，L=40）：键数 vs 时间（实线=有力，虚线=无力）",
          xlab="t（拍）")
    ax = axes_box(box, pad_l=70, pad_b=48, pad_t=40)
    x0, y0, x1, y1 = ax
    e1 = wd["e1"]
    groups = [("O2K2A2", C_ATT), ("O2K6A2", (226, 140, 40)), ("O2", C_LINE), ("C2", C_LINE2), ("K2", C_GREY), ("WA", (150, 110, 60))]
    curves = []
    ymax = 0
    for f, col in groups:
        rs = [r for r in e1 if r["formula"] == f]
        if not rs:
            continue
        ts = [s["t"] for s in rs[0]["series"]]
        ys = [sum(r["series"][k]["bonds"] for r in rs) / len(rs) for k in range(len(ts))]
        curves.append((f, ts, ys, col, None))
        ymax = max(ymax, max(ys))
    e1c = wd.get("e1c", [])
    for f, col in [("O2K2A2", C_ATT), ("O2", C_LINE)]:
        rs = [r for r in e1c if r.get("formula") == f]
        if rs:
            ts = [s["t"] for s in rs[0]["series"]]
            ys = [s["bonds"] for s in rs[0]["series"]]
            curves.append((f + "·无力", ts, ys, col, (3, 7)))
            ymax = max(ymax, max(ys))
    ymax = max(20.0, math.ceil(ymax / 10.0) * 10.0)
    yticks(d, ax, ymax, 4, "%.0f")
    xt = [s["t"] for s in e1[0]["series"]]
    xticks(d, ax, xt[::max(1, len(xt) // 6)])
    labels = []
    for f, ts, ys, col, dash in curves:
        pts = [(x0 + (x1 - x0) * t / max(1, ts[-1]), y1 - (y1 - y0) * y / ymax) for t, y in zip(ts, ys)]
        poly(d, pts, col, 2, dash)
    # 图例（左上空白区）
    leg = [("O2K2A2", C_ATT, None), ("O2K6A2", (226, 140, 40), None), ("O2", C_LINE, None),
           ("C2", C_LINE2, None), ("K2", C_GREY, None), ("WA", (150, 110, 60), None),
           ("O2K2A2/O2 无力", C_GREY, (3, 7))]
    for i, (f, col, dash) in enumerate(leg):
        ly = y0 + 6 + i * 15
        poly(d, [(x0 + 6, ly + 7), (x0 + 28, ly + 7)], col, 2, dash)
        text(d, (x0 + 34, ly), f, 12, False, col)

    # ---- D E2 选择性 ----
    box = (924, 412, 1772, 640)
    frame(d, box, "D 混合世界（6 种×20，L=40）：同性键占比 vs 随机期望", xlab="")
    ax = axes_box(box, pad_l=70, pad_b=40, pad_t=38)
    x0, y0, x1, y1 = ax
    yticks(d, ax, 1.0, 4, "%.2f")
    e2 = wd["e2"]
    mixes = sorted(set(e["mix"] for e in e2))
    bw = (x1 - x0) / (len(mixes) * 1.5)
    for m in mixes:
        rs = [e["result"]["final"]["same_bond"] for e in e2 if e["mix"] == m]
        fr = sum(r["frac"] for r in rs) / len(rs)
        ex = sum(r["expected"] for r in rs) / len(rs)
        cx = x0 + (m + 0.75) * (x1 - x0) / len(mixes)
        h = (y1 - y0) * fr
        d.rectangle([cx - bw / 2, y1 - h, cx + bw / 2, y1], fill=C_LINE)
        text(d, (cx - 20, y1 - h - 16), "%.2f" % fr, 13, True)
        yex = y1 - (y1 - y0) * ex
        d.line([(cx - bw / 2 - 8, yex), (cx + bw / 2 + 8, yex)], fill=C_ATT, width=2)
        text(d, (cx - 16, y1 + 6), "mix%d" % m, 12)
    text(d, (x0 + 4, y1 + 26), "红线=随机期望 0.16", 12, False, C_ATT)

    # ---- E E3 体生长 ----
    box = (924, 652, 1772, 900)
    frame(d, box, "E 种子体生长（6 个 A + 15 个游离 A，L=48，2500 拍）：体内 A 数 vs 时间",
          xlab="t（拍）")
    ax = axes_box(box, pad_l=70, pad_b=44, pad_t=38)
    x0, y0, x1, y1 = ax
    e3 = wd["e3"]
    ymax = 1.0
    for r in e3:
        ymax = max(ymax, max(s["body_n"] for s in r["series"]))
    yticks(d, ax, 8.0, 4, "%.0f")
    cols = {"O2K2A2": C_ATT, "O2K3A2F2": (226, 140, 40), "O2": C_LINE, "C2": C_LINE2, "WA": C_GREY, "L2": (150, 150, 150)}
    for r in e3:
        ts = [s["t"] for s in r["series"]]
        ys = [s["body_n"] for s in r["series"]]
        col = cols.get(r["A"], C_GREY)
        pts = [(x0 + (x1 - x0) * t / max(1, ts[-1]), y1 - (y1 - y0) * y / max(6.0, ymax)) for t, y in zip(ts, ys)]
        style = 2 if r["use_force"] else 1
        poly(d, pts, col, style, None if r["use_force"] else (2, 8))
    # 标注（中部空白带）
    text(d, (x0 + 8, y1 - 66), "6~7：O2K2A2 / O2K3A2F2 / O2（实线=有力，虚线=无力，几乎重合）", 12, False, (70, 70, 70))
    text(d, (x0 + 8, y1 - 46), "0：C2（w=0.83）/ WA（w=-0.33）/ L2（w=-0.17），力开或关都不成团", 12, False, (70, 70, 70))
    text(d, (x0 + 8, y1 - 26), "结论：同质吸引只让游离单体彼此成团，不能让单个种子体选择性长大", 12, False, (150, 60, 40))

    text(d, (28 + 4, 930),
         "读图：A 同种净吸引 95.5%、强粘 82.0%；异种最常见的是双弱（58.7%；<1.0 时 94.6%），强吸仅 5.4%。"
         " B 吸引半径 1/2/3 覆盖 54%/32%/14%，排斥永远落后。", 15)
    text(d, (28 + 4, 962),
         "C 强吸引分子（O2/XA，self w=2.5）成团，无聚素（K2/WA/LF）0 键；力显著加速初期装配（t≤100 键数 15→24，关力仅 3→11）。"
         " D 混合世界同性键占比 0.40~1.00，远高于随机期望 0.16。", 15)
    text(d, (28 + 4, 994),
         "E 同质吸引不能让单个种子体选择性长大（6→7，力/无力几乎相同）：游离单体彼此成团竞争；需不对称机制（食物不自粘/体更大/表面选择性）。", 15)
    text(d, (28 + 4, 1032),
         "注：动态世界为方阵环面 8 邻域（与分子内部六边形格子无关）；每格 1 个点粒子；键记录 w≥0.2 的贴邻接触，强键（w≥1）锁住相对位置；本图未启用反应路径。", 14, False, (90, 90, 90))

    out = os.path.join(BASE, "images", "t81_su.png")
    img.save(out)
    print("saved", out, img.size)


if __name__ == "__main__":
    main()
