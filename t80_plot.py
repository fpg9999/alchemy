# -*- coding: utf-8 -*-
"""T80 组装体生长实验：作图（只读结果 JSON，不跑模拟）。

输出 images/t80_assembly.png：
  A 体大小 body_molA(t)：full 三 seed + 三个对照臂
  B 合成 vs 并入（终态，按 seed）
  C 抓取→反应→并入 漏斗（三 seed 合计，按臂）
  D 体的界面能量 E(t)（full 三 seed）
"""
import io
import json
import os

from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "images", "t80_assembly.png")
FONT = r"C:\Windows\Fonts\msyh.ttc"
FONTB = r"C:\Windows\Fonts\msyhbd.ttc"

ARMS = ["full", "farspawn", "nochem", "bare"]
SEEDS = [20261119, 20261120, 20261121]
COL = {"full": (32, 110, 180), "farspawn": (214, 120, 30), "nochem": (96, 150, 90), "bare": (140, 140, 140)}
LBL = {"full": "full 合成+并入", "farspawn": "farspawn 合成但远投", "nochem": "nochem 只抓取", "bare": "bare 无食物"}


def fnt(sz, bold=False):
    try:
        return ImageFont.truetype(FONTB if bold else FONT, sz)
    except Exception:
        return ImageFont.load_default()


def load():
    data = {}
    for arm in ARMS:
        for s in SEEDS:
            p = os.path.join(BASE, "t80_assembly_%s_s%d.json" % (arm, s))
            if os.path.exists(p):
                data[(arm, s)] = json.load(io.open(p, encoding="utf-8"))
    return data


class P(object):
    def __init__(self, d, box):
        self.d = d
        self.x0, self.y0, self.x1, self.y1 = box

    def axes(self, xmin, xmax, ymin, ymax, xt=(), yt=(), xlab="", ylab=""):
        d, x0, y0, x1, y1 = self.d, self.x0, self.y0, self.x1, self.y1
        d.rectangle([x0, y0, x1, y1], outline=(60, 60, 60), width=2)
        for xv, xl in xt:
            fx = self.xp(xv, xmin, xmax)
            d.line([fx, y1, fx, y1 + 6], fill=(60, 60, 60), width=2)
            w = d.textlength(xl, font=fnt(15))
            d.text((fx - w / 2, y1 + 9), xl, font=fnt(15), fill=(60, 60, 60))
        for yv, yl in yt:
            fy = self.yp(yv, ymin, ymax)
            d.line([x0 - 6, fy, x0, fy], fill=(60, 60, 60), width=2)
            w = d.textlength(yl, font=fnt(15))
            d.text((x0 - 9 - w, fy - 9), yl, font=fnt(15), fill=(60, 60, 60))
        if xlab:
            d.text((x1 - d.textlength(xlab, font=fnt(15)), y1 + 32), xlab, font=fnt(15), fill=(60, 60, 60))
        if ylab:
            d.text((x0, y0 - 30), ylab, font=fnt(15), fill=(60, 60, 60))

    def xp(self, xv, xmin, xmax):
        return self.x0 + (xv - xmin) / float(xmax - xmin) * (self.x1 - self.x0)

    def yp(self, yv, ymin, ymax):
        return self.y1 - (yv - ymin) / float(max(1e-9, ymax - ymin)) * (self.y1 - self.y0)


def render():
    data = load()
    W, H = 1800, 1160
    img = Image.new("RGB", (W, H), (252, 252, 250))
    d = ImageDraw.Draw(img)
    d.text((40, 22), "T80 组装体生长模拟：主体 A（多分子组装体）吞食小分子→合成新 A→并入自身", font=fnt(31, True), fill=(25, 25, 25))
    d.text((40, 66), "A=C3K3F2（8 原子、5 位点，自界面能 2.5）；食物 C2K2+CKF2 → 反应生成 C3K3F2；体基线 5~7 个 A；每臂 600 步 × 3 seed；闭合元素池（conservation_ok 全 True）",
           font=fnt(16), fill=(85, 85, 85))

    # ---- A: body_molA(t) ----
    pA = P(d, (96, 160, 860, 600))
    pA.axes(100, 720, 0, 22,
            [(120, "120"), (200, "200"), (300, "300"), (400, "400"), (500, "500"), (600, "600"), (720, "720")],
            [(0, "0"), (5, "5"), (10, "10"), (15, "15"), (20, "20")],
            xlab="t（步）", ylab="体中的 A 个数 body_molA")
    for arm in ARMS:
        for s in SEEDS:
            r = data.get((arm, s))
            if not r:
                continue
            pts = [(q["t"], q["body_molA"]) for q in r["time_series"]]
            xy = [(pA.xp(t, 100, 720), pA.yp(v, 0, 22)) for t, v in pts]
            if len(xy) >= 2:
                d.line(xy, fill=COL[arm], width=3 if arm == "full" else 2)
    lx, ly = 596, 452
    for i, arm in enumerate(ARMS):
        yy = ly + i * 24
        d.line([lx, yy + 8, lx + 26, yy + 8], fill=COL[arm], width=3 if arm == "full" else 2)
        d.text((lx + 32, yy), LBL[arm], font=fnt(14), fill=(60, 60, 60))
    d.text((96, 560), "粗线=full（三 seed：5→19 / 7→20 / 7→10）；细线=对照臂", font=fnt(15), fill=(70, 70, 70))

    # ---- B: 合成 vs 并入 ----
    pB = P(d, (980, 160, 1260, 600))
    pB.axes(-0.5, 2.5, 0, 22,
            [(0, "s19"), (1, "s20"), (2, "s21")],
            [(0, "0"), (5, "5"), (10, "10"), (15, "15"), (20, "20")],
            xlab="seed", ylab="分子数")
    for i, s in enumerate(SEEDS):
        r = data.get(("full", s))
        if not r:
            continue
        sm = r["summary"]
        joined = sm["body_molA"] - sm["baseline"]["body_molA"]
        bx = pB.xp(i, -0.5, 2.5)
        for val, col, off in [(sm["react"], (168, 190, 218), -34), (joined, (32, 110, 180), 4)]:
            h = abs(pB.yp(val, 0, 22) - pB.yp(0, 0, 22))
            d.rectangle([bx + off - 13, pB.yp(0, 0, 22) - h, bx + off + 13, pB.yp(0, 0, 22)], fill=col)
            d.text((bx + off - 9, pB.yp(0, 0, 22) - h - 22), str(val), font=fnt(14, True), fill=col)
    d.text((980, 648), "浅=合成（react） 深=并入体（body 增量）", font=fnt(15), fill=(70, 70, 70))

    # ---- C: 漏斗（三 seed 合计） ----
    pC = P(d, (1340, 160, 1740, 600))
    pC.axes(0, 110, -0.5, 3.5,
            [(0, "0"), (25, "25"), (50, "50"), (75, "75"), (100, "100")],
            [(0, "full"), (1, "farspawn"), (2, "nochem"), (3, "bare")],
            xlab="", ylab="臂")
    for i, arm in enumerate(ARMS):
        ts = [data[(arm, s)] for s in SEEDS if (arm, s) in data]
        if not ts:
            continue
        cap = sum(x["summary"]["captured"] for x in ts)
        rx = sum(x["summary"]["react"] for x in ts)
        join = sum(x["summary"]["body_molA"] - x["summary"]["baseline"]["body_molA"] for x in ts)
        for val, col, off in [(cap, (212, 186, 140), -0.24), (rx, (168, 190, 218), 0.0), (join, (32, 110, 180), 0.24)]:
            lo, hi = i + off - 0.11, i + off + 0.11
            ay, by = pC.yp(lo, -0.5, 3.5), pC.yp(hi, -0.5, 3.5)
            d.rectangle([pC.xp(0, 0, 110), min(ay, by), pC.xp(val, 0, 110), max(ay, by)], fill=col)
            if val:
                d.text((pC.xp(val, 0, 110) + 6, min(ay, by)), str(val), font=fnt(13, True), fill=col)
    d.text((1340, 648), "稻=抓取 浅蓝=反应 深蓝=并入（三 seed 合计，横轴次数）", font=fnt(15), fill=(70, 70, 70))

    # ---- D: E(t) ----
    pD = P(d, (96, 700, 860, 1090))
    pD.axes(100, 720, 0, 70,
            [(120, ""), (200, "200"), (400, "400"), (600, "600"), (720, "720")],
            [(0, "0"), (20, "20"), (40, "40"), (60, "60")],
            xlab="t（步）", ylab="体的界面能量 E")
    for s in SEEDS:
        r = data.get(("full", s))
        if not r:
            continue
        pts = [(q["t"], q["body_E"]) for q in r["time_series"]]
        xy = [(pD.xp(t, 100, 720), pD.yp(v, 0, 70)) for t, v in pts]
        d.line(xy, fill=(120, 160, 205), width=2)
    d.text((96, 1066), "E 随体长大持续上升（14~22 → 30~57），对照臂 E 基本持平", font=fnt(15), fill=(70, 70, 70))

    # ---- 说明 ----
    d.text((960, 700), "读图与结论", font=fnt(20, True), fill=(30, 30, 30))
    lines = [
        "1. full 臂：抓取小分子 → 体内缓冲池反应 C2K2+CKF2 → C3K3F2 → 新 A 放到体表空位并主动并入（assimilate）",
        "     体从 5~7 个 A 长到 10~20 个 A，元素守恒不破（conservation_ok=True）。",
        "2. 三个对照证明两个环节缺一不可：",
        "     farspawn（有合成但不并入，随机远投）→ 体不长大；",
        "     nochem（只抓取不合成）→ 体不长大；bare（无食物）→ 体不长大。",
        "3. 在这个 emergence 物理里，用户描述的「主体 A 的组装体吞食小分子合成新 A 并连入自身」",
        "    是**可以复现的**——但它只是「代谢生长」：没有边界膜、没有遗传模板、不能复制、",
        "    且抓取（capture）和并入（assimilate）是脚本化的主动步骤，其余动力学全部交给 emergence。",
        "4. 体是动态组装体：会短暂解体再重组（如 12→2→12），增长曲线呈台阶状。",
    ]
    for i, t in enumerate(lines):
        d.text((960, 740 + i * 30), t, font=fnt(16), fill=(60, 60, 60))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT, "PNG")
    print("saved", OUT, img.size)


if __name__ == "__main__":
    render()
