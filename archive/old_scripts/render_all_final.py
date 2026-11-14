# -*- coding: utf-8 -*-
"""最终总表图：29 种聚素物质一张图，并高亮 秩3晶冰 / 秩3晶2冰"""
import json
import math
import sys
from collections import Counter

from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import render_final as RF

S3 = math.sqrt(3)
FONT = RF.FONT
FONT_B = RF.FONT_B
CN = RF.CN
FILL = RF.FILL
BONDC = RF.BONDC
font = RF.font
text_center = RF.text_center
draw_formula = RF.draw_formula
draw_molecule = RF.draw_molecule

HIGHLIGHT = {"O3XC", "O3X2C"}
RECIPE = {"O3XC": "投料：秩晶冰 + 秩---秩", "O3X2C": "投料：秩晶冰 + 秩2晶"}


def main():
    data = json.load(open(r"G:\AI work\deepseek\work1\alchemy\substances.json", encoding="utf-8"))
    # 排序：按元素组成分组，单质→秩晶→秩冰→晶冰→三元素
    def group_key(it):
        v = tuple(it["vec"])
        o, x, c = v
        if o and x and c:
            g = 4
        elif o and x:
            g = 1
        elif o and c:
            g = 2
        elif x and c:
            g = 3
        else:
            g = 0
        return (g, sum(v), v)

    items = sorted(data, key=group_key)
    ncol = 6
    pw, ph = 282, 320
    left, top = 26, 150
    nrow = (len(items) + ncol - 1) // ncol
    W = left + ncol * pw + 22
    H = top + nrow * ph + 26
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    d.text((26, 18), "聚素 · 自然反应可产出物质总表（29 种）", font=font(FONT_B, 30), fill="#111111")
    d.text((26, 62), "规则 1~8 全部启用；穷举总原子 ≤36 的所有投料 + 产物再投料闭包，无并列、无规则 9。",
           font=font(FONT, 18), fill="#555555")
    d.text((26, 90), "★ 高亮的两种：秩3晶冰（O3XC，对应你左图）与 秩3晶2冰（O3X2C，对应你右图）—— 确实在清单内。",
           font=font(FONT, 18), fill="#b8860b")
    d.text((26, 116), "红平行线 = 短键（1~3 根）；绿=秩、橙=晶、蓝=冰；右上角为该分子的原子数。",
           font=font(FONT, 17), fill="#888888")

    for i, it in enumerate(items):
        r, c = divmod(i, ncol)
        x0 = left + c * pw + 3
        y0 = top + r * ph + 3
        w = pw - 6
        h = ph - 6
        hi = it["formula"] in HIGHLIGHT
        d.rectangle([x0, y0, x0 + w, y0 + h],
                    fill="#fffdf2" if hi else "white",
                    outline="#e8b923" if hi else "#dddddd",
                    width=3 if hi else 1)
        d.text((x0 + 10, y0 + 7), f"{i+1:02d}", font=font(FONT_B, 16), fill="#999999")
        text_center(d, x0 + w - 40, y0 + 15, f"{it['natoms']}原子", font(FONT, 14), "#999999")
        if hi:
            text_center(d, x0 + w - 30, y0 + 15, "★", font(FONT_B, 20), "#e8a000")
        draw_molecule(d, it, (x0 + 6, y0 + 24, w - 12, h - 96))
        draw_formula(d, x0 + w / 2, y0 + h - 62, it["formula"], 25, "#111111")
        draw_formula(d, x0 + w / 2, y0 + h - 32, it["zh"], 19, "#555555", bold=False)
        if hi:
            d.text((x0 + 10, y0 + h - 12), RECIPE[it["formula"]], font=font(FONT, 13), fill="#b8860b")

    img.save(r"G:\AI work\deepseek\work1\alchemy\final_all_29.png")
    print("saved final_all_29.png")


if __name__ == "__main__":
    main()
