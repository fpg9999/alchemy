# -*- coding: utf-8 -*-
"""按四象限分组的径向力图：每象限 4 个实例。

红 = 引力作用半径（实心淡红 + 红圈）
蓝 = 斥力作用半径（实心 + 蓝圈）
蓝画在红之后，保证斥力范围可见。
"""
from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lattice_sim import four_values  # noqa: E402

PXC = 17.0
PANEL = 250
COLS = 4
RED = (200, 60, 50)
BLUE = (40, 100, 200)

QUADS = [
    ("引力强 · 引力远", lambda a, r, ra, rr: a >= r and ra >= rr),
    ("引力强 · 斥力远", lambda a, r, ra, rr: a >= r and rr > ra),
    ("斥力强 · 引力远", lambda a, r, ra, rr: r > a and ra >= rr),
    ("斥力强 · 斥力远", lambda a, r, ra, rr: r > a and rr > ra),
]


def font(sz):
    try:
        return ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", sz)
    except Exception:
        return ImageFont.load_default()


def pick_examples():
    rows = list(csv.DictReader(open("data/biomes/candidates/_union.csv",
                                   encoding="utf-8-sig")))
    groups = [[] for _ in QUADS]
    for r in rows:
        f = r["formula"]
        a, rep, ra, rr = four_values(f)
        for i, (_, test) in enumerate(QUADS):
            if test(a, rep, ra, rr):
                groups[i].append(f)
                break
    out = []
    for g in groups:
        # 取力矩范围分散的 4 个
        scored = sorted(g, key=lambda f: four_values(f)[2] + four_values(f)[3])
        if len(scored) >= 4:
            idx = [0, len(scored)//3, 2*len(scored)//3, len(scored)-1]
            out.append([scored[i] for i in idx])
        else:
            out.append(scored)
    return out


def panel(f, lf, sf):
    a, r, ra, rr = four_values(f)
    img = Image.new("RGBA", (PANEL, PANEL), (252, 252, 252, 255))
    cx = cy = PANEL // 2
    ov = Image.new("RGBA", (PANEL, PANEL), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    # 引力（先画，淡红实心 + 红圈）
    Ra = ra * PXC
    d.ellipse([cx - Ra, cy - Ra, cx + Ra, cy + Ra], fill=RED + (60,))
    # 斥力（后画，更实的蓝 + 蓝圈）
    Rr = rr * PXC
    d.ellipse([cx - Rr, cy - Rr, cx + Rr, cy + Rr], fill=BLUE + (95,))
    img = Image.alpha_composite(img, ov)
    d2 = ImageDraw.Draw(img)
    d2.ellipse([cx - Ra, cy - Ra, cx + Ra, cy + Ra], outline=RED + (255,), width=2)
    d2.ellipse([cx - Rr, cy - Rr, cx + Rr, cy + Rr], outline=BLUE + (255,), width=3)
    # 1 格虚线
    r1 = PXC
    for k in range(0, 360, 12):
        d2.line([cx + r1*math.cos(math.radians(k)), cy + r1*math.sin(math.radians(k)),
                 cx + r1*math.cos(math.radians(k+6)), cy + r1*math.sin(math.radians(k+6))],
                fill=(40, 40, 40, 200), width=1)
    d2.ellipse([cx-4, cy-4, cx+4, cy+4], fill=(30, 30, 30, 255))
    d2.text((7, 5), f, fill=(0, 0, 0, 255), font=lf)
    d2.text((7, PANEL - 46), f"A={a:.2f}  R={r:.2f}", fill=(0, 0, 0, 255), font=sf)
    d2.text((7, PANEL - 28), f"r吸={ra:.2f}  r斥={rr:.2f}", fill=(60, 60, 60, 255), font=sf)
    return img


def main():
    examples = pick_examples()
    big = font(18)
    lf = font(14)
    sf = font(12)
    head = 34
    W = COLS * PANEL + 30
    H = 70 + len(QUADS) * (PANEL + head)
    sheet = Image.new("RGBA", (W, H), (252, 252, 252, 255))
    d = ImageDraw.Draw(sheet)
    d.text((20, 12), "四种力学象限（每格 4 个实例）", fill=(0, 0, 0, 255), font=big)
    d.text((20, 40),
           "红圈 = 引力半径   蓝圈 = 斥力半径（画在红之上）   虚线 = 1 格   蓝超出红 = 斥力更远",
           fill=(70, 70, 70, 255), font=font(12))

    for qi, (name, _) in enumerate(QUADS):
        y0 = 70 + qi * (PANEL + head)
        d.rectangle([10, y0, W - 10, y0 + head - 4], fill=(238, 238, 242, 255))
        d.text((18, y0 + 6), f"{qi+1}. {name}", fill=(20, 20, 20, 255), font=font(16))
        for ci, f in enumerate(examples[qi][:COLS]):
            p = panel(f, lf, sf)
            x = 15 + ci * PANEL
            y = y0 + head
            sheet.paste(p, (x, y), p)
            d.rectangle([x, y, x + PANEL - 1, y + PANEL - 1], outline=(220, 220, 220, 255))

    out = Path("images/force_quadrants.png")
    sheet.convert("RGB").save(out)
    print("saved", out)
    for qi, (name, _) in enumerate(QUADS):
        print(f"  {qi+1}. {name}: {examples[qi][:COLS]}")


if __name__ == "__main__":
    main()
