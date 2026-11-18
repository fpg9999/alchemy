# -*- coding: utf-8 -*-
"""T75 渲染：方块世界的规则页 + 大分子方块图 + 总览。"""
import math
from collections import Counter

import t68_shapes as S
import t69_pieces as P
import t75_attrs as AT
import t75_tiles as T

INK = (38, 50, 64)
INK2 = (104, 120, 136)
HCOL = (0xC0, 0x39, 0x2B)
VCOL = (0x1E, 0x84, 0x49)
TCOL = (0x8E, 0x44, 0xAD)


def _bar(cv, x, y, w, h, frac, col, label, value, note=""):
    cv.d.rounded_rectangle([x, y, x + w, y + h], radius=h / 2, fill=(240, 243, 247), outline=(224, 230, 236))
    fw = max(2, int(w * max(0.0, min(1.0, frac))))
    cv.d.rounded_rectangle([x, y, x + fw, y + h], radius=h / 2, fill=col)
    cv.txt(x, y - 4, label, 10.5, True, col, "ld")
    cv.txt(x + w + 8, y + h / 2, value, 12, True, INK, "lm")
    if note:
        cv.txt(x, y + h + 6, note, 9, False, INK2, "la")


def page_rules(path="images/t75_rules.png"):
    W, H = 1600, 1010
    cv = S.Canvas(W, H, (255, 255, 255))
    cv.txt(40, 46, "T75 方块世界：每个骨架 = 地图上的 1 个单位方块", 26, True, INK, "lm")
    cv.txt(40, 78, "物质由一个或几个单位方块拼成；方块内部用家族纹样区分；方块之间用桥/融合连接；"
                   "一价端帽是方块外缘的小方钉。", 12.5, False, INK2, "lm")

    # A. 单个方块解剖
    cv.txt(40, 128, "A. 一个方块里放什么", 16, True, INK, "lm")
    x0, y0, s = 70, 168, 168
    T.draw_tile(cv, x0, y0, s, {"family": "OPK", "n": 6, "blocks": [1, 2], "block_forms": ["OP4K"]},
                S.FAMILY["OPK"]["col"])
    cv.txt(x0 + s + 26, y0 + 16, "① 方块外框 = 1 个地图单位；颜色/纹样 = 骨架家族（7 种）", 11.5, False, INK, "lm")
    cv.txt(x0 + s + 26, y0 + 42, "② 内部纹样：纯秩三角 / 纯势圆 / 纯散五角 / 秩势拱 / 秩散盾 / 势散圆角方 / 秩势散六边", 11.5, False, INK, "lm")
    cv.txt(x0 + s + 26, y0 + 68, "③ 右上小方点 = 这个骨架含几个 6 级块（融合的块数）", 11.5, False, INK, "lm")
    cv.txt(x0 + s + 26, y0 + 94, "④ 底部文字 = 块形态（38 库里的编号/公式），顶部 = 三价原子数", 11.5, False, INK, "lm")

    # B. 7 家族方块
    cv.txt(40, 400, "B. 七种骨架家族方块（同一单位大小，纹样不同）", 16, True, INK, "lm")
    fams = ["O", "P", "K", "OP", "OK", "PK", "OPK"]
    for i, fam in enumerate(fams):
        x = 70 + i * 210
        T.draw_tile(cv, x, 440, 150, {"family": fam, "n": 4, "blocks": [1], "block_forms": [fam + "2"]},
                    S.FAMILY[fam]["col"], labels=False)
        cv.txt(x + 75, 610, S.FAMILY[fam]["zh"], 13, True, INK, "mm")
        cv.txt(x + 75, 630, fam, 10, False, INK2, "mm")

    # C. 连接件
    cv.txt(40, 690, "C. 方块之间怎么连（画在共用的边上）", 16, True, INK, "lm")
    demo = [
        ("X 晶", "短粗焊块（最硬：两块直接咬死）", lambda cv, x, y: T.draw_bridge_on_edge(cv, x, y, 120, "h", ["X"])),
        ("W 流", "可拉伸椭圆肌腱（能弯）", lambda cv, x, y: T.draw_bridge_on_edge(cv, x, y, 120, "h", ["W"])),
        ("A 气", "沿边的细长薄膜（隔空软连）", lambda cv, x, y: T.draw_bridge_on_edge(cv, x, y, 120, "h", ["A"])),
        ("融合", "两块骨架在同一边焊死（焊纹）", lambda cv, x, y: T.draw_weld(cv, x, y, 120, "h")),
    ]
    for i, (name, desc, fn) in enumerate(demo):
        x = 90 + i * 390
        a, b = (x, 760), (x + 120, 760)
        S.Canvas(10, 10).d.rectangle([0, 0, 1, 1], fill=None)
        cv.d.rectangle([a[0] - 60, a[1] - 60, a[0], a[1] + 60], fill=(245, 249, 252), outline=(180, 190, 200))
        cv.d.rectangle([a[0], a[1] - 60, a[0] + 60, a[1] + 60], fill=(245, 249, 252), outline=(180, 190, 200))
        fn(cv, a[0], a[1])
        cv.txt(a[0] + 60, a[1] + 74, name, 13, True, INK, "mm")
        cv.txt(a[0] + 60, a[1] + 94, desc, 9.5, False, INK2, "mm")

    # D. 端帽
    cv.txt(40, 895, "D. 一价端帽 = 方块外缘的小方钉：冰C 三角钉 / 焰F 方钉 / 电L 细椭圆钉", 13, True, INK, "lm")
    for i, el in enumerate("CFL"):
        x = 1100 + i * 150
        cv.d.rectangle([x - 60, 862, x, 922], fill=(245, 249, 252), outline=(180, 190, 200))
        T.draw_stud(cv, x, 892, 120, (1, 0), el)
        cv.txt(x + 20, 944, {"C": "冰 C", "F": "焰 F", "L": "电 L"}[el], 10, True, INK, "mm")

    # E. 属性
    cv.txt(40, 972, "E. 属性值：硬度 = Σ 三价原子×权重(O1.2/P0.9/K0.6)；粘性 = Σ 二价(X1.0/W1.4/A0.4)；"
                    "温度 = Σ 一价(C-2.0/L0.5/F3.0，负=冷)", 11, False, INK, "lm")
    cv.save(path)
    print("saved", path)


def page_molecules(path="images/t75_molecules.png", picks=None):
    data = P.load_data()
    mols = data["molecules"]
    by = {m["mid"]: m for m in mols}
    if picks is None:
        picks = ["G13", "G14", "G16", "G23", "G24", "G33", "G17", "G19", "G20", "G21", "G27", "G32",
                 "G18", "G25", "G26", "G30", "G31", "G34"]
    picks = [p for p in picks if p in by]
    cw, ch = 780, 470
    cols = 2
    n = len(picks)
    nrows = (n + cols - 1) // cols
    cv = S.Canvas(40 + cols * cw, 190 + nrows * ch, (255, 255, 255))
    cv.txt(40, 46, "T75 大分子的方块形态：每个骨架就是一个单位方块", 26, True, INK, "lm")
    cv.txt(40, 78, "硬度由三价元素决定、粘性由二价、温度由一价；方块之间用 X 焊块 / W 肌腱 / A 薄膜 / 融合焊纹相连，"
                   "一价端帽是外缘的小方钉。", 12.3, False, INK2, "lm")
    hr, vr, tr = AT.norm_ranges(mols)

    for i, mid in enumerate(picks):
        mol = by[mid]
        cc, r = i % cols, i // cols
        x = 40 + cc * cw
        y = 150 + r * ch
        cv.d.rounded_rectangle([x, y, x + cw - 18, y + ch - 18], radius=12,
                               fill=(252, 253, 255), outline=(226, 232, 238))
        cv.txt(x + 16, y + 22, "%s  %s" % (mid, mol["formula"]), 17, True, INK, "lm")
        T.draw_molecule(cv, (x + 10, y + 40, 470, ch - 66), mol, max_tile=124)
        # 属性
        a = AT.attrs(Counter(mol["atoms"]))
        px, py = x + 500, y + 54
        cv.txt(px, py - 14, "属性", 14, True, INK, "lm")
        hf = (a["hardness"] - hr[0]) / max(1e-6, hr[1] - hr[0])
        vf = (a["viscosity"] - vr[0]) / max(1e-6, vr[1] - vr[0])
        tf = (a["temperature"] - tr[0]) / max(1e-6, tr[1] - tr[0])
        cv.txt(px, py + 6, "硬度", 11, True, HCOL, "lm")
        cv.txt(px + 44, py + 6, "%.2f" % a["hardness"], 13, True, INK, "lm")
        cv.d.rounded_rectangle([px + 120, py, px + 250, py + 12], radius=6, fill=(243, 246, 249), outline=(226, 232, 238))
        cv.d.rounded_rectangle([px + 120, py, px + 120 + max(3, int(130 * hf)), py + 12], radius=6, fill=HCOL)
        cv.txt(px, py + 28, "粘性", 11, True, VCOL, "lm")
        cv.txt(px + 44, py + 28, "%.2f" % a["viscosity"], 13, True, INK, "lm")
        cv.d.rounded_rectangle([px + 120, py + 22, px + 250, py + 34], radius=6, fill=(243, 246, 249), outline=(226, 232, 238))
        cv.d.rounded_rectangle([px + 120, py + 22, px + 120 + max(3, int(130 * vf)), py + 34], radius=6, fill=VCOL)
        cv.txt(px, py + 50, "温度", 11, True, TCOL, "lm")
        cv.txt(px + 44, py + 50, "%+.2f" % a["temperature"], 13, True, INK, "lm")
        cv.d.rounded_rectangle([px + 120, py + 44, px + 250, py + 56], radius=6, fill=(243, 246, 249), outline=(226, 232, 238))
        cv.d.rounded_rectangle([px + 120, py + 44, px + 120 + max(3, int(130 * tf)), py + 56], radius=6, fill=TCOL)
        # 元素拆分
        yy = py + 78
        for key, col, zh in (("hardness", HCOL, "硬度"), ("viscosity", VCOL, "粘性"), ("temperature", TCOL, "温度")):
            parts = a["parts"][key]
            if not parts:
                cv.txt(px, yy, "%s：无对应价数元素" % zh, 9.5, False, INK2, "lm")
            else:
                s2 = " + ".join("%s×%d(%.1f)" % (nm, c, w) for nm, c, w in parts)
                cv.txt(px, yy, "%s：%s" % (zh, s2), 9.5, False, INK2, "lm")
            yy += 16
        skn = len(mol["skeletons"])
        cv.txt(px, py + 134, "方块数 %d · 桥 %d · 融合 %d · 端帽 %d" % (
            skn, len(mol["bridges"]),
            sum(1 for sk in mol["skeletons"] if sk.get("n_fusion_bonds")),
            len(mol["decoration"].get("mono", []))), 9.5, False, INK2, "lm")
        fams = sorted({(sk.get("family") or "?") for sk in mol["skeletons"]})
        cv.txt(px, py + 152, "家族：" + " / ".join(S.FAMILY.get(f, {}).get("zh", f) for f in fams),
               9.5, False, INK2, "lm")
    cv.save(path)
    print("saved", path)


def page_overview(path="images/t75_overview.png", cols=6, rows=6):
    data = P.load_data()
    mols = data["molecules"][: cols * rows]
    cw, ch = 262, 268
    W = 40 + cols * cw
    H = 150 + rows * ch
    cv = S.Canvas(W, H, (255, 255, 255))
    cv.txt(40, 46, "T75 方块世界 · 36 个稳定大分子的方块形态总览", 26, True, INK, "lm")
    cv.txt(40, 78, "每格一个分子：方块 = 骨架，共用边上的小件 = 桥/融合，外缘小方钉 = 一价端帽；数值为硬度/粘性/温度。",
           12, False, INK2, "lm")
    for i, mol in enumerate(mols):
        cc, r = i % cols, i // cols
        x = 40 + cc * cw
        y = 112 + r * ch
        cv.d.rectangle([x, y, x + cw - 10, y + ch - 12], outline=(230, 235, 241))
        T.draw_molecule(cv, (x + 4, y + 22, cw - 22, ch - 74), mol, show_attrs=False, max_tile=44)
        a = AT.attrs(Counter(mol["atoms"]))
        cv.txt(x + 6, y + 14, mol["mid"], 11, True, INK, "lm")
        cv.txt(x + 6, y + ch - 56, "硬度 %.1f · 粘性 %.1f · 温度 %+.1f" % (a["hardness"], a["viscosity"], a["temperature"]),
               8.6, False, INK2, "lm")
        cv.txt(x + 6, y + ch - 40, "%d 方块" % len(mol["skeletons"]), 8.6, False, INK2, "lm")
    cv.save(path)
    print("saved", path)


def main():
    page_rules()
    page_molecules()
    page_overview()


if __name__ == "__main__":
    main()
