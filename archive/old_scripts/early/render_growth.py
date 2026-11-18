# -*- coding: utf-8 -*-
"""render_growth：画"投料总原子 T vs 最大单分子原子数"图，证明跨类范围无限。"""
import json
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import render_final as RF

BASE = r"G:\AI work\deepseek\work1\alchemy"
FONT, FONT_B = RF.FONT, RF.FONT_B
font, text_center = RF.font, RF.text_center


def load(path, key="T"):
    d = json.load(open(path, encoding="utf-8"))
    pts = []
    for x in d:
        pts.append((x[key], x["natoms"], x["formula"]))
    return pts


def main():
    data = {
        "范围3 聚-散": (load(BASE + r"\scope3_big_examples.json"), "#c0392b"),
        "范围4 聚-动": (load(BASE + r"\scope4_big_examples.json"), "#d68910"),
        "范围5 动-散": (load(BASE + r"\scope5_big_examples.json"), "#7d3f9c"),
        "范围6 三类": (load(BASE + r"\scope6_big_examples.json"), "#1f7a7a"),
    }
    W, H = 1250, 780
    left, top, right, bottom = 110, 130, 60, 90
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((30, 18), "跨类范围无限性：投料越大，最大单分子越大（不封顶）", font=font(FONT_B, 30), fill="#111111")
    d.text((30, 60), "每个点 = 一个实测成功的“一锅一分子”投料：横轴=投料总原子数 T，纵轴=产物最大分子原子数。",
           font=font(FONT, 17), fill="#555555")
    d.text((30, 108), "三条两两跨类线几乎贴着 y=x（整锅可成一个分子）；范围6（三类）同样一路增长到 34 原子。",
           font=font(FONT, 16), fill="#777777")
    xmax, ymax = 40, 40
    px0, py0 = left, top
    px1, py1 = W - right, H - bottom

    def X(v):
        return px0 + (v / xmax) * (px1 - px0)

    def Y(v):
        return py1 - (v / ymax) * (py1 - py0)

    # 网格
    for v in range(0, 41, 5):
        d.line([(X(v), py0), (X(v), py1)], fill="#eeeeee")
        d.line([(px0, Y(v)), (px1, Y(v))], fill="#eeeeee")
        text_center(d, X(v), py1 + 18, str(v), font(FONT, 15), "#888888")
        text_center(d, px0 - 22, Y(v), str(v), font(FONT, 15), "#888888")
    d.line([(px0, py1), (px1, py1)], fill="#333333", width=2)
    d.line([(px0, py0), (px0, py1)], fill="#333333", width=2)
    d.text((px1 - 170, py1 + 44), "投料总原子 T", font=font(FONT_B, 17), fill="#333333")
    # y=x 参考线
    d.line([(X(0), Y(0)), (X(ymax), Y(ymax))], fill="#bbbbbb", width=1)
    d.text((X(33), Y(36)), "y = x", font=font(FONT, 15), fill="#aaaaaa")

    style = {"范围3 聚-散": (5, 2), "范围4 聚-动": (4, 1), "范围5 动-散": (4, 1), "范围6 三类": (3, 0)}
    for i, (name, (pts, color)) in enumerate(data.items()):
        pts = sorted(pts)
        rad, wid = style[name]
        for (t, n, f) in pts:
            d.ellipse([X(t) - rad, Y(n) - rad, X(t) + rad, Y(n) + rad], fill=color)
        for a, b in zip(pts, pts[1:]):
            d.line([(X(a[0]), Y(a[1])), (X(b[0]), Y(b[1]))], fill=color, width=wid)
        lx = px1 - 250
        ly = py0 + 16 + i * 26
        if name == "范围6 三类":
            d.rectangle([lx, ly, lx + 14, ly + 10], outline=color, width=2)
        else:
            d.rectangle([lx, ly, lx + 14, ly + 10], fill=color)
        d.text((lx + 22, ly - 4), name, font=font(FONT, 17), fill="#333333")
    # 有限子集封顶参考
    d.line([(px0, Y(16)), (px1, Y(16))], fill="#999999", width=1)
    d.text((px0 + 10, Y(16) - 26), "有限元素组合封顶带（≤16 原子，见 RESULTS 的子集表）",
           font=font(FONT, 15), fill="#888888")
    img.save(BASE + r"\growth_infinity.png")
    print("saved growth_infinity.png")


if __name__ == "__main__":
    main()
