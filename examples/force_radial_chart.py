# -*- coding: utf-8 -*-
"""径向力场图：分子在中心，蓝色实心圆 = 斥力半径，红色圆环 = 引力半径。

每格 20px；虚线圆 = 1 格（相邻分子间距），用来判断"邻居落在哪个区"。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lattice_sim import four_values  # noqa: E402

MOLS = ["OXC", "OXCPWKA", "LF", "OK", "PK", "L2", "CF", "WA",
        "XA", "X2", "O2X2C2F2", "OCF2", "O2XP2WK2A2", "OXPWKAF",
        "O9X11CK14A4", "KAF"]
COLS = 4
PANEL = 270
PXC = 20.0              # 每格像素
RED = (220, 80, 70)
BLUE = (70, 130, 210)


def font(sz):
    try:
        return ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", sz)
    except Exception:
        return ImageFont.load_default()


def panel(f, label_font, small_font):
    a, r, da, dr = four_values(f)
    D = max(da, dr)
    img = Image.new("RGBA", (PANEL, PANEL), (252, 252, 252, 255))
    ov = Image.new("RGBA", (PANEL, PANEL), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    cx = cy = PANEL // 2

    # 新模型：两项各自独立衰减
    #   红圆 = 引力作用半径 r_att
    #   蓝圆 = 斥力作用半径 r_rep
    Rr = D * PXC
    Ra = da * PXC
    d.ellipse([cx - Rr, cy - Rr, cx + Rr, cy + Rr], fill=BLUE + (80,))
    d.ellipse([cx - Ra, cy - Ra, cx + Ra, cy + Ra], fill=RED + (80,))
    img = Image.alpha_composite(img, ov)
    d2 = ImageDraw.Draw(img)

    # 1 格虚线圆
    r1 = 1.0 * PXC
    for k in range(0, 360, 12):
        import math
        x1 = cx + r1 * math.cos(math.radians(k))
        y1 = cy + r1 * math.sin(math.radians(k))
        x2 = cx + r1 * math.cos(math.radians(k + 6))
        y2 = cy + r1 * math.sin(math.radians(k + 6))
        d2.line([x1, y1, x2, y2], fill=(30, 30, 30, 220), width=2)

    # 中心粒子
    d2.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(30, 30, 30, 255))

    # 文字
    d2.text((8, 6), f, fill=(0, 0, 0, 255), font=label_font)
    d2.text((8, PANEL - 52), f"A={a:.1f}  R={r:.1f}", fill=(0, 0, 0, 255), font=small_font)
    d2.text((8, PANEL - 32), f"吸半径 {da:.2f}  斥半径 {dr:.2f}", fill=(80, 80, 80, 255), font=small_font)
    d2.text((8, PANEL - 14),
            ("吸更远" if da >= dr else "斥更远"),
            fill=(80, 80, 80, 255), font=small_font)
    return img


def main():
    rows = (len(MOLS) + COLS - 1) // COLS
    W = COLS * PANEL + 40
    H = rows * PANEL + 96
    sheet = Image.new("RGBA", (W, H), (252, 252, 252, 255))
    d = ImageDraw.Draw(sheet)
    big = font(20)
    f14 = font(14)
    f13 = font(13)

    d.text((20, 12), "径向力场：分子在中心", fill=(0, 0, 0, 255), font=big)
    d.text((20, 42),
           "红圆 = 引力作用半径   蓝圆 = 斥力作用半径   两圆重叠区 = 两种力同时作用   虚线 = 1 格",
           fill=(70, 70, 70, 255), font=f13)

    for i, f in enumerate(MOLS):
        p = panel(f, f14, f13)
        x = 20 + (i % COLS) * PANEL
        y = 70 + (i // COLS) * PANEL
        sheet.paste(p, (x, y), p)
        d.rectangle([x, y, x + PANEL - 1, y + PANEL - 1], outline=(220, 220, 220, 255))

    out = Path("images/force_radial.png")
    sheet.convert("RGB").save(out)
    print("saved", out)


if __name__ == "__main__":
    main()
