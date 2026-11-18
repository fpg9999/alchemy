# -*- coding: utf-8 -*-
"""画跨大类例子图"""
import sys
from PIL import Image, ImageDraw
sys.path.insert(0, r"G:\AI work\deepseek\work1\alchemy")
import fig_notation as FN
from figures import font, FONT, FONT_BOLD
import notation2 as N2

EX = [
    ("秩电3", "聚-动：全用 C 键", [("L", 0, 0, ["C2"]), ("L", 0, 6, ["C6"]),
                              ("O", 1, 3, ["C4", "C8", "C12"]), ("L", 3, 3, ["C10"])]),
    ("势冰3", "聚-动：全用 S 键", [("C", 0, 0, ["S3"]), ("C", 1, 3, ["S7"]),
                              ("C", 2, 0, ["S11"]), ("P", 1, 1, ["S1", "S5", "S9"])]),
    ("冰2流", "聚-动：全用 S 键", [("W", 0, 0, ["S1", "S3"]), ("C", 0, 2, ["S7"]),
                              ("C", 1, 1, ["S9"])]),
    ("秩冰2电", "同一分子：S 与 C 混用", [("C", 0, 0, ["S3"]), ("C", 1, 3, ["S7"]),
                                  ("O", 1, 1, ["S1", "S9", "C4"]), ("L", 3, 1, ["C10"])]),
    ("流焰2", "动-散：全用 L 键", [("W", 0, 0, ["L1", "L3"]), ("F", 0, 4, ["L7"]),
                              ("F", 2, 2, ["L9"])]),
    ("沌电3", "动-散：全用 C 键", [("L", 0, 0, ["C2"]), ("L", 0, 6, ["C6"]),
                              ("K", 1, 3, ["C4", "C8", "C12"]), ("L", 3, 3, ["C10"])]),
]


def main(path):
    ncol, nrow = 3, 2
    pw, ph = 360, 350
    left, top = 30, 128
    W = left + ncol * pw + 24
    Hh = top + nrow * ph + 34
    img = Image.new("RGB", (W, Hh), "white")
    d = ImageDraw.Draw(img)
    d.text((26, 14), "跨大类的例子：一根键的键型，只要两端有一方“支持”就行",
           font=font(FONT_BOLD, 26), fill="#111111")
    d.text((26, 50), "红粗线 = 短键 S；绿线 = 角键 C；紫虚线 = 长键 L（中间格必须为空）。已逐条校验：键数=价数、两端方向互认、跨类键型合法。",
           font=font(FONT, 17), fill="#666666")
    d.text((26, 78), "注意：相邻但没画键 = 没关系（你已确认）；同一个分子里可以同时出现 S 和 C。",
           font=font(FONT, 17), fill="#888888")
    for i, (name, note, entries) in enumerate(EX):
        r, c = divmod(i, ncol)
        x = left + c * pw
        y = top + r * ph
        d.rectangle([x + 2, y + 2, x + pw - 2, y + ph - 2], outline="#e8e8e8")
        FN.draw_formula(d, x + 12, y + 14, name, 23, "#111111", align="left")
        d.text((x + 12, y + 42), note, font=font(FONT, 16), fill="#888888")
        FN.draw_mol(d, entries, (x + 6, y + 66, pw - 12, ph - 140), s_cap=30.0)
        sym, zh = FN.build_formula(entries)
        FN.draw_formula(d, x + pw / 2, y + ph - 64, sym, 26, "#111111")
        FN.draw_formula(d, x + pw / 2, y + ph - 30, zh, 18, "#777777", bold=False)
    img.save(path)
    print("saved", path)


if __name__ == "__main__":
    main(r"G:\AI work\deepseek\work1\alchemy\fig5_mixed.png")
