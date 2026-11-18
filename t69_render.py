# -*- coding: utf-8 -*-
"""T69 成品渲染：36 张卡片页 + 总览 + 图例页。"""
import os

from PIL import Image, ImageDraw

import t68_shapes as S
import t69_pieces as P
import t69_draw as D
import t69_draft as K

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "images")

CARD_W, CARD_H = K.CW, K.CH
PAGE_W, PAGE_H = 1600, 1440
PER_PAGE = 2
FONT = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")


def page_frame(pageno, npage):
    cv = S.Canvas(PAGE_W, PAGE_H, (255, 255, 255))
    cv.txt(30, 36, "T69 大分子骨架图册 · 元素隐去版", 27, True, D.INK, "lm")
    cv.txt(30, 64, "36 个 T61–T64 稳定大分子（≥14 原子）· 只画骨架外轮廓与连接件、端帽，元素字形与字母全部隐去 · "
                   "骨架 = 6 级骨架块的几何容器（7 家族外形）· 块间融合 = 贴边焊死 · 骨架间 = 二价桥连接件",
           12.5, False, D.INK2, "lm")
    cv.txt(PAGE_W - 30, 40, "第 %d / %d 页" % (pageno, npage), 15, True, D.INK, "rm")
    d = cv.d
    d.line([(30, 84), (PAGE_W - 30, 84)], fill=(200, 210, 220), width=2)
    # 页脚图例
    y = PAGE_H - 62
    cv.txt(30, y, "图例：", 13, True, D.INK, "lm")
    x = 92
    cv.d.polygon([(x, y + 9), (x + 9, y + 9), (x + 4.5, y - 6)], fill=(208, 218, 228), outline=D.WELDC)
    cv.txt(x + 16, y, "晶X 三角楔块（焊死）", 12, False, D.INK, "lm")
    x += 176
    cv.d.ellipse([x - 10, y - 6, x + 10, y + 6], fill=(205, 227, 244), outline=(31, 91, 138))
    cv.txt(x + 16, y, "流W 肌腱", 12, False, D.INK, "lm")
    x += 96
    cv.d.rectangle([x - 16, y - 5, x + 16, y + 5], fill=(208, 238, 230), outline=(17, 100, 85))
    cv.txt(x + 24, y, "气A 薄膜", 12, False, D.INK, "lm")
    x += 96
    cv.d.polygon([(x - 6, y - 8), (x + 8, y - 3), (x, y + 8)], fill=(232, 200, 160), outline=(150, 90, 40))
    cv.txt(x + 16, y, "冰C 尖三角触肢", 12, False, D.INK, "lm")
    x += 140
    cv.d.polygon([(x - 7, y - 6), (x + 6, y - 8), (x + 8, y + 6), (x - 5, y + 8)], fill=(238, 210, 180), outline=(150, 90, 40))
    cv.txt(x + 16, y, "焰F 软四边形", 12, False, D.INK, "lm")
    x += 130
    cv.d.ellipse([x - 12, y - 5, x + 12, y + 5], fill=(230, 218, 240), outline=(110, 70, 150))
    cv.txt(x + 18, y, "电L 细椭圆", 12, False, D.INK, "lm")
    x += 110
    cv.d.rectangle([x - 12, y - 5, x + 12, y + 5], fill=(58, 72, 86))
    cv.txt(x + 18, y, "焊带（融合）", 12, False, D.INK, "lm")
    return cv


def card_into(cv, mol, x0, y0):
    """把一张卡片画到页面 (x0,y0)。"""
    d = cv.d
    d.rectangle([x0, y0, x0 + CARD_W, y0 + CARD_H], outline=(214, 220, 228), width=2)
    cv.txt(x0 + 24, y0 + 34, mol["mid"], 28, True, D.INK, "lm")
    S.draw_formula(d, x0 + 92, y0 + 34, mol["formula"], 24, D.INK, True, center=False)
    cv.txt(x0 + 92, y0 + 60, "%s · %d 原子 · %d 骨架 · %d 桥 · 元素隐去，只留骨架外轮廓" %
           (mol["exp"], mol["n_atoms"], len(mol["skeletons"]), len(mol["bridges"])),
           13, False, D.INK2, "lm")
    info = D.draw_molecule(cv, (x0 + 16, y0 + 74, 900, 522), mol, max_s=56)
    K.panel(cv, x0 + 946, y0 + 76, mol, info)
    return info


def build_cards(data):
    mols = data["molecules"]
    npage = (len(mols) + PER_PAGE - 1) // PER_PAGE
    for pi in range(npage):
        cv = page_frame(pi + 1, npage)
        for j in range(PER_PAGE):
            idx = pi * PER_PAGE + j
            if idx >= len(mols):
                break
            card_into(cv, mols[idx], 30, 100 + j * (CARD_H + 22))
        cv.save(os.path.join(IMG, "t69_giants_%02d.png" % (pi + 1)))
    return npage


def build_overview(data):
    mols = data["molecules"]
    cols, rows = 6, 6
    cellw, cellh = 262, 262
    W = 30 * 2 + cols * cellw
    H = 150 + rows * cellh + 40
    cv = S.Canvas(W, H, (255, 255, 255))
    cv.txt(30, 40, "T69 大分子骨架图册 · 总览（36 个稳定大分子）", 26, True, D.INK, "lm")
    cv.txt(30, 70, "元素字形已隐去：只留骨架块的外形容器 + 连接件 + 端帽；每格标注编号 / 分子式 / 原子·骨架·桥数 / 骨架家族",
           12.5, False, D.INK2, "lm")
    d = cv.d
    for i, mol in enumerate(mols):
        r, c = i // cols, i % cols
        x = 30 + c * cellw
        y = 132 + r * cellh
        d.rectangle([x + 4, y + 4, x + cellw - 8, y + cellh - 8], outline=(216, 222, 228), width=1)
        cv.txt(x + 12, y + 20, mol["mid"], 14, True, D.INK, "lm")
        cv.txt(x + cellw - 16, y + 20, mol["family_zh"], 10.5, False, D.INK2, "rm")
        cv.txt(x + 12, y + 36, "%s · %d原子·%d骨架·%d桥" %
               (P.short_comp(mol["atoms"]), mol["n_atoms"], len(mol["skeletons"]), len(mol["bridges"])),
               10, False, D.INK2, "lm")
        info = D.draw_molecule(cv, (x + 8, y + 48, cellw - 20, cellh - 62), mol, max_s=13)
        cv.txt(x + 12, y + cellh - 18, "".join(sorted(set(s["formula"] for s in mol["skeletons"])))[:24],
               9.5, False, D.INK2, "lm")
    cv.save(os.path.join(IMG, "t69_overview.png"))


def legend_page():
    cv = S.Canvas(1600, 1180, (255, 255, 255))
    d = cv.d
    cv.txt(30, 40, "T69 形状语言 · 骨架单元 / 融合 / 连接件 / 端帽", 27, True, D.INK, "lm")
    cv.txt(30, 68, "骨架形状来自 38 个 6 级骨架块形态的所属家族（7 种外形）；块与块之间若有 0 级同类三价键就是融合（贴边焊死）；"
                   "骨架之间用二价桥连接件：晶 X 楔块（嵌死）/ 流 W 肌腱（可拉伸）/ 气 A 薄膜（隔空软连）。",
           12.5, False, D.INK2, "lm")

    # A：7 家族容器
    y = 108
    cv.txt(30, y, "A. 骨架单元的 7 种外形容器（容器内不再画元素字形）", 19, True, D.INK, "lm")
    y += 28
    fams = [("O", "纯秩 O"), ("P", "纯势 P"), ("K", "纯散 K"), ("OP", "秩势 O+P"),
            ("OK", "秩散 O+K"), ("PK", "势散 P+K"), ("OPK", "秩势散 O+P+K")]
    for i, (key, name) in enumerate(fams):
        cx = 100 + i * 214
        col = S.FAMILY[key]["col"]
        pts = S.fam_shape(key, cx, y + 62, 46, 46, 2)
        d.polygon(pts, fill=S.lighten(col, 0.93), outline=col)
        d.line(pts + [pts[0]], fill=col, width=4)
        cv.txt(cx, y + 124, name, 14, True, D.INK, "mm")
    y += 168

    # B：融合
    cv.txt(30, y, "B. 融合：两块骨架单元的边贴在一起焊死（0 级同类三价键）", 19, True, D.INK, "lm")
    y += 24
    bx, by = 96, y + 92
    for k, (key, dx) in enumerate([("OPK", 0), ("OPK", 148)]):
        col = S.FAMILY[key]["col"]
        pts = S.fam_shape(key, bx + dx, by, 46, 44, 2)
        d.polygon(pts, fill=S.lighten(col, 0.93), outline=col)
        d.line(pts + [pts[0]], fill=col, width=4)
    d.polygon([(bx + 66, by - 40), (bx + 82, by - 40), (bx + 82, by + 40), (bx + 66, by + 40)],
              fill=(58, 72, 86), outline=(20, 28, 36))
    for i in range(-2, 3):
        d.line([(bx + 66, by + i * 16 - 6), (bx + 82, by + i * 16 + 6)], fill=(214, 222, 230), width=2)
    cv.txt(bx + 74, by + 60, "焊带", 12, False, D.INK2, "mm")
    cv.txt(bx + 210, by - 30, "两条边完全贴合：", 13, False, D.INK, "lm")
    cv.txt(bx + 210, by - 6, "① 两块容器边对边叠合，接缝画一条实心焊带；", 13, False, D.INK, "lm")
    cv.txt(bx + 210, by + 18, "② 焊带两端带焊点，表示这一对骨架单元已经焊死；", 13, False, D.INK, "lm")
    cv.txt(bx + 210, by + 42, "③ 本图册 36 个分子里只出现 1 次（G13 的 P–P 键）。", 13, False, D.INK, "lm")
    y += 210

    # C：连接件
    cv.txt(30, y, "C. 骨架之间的连接件（按二价桥的桥原子元素决定）", 19, True, D.INK, "lm")
    y += 26
    y0 = y + 92
    A = (120, y0)
    Bv = (152, y0)
    D.draw_x_block(cv, A, Bv, 42)
    cv.txt(96, y0 + 78, "晶 X = 三角楔块", 15, True, D.INK, "lm")
    cv.txt(96, y0 + 100, "最短最粗；尖端深插一侧骨架，", 12.5, False, D.INK2, "lm")
    cv.txt(96, y0 + 118, "另一侧压焊板 → 焊死", 12.5, False, D.INK2, "lm")
    A = (470, y0)
    Bv = (620, y0)
    D.draw_w_tendon2(cv, A, Bv, 40)
    cv.txt(456, y0 + 78, "流 W = 可拉伸肌腱", 15, True, D.INK, "lm")
    cv.txt(456, y0 + 100, "两端窄、中间鼓，像肌腱一样", 12.5, False, D.INK2, "lm")
    cv.txt(456, y0 + 118, "留出可弯曲/伸缩的长度", 12.5, False, D.INK2, "lm")
    A = (830, y0)
    Bv = (985, y0)
    D.draw_a_slab(cv, A, Bv, 34)
    cv.txt(816, y0 + 78, "气 A = 长条薄膜", 15, True, D.INK, "lm")
    cv.txt(816, y0 + 100, "长方形横置，长边贴着两侧骨架，", 12.5, False, D.INK2, "lm")
    cv.txt(816, y0 + 118, "两骨架隔空软连", 12.5, False, D.INK2, "lm")

    # D：多元素规则
    y2 = y0 + 160
    cv.txt(96, y2, "多元素桥的组合规则：按链上的元素顺序逐段放置连接件，同种元素合并成一段；整条链沿同一轴线排布；"
                   "两端段各自嵌入所连的骨架（X 用楔块/焊板，W 用肌腱端，A 用膜边），中间段保持各自的形状——"
                   "于是 W–A–W 读作「肌腱＋薄膜＋肌腱」的组合接头。", 12.5, False, D.INK, "lm")
    cv.txt(96, y2 + 24, "示例（G16 桥3 / G26 桥5）：", 12.5, True, D.INK, "lm")
    D.draw_chain(cv, (300, y2 + 90), (640, y2 + 90), ["W", "A", "W"], 34)
    cv.txt(650, y2 + 78, "W–A–W 组合接头", 13, False, D.INK, "lm")
    cv.txt(650, y2 + 98, "（3 原子桥，画成三段）", 12, False, D.INK2, "lm")

    # E：端帽
    y3 = y2 + 150
    cv.txt(30, y3, "D. 端帽触肢（一价端帽）与装饰", 19, True, D.INK, "lm")
    y3 += 24
    base = (150, y3 + 70)
    P.draw_terminal(cv, base, (1, 0), "C", 34, 0)
    cv.txt(150, y3 + 120, "冰 C：尖三角触肢（正/倒三角）", 13, True, D.INK, "mm")
    base = (460, y3 + 70)
    P.draw_terminal(cv, base, (1, 0), "F", 34, 0)
    cv.txt(460, y3 + 120, "焰 F：四边形软触肢", 13, True, D.INK, "mm")
    base = (770, y3 + 70)
    P.draw_terminal(cv, base, (1, 0), "L", 34, 0)
    cv.txt(770, y3 + 120, "电 L：椭圆细长软触肢", 13, True, D.INK, "mm")
    # 支臂与铆钉
    P.draw_arm(cv, [(1000, y3 + 40), (1060, y3 + 50), (1120, y3 + 40)], ["W", "A"], 30)
    cv.txt(1140, y3 + 48, "支臂：容器边缘伸出的管状触须（非端帽）", 12.5, False, D.INK2, "lm")
    P.draw_rivet(cv, (1030, y3 + 96), 30)
    cv.txt(1060, y3 + 96, "骨架内桥：容器边上的小铆钉", 12.5, False, D.INK2, "lm")

    cv.txt(30, 1148, "读法：容器外形 = 骨架家族的 7 种轮廓之一；容器内无元素字形；容器上的 ① ② = 块编号；"
                     "两个容器之间的图形 = 连接件；容器边缘外的小图形 = 端帽/支臂。每个分子的元素组成写在右下角。",
           12, False, D.INK2, "lm")
    cv.save(os.path.join(IMG, "t69_legend.png"))


def main():
    data = P.load_data()
    npage = build_cards(data)
    print("pages", npage)
    build_overview(data)
    print("overview ok")
    legend_page()
    print("legend ok")


if __name__ == "__main__":
    main()
