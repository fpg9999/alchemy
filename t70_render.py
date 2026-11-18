# -*- coding: utf-8 -*-
"""T70 生成式形状语言图集：骨架 / 桥梁 / 端帽，以及用它们重画的示例分子。"""
import json
import math
import os

import t68_shapes as S
import t70_glyphs as G
import t69_pieces as P
import t69_draw as D
import t69_bodies as B

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "images")
INK = (34, 48, 62)
INK2 = (96, 112, 128)


def page_skeletons():
    blocks = G.library_blocks()
    cols, rows = 8, 5
    cw, ch = 196, 214
    W, H = 40 + cols * cw, 190 + rows * ch
    cv = S.Canvas(W, H, (255, 255, 255))
    cv.txt(40, 46, "T70 生成式形状语言 · 38 个骨架块（同一条规则生成）", 26, True, INK, "lm")
    cv.txt(40, 76, "外形 = 谐波晶核：元素计数决定主瓣数（3+K）、O 给三重对称、P 给二重平滑、邻接度数决定瓣相位与晶脉亮度、"
                   "键角决定整体旋转。因此同类骨架风格一致、个体又各不相同。", 12.5, False, INK2, "lm")
    for i, (formula, atoms, edges, key, label) in enumerate(blocks):
        r, c = i // cols, i % cols
        x = 40 + c * cw
        y = 116 + r * ch
        cv.d.rectangle([x + 4, y + 4, x + cw - 8, y + ch - 12], outline=(224, 230, 236), width=1)
        G.block_glyph(cv, x + cw / 2.0, y + 96, 62, atoms, edges, key, label)
        cv.txt(x + cw / 2.0, y + 178, formula or "—", 15, True, INK, "mm")
        p = G.block_params(atoms, edges, label)
        cv.txt(x + cw / 2.0, y + 196, "瓣 %d · 度数 %s" % (p["m"], "/".join(str(v) for v in p["dsorted"][:3])),
               10, False, INK2, "mm")
    cv.save(os.path.join(IMG, "t70_skeletons38.png"))
    return blocks


def page_bridges():
    W, H = 1600, 1080
    cv = S.Canvas(W, H, (255, 255, 255))
    cv.txt(40, 46, "T70 生成式形状语言 · 桥梁（按桥原子与链长生成）", 26, True, INK, "lm")
    cv.txt(40, 76, "晶 X = 焊核（钝三角 + 放射焊纹 + 两片焊板，键数越多焊纹越多）；流 W = 双股编织腱（链越长交叉越多）；"
                   "气 A = 褶皱膜（链越长褶越多）；多元素桥 = 分段共用轴线、接缝打结。", 12.5, False, INK2, "lm")
    y = 150
    cv.txt(48, y, "晶 X 焊核：单原子桥在三种间距下的形态（左→右：贴紧 / 中等 / 拉长）", 15, True, INK, "lm")
    for k, gap in enumerate((90, 150, 230)):
        a = (60 + k * 330, y + 92)
        b = (a[0] + gap, y + 92)
        G.draw_bridge_x(cv, a, b, 34, mult=1)
        cv.txt(a[0] + gap / 2.0, y + 140, "间距 %d" % gap, 11, False, INK2, "mm")
    cv.txt(1060, y + 60, "多键：焊纹随多重键增加", 13, True, INK, "lm")
    for m in (1, 2, 3):
        a = (1120, y + 30 + (m - 1) * 46)
        G.draw_bridge_x(cv, a, (a[0] + 110, a[1]), 34, mult=m)
        cv.txt(a[0] + 150, a[1], "m=%d" % m, 12, False, INK2, "lm")

    y = 400
    cv.txt(48, y, "流 W 编织腱：链长 1 / 3 / 5 原子（交叉数随长度）", 15, True, INK, "lm")
    for k, (n, ln) in enumerate(((1, 150), (3, 210), (5, 270))):
        a = (60 + k * 400, y + 92)
        b = (a[0] + ln, y + 92)
        G.draw_bridge_w(cv, a, b, 34, ncross=n)
        cv.txt(a[0] + ln / 2.0, y + 140, "%d 原子" % n, 11, False, INK2, "mm")

    y = 640
    cv.txt(48, y, "气 A 褶皱膜：链长 1 / 3（褶数随长度）", 15, True, INK, "lm")
    for k, (n, ln) in enumerate(((1, 150), (3, 190))):
        a = (60 + k * 400, y + 92)
        b = (a[0] + ln, y + 92)
        G.draw_bridge_a(cv, a, b, 34, pleats=n)
        cv.txt(a[0] + ln / 2.0, y + 150, "%d 原子" % n, 11, False, INK2, "mm")

    y = 860
    cv.txt(48, y, "多元素组合桥（G16 / G26 里的真实序列）", 15, True, INK, "lm")
    seqs = [["W", "A", "W"], ["A", "X"], ["X", "W", "A"], ["W", "W", "A", "W"]]
    for k, seq in enumerate(seqs):
        a = (60 + k * 380, y + 92)
        b = (a[0] + 240, y + 92)
        G.draw_bridge_chain(cv, a, b, 34, seq)
        cv.txt(a[0] + 120, y + 140, "–".join(seq), 12, False, INK2, "mm")
    cv.save(os.path.join(IMG, "t70_bridges.png"))


def page_terminals():
    W, H = 1600, 900
    cv = S.Canvas(W, H, (255, 255, 255))
    cv.txt(40, 46, "T70 生成式形状语言 · 端帽触肢（按一价原子与所在骨架生成）", 26, True, INK, "lm")
    cv.txt(40, 76, "冰 C = 分形尖刺（递归层数 = 2，尖端再分叉）；焰 F = 正弦飘带（波数 2）；电 L = 双股螺旋丝（圈数 1~2）。"
                   "尺寸随所连骨架的大小缩放。", 12.5, False, INK2, "lm")
    # C
    cv.txt(60, 150, "冰 C 尖刺：递归层数 1 / 2 / 3", 15, True, INK, "lm")
    for k, dep in enumerate((1, 2, 3)):
        base = (120 + k * 260, 330)
        G.draw_terminal_c(cv, base, (1, 0), 42, depth=dep)
        cv.txt(base[0] + 70, 430, "depth %d" % dep, 11, False, INK2, "mm")
    # F
    cv.txt(900, 150, "焰 F 飘带：波数 1 / 2 / 3", 15, True, INK, "lm")
    for k, wv in enumerate((1, 2, 3)):
        base = (930 + k * 210, 330)
        G.draw_terminal_f(cv, base, (1, 0), 40, waves=wv)
        cv.txt(base[0] + 60, 430, "waves %d" % wv, 11, False, INK2, "mm")
    # L
    cv.txt(60, 520, "电 L 螺旋丝：圈数 1 / 2 / 3", 15, True, INK, "lm")
    for k, tn in enumerate((1, 2, 3)):
        base = (120 + k * 260, 690)
        G.draw_terminal_l(cv, base, (1, 0), 42, turns=tn)
        cv.txt(base[0] + 70, 760, "turns %d" % tn, 11, False, INK2, "mm")
    # 组合示例
    cv.txt(900, 520, "同一骨架上的混合端帽（示意）", 15, True, INK, "lm")
    cx, cy = 1060, 690
    G.block_glyph(cv, cx, cy, 74, ["O", "P", "K", "O", "P", "K"], [(0, 1, 1), (1, 2, 1), (2, 3, 1), (3, 4, 1), (4, 5, 1)],
                  "OPK", "demo|term")
    import random
    rnd = random.Random(7)
    for i in range(5):
        th = G.TAU * i / 5.0 + 0.3
        base = (cx + math.cos(th) * 78, cy + math.sin(th) * 78)
        el = ["C", "F", "L"][i % 3]
        if el == "C":
            G.draw_terminal_c(cv, base, (math.cos(th), math.sin(th)), 20, depth=1)
        elif el == "F":
            G.draw_terminal_f(cv, base, (math.cos(th), math.sin(th)), 17)
        else:
            G.draw_terminal_l(cv, base, (math.cos(th), math.sin(th)), 15)
    cv.save(os.path.join(IMG, "t70_terminals.png"))


# ---------------------------------------------------------------- 示例分子
def mol_maps(mol):
    atoms = mol["atoms"]
    blocks = B.blocks_of(mol)
    idx_of = B.block_index(mol, blocks)
    bedges = {}
    for (i, j, m) in mol["edges"]:
        ka, kb = idx_of.get(i), idx_of.get(j)
        if ka is None or kb is None:
            continue
        bedges.setdefault(ka, []).append((i, j, m))
    return blocks, idx_of, bedges


def draw_molecule(cv, mol, box, max_r=150.0, title=True):
    bodies, bridges, fusion, idx_of, adj, skel_of, kinds = D.build(mol)
    s, ox, oy = D.fit_scale(bodies, box, max_s=52)
    blocks, b_idx, bedges = mol_maps(mol)
    # 位置与半径（像素）
    for b in bodies:
        cx, cy = b.cx * s + ox, b.cy * s + oy
        ka = b.k
        local = []
        mem = set(blocks[ka]["mem"])
        if False:
            pass
        for (i, j, m) in mol["edges"]:
            if idx_of.get(i) != ka or idx_of.get(j) != ka:
                continue
            li = blocks[ka]["mem"].index(i)
            lj = blocks[ka]["mem"].index(j)
            local.append((li, lj, m))
        atoms = [mol["atoms"][i] for i in blocks[ka]["mem"]]
        G.block_glyph(cv, cx, cy, b.r * s * 1.02, atoms, local, b.key,
                      "%s|%s" % (mol["mid"], blocks[ka]["formula"]))
        P.badge(cv, (cx + b.r * s * 0.55, cy - b.r * s * 0.55), str(b.k + 1),
                r=max(9, int(0.22 * s)), size=max(10, int(0.25 * s)))
    # 桥
    seg = {}
    for key, items in kinds.items():
        ka, kb = key
        sa, sb = bodies[ka].block["sk"], bodies[kb].block["sk"]
        if sa == sb:
            continue
        gkey = (min(sa, sb), max(sa, sb))
        seg.setdefault(gkey, []).extend(items)

    def poly_px(b):
        return [(x * s + ox, y * s + oy) for (x, y) in b.poly()]

    for gkey, items in seg.items():
        rep = max(items, key=lambda it: (len(it.get("elems") or []), it["br"].get("k", 0)))
        ka, kb = rep["ka"], rep["kb"]
        ca = (bodies[ka].cx * s + ox, bodies[ka].cy * s + oy)
        cb = (bodies[kb].cx * s + ox, bodies[kb].cy * s + oy)
        a = S.ray_exit(poly_px(bodies[ka]), ca, cb)
        b = S.ray_exit(poly_px(bodies[kb]), cb, ca)
        sp = min(bodies[ka].r, bodies[kb].r) * s * 0.58
        elems = rep.get("elems") or []
        G.draw_bridge_chain(cv, a, b, sp, elems)
    # 融合：焊带
    for (ka, kb, fu) in fusion:
        ca = (bodies[ka].cx * s + ox, bodies[ka].cy * s + oy)
        cb = (bodies[kb].cx * s + ox, bodies[kb].cy * s + oy)
        mid = ((ca[0] + cb[0]) / 2.0, (ca[1] + cb[1]) / 2.0)
        u = D.norm((cb[0] - ca[0], cb[1] - ca[1]))
        n = (-u[1], u[0])
        L = min(bodies[ka].r, bodies[kb].r) * s * 0.85
        th = s * 0.12
        band = [(mid[0] + n[0] * L + u[0] * th, mid[1] + n[1] * L + u[1] * th),
                (mid[0] + n[0] * L - u[0] * th, mid[1] + n[1] * L - u[1] * th),
                (mid[0] - n[0] * L - u[0] * th, mid[1] - n[1] * L - u[1] * th),
                (mid[0] - n[0] * L + u[0] * th, mid[1] - n[1] * L + u[1] * th)]
        cv.d.polygon(band, fill=(64, 80, 98), outline=(28, 40, 54))
        for i in range(-2, 3):
            px, py = mid[0] + n[0] * i * L * 0.32, mid[1] + n[1] * i * L * 0.32
            cv.d.line([(px + u[0] * th * 0.9, py + u[1] * th * 0.9),
                       (px - u[0] * th * 0.9, py - u[1] * th * 0.9)], fill=(214, 224, 234), width=2)
    # 端帽 / 支臂
    geoms = D.attach_geoms(mol, bodies, idx_of, adj, skel_of)
    for m in geoms["mono"]:
        kb = m["kb"]
        if kb is None:
            continue
        pb = bodies[kb]
        c = (pb.cx * s + ox, pb.cy * s + oy)
        dv = m["dir"]
        far = (c[0] + dv[0] * pb.r * s * 3.0, c[1] + dv[1] * pb.r * s * 3.0)
        base = S.ray_exit(poly_px(pb), c, far)
        el = mol["atoms"][m["atom"]]
        sz = max(6.0, pb.r * s * 0.30)
        if el == "C":
            G.draw_terminal_c(cv, base, dv, sz, depth=2)
        elif el == "F":
            G.draw_terminal_f(cv, base, dv, sz, waves=2)
        elif el == "L":
            G.draw_terminal_l(cv, base, dv, sz, turns=1)
    for arm in geoms["arms"]:
        kb = arm["kb"]
        pb = bodies[kb]
        c = (pb.cx * s + ox, pb.cy * s + oy)
        dv = arm["dir"]
        far = (c[0] + dv[0] * pb.r * s * 3.0, c[1] + dv[1] * pb.r * s * 3.0)
        base = S.ray_exit(poly_px(pb), c, far)
        n = len(arm["comp"])
        L = s * (1.2 + 0.18 * n)
        pts = [base, (base[0] + dv[0] * L * 0.55, base[1] + dv[1] * L * 0.55),
               (base[0] + dv[0] * L, base[1] + dv[1] * L)]
        P.draw_arm(cv, pts, [mol["atoms"][i] for i in arm["comp"]], s * 0.7)
    if title:
        cv.txt(box[0] + 6, box[1] - 8, mol["mid"], 20, True, INK, "lm")
        S.draw_formula(cv.d, box[0] + 78, box[1] - 8, mol["formula"], 18, INK, True, center=False)


def page_molecules(picks=("G13", "G24", "G16", "G26")):
    data = P.load_data()
    by = {m["mid"]: m for m in data["molecules"]}
    W, H = 1600, 1500
    cv = S.Canvas(W, H, (255, 255, 255))
    cv.txt(40, 46, "T70 生成式形状语言 · 用新图形重画的示例分子", 26, True, INK, "lm")
    cv.txt(40, 76, "骨架块 = 谐波晶核（外形由元素计数/度数/键角生成）；骨架之间 = 焊核 / 编织腱 / 褶皱膜；"
                   "边缘 = 分形尖刺 / 飘带 / 螺旋丝。元素字形与字母仍然隐去。", 12.5, False, INK2, "lm")
    # 两列两行
    cells = [(40, 120, 740, 640), (820, 120, 740, 640), (40, 790, 740, 640), (820, 790, 740, 640)]
    for mid, (x, y, w, h) in zip(picks, cells):
        cv.d.rectangle([x, y, x + w, y + h], outline=(222, 228, 236), width=2)
        draw_molecule(cv, by[mid], (x + 16, y + 40, w - 32, h - 70))
    cv.save(os.path.join(IMG, "t70_molecules.png"))


def main():
    page_skeletons()
    print("skeletons ok")
    page_bridges()
    print("bridges ok")
    page_terminals()
    print("terminals ok")
    page_molecules()
    print("molecules ok")


if __name__ == "__main__":
    main()
