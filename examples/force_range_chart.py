# -*- coding: utf-8 -*-
"""引力/斥力范围图示：蓝 = 斥力区，红 = 引力区。

横轴是距离（格子单位），纵向列出各分子。竖虚线 = 1 格（格子间距）。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lattice_sim import four_values  # noqa: E402

BETA = 0.3
MOLS = ["OXC", "OXCPWKA", "LF", "OK", "PK", "L2", "CF", "WA", "XA", "X2",
        "O2X2C2F2", "OCF2", "O2XP2WK2A2", "OXPWKAF", "O9X11CK14A4", "KAF"]

W, H = 1080, 780
LEFT, RIGHT = 190, 1010
TOP = 110
ROWH = 36
SCALE = (RIGHT - LEFT) / 8.2          # 0~8.2 格

BLUE = (70, 130, 210)
RED = (220, 80, 70)
GRID_LINE = (120, 120, 120)
GREY = (90, 90, 90)


def main():
    img = Image.new("RGB", (W, H), (252, 252, 252))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 14)
        big = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 20)
    except Exception:
        font = ImageFont.load_default()
        big = font

    d.text((30, 20), "分子间作用范围（蓝 = 斥力区，红 = 引力区）", fill=(0, 0, 0), font=big)
    d.text((30, 52), "横轴：距离（格子单位）  竖虚线 = 1 格（相邻分子的间距）", fill=GREY, font=font)
    # 图例
    d.rectangle([30, 78, 60, 92], fill=BLUE)
    d.text((68, 77), "斥力区（0 ~ 0.3·D）", fill=(0, 0, 0), font=font)
    d.rectangle([230, 78, 260, 92], fill=RED)
    d.text((268, 77), "引力区（0.3·D ~ D）", fill=(0, 0, 0), font=font)

    # 网格刻度
    for g in range(0, 9):
        x = LEFT + g * SCALE
        d.line([x, TOP - 10, x, TOP + ROWH * len(MOLS) + 4], fill=(225, 225, 225))
        d.text((x - 4, TOP - 26), str(g), fill=GREY, font=font)

    # 1 格竖线
    x1 = LEFT + 1 * SCALE
    for yy in range(TOP - 10, TOP + ROWH * len(MOLS) + 4, 8):
        d.line([x1, yy, x1, yy + 4], fill=(30, 30, 30), width=2)

    for i, f in enumerate(MOLS):
        a, r, da, dr = four_values(f)
        D = max(da, dr)
        y = TOP + i * ROWH
        # 标签
        d.text((20, y + 6), f, fill=(0, 0, 0), font=font)
        # 强度
        d.text((120, y + 6), f"A{a:.1f}", fill=RED, font=font)
        d.text((155, y + 8), f"R{r:.1f}", fill=BLUE, font=font)
        # 蓝：斥力区
        xb = LEFT + 0.3 * D * SCALE
        d.rectangle([LEFT, y + 8, xb, y + 26], fill=BLUE)
        # 红：引力区
        xr = LEFT + D * SCALE
        d.rectangle([xb, y + 8, xr, y + 26], fill=RED)
        # D 标注
        d.text((xr + 5, y + 9), f"{D:.2f}", fill=GREY, font=font)

    out = Path("images/force_ranges.png")
    img.save(out)
    print("saved", out)


if __name__ == "__main__":
    main()
