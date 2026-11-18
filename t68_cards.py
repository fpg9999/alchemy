# -*- coding: utf-8 -*-
"""t68_cards.py —— T68 大分子骨架卡片渲染

用法：
  python t68_cards.py one G13      # 只渲染一张卡（调试）
  python t68_cards.py all          # 全部 36 个：9 页 × 2 卡 + 总览图
"""
import json
import os
import sys

import t68_shapes as S

BASE = S.BASE
DATA = os.path.join(BASE, "t68_data.json")
OUT = os.path.join(BASE, "images")

CARD_W, CARD_H = 1540, 620
PAGE_W, PAGE_H = 1600, 1440
CARDS_PER_PAGE = 2
N_PAGE = 18

LEGEND_GLYPH = ("△=秩O   ○=势P   ■/多角=散K(角数=骨架内K数)   "
                "尖六边形=晶X  圆角六边形=流W  虚线六边形=气A   "
                "小红点=冰C/电L/焰F  |  红= S短键  绿= C角键   "
                "紫虚线+空六边形= L长键  |  彩色轮廓=骨架家族，圈号=骨架，椭圆=桥")


def lib_index():
    with open(os.path.join(BASE, "t8_forms.json"), "r", encoding="utf-8") as f:
        forms = json.load(f)
    return {fm["formula"]: i + 1 for i, fm in enumerate(forms)}


LIBIDX = lib_index()


def load():
    with open(DATA, "r", encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------- 小图标
def fam_icon(d, cx, cy, r, key, kcount=1, col=None):
    poly = S.fam_shape(key, cx, cy, r, r, kcount)
    col = col or S.FAMILY[key]["col"]
    d.polygon(poly, fill=S.lighten(col, 0.78), outline=col, width=2)


def sk_badge(d, cx, cy, r, num, col, size=15):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#ffffff",
              outline=col, width=2)
    S.text_center(d, cx, cy, str(num), size, col)


def kind_col(kind):
    return S.BRIDGE_COL.get(kind, S.BRIDGE_COL.get(kind[:1], "#7f8c8d"))


def mini_skel(d, box, mol, sk):
    """在 box 内画该骨架自身的真实形状（字形 + 键 + 家族轮廓）。"""
    idx = sk["idx"]
    pos0 = {v: tuple(mol["place"][v]) for v in idx}
    s, ox, oy = S.fit_layout(list(pos0.values()), box, margin=1.0)
    pos = {}
    for v, (q, r) in pos0.items():
        x, y = S.center_of((q, r), s)
        pos[v] = (x + ox, y + oy)
    key, tint = S.fam_tint([mol["atoms"][v] for v in idx])
    kk = max(1, len([v for v in idx if mol["atoms"][v] == "K"]))
    hull = S.pad_hull(list(pos.values()), max(1.5, 0.42 * s + 1.5))
    d.polygon(hull, fill=S.lighten(tint, 0.80), outline=tint,
              width=max(1, int(s * 0.16)))
    inset = set(idx)
    for bd in mol["bonds"]:
        a, b = bd["a"], bd["b"]
        if a in inset and b in inset:
            col = S.BONDC.get(bd.get("type"), "#95a5a6")
            w = max(1, int(s * 0.14))
            if bd.get("type") == "L":
                S.dashed(d, pos[a], pos[b], S.lighten(col, 0.2), w, 3, 3)
            else:
                d.line([pos[a], pos[b]], fill=S.lighten(col, 0.1), width=w)
    for v in idx:
        el = mol["atoms"][v]
        poly = S.atom_poly(el, pos[v][0], pos[v][1], s, kk)
        d.polygon(poly, fill=S.lighten(S.ELEMCOL[el], 0.28),
                  outline="#34495e", width=max(1, int(s * 0.10)))


# --------------------------------------------------------------- 卡片
def render_card(cv, x0, y0, mol, idx):
    d = cv.d
    W, H = CARD_W, CARD_H
    # 卡片边框
    d.rectangle([x0, y0, x0 + W, y0 + H], fill="#ffffff",
                outline="#c8cdd2", width=2)
    # ---- 头部
    hx = x0 + 22
    d.text((hx, y0 + 12), mol["mid"], font=cv.f(30, True), fill="#1c2833")
    num_w = cv.f(30, True).getlength(mol["mid"])
    fx = hx + num_w + 16
    S.draw_formula(d, fx, y0 + 30, mol["formula"], 25, "#1c2833", True,
                   center=False)
    fw = cv.f(25, True).getlength(mol["formula"])
    sub = "%s · %d 原子 · %d 骨架 · %d 桥 · 分子家族 %s" % (
        mol["exp"], mol["n_atoms"], len(mol["skeletons"]), len(mol["bridges"]),
        mol["family_zh"])
    cv.txt(fx, y0 + 50, sub, 15, False, "#566573")
    # 右上角：稳定性 + 装饰
    dd = mol["deco_stats"]
    tag = "稳定 F(v_M)={M}  ✓ (pot_v4 复核)"
    tw = cv.f(14, True).getlength(tag)
    d.rounded_rectangle([x0 + W - 22 - tw - 18, y0 + 14,
                         x0 + W - 22, y0 + 40], radius=8,
                        fill="#eafaf1", outline="#27ae60", width=2)
    cv.txt(x0 + W - 22 - tw - 9, y0 + 20, tag, 14, True, "#1e8449")
    cv.txt(x0 + W - 22, y0 + 48, "来源 %s" % mol["exp"], 13, False,
           "#7f8c8d", "ra")
    # ---- 分子图
    box = (x0 + 16, y0 + 74, 1000, CARD_H - 96)
    info = S.draw_molecule(cv, box, mol, show_badges=True, max_s=44)
    d = cv.d  # composite 之后 draw 对象已更换，必须重新取
    # ---- 右侧面板
    px = x0 + 1032
    pw = W - 1052
    d.line([(px - 12, y0 + 62), (px - 12, y0 + H - 18)], fill="#dfe4e8",
           width=2)
    y = y0 + 66
    cv.txt(px, y, "骨架", 17, True, "#1c2833")
    cv.txt(px + pw, y, "S = 6 级骨架块", 11, False, "#95a5a6", "ra")
    y += 26
    for sk in mol["skeletons"]:
        fkey, col = S.fam_tint([mol["atoms"][v] for v in sk["idx"]])
        sk_badge(d, px + 13, y + 12, 13, sk["num"], col, 14)
        fam_icon(d, px + 46, y + 13, 13, fkey,
                 max(1, len([a for a in sk["idx"]
                             if mol["atoms"][a] == "K"])), col=col)
        S.draw_formula(d, px + 68, y + 12, sk["formula"], 18, "#1c2833",
                       True, center=False)
        blk_txt = "6级块 %d 个" % len(sk["blocks"])
        if sk["n_fusion_bonds"]:
            blk_txt += " · 融合 %d 键 %s" % (
                sk["n_fusion_bonds"], "/".join(sk["fusion_elems"]))
        libids = [LIBIDX.get(b["formula"]) for b in sk["blocks"]]
        lib_txt = "+".join("#%d" % i for i in libids if i)
        line2 = "%s · %d 原子 · %s%s" % (
            sk["family_zh"], sk["n"], blk_txt,
            (" · 38库 " + lib_txt) if lib_txt else "")
        cv.txt(px + 68, y + 26, line2, 12, False, "#5d6d7e")
        mini_skel(d, (px + pw - 88, y - 2, 88, 48), mol, sk)
        y += 48
    y += 6
    cv.txt(px, y, "桥（二价连接层）", 17, True, "#1c2833")
    cv.txt(px + pw, y, "%d 条" % len(mol["bridges"]), 12, False,
           "#95a5a6", "ra")
    y += 32
    for bi, br in enumerate(mol["bridges"]):
        col = kind_col(br["kind"])
        d.ellipse([px + 2, y + 4, px + 22, y + 18], outline=col, width=2)
        S.text_center(d, px + 12, y + 11, str(bi + 1), 10, col)
        S.draw_formula(d, px + 30, y + 11, br["formula"], 15, "#1c2833",
                       True, center=False)
        types = "+".join("%s×%d" % (t, br["types"].count(t))
                         for t in "SCL" if t in br["types"])
        cv.txt(px + 176, y + 2, "%s · %d 原子 · %s" % (
            br["kind"], br["k"], types), 12, False, "#5d6d7e")
        y += 20
    # 装饰统计
    y += 8
    cv.txt(px, y, "装饰层", 15, True, "#1c2833")
    y += 20
    dd = mol["deco_stats"]
    cv.txt(px, y, "一价端帽 %d · 支臂 %d · 骨架内桥 %d · 游离二价 %d" % (
        dd.get("mono", 0), dd.get("arms", 0), dd.get("intra", 0),
        dd.get("free", 0)), 12, False, "#5d6d7e")
    # ---- 底部小图例
    cv.txt(x0 + 18, y0 + H - 22, "△O ○P ■K 尖六边形X 圆角W 虚线A 小点C/L/F | "
           "红S键 绿C键 紫虚L键 | 彩框=骨架家族 圈号=骨架 椭圆=桥", 11, False,
           "#95a5a6")
    return info


def page_frame(cv, page, n_pages, subtitle):
    d = cv.d
    cv.txt(38, 26, "T68 大分子骨架图册", 34, True, "#1c2833")
    cv.txt(38, 68, subtitle, 15, False, "#566573")
    cv.txt(PAGE_W - 38, 30, "第 %d / %d 页" % (page, n_pages), 18, True,
           "#7f8c8d", "ra")
    d.line([(38, 92), (PAGE_W - 38, 92)], fill="#bdc3c7", width=2)
    # 7 家族容器图例
    x = 38
    cv.txt(x, PAGE_H - 74, "骨架容器（三价组成 → 7 种外形）：", 12, True,
           "#5d6d7e")
    x += 250
    for key in ("O", "P", "K", "OP", "OK", "PK", "OPK"):
        fam_icon(d, x + 9, PAGE_H - 68, 9, key)
        cv.txt(x + 22, PAGE_H - 75, S.FAMILY[key]["zh"] + key, 11, False,
               "#5d6d7e")
        x += 20 + int(cv.f(11).getlength(S.FAMILY[key]["zh"] + key)) + 26
    cv.txt(38, PAGE_H - 32, LEGEND_GLYPH, 11, False, "#95a5a6")


def do_one(mid):
    data = load()
    mol = next(m for m in data["molecules"] if m["mid"] == mid)
    cv = S.Canvas(CARD_W, CARD_H)
    info = render_card(cv, 0, 0, mol, 0)
    p = os.path.join(OUT, "t68_card_%s.png" % mid)
    cv.save(p)
    print("s =", info["s"], "badges =", len(info["badges"]))


def do_all():
    data = load()
    mols = data["molecules"]
    for pg in range(N_PAGE):
        chunk = mols[pg * CARDS_PER_PAGE:(pg + 1) * CARDS_PER_PAGE]
        cv = S.Canvas(PAGE_W, PAGE_H)
        page_frame(cv, pg + 1, N_PAGE,
                   "36 个来自 T61~T64 的大分子 / 特大分子稳定物质（≥14 原子；"
                   "全部 F(v_M)={M} 并经 pot_v4 复核）")
        for j, mol in enumerate(chunk):
            render_card(cv, 30, 100 + j * (CARD_H + 22), mol, j)
        cv.save(os.path.join(OUT, "t68_giants_%02d.png" % (pg + 1)))
    # 总览
    do_overview(mols)


def do_overview(mols):
    cols, rows = 6, 6
    cw, ch = 250, 236
    W, H = cols * cw + 80, rows * ch + 190
    cv = S.Canvas(W, H)
    cv.txt(40, 24, "T68 大分子骨架图册 · 总览（36 个稳定大分子）", 32, True,
           "#1c2833")
    cv.txt(40, 66, "每格：编号 + 分子式 + 原子数/骨架数/桥数 + 骨架家族色块；"
           "详细卡片见 t68_giants_01~18.png", 14, False, "#566573")
    for i, mol in enumerate(mols):
        r, c = divmod(i, cols)
        x0 = 40 + c * cw
        y0 = 120 + r * ch
        cv.txt(x0, y0, mol["mid"], 17, True, "#1c2833")
        S.draw_formula(cv.d, x0 + 42, y0 + 5, mol["formula"], 12, "#1c2833",
                       False, center=False)
        cv.txt(x0, y0 + 22, "%d 原子 · %d 骨架 · %d 桥" % (
            mol["n_atoms"], len(mol["skeletons"]), len(mol["bridges"])),
            11, False, "#7f8c8d")
        box = (x0 + 4, y0 + 40, cw - 24, ch - 66)
        S.draw_molecule(cv, box, mol, show_badges=False, max_s=12)
        y = y0 + ch - 22
        # 家族色条
        acc = []
        for sk in mol["skeletons"]:
            if sk["family"] not in acc:
                acc.append(sk["family"])
        for j, fam in enumerate(acc[:5]):
            col = S.FAMILY[fam]["col"]
            cv.d.rectangle([x0 + 2 + j * 26, y0 + ch - 26,
                            x0 + 20 + j * 26, y0 + ch - 12],
                           fill=S.lighten(col, 0.55), outline=col)
            S.text_center(cv.d, x0 + 11 + j * 26, y0 + ch - 19,
                          fam, 8, "#1c2833")
    cv.save(os.path.join(OUT, "t68_overview.png"))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "one"
    if mode == "one":
        do_one(sys.argv[2] if len(sys.argv) > 2 else "G13")
    else:
        do_all()
