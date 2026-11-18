# -*- coding: utf-8 -*-
"""T75b 渲染：属性按骨架计算（桥不计入）。"""
import math

import t68_shapes as S
import t69_pieces as P
import t75b_attrs as SA
import t75_tiles as T

INK = (38, 50, 64)
INK2 = (104, 120, 136)
HCOL = (0xC0, 0x39, 0x2B)
VCOL = (0x1E, 0x84, 0x49)
TCOL = (0x8E, 0x44, 0xAD)

MOLS = None
RNG = None


def _load():
    global MOLS, RNG
    if MOLS is None:
        MOLS = P.load_data()["molecules"]
        RNG = SA.ranges(MOLS)
    return MOLS, RNG


def page_rules(path="images/t75b_rules.png"):
    cv = S.Canvas(1600, 1010, (255, 255, 255))
    cv.txt(40, 46, "T75 方块世界：每个骨架 = 1 个单位方块，属性按骨架算", 26, True, INK, "lm")
    cv.txt(40, 78, "物质由单位方块拼成；方块内部用家族纹样区分；方块之间用桥/融合连接；一价端帽是方块外缘的小方钉。",
           12.5, False, INK2, "lm")

    cv.txt(40, 128, "A. 一个方块里放什么", 16, True, INK, "lm")
    x0, y0, s = 70, 168, 168
    T.draw_tile(cv, x0, y0, s, {"family": "OPK", "n": 6, "blocks": [1, 2], "block_forms": ["OP4K"]},
                S.FAMILY["OPK"]["col"])
    lines = [
        "① 方块外框 = 1 个地图单位；颜色/纹样 = 骨架家族（7 种）",
        "② 内部纹样：纯秩三角 / 纯势圆 / 纯散五角 / 秩势拱 / 秩散盾 / 势散圆角方 / 秩势散六边",
        "③ 右上小方点 = 这个骨架含几个 6 级块（融合的块数）",
        "④ 底部文字 = 块形态（38 库编号/公式），顶部 = 三价原子数",
        "⑤ 右下三条小色条 = 这个骨架自己的 硬度/粘性/温度（由它拥有的元素算）",
    ]
    for i, t in enumerate(lines):
        cv.txt(x0 + s + 26, y0 + 16 + i * 26, t, 11.5, False, INK, "lm")

    # B 家族方块
    cv.txt(40, 360, "B. 七种骨架家族方块（同一单位大小，纹样不同）", 16, True, INK, "lm")
    fams = ["O", "P", "K", "OP", "OK", "PK", "OPK"]
    for i, fam in enumerate(fams):
        x = 70 + i * 210
        T.draw_tile(cv, x, 400, 150, {"family": fam, "n": 4, "blocks": [1], "block_forms": [fam + "2"]},
                    S.FAMILY[fam]["col"], labels=False)
        cv.txt(x + 75, 570, S.FAMILY[fam]["zh"], 13, True, INK, "mm")
        cv.txt(x + 75, 590, fam, 10, False, INK2, "mm")

    # C 连接件
    cv.txt(40, 650, "C. 方块之间怎么连（画在共用的边上）", 16, True, INK, "lm")
    demo = [
        ("X 晶", "短粗焊块（最硬：两块直接咬死）", lambda cv, x, y: T.draw_bridge_on_edge(cv, x, y, 120, "h", ["X"])),
        ("W 流", "可拉伸椭圆肌腱（能弯）", lambda cv, x, y: T.draw_bridge_on_edge(cv, x, y, 120, "h", ["W"])),
        ("A 气", "沿边的细长薄膜（隔空软连）", lambda cv, x, y: T.draw_bridge_on_edge(cv, x, y, 120, "h", ["A"])),
        ("融合", "两块骨架在同一边焊死（焊纹）", lambda cv, x, y: T.draw_weld(cv, x, y, 120, "h")),
    ]
    for i, (name, desc, fn) in enumerate(demo):
        x = 90 + i * 390
        a, b = (x, 720), (x + 120, 720)
        cv.d.rectangle([a[0] - 60, a[1] - 60, a[0], a[1] + 60], fill=(246, 250, 253), outline=(184, 194, 204))
        cv.d.rectangle([a[0], a[1] - 60, a[0] + 60, a[1] + 60], fill=(246, 250, 253), outline=(184, 194, 204))
        fn(cv, a[0], a[1])
        cv.txt(a[0] + 60, a[1] + 74, name, 13, True, INK, "mm")
        cv.txt(a[0] + 60, a[1] + 94, desc, 9.5, False, INK2, "mm")
    cv.txt(40, 866, "注：桥（连接两个骨架的二价元素）只负责连接，不计入任何骨架的属性；"
                    "骨架自己的属性只看它拥有的三价元素 + 挂在自己身上的二价/一价元素。", 11, False, INK, "lm")

    # D 端帽
    cv.txt(40, 900, "D. 一价端帽 = 方块外缘的小方钉：冰C 三角钉 / 焰F 方钉 / 电L 细圆钉（计入所挂骨架的温度）",
           12.5, True, INK, "lm")
    for i, el in enumerate("CFL"):
        x = 1150 + i * 140
        cv.d.rectangle([x - 55, 862, x, 920], fill=(246, 250, 253), outline=(184, 194, 204))
        T.draw_stud(cv, x, 891, 110, (1, 0), el)
        cv.txt(x + 16, 944, {"C": "冰 C", "F": "焰 F", "L": "电 L"}[el], 10, True, INK, "mm")

    # E 属性公式
    cv.txt(40, 978, "E. 逐骨架属性：硬度 = Σ三价×权重(O1.2/P0.9/K0.6)；粘性 = Σ挂在它的二价×权重(X1.0/W1.4/A0.4)；"
                    "温度 = Σ挂在它的一价×权重(C−2.0/L0.5/F3.0)；桥不参与。", 10.8, False, INK, "lm")
    cv.save(path)
    print("saved", path)


def page_molecules(path="images/t75b_molecules.png", picks=None):
    mols, rng = _load()
    by = {m["mid"]: m for m in mols}
    if picks is None:
        picks = ["G13", "G14", "G16", "G23", "G24", "G33", "G17", "G19", "G20", "G21", "G27", "G32",
                 "G18", "G25", "G26", "G30", "G31", "G34"]
    picks = [p for p in picks if p in by]
    cw, ch = 780, 520
    cols, n = 2, len(picks)
    nrows = (n + cols - 1) // cols
    cv = S.Canvas(40 + cols * cw, 200 + nrows * ch, (255, 255, 255))
    cv.txt(40, 46, "T75 大分子的方块形态：属性按每个骨架各自计算", 26, True, INK, "lm")
    cv.txt(40, 78, "每块方块右下角的三色小条 = 这块骨架自己的 硬度(红)/粘性(绿)/温度(紫)；"
                   "连接用的二价桥不计入任何属性，只画在共用边上。", 12.2, False, INK2, "lm")
    for i, mid in enumerate(picks):
        mol = by[mid]
        cc, rr = i % cols, i // cols
        x = 40 + cc * cw
        y = 160 + rr * ch
        cv.d.rounded_rectangle([x, y, x + cw - 18, y + ch - 18], radius=12,
                               fill=(252, 253, 255), outline=(226, 232, 238))
        cv.txt(x + 16, y + 22, "%s  %s" % (mid, mol["formula"]), 17, True, INK, "lm")
        info = T.draw_molecule(cv, (x + 8, y + 42, 420, ch - 66), mol, max_tile=124, attr_rng=rng)
        attrs = info["attrs"]
        px = x + 428
        cv.txt(px, y + 30, "骨架 / 硬度 · 粘性 · 温度", 12.5, True, INK, "lm")
        yy = y + 52
        for k, a in enumerate(attrs):
            col = S.FAMILY.get(a["sk"].get("family", "OPK"), {}).get("col", "#2c3e50")
            cv.txt(px, yy, "①②③④⑤⑥⑦"[k], 12, True, col, "lm")
            cv.txt(px + 20, yy, "%s" % (a["formula"] or ""), 12, True, INK, "lm")
            cv.txt(px + 108, yy, "H %.1f" % a["hardness"], 11.5, True, HCOL, "lm")
            cv.txt(px + 166, yy, "V %.1f" % a["viscosity"], 11.5, True, VCOL, "lm")
            cv.txt(px + 224, yy, "T %+.1f" % a["temperature"], 11.5, True, TCOL, "lm")
            yy += 19
            seg = []
            for key, zh in (("hard_parts", "硬"), ("visc_parts", "粘"), ("temp_parts", "温")):
                if a[key]:
                    seg.append(zh + ":" + "+".join("%s%d" % (nm[1:], c) for nm, c, w in a[key]))
            cv.txt(px + 20, yy, "；".join(seg) if seg else "只有三价元素（桥不计）", 8.6, False, INK2, "lm")
            yy += 17
            if yy > y + ch - 100:
                break
        cv.txt(px, y + ch - 60, "方块 %d · 桥 %d（不计属性）· 融合 %d · 端帽 %d" % (
            len(mol["skeletons"]), len(mol["bridges"]),
            sum(1 for sk in mol["skeletons"] if sk.get("n_fusion_bonds")),
            len(mol["decoration"].get("mono", []))), 9.5, False, INK2, "lm")
        fams = sorted({(sk.get("family") or "?") for sk in mol["skeletons"]})
        cv.txt(px, y + ch - 42, "家族：" + " / ".join(S.FAMILY.get(f, {}).get("zh", f) for f in fams),
               9.5, False, INK2, "lm")
    cv.save(path)
    print("saved", path)


def page_overview(path="images/t75b_overview.png", cols=6, rows=6):
    mols, rng = _load()
    ms = mols[: cols * rows]
    cw, ch = 262, 268
    cv = S.Canvas(40 + cols * cw, 150 + rows * ch, (255, 255, 255))
    cv.txt(40, 46, "T75 方块世界 · 36 个稳定大分子的方块形态总览", 26, True, INK, "lm")
    cv.txt(40, 78, "方块 = 骨架；共用边上的小件 = 桥/融合（不计属性）；外缘小方钉 = 一价端帽；"
                   "方块右下三色小条 = 该骨架的 硬度/粘性/温度。", 12, False, INK2, "lm")
    for i, mol in enumerate(ms):
        cc, rr = i % cols, i // cols
        x = 40 + cc * cw
        y = 112 + rr * ch
        cv.d.rectangle([x, y, x + cw - 10, y + ch - 12], outline=(230, 235, 241))
        T.draw_molecule(cv, (x + 4, y + 22, cw - 22, ch - 64), mol, show_attrs=False, max_tile=42, attr_rng=rng)
        cv.txt(x + 6, y + 14, mol["mid"], 11, True, INK, "lm")
        cv.txt(x + 6, y + ch - 46, "%d 方块 · %d 桥" % (len(mol["skeletons"]), len(mol["bridges"])),
               8.6, False, INK2, "lm")
    cv.save(path)
    print("saved", path)


def main():
    page_rules()
    page_molecules()
    page_overview()


if __name__ == "__main__":
    main()
