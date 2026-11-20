# -*- coding: utf-8 -*-
"""T90 作图：主体 A 团簇的抓取-反应-并入-生长。"""
import io
import json
import os
from PIL import Image, ImageDraw, ImageFont

BASE = r"G:\AI work\deepseek\work1\alchemy"
FONT = r"C:\Windows\Fonts\msyh.ttc"
FONTB = r"C:\Windows\Fonts\msyhbd.ttc"
INK = (32, 32, 38)
SUB = (90, 90, 100)
GRID = (235, 235, 240)
C_BODY = (200, 40, 40)
C_FOOD1 = (60, 130, 210)
C_FOOD2 = (40, 170, 110)
C_EMPTY = (252, 252, 252)


def fnt(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)


def load(name):
    return json.load(io.open(os.path.join(BASE, name), encoding="utf-8"))


def axes(d, box, ymax, ylab, xlab):
    x0, y0, x1, y1 = box
    d.rectangle([x0, y0, x1, y1], outline=(150, 150, 160))
    for i in range(5):
        v = ymax * i / 4.0
        y = y1 - (y1 - y0) * i / 4.0
        d.line([(x0, y), (x1, y)], fill=GRID)
        d.text((x0 - 54, y - 9), "%d" % round(v), font=fnt(14), fill=SUB)
    d.text((x0 - 44, y0 - 26), ylab, font=fnt(15), fill=SUB)
    d.text(((x0 + x1) / 2 - len(xlab) * 6, y1 + 8), xlab, font=fnt(15), fill=SUB)


def line(d, box, xs, ys, xmax, ymax, col, w=3):
    x0, y0, x1, y1 = box
    pts = []
    for x, y in zip(xs, ys):
        px = x0 + (x1 - x0) * x / max(1.0, xmax)
        py = y1 - (y1 - y0) * y / max(1.0, ymax)
        pts.append((px, py))
    if len(pts) >= 2:
        d.line(pts, fill=col, width=w)


def main():
    arms = [("t90_full.json", "full（吸引+反应）", C_BODY, 3),
            ("t90_noattr.json", "no-attr（无吸引）", (120, 120, 130), 2),
            ("t90_noreact.json", "no-react（不反应）", (130, 170, 220), 2),
            ("t90_noseed.json", "no-seed（无主体）", (170, 170, 120), 2)]
    datas = [(load(f), lab, col, w) for f, lab, col, w in arms]
    W_IMG, H_IMG = 2400, 1500
    img = Image.new("RGB", (W_IMG, H_IMG), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((40, 22), "T90：主体 A 团簇的“抓取 → 体内反应再生 A → 并入 → 生长”",
           font=fnt(30, True), fill=INK)
    d.text((40, 68), "世界 240×160；A=C3K3F2（8 原子、5 位点）；F1=C2K2、F2=CKF2；"
                     "F1+F2 → A；营养物被 A 吸引，F1/F2 只在主体表面 3 格内反应；"
                     "产物 A 邻接主体即并入（主体设为固态）", font=fnt(15), fill=SUB)

    # A: body size
    boxA = (110, 150, 900, 640)
    d.text((110, 88), "A 主体尺寸（A 分子数）vs 时间", font=fnt(19, True), fill=INK)
    ymax = 300
    axes(d, boxA, ymax, "A 分子数", "t（拍）")
    for data, lab, col, w in datas:
        xs = [p["t"] for p in data["series"]]
        ys = [p["body"] for p in data["series"]]
        line(d, boxA, xs, ys, 700, ymax, col, w)
    lx, ly = boxA[0] + 14, boxA[1] + 14
    for data, lab, col, w in datas:
        d.line([(lx, ly + 7), (lx + 26, ly + 7)], fill=col, width=w)
        d.text((lx + 32, ly - 4), lab, font=fnt(14), fill=SUB)
        ly += 26

    # B: food remaining
    boxB = (980, 150, 1740, 640)
    d.text((980, 88), "B 剩余营养物 F1+F2（full 臂）", font=fnt(19, True), fill=INK)
    axes(d, boxB, 520, "分子数", "t（拍）")
    data = datas[0][0]
    xs = [p["t"] for p in data["series"]]
    line(d, boxB, xs, [p["food1"] + p["food2"] for p in data["series"]],
         700, 520, C_FOOD1, 3)
    d.text((boxB[0] + 16, boxB[1] + 40),
           "峰值 500 → 终态 24：被主体抓走并在表面反应掉",
           font=fnt(15), fill=SUB)

    # C: final world map (full arm)
    mx0, my0, mw, mh = 1820, 110, 540, 760
    d.text((mx0, 80), "C full 臂终态（t=700）", font=fnt(19, True), fill=INK)
    sc = min(mw / 240.0, mh / 160.0)
    d.rectangle([mx0, my0, mx0 + 240 * sc, my0 + 160 * sc],
                outline=(150, 150, 160))
    for (r, c) in data["final_food_cells"]:
        d.rectangle([mx0 + c * sc, my0 + r * sc,
                     mx0 + (c + 1) * sc, my0 + (r + 1) * sc], fill=C_FOOD1)
    for (r, c) in data["final_body_cells"]:
        d.rectangle([mx0 + c * sc, my0 + r * sc,
                     mx0 + (c + 1) * sc, my0 + (r + 1) * sc], fill=C_BODY)
    d.text((mx0, my0 + 160 * sc + 10),
           "红=主体 A（263 个，连通团簇）；蓝=残余营养物（24 个）",
           font=fnt(14), fill=SUB)
    d.text((mx0, my0 + 160 * sc + 34),
           "主体从半径 8 长到 62 格，但形态是疏松网络（不是紧凑球）",
           font=fnt(14), fill=SUB)

    # D: bars
    d.text((110, 700), "D 四臂终态对比", font=fnt(19, True), fill=INK)
    y0 = 760
    labels = ["主体 A 数", "反应次数", "并入次数"]
    vals = [(dta["series"][-1]["body"], dta["series"][-1]["react"],
             dta["series"][-1]["join"]) for dta, _, _, _ in datas]
    xmax = 280.0
    for j, lab in enumerate(labels):
        yy = y0 + j * 150
        d.text((110, yy - 24), lab, font=fnt(16), fill=INK)
        for i, (dta, alab, col, w) in enumerate(datas):
            v = vals[i][j]
            bw2 = 900 * v / xmax
            byy = yy + i * 34
            d.rectangle([110, byy, 110 + max(2, bw2), byy + 26], fill=col)
            d.text((110 + max(2, bw2) + 8, byy + 3),
                   "%d（%s）" % (v, alab.split("（")[0]),
                   font=fnt(13), fill=SUB)

    # E: conclusion text
    tx, ty = 1250, 700
    lines = [
        "结论（对照实验）",
        "1. 稳定团簇可以存在：no-react 臂中 24 个 A 的团簇 700 拍内一个没散（尺寸、半径不变）。",
        "2. 抓取靠吸引力：no-attr 臂无营养物被拉近，0 次反应、主体停在 24。",
        "3. 体内/表面反应再生 A 后并入：full 臂 239 次反应、176 次并入，主体 24 → 263（×11）。",
        "4. 生长会自限：营养物耗尽后停止（500 → 24），主体半径 8 → 62，长成疏松网络而非紧凑球。",
        "5. 无主体则完全不反应：no-seed 臂 0 次反应（表面催化是必要条件）。",
        "",
        "诚实说明：本实验用“主体固态 + 表面 3 格内才反应 + 营养物被 A 吸引”三条建模假设；",
        "稳定性和抓取是假设的、不是自发涌现的（T89 里自发稳定团簇极少）。要让它自发涌现，",
        "需要更真实的粘附/模板/供能机制，而不是本文的脚本化规则。",
    ]
    for i, s in enumerate(lines):
        d.text((tx, ty + i * 32), s, font=fnt(16 if i == 0 else 15, i == 0),
               fill=INK if i == 0 else SUB)

    img.save(os.path.join(BASE, "images", "t90_body.png"))
    print("saved images/t90_body.png", img.size)


if __name__ == "__main__":
    main()
