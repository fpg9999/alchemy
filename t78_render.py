# -*- coding: utf-8 -*-
"""t78_render.py —— T78 三轴介质箱结果作图（Pillow，中文字体 msyh）

输出 images/t78_overview.png（3x2 面板）：
  A 质量分层：轻/中/重 y 均值 vs 时间（main / nochem 两臂）
  B 恒素场：rho 均值±std vs 时间（三臂）
  C 终态 rho 场（main，10x20 网格热图；上=顶）
  D 终态竖直分布（main，40 桶，按质量档堆叠）
  E 反应地理：ρ 分桶反应数（三臂柱状）
  F 反应高度：底/中/上带反应数（三臂柱状）
用法：python t78_render.py
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

BASE = r"G:\AI work\deepseek\work1\alchemy"
FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_B = r"C:\Windows\Fonts\msyhbd.ttc"
OUT = os.path.join(BASE, "images", "t78_overview.png")
W_IMG, H_IMG = 1860, 1120
ARMS = ("main", "nogate", "nochem")
COL_ARM = {"main": (31, 119, 180), "nogate": (255, 127, 14), "nochem": (44, 160, 44)}
COL_MASS = {"轻": (44, 160, 44), "中": (31, 119, 180), "重": (214, 39, 40)}


def fnt(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, size)


def load(arm):
    with open(os.path.join(BASE, "t78_%s_result.json" % arm), encoding="utf-8") as fh:
        return json.load(fh)


class Panel:
    def __init__(self, img, draw, box, title):
        self.x0, self.y0, self.x1, self.y1 = box
        self.d = draw
        self.img = img
        self.title = title

    def frame(self):
        self.d.rectangle([self.x0, self.y0, self.x1, self.y1], outline=(150, 150, 150), width=1)
        self.d.text((self.x0 + 6, self.y0 + 4), self.title, font=fnt(20, True), fill=(20, 20, 20))

    def plot_area(self, pad_l=64, pad_r=16, pad_t=40, pad_b=44):
        return (self.x0 + pad_l, self.y0 + pad_t, self.x1 - pad_r, self.y1 - pad_b)

    def axes(self, xr, yr, xlabel="", ylabel="", xticks=None, yticks=None):
        x0, y0, x1, y1 = self.plot_area()
        d = self.d
        d.line([x0, y1, x1, y1], fill=(60, 60, 60), width=2)
        d.line([x0, y0, x0, y1], fill=(60, 60, 60), width=2)
        fx = lambda v: x0 + (v - xr[0]) / (xr[1] - xr[0]) * (x1 - x0)
        fy = lambda v: y1 - (v - yr[0]) / (yr[1] - yr[0]) * (y1 - y0)
        d.font = fnt(15)
        if xticks:
            for v in xticks:
                d.line([fx(v), y1, fx(v), y1 + 5], fill=(60, 60, 60), width=1)
                d.text((fx(v) - 14, y1 + 7), str(v), font=fnt(14), fill=(40, 40, 40))
        if yticks:
            for v in yticks:
                d.line([x0 - 5, fy(v), x0, fy(v)], fill=(60, 60, 60), width=1)
                lab = ("%.2f" % v) if isinstance(v, float) else str(v)
                ty = min(y1 - 18, max(y0 + 2, fy(v) - 8))
                d.text((self.x0 + 4, ty), lab, font=fnt(13), fill=(40, 40, 40))
        if xlabel:
            d.text(((x0 + x1) / 2 - 40, y1 + 24), xlabel, font=fnt(15), fill=(40, 40, 40))
        if ylabel:
            d.text((self.x0 + 4, y0 - 20), ylabel, font=fnt(15), fill=(40, 40, 40))
        return fx, fy

    def polyline(self, pts, color, width=2):
        self.d.line(pts, fill=color, width=width)

    def legend(self, items, x, y):
        for i, (lab, col) in enumerate(items):
            self.d.rectangle([x, y + i * 20, x + 16, y + i * 20 + 12], fill=col)
            self.d.text((x + 22, y + i * 20 - 2), lab, font=fnt(15), fill=(40, 40, 40))


def panel_A(img, d, box, data):
    p = Panel(img, d, box, "A 质量分层：三档 y 均值 vs 时间（上 main / 下 nochem）")
    p.frame()
    x0, y0, x1, y1 = p.plot_area(pad_l=70)
    d.line([x0, y1, x1, y1], fill=(60, 60, 60), width=2)
    d.line([x0, y0, x0, y1], fill=(60, 60, 60), width=2)
    # y 轴 0..4000，两臂并排：上半 main，下半 nochem
    for half, arm in ((0, "main"), (1, "nochem")):
        ty0 = y0 + half * (y1 - y0) / 2 + 30
        ty1 = y0 + (half + 1) * (y1 - y0) / 2 - 10
        ts = data[arm]["time_series"]
        n = len(ts)
        fx = lambda t: x0 + t / max(1, n - 1) * (x1 - x0)
        fy = lambda v: ty1 - v / 4000.0 * (ty1 - ty0)
        d.text((x0 + 6, ty0 - 20), ("%s 臂" % arm), font=fnt(15, True), fill=(40, 40, 40))
        for tier in ("轻", "中", "重"):
            pts = []
            for i in range(0, n, 2):
                v = ts[i]["y_mean"][tier]
                if v is None:
                    continue
                pts.append((fx(ts[i]["t"]), fy(v)))
            if len(pts) > 1:
                p.polyline(pts, COL_MASS[tier], 2)
        for v in (0, 2000, 4000):
            d.line([x0 - 4, fy(v), x0, fy(v)], fill=(60, 60, 60))
            d.text((x0 - 40, fy(v) - 8), str(v), font=fnt(12), fill=(40, 40, 40))
    for v in (0, 60, 120, 180, 240):
        d.text((x0 + v / 240.0 * (x1 - x0) - 10, y1 + 7), str(v), font=fnt(13), fill=(40, 40, 40))
    d.text(((x0 + x1) / 2 - 20, y1 + 26), "时间 (min)", font=fnt(15), fill=(40, 40, 40))
    p.legend([("轻", COL_MASS["轻"]), ("中", COL_MASS["中"]), ("重", COL_MASS["重"])], x1 - 90, y0 + 4)


def panel_B(img, d, box, data):
    p = Panel(img, d, box, "B 恒素场 rho：均值 ± std vs 时间（三臂）")
    p.frame()
    x0, y0, x1, y1 = p.plot_area(pad_l=64)
    p.axes((0, 240), (0, 0.75), "时间 (min)", "")
    d.text((x0 + 6, y0 + 4), "rho", font=fnt(14), fill=(40, 40, 40))
    n = len(data["main"]["time_series"])
    fx = lambda t: x0 + t / 240.0 * (x1 - x0)
    fy = lambda v: y1 - v / 0.75 * (y1 - y0)
    for v in (0, 0.25, 0.5, 0.75):
        d.text((x0 - 40, fy(v) - 8), "%.2f" % v, font=fnt(12), fill=(40, 40, 40))
    for arm in ARMS:
        ts = data[arm]["time_series"]
        mean_pts = [(fx(r["t"]), fy(r["rho_mean"])) for r in ts if r["t"] % 2 == 0]
        lo = [(fx(r["t"]), fy(max(0.0, r["rho_mean"] - r["rho_std"]))) for r in ts if r["t"] % 2 == 0]
        hi = [(fx(r["t"]), fy(min(1.0, r["rho_mean"] + r["rho_std"]))) for r in ts if r["t"] % 2 == 0]
        if len(mean_pts) > 1:
            p.polyline(lo, COL_ARM[arm] + (80,), 1)
            p.polyline(hi, COL_ARM[arm] + (80,), 1)
            p.polyline(mean_pts, COL_ARM[arm], 2)
    p.legend([("main（门控）", COL_ARM["main"]), ("nogate（无门控）", COL_ARM["nogate"]),
              ("nochem（无化学）", COL_ARM["nochem"])], x1 - 190, y1 - 78)


def panel_C(img, d, box, data):
    p = Panel(img, d, box, "C 终态 rho 场（main，上=顶）")
    p.frame()
    x0, y0, x1, y1 = p.plot_area(pad_l=24, pad_r=20, pad_t=34, pad_b=56)
    snaps = data["main"]["snapshots"]
    rho = snaps[-1]["rho"]
    EX, EY = 10, 20
    cw = (x1 - x0) / EX
    ch = (y1 - y0) / EY
    for ey in range(EY):
        for ex in range(EX):
            v = rho[ey * EX + ex]
            # 蓝(0.1) -> 白(0.5) -> 红(0.9)
            if v < 0.5:
                k = v / 0.5
                col = (int(30 + 215 * k), int(60 + 180 * k), int(200 + 40 * k))
            else:
                k = (v - 0.5) / 0.5
                col = (int(245 - 60 * k), int(240 - 180 * k), int(240 - 200 * k))
            xa = x0 + ex * cw
            ya = y1 - (ey + 1) * ch
            d.rectangle([xa, ya, xa + cw, ya + ch], fill=col, outline=(230, 230, 230))
            d.text((xa + 4, ya + ch / 2 - 7), "%.2f" % v, font=fnt(11), fill=(30, 30, 30))
    # 色标
    cw = (x1 - x0) / 2.0
    for k in range(100):
        v = k / 99.0
        if v < 0.5:
            q = v / 0.5
            col = (int(30 + 215 * q), int(60 + 180 * q), int(200 + 40 * q))
        else:
            q = (v - 0.5) / 0.5
            col = (int(245 - 60 * q), int(240 - 180 * q), int(240 - 200 * q))
        d.rectangle([x0 + k * cw / 100.0, y1 + 6, x0 + (k + 1) * cw / 100.0 + 0.5, y1 + 18], fill=col)
    d.text((x0 - 2, y1 + 20), "0.0", font=fnt(11), fill=(40, 40, 40))
    d.text((x0 + cw / 2 - 10, y1 + 20), "0.5", font=fnt(11), fill=(40, 40, 40))
    d.text((x0 + cw - 16, y1 + 20), "1.0", font=fnt(11), fill=(40, 40, 40))
    d.text((x0, y1 + 36), "t=%d min，N=%d，rho min %.2f / max %.2f" % (
        snaps[-1]["t"], snaps[-1]["n"], min(rho), max(rho)),
        font=fnt(12), fill=(40, 40, 40))


def panel_D(img, d, box, data):
    p = Panel(img, d, box, "D 终态竖直组成（main，40 桶 100% 堆叠；颜色同 A）")
    p.frame()
    x0, y0, x1, y1 = p.plot_area(pad_l=56)
    hist = data["main"]["vertical_hist"]
    BINS = len(hist["all"])
    fx = lambda i: x0 + i / BINS * (x1 - x0)
    fw = (x1 - x0) / BINS
    # 底 = 桶 0，顶 = 桶 BINS-1；逐桶归一化
    for i in range(BINS):
        tot = max(1, hist["all"][i])
        base = y1
        for tier in ("重", "中", "轻"):
            v = hist[tier][i]
            h = v / tot * (y1 - y0)
            d.rectangle([fx(i) + 1, base - h, fx(i) + fw - 1, base], fill=COL_MASS[tier])
            base -= h
    d.text((x0, y1 + 5), "底", font=fnt(13), fill=(40, 40, 40))
    d.text(((x0 + x1) / 2 - 10, y1 + 5), "高度", font=fnt(13), fill=(40, 40, 40))
    d.text((x1 - 20, y1 + 5), "顶", font=fnt(13), fill=(40, 40, 40))


def panel_E(img, d, box, data):
    p = Panel(img, d, box, "E 反应地理：按 rho 分桶的反应数（三臂）")
    p.frame()
    x0, y0, x1, y1 = p.plot_area(pad_l=56)
    gs = {a: data[a]["reaction_geography"] for a in ARMS}
    nb = len(gs["main"])
    maxv = max(1, max(b["reactions"] for a in ARMS for b in gs[a]))
    bw = (x1 - x0) / nb / 4.0
    for i, b in enumerate(gs["main"]):
        for j, arm in enumerate(ARMS):
            v = gs[arm][i]["reactions"]
            h = v / maxv * (y1 - y0)
            xa = x0 + i * (x1 - x0) / nb + j * bw + 2
            d.rectangle([xa, y1 - h, xa + bw - 2, y1], fill=COL_ARM[arm])
        if i % 2 == 0:
            d.text((x0 + i * (x1 - x0) / nb + 2, y1 + 4), "%.1f" % b["rho_bin"], font=fnt(11), fill=(40, 40, 40))
    d.text((x0, y1 + 22), "rho 分桶", font=fnt(13), fill=(40, 40, 40))
    d.text((x0 - 44, y0 + 4), str(maxv), font=fnt(12), fill=(40, 40, 40))
    p.legend([("main", COL_ARM["main"]), ("nogate", COL_ARM["nogate"]), ("nochem", COL_ARM["nochem"])],
             x1 - 90, y1 - 70)


def panel_F(img, d, box, data):
    p = Panel(img, d, box, "F 反应高度：底/中/上带反应数（三臂）")
    p.frame()
    x0, y0, x1, y1 = p.plot_area(pad_l=56)
    bands = ("bottom", "mid", "top")
    maxv = max(1, max(data[a]["summary"]["band_reaction"][b] for a in ARMS for b in bands))
    bw = (x1 - x0) / 3 / 4.0
    for i, b in enumerate(bands):
        for j, arm in enumerate(ARMS):
            v = data[arm]["summary"]["band_reaction"][b]
            h = v / maxv * (y1 - y0)
            xa = x0 + i * (x1 - x0) / 3 + j * bw + 2
            d.rectangle([xa, y1 - h, xa + bw - 2, y1], fill=COL_ARM[arm])
            if v:
                d.text((xa, y1 - h - 14), str(v), font=fnt(11), fill=(40, 40, 40))
        d.text((x0 + i * (x1 - x0) / 3 + 4, y1 + 4), b, font=fnt(12), fill=(40, 40, 40))
    d.text((x0 - 44, y0 + 4), str(maxv), font=fnt(12), fill=(40, 40, 40))
    p.legend([("main", COL_ARM["main"]), ("nogate", COL_ARM["nogate"]), ("nochem", COL_ARM["nochem"])],
             x1 - 90, y0 + 2)


def main():
    data = {a: load(a) for a in ARMS}
    img = Image.new("RGB", (W_IMG, H_IMG), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((30, 18), "T78 九元素三轴介质箱：质量->重力、物态->碰撞、温度->恒素富集（240 min，single seed）",
           font=fnt(26, True), fill=(10, 10, 10))
    gap = 18
    cw = (W_IMG - 2 * 30 - 2 * gap) / 3
    ch = (H_IMG - 2 * 30 - 90 - gap) / 2
    boxes = []
    for r in range(2):
        for c in range(3):
            x0 = 30 + c * (cw + gap)
            y0 = 76 + r * (ch + gap)
            boxes.append((x0, y0, x0 + cw, y0 + ch))
    panel_A(img, d, boxes[0], data)
    panel_B(img, d, boxes[1], data)
    panel_C(img, d, boxes[2], data)
    panel_D(img, d, boxes[3], data)
    panel_E(img, d, boxes[4], data)
    panel_F(img, d, boxes[5], data)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT)
    print("saved", OUT, img.size)


if __name__ == "__main__":
    main()
