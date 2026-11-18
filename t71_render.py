# -*- coding: utf-8 -*-
"""T71 图集：能力总表 / 38 骨架能力与分化 / 涌现物种卡 / 36 物种总览。"""
import json
import math

import t68_shapes as S
import t71_abilities as A
import t70b_body as B

INK = (32, 44, 58)
INK2 = (96, 112, 128)
ORG = (36, 120, 96)
INORG = (52, 92, 150)
GRID = (232, 238, 244)

ABIL_ZH = {k: v[0] for k, v in A.ABIL.items()}
ABIL_KIND = {k: v[1] for k, v in A.ABIL.items()}
LV = {1: "Ⅰ", 2: "Ⅱ", 3: "Ⅲ"}

MORPH_ZH = {k: (zh, desc) for (k, zh, desc) in A.MORPH_RULES}
MORPH_COL = {"clasper": (140, 82, 160), "bridge": (38, 120, 168), "tentacle": (196, 118, 44),
             "cap": (86, 140, 92), "sensory": (168, 72, 96), "basic": (120, 128, 138)}


def _chip(cv, x, y, text, col=(248, 250, 252), ink=INK, size=11, bold=False, padx=6, h=18):
    f = cv.f(size, bold)
    w = int(cv.d.textlength(text, font=f)) + padx * 2
    cv.d.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=col, outline=(214, 222, 230))
    cv.txt(x + padx, y + h // 2, text, size, bold, ink, "lm")
    return x + w + 5


def _bar(cv, x, y, w, frac, col=(52, 132, 180)):
    cv.d.rounded_rectangle([x, y, x + w, y + 7], radius=3, fill=(232, 238, 244))
    if frac > 0:
        cv.d.rounded_rectangle([x, y, x + max(3, w * frac), y + 7], radius=3, fill=col)


# ---------------------------------------------------------------- 能力总表
def page_abilities(path="images/t71_abilities.png"):
    W, H = 1600, 1180
    cv = S.Canvas(W, H, (255, 255, 255))
    cv.txt(40, 52, "T71 能力系统 · 每种骨架能长出什么本事", 26, True, INK, "lm")
    cv.txt(40, 82, "能力来自元素（材料层）× 骨架（器官层）：元素给出能力的“材料底子”，骨架的分化形态决定它把这份本事用在哪儿。",
           12.5, False, INK2, "lm")

    # A 元素 → 能力
    cv.txt(40, 122, "A. 九元素的能力底色（Ⅰ/Ⅱ/Ⅲ = 能力强度，随该元素在骨架里的数量升级）", 15, True, INK, "lm")
    ELS = [("O", "秩"), ("X", "晶"), ("C", "冰"), ("P", "势"), ("W", "流"), ("L", "电"),
           ("K", "沌"), ("A", "气"), ("F", "焰")]
    cw = 168
    for i, (el, zh) in enumerate(ELS):
        x = 44 + i * (cw + 6)
        y = 152
        cv.d.rounded_rectangle([x, y, x + cw, y + 128], radius=10, fill=(250, 252, 254), outline=GRID)
        col = S.ELEMCOL[el]
        cv.d.polygon(S.atom_poly(el, x + 30, y + 26, 22, 2), fill=S.lighten(col, 0.45), outline=col)
        cv.txt(x + 48, y + 26, "%s%s" % (zh, el), 15, True, INK, "lm")
        for j, (ab, lv) in enumerate(A.ELEM_ABIL[el]):
            yy = y + 52 + j * 18
            kind = ABIL_KIND[ab]
            dot = ORG if kind == "org" else INORG
            cv.d.ellipse([x + 12, yy + 5, x + 19, yy + 12], fill=dot)
            cv.txt(x + 25, yy + 8, "%s %s" % (ABIL_ZH[ab], LV[lv]), 11.5, False, INK, "lm")

    # B 30 能力
    cv.txt(40, 320, "B. 30 项能力清单（● 有机向 / ● 无机向）", 15, True, INK, "lm")
    org = [k for k, v in A.ABIL.items() if v[1] == "org"]
    ino = [k for k, v in A.ABIL.items() if v[1] == "inorg"]
    col_w = 250
    for i, ab in enumerate(org):
        x = 44 + (i % 5) * (col_w + 18)
        y = 344 + (i // 5) * 46
        cv.d.ellipse([x, y + 5, x + 8, y + 13], fill=ORG)
        cv.txt(x + 14, y + 9, ABIL_ZH[ab], 13, True, INK, "lm")
        cv.txt(x + 14, y + 26, {"differentiate": "长出不同形态的接口", "regenerate": "断口重新长出",
                                "adhere": "把器官粘成一体", "mutate": "结构可塑性",
                                "move": "触肢/腱推动整体", "pump": "流桥推动体液",
                                "flex": "关节可弯", "store": "蓄能待发",
                                "elastic": "形变回弹", "catalyze": "加速邻体反应",
                                "heal": "受损自修补", "sense": "感知邻体/电场",
                                "shape_s": "整体变形", "float": "气腔漂浮",
                                "adsorb": "表面吸附", "volatile": "挥发扩散",
                                "grasp": "冰端抓握", "glow": "焰端发光",
                                "cut": "焰端切割", "defend": "外壳防御",
                                "climb": "攀附", "charge": "放电",
                                "signal": "长距信号"}.get(ab, ""), 10.5, False, INK2, "lm")
    ybase = 344 + ((len(org) + 4) // 5) * 46 + 18
    cv.txt(44, ybase, "无机向：", 13, True, INORG, "lm")
    xx = 120
    for ab in ino:
        xx = _chip(cv, xx, ybase - 9, "%s（%s）" % (ABIL_ZH[ab], {"support": "结构", "rigid": "刚性",
                                                                 "heat": "耐热", "dense": "致密",
                                                                 "insulate": "绝缘", "conduct": "导电",
                                                                 "cold": "耐寒"}[ab]), size=11.5)
        if xx > W - 160:
            xx = 120
            ybase += 26

    # C 分化形态
    yc = ybase + 70
    cv.txt(40, yc, "C. 三价骨架的分化形态（6 种，按“这个骨架接了几个邻居、长出几根触肢”自动选型）", 15, True, INK, "lm")
    for i, (key, zh, desc) in enumerate(A.MORPH_RULES):
        x = 44 + i * 258
        y = yc + 20
        col = MORPH_COL[key]
        cv.d.rounded_rectangle([x, y, x + 244, y + 154], radius=10, fill=S.lighten("#%02x%02x%02x" % col, 0.90), outline=col)
        _morph_icon(cv, x + 40, y + 46, key, 26, col)
        cv.txt(x + 76, y + 30, zh, 15, True, col, "lm")
        cv.txt(x + 16, y + 82, "%s" % desc, 10.8, False, INK, "la", wrap=210)

    cv.txt(40, H - 46, "注：当前“刚性/松散/粘性”按 S/C/L 键占比暂行推断，等同事正式规则上传后替换；固/液/气按 X/W/A 数量按新规则判定。",
           11.5, False, INK2, "lm")
    cv.save(path)
    print("saved", path)


def _morph_icon(cv, cx, cy, key, r, col):
    d = cv.d
    pts = S.fam_shape("OPK", cx, cy, r * 1.1, r, 2)
    d.polygon(pts, fill=S.lighten("#%02x%02x%02x" % col, 0.72), outline=col)
    if key == "clasper":
        for a in (-150, -30, 90):
            p = (cx + math.cos(math.radians(a)) * r * 1.5, cy + math.sin(math.radians(a)) * r * 1.5)
            d.polygon(S.poly_pts(p[0], p[1], r * 0.55, r * 0.30, 3, rot=math.radians(a)), fill=None, outline=col, width=2)
    elif key == "bridge":
        d.line([cx - r * 2.0, cy, cx + r * 2.0, cy], fill=col, width=3)
    elif key == "tentacle":
        for a in (-40, 20, 70):
            d.line([cx, cy, cx + math.cos(math.radians(a)) * r * 2.0, cy + math.sin(math.radians(a)) * r * 2.0],
                   fill=col, width=2)
    elif key == "cap":
        d.arc([cx - r * 0.7, cy - r * 1.9, cx + r * 0.7, cy - r * 0.3], 180, 360, fill=col, width=3)
    elif key == "sensory":
        for a in range(0, 360, 45):
            d.line([cx + math.cos(math.radians(a)) * r * 1.1, cy + math.sin(math.radians(a)) * r * 1.1,
                    cx + math.cos(math.radians(a)) * r * 1.7, cy + math.sin(math.radians(a)) * r * 1.7],
                   fill=col, width=1)
    else:
        for a in range(0, 360, 120):
            d.line([cx, cy, cx + math.cos(math.radians(a)) * r * 1.4, cy + math.sin(math.radians(a)) * r * 1.4],
                   fill=col, width=2)


# 支持 wrap 的 txt
_orig_txt = S.Canvas.txt


def _txt_wrap(self, x, y, s, size=12, bold=False, fill=INK, anchor="lm", wrap=None):
    if not wrap:
        return _orig_txt(self, x, y, s, size, bold, fill, anchor)
    f = self.f(size, bold)
    lines, cur = [], ""
    for ch in s:
        if self.d.textlength(cur + ch, font=f) <= wrap:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    lines.append(cur)
    for i, ln in enumerate(lines):
        _orig_txt(self, x, y + i * (size + 4), ln, size, bold, fill, anchor)
    return y + len(lines) * (size + 4)


S.Canvas.txt = _txt_wrap


# ---------------------------------------------------------------- 38 骨架
def block_rows():
    forms = json.load(open("t8_forms.json", encoding="utf-8"))
    rows = []
    for i, f in enumerate(forms):
        atoms = f["atoms"]
        counts = {}
        for a in atoms:
            counts[a] = counts.get(a, 0) + 1
        ab = A.abilities_of(counts)
        top = sorted(ab.items(), key=lambda kv: (-kv[1], kv[0]))[:4]
        key = S.fam_key([a for a in counts if a in ("O", "P", "K")])
        rows.append({"lib": i + 1, "formula": f["formula"], "atoms": atoms, "key": key,
                     "n": len(atoms), "ab": ab, "top": top, "counts": counts})
    return rows


def page_skeletons(path="images/t71_skeletons38.png"):
    rows = block_rows()
    cols, cw, ch = 4, 392, 92
    W = 40 + cols * cw + 20
    H = 150 + 10 * ch
    cv = S.Canvas(W, H, (255, 255, 255))
    cv.txt(40, 48, "T71 骨架能力表 · 38 个骨架块各自的能力与分化形态", 25, True, INK, "lm")
    cv.txt(40, 78, "每行：编号 / 公式 / 家族 / 材料能力（由元素给）/ 分化形态（由结构给）/ 器官角色。能力强度 Ⅰ~Ⅲ。",
           12.5, False, INK2, "lm")
    for i, r in enumerate(rows):
        col, row = i % cols, i // cols
        x = 40 + col * cw
        y = 104 + row * ch
        cv.d.rounded_rectangle([x, y, x + cw - 14, y + ch - 10], radius=8, fill=(252, 253, 255), outline=GRID)
        fam = S.FAMILY[r["key"]]
        cv.txt(x + 10, y + 14, "#%d" % r["lib"], 11, True, INK2, "lm")
        cv.txt(x + 40, y + 14, r["formula"], 13, True, INK, "lm")
        cv.d.rounded_rectangle([x + cw - 96, y + 6, x + cw - 22, y + 22], radius=8,
                               fill=S.lighten(fam["col"], 0.86), outline=fam["col"])
        cv.txt(x + cw - 59, y + 14, fam["zh"], 9.5, False, INK, "mm")
        xx = x + 10
        for ab, lv in r["top"]:
            kind = ABIL_KIND[ab]
            col2 = ORG if kind == "org" else INORG
            xx = _chip(cv, xx, y + 28, "%s %s" % (ABIL_ZH[ab], LV.get(lv, lv)), col=S.lighten("#%02x%02x%02x" % col2, 0.90),
                       ink=INK, size=9.5, padx=4, h=15)
            if xx > x + cw - 40:
                break
        # 分化形态：按骨架在库里的度数潜力给一个主形态
        n3 = sum(1 for a in r["atoms"] if a in ("O", "P", "K"))
        morph = "clasper" if r["n"] >= 5 else ("bridge" if r["n"] >= 3 else "basic")
        cv.txt(x + 10, y + 56, "分化：%s · 器官角色 %s" % (MORPH_ZH[morph][0], A.FAMILY_PREFIX.get(r["key"], ["体"])[0]),
               11, False, INK, "lm")
        cv.txt(x + 10, y + 74, "结构：%d 原子 · 三价 %d · 家族 %s" % (r["n"], n3, fam["zh"]), 10.5, False, INK2, "lm")
    cv.save(path)
    print("saved", path)


# ---------------------------------------------------------------- 物种卡
def _species_panel(cv, x, y, w, h, tr):
    cv.txt(x, y + 14, tr["name"], 19, True, INK, "lm", wrap=w)
    cv.txt(x, y + 40, "%s" % tr["formula"], 12, False, INK2, "lm")
    xx = x
    for text, col in [("生命分 %.1f" % tr["life_score"], (200, 92, 60)),
                      (tr["class_zh"], ORG if tr["class"] in ("life", "proto") else INORG),
                      (tr["state"], (110, 118, 130)), (tr["softness"], (120, 100, 160))]:
        xx = _chip(cv, xx, y + 50, text, col=S.lighten("#%02x%02x%02x" % col, 0.88), size=10.5, h=17)
    yy = y + 76
    cv.txt(x, yy, "器官（骨架块 · 分化形态 · 主要能力）", 11.5, True, INK, "lm")
    yy += 18
    for o in tr["organs"]:
        col = S.FAMILY[o["family"]]["col"] if o["family"] in S.FAMILY else INK2
        cv.d.ellipse([x + 2, yy + 5, x + 10, yy + 13], fill=col)
        mk = o["morph"]["key"]
        cv.txt(x + 17, yy + 9, "%d %s" % (o["num"], o["formula"]), 11, True, INK, "lm")
        cv.txt(x + 100, yy + 9, MORPH_ZH[mk][0], 10.5, False, MORPH_COL[mk], "lm")
        top = sorted(o["abilities"].items(), key=lambda kv: -kv[1])[:3]
        cv.txt(x + 158, yy + 9, " · ".join("%s%s" % (ABIL_ZH[a], LV.get(l, l)) for a, l in top), 10, False, INK2, "lm")
        yy += 17
        if yy > y + h - 34:
            break
    yy += 6
    cv.txt(x, yy, "整体能力：", 11.5, True, INK, "lm")
    xx = x + 70
    for ab, lv in sorted(tr["abilities"].items(), key=lambda kv: -kv[1])[:6]:
        xx = _chip(cv, xx, yy - 8, "%s %s" % (ABIL_ZH.get(ab, ab), LV.get(lv, lv)), size=9.5, padx=4, h=15)
        if xx > x + w - 70:
            break
    cv.txt(x, y + h - 16, "生态位：%s" % _niche(tr), 10.8, False, INK2, "lm", wrap=w)


def _niche(tr):
    f = tr["life_flags"]
    bits = []
    if f.get("differentiate"):
        bits.append("多器官分工")
    if f.get("move"):
        bits.append("主动移动")
    if f.get("symbiosis"):
        bits.append("器官共生")
    if f.get("grasp"):
        bits.append("抓握取食")
    if f.get("adsorb"):
        bits.append("表面吸附")
    if f.get("heal"):
        bits.append("损伤自修")
    if f.get("pump"):
        bits.append("体液泵送")
    if f.get("store"):
        bits.append("能量储备")
    if f.get("sense"):
        bits.append("感知环境")
    if tr["class"] == "inert":
        return "无机晶体，仅靠结构与表面反应存在"
    return "；".join(bits) if bits else "结构简单，行为被动"


CHOICE = ["G33", "G14", "G13", "G16", "G24", "G07"]


def page_organisms(picks=CHOICE, path="images/t71_organisms.png"):
    data = A.load_molecules()
    by = {m["mid"]: m for m in data}
    rows = []
    for mid in picks:
        rows.append(A.molecule_traits(by[mid]))
    W, H = 1600, 200 + len(rows) * 470
    cv = S.Canvas(W, H, (255, 255, 255))
    cv.txt(40, 48, "T71 涌现物种卡 · 从骨架能力长出来的“生物”", 26, True, INK, "lm")
    cv.txt(40, 78, "每个分子 = 一个完整形体；体内分区 = 器官（骨架块）；器官的分化形态决定它怎么跟别的器官配合。"
                   "由 30 项能力 + 6 种分化形态 + 固/液/气判定，自动算出物种名与生态位。",
           12.3, False, INK2, "lm")
    for i, tr in enumerate(rows):
        y = 110 + i * 470
        cv.d.rounded_rectangle([30, y, W - 30, y + 450], radius=12, fill=(252, 253, 255), outline=GRID)
        B.draw_body_molecule(cv, by[tr["mid"]], (44, y + 20, 560, 410), max_s=76, show_badges=False)
        _species_panel(cv, 650, y + 16, 900, 424, tr)
    cv.save(path)
    print("saved", path)


def page_gallery(path="images/t71_gallery.png"):
    data = A.load_molecules()
    rows = [A.molecule_traits(m) for m in data]
    rows.sort(key=lambda t: -t["life_score"])
    cols, cw, ch = 4, 392, 226
    W, H = 40 + cols * cw + 20, 150 + 9 * ch
    cv = S.Canvas(W, H, (255, 255, 255))
    cv.txt(40, 48, "T71 36 个稳定大分子的物种名录（按生命分排序）", 26, True, INK, "lm")
    cv.txt(40, 78, "灰色=无机晶体 / 蓝=活性无机物 / 青=拟生命 / 绿=有机生命；每个格子里是它的完整形体与自动生成的名字。",
           12.3, False, INK2, "lm")
    by = {m["mid"]: m for m in data}
    for i, tr in enumerate(rows):
        col, row = i % cols, i // cols
        x = 40 + col * cw
        y = 104 + row * ch
        colr = {"life": ORG, "proto": (46, 140, 140), "active": (60, 100, 170), "inert": (130, 138, 148)}[tr["class"]]
        cv.d.rounded_rectangle([x, y, x + cw - 14, y + ch - 12], radius=8, fill=(252, 253, 255), outline=GRID)
        cv.d.rectangle([x, y, x + 4, y + ch - 12], fill=colr)
        cv.txt(x + 12, y + 13, tr["mid"], 12, True, INK, "lm")
        cv.txt(x + 56, y + 13, "%.1f" % tr["life_score"], 11, True, colr, "lm")
        B.draw_body_molecule(cv, by[tr["mid"]], (x + 12, y + 24, cw - 40, 130), max_s=17, show_badges=False)
        cv.txt(x + 12, y + ch - 62, tr["name"], 10.5, True, INK, "lm", wrap=cw - 34)
    cv.save(path)
    print("saved", path)


def main():
    page_abilities()
    page_skeletons()
    page_organisms()
    page_gallery()



# ================================================================ PATCH v2
def _morph_potential(n3):
    if n3 <= 0:
        return ["basic"]
    if n3 == 1:
        return ["cap", "sensory"]
    if n3 == 2:
        return ["bridge", "cap", "tentacle"]
    return ["clasper", "bridge", "tentacle"]


def page_abilities(path="images/t71_abilities.png"):
    W, H = 1600, 1230
    cv = S.Canvas(W, H, (255, 255, 255))
    cv.txt(40, 52, "T71 能力系统 · 每种骨架能长出什么本事", 26, True, INK, "lm")
    cv.txt(40, 82, "能力来自元素（材料层）× 骨架（器官层）：元素给出“材料底子”，骨架的分化形态决定它把这份本事用在哪儿。",
           12.5, False, INK2, "lm")

    cv.txt(40, 122, "A. 九元素的能力底色（Ⅰ/Ⅱ/Ⅲ = 能力强度，随该元素在骨架里的数量升级）", 15, True, INK, "lm")
    ELS = [("O", "秩"), ("X", "晶"), ("C", "冰"), ("P", "势"), ("W", "流"), ("L", "电"),
           ("K", "沌"), ("A", "气"), ("F", "焰")]
    cw = 168
    for i, (el, zh) in enumerate(ELS):
        x = 44 + i * (cw + 6)
        y = 150
        cv.d.rounded_rectangle([x, y, x + cw, y + 128], radius=10, fill=(250, 252, 254), outline=GRID)
        col = S.ELEMCOL[el]
        cv.d.polygon(S.atom_poly(el, x + 30, y + 26, 22, 2), fill=S.lighten(col, 0.45), outline=col)
        cv.txt(x + 48, y + 26, "%s%s" % (zh, el), 15, True, INK, "lm")
        for j, (ab, lv) in enumerate(A.ELEM_ABIL[el]):
            yy = y + 52 + j * 18
            dot = ORG if ABIL_KIND[ab] == "org" else INORG
            cv.d.ellipse([x + 12, yy + 5, x + 19, yy + 12], fill=dot)
            cv.txt(x + 25, yy + 8, "%s %s" % (ABIL_ZH[ab], LV[lv]), 11.5, False, INK, "lm")

    cv.txt(40, 318, "B. 30 项能力清单（● 有机向 / ● 无机向）", 15, True, INK, "lm")
    DESC = {"differentiate": "长出不同形态的接口", "regenerate": "断口重新长出",
            "adhere": "把器官粘成一体", "mutate": "结构可塑性",
            "move": "触肢/腱推动整体", "pump": "流桥推动体液",
            "flex": "关节可弯", "store": "蓄能待发",
            "elastic": "形变回弹", "catalyze": "加速邻体反应",
            "heal": "受损自修补", "sense": "感知邻体/电场",
            "shape_s": "整体变形", "float": "气腔漂浮",
            "adsorb": "表面吸附", "volatile": "挥发扩散",
            "grasp": "冰端抓握", "glow": "焰端发光",
            "cut": "焰端切割", "defend": "外壳防御",
            "climb": "攀附", "charge": "放电", "signal": "长距信号"}
    org = [k for k, v in A.ABIL.items() if v[1] == "org"]
    ino = [k for k, v in A.ABIL.items() if v[1] == "inorg"]
    col_w = 250
    for i, ab in enumerate(org):
        x = 44 + (i % 5) * (col_w + 18)
        y = 342 + (i // 5) * 46
        cv.d.ellipse([x, y + 5, x + 8, y + 13], fill=ORG)
        cv.txt(x + 14, y + 9, ABIL_ZH[ab], 13, True, INK, "lm")
        cv.txt(x + 14, y + 26, DESC.get(ab, ""), 10.5, False, INK2, "lm")
    ybase = 342 + ((len(org) + 4) // 5) * 46 + 14
    cv.txt(44, ybase, "无机向：", 13, True, INORG, "lm")
    xx = 120
    for ab in ino:
        xx = _chip(cv, xx, ybase - 9, ABIL_ZH[ab], size=11.5)
        if xx > W - 200:
            xx = 120
            ybase += 26

    yc = ybase + 46
    cv.txt(40, yc, "C. 三价骨架的分化形态（6 种，按“接了几个邻居、长出几根触肢”自动选型）", 15, True, INK, "lm")
    for i, (key, zh, desc) in enumerate(A.MORPH_RULES):
        x = 44 + i * 258
        y = yc + 18
        col = MORPH_COL[key]
        cv.d.rounded_rectangle([x, y, x + 244, y + 172], radius=10,
                               fill=S.lighten("#%02x%02x%02x" % col, 0.91), outline=col)
        _morph_icon(cv, x + 34, y + 56, key, 22, col)
        cv.txt(x + 62, y + 18, zh, 15, True, col, "lm")
        cv.txt(x + 14, y + 96, desc, 10.8, False, INK, "la", wrap=214)

    yd = yc + 208
    cv.txt(40, yd, "D. 生命度分级（结构门控打分：只有真正长出对应器官结构的能力才计分）", 15, True, INK, "lm")
    CLASSES = [("有机生命", "≥ 8.0", ORG, "多器官分工 + 主动移动/共生/储能中至少三项；可自主行动与配合"),
               ("拟生命", "5.0 ~ 8.0", (46, 140, 140), "器官分工已出现，但缺少完整的行动-感知-代谢闭环"),
               ("活性无机物", "3.0 ~ 5.0", (60, 100, 170), "结构上有活性（会动/会吸/会蓄能），但没有器官分工"),
               ("无机晶体", "< 3.0", (130, 138, 148), "结构稳定、行为被动，只靠表面与晶格性质存在")]
    for i, (zh, rng, col, desc) in enumerate(CLASSES):
        x = 44 + i * 382
        y = yd + 16
        cv.d.rounded_rectangle([x, y, x + 366, y + 96], radius=10, fill=S.lighten("#%02x%02x%02x" % col, 0.92), outline=col)
        cv.txt(x + 14, y + 20, zh, 15, True, col, "lm")
        cv.txt(x + 100, y + 20, rng, 12, False, INK, "lm")
        cv.txt(x + 14, y + 44, desc, 10.8, False, INK, "la", wrap=336)
    cv.txt(44, yd + 132, "物种命名：状态（固/流/浮）· 软硬（刚性/粘性/松散） + 生命类 + 主体形状 + 「主要能力」。"
                         "例：固态·粘性 生体·多器官六面簇体「分化·移动·储能」。", 12, False, INK2, "lm")
    cv.txt(40, H - 44, "注：“刚性/松散/粘性”目前按 S/C/L 键占比暂行推断，等同事正式规则上传后替换；固/液/气按 X/W/A 数量判定。",
           11.5, False, INK2, "lm")
    cv.save(path)
    print("saved", path)


def page_skeletons(path="images/t71_skeletons38.png"):
    rows = block_rows()
    cols, cw, ch = 4, 392, 112
    W = 40 + cols * cw + 16
    H = 150 + 10 * ch
    cv = S.Canvas(W, H, (255, 255, 255))
    cv.txt(40, 48, "T71 骨架能力表 · 38 个骨架块各自能长出什么", 25, True, INK, "lm")
    cv.txt(40, 78, "每格：编号 / 公式 / 家族 / 材料能力（元素给） / 可分化形态（结构给） / 器官角色。能力强度 Ⅰ~Ⅲ。",
           12.5, False, INK2, "lm")
    for i, r in enumerate(rows):
        col, row = i % cols, i // cols
        x = 40 + col * cw
        y = 106 + row * ch
        cv.d.rounded_rectangle([x, y, x + cw - 14, y + ch - 12], radius=8, fill=(252, 253, 255), outline=GRID)
        fam = S.FAMILY[r["key"]]
        cv.txt(x + 12, y + 15, "#%d" % r["lib"], 11, True, INK2, "lm")
        cv.txt(x + 44, y + 15, r["formula"], 14, True, INK, "lm")
        cv.d.rounded_rectangle([x + cw - 100, y + 6, x + cw - 22, y + 24], radius=9,
                               fill=S.lighten(fam["col"], 0.86), outline=fam["col"])
        cv.txt(x + cw - 61, y + 15, fam["zh"], 9.5, False, INK, "mm")
        xx = x + 12
        for ab, lv in r["top"]:
            kind = ABIL_KIND[ab]
            col2 = ORG if kind == "org" else INORG
            f = cv.f(9.5)
            wtxt = "%s %s" % (ABIL_ZH[ab], LV.get(lv, lv))
            wch = int(cv.d.textlength(wtxt, font=f)) + 8
            if xx + wch > x + cw - 26:
                break
            _chip(cv, xx, y + 30, wtxt, col=S.lighten("#%02x%02x%02x" % col2, 0.90),
                  ink=INK, size=9.5, padx=4, h=15)
            xx += wch + 5
        n3 = sum(1 for a in r["atoms"] if a in ("O", "P", "K"))
        xx = x + 12
        yy = y + 56
        for mk in _morph_potential(n3):
            col3 = MORPH_COL[mk]
            xx = _chip(cv, xx, yy, MORPH_ZH[mk][0], col=S.lighten("#%02x%02x%02x" % col3, 0.90),
                       ink=col3, size=9.5, padx=5, h=16) - 5
        cv.txt(x + 12, y + 86, "器官角色：%s%s · %d 原子（三价 %d）" % (
            A.FAMILY_PREFIX.get(r["key"], ["体"])[0], "·" + fam["zh"], r["n"], n3), 10.5, False, INK2, "lm")
    cv.save(path)
    print("saved", path)


def _species_panel(cv, x, y, w, h, tr):
    cv.txt(x, y + 14, tr["name"], 19, True, INK, "lm", wrap=w)
    cv.txt(x, y + 42, tr["formula"] + "   ·   生命分 %.1f   ·   %s   ·   %s   ·   %s" % (
        tr["life_score"], tr["class_zh"], tr["state"], tr["softness"]), 11.5, False, INK2, "lm")
    yy = y + 64
    cv.txt(x, yy, "器官（骨架块 · 分化形态 · 主要能力）", 11.5, True, INK, "lm")
    yy += 17
    for o in tr["organs"][:6]:
        col = S.FAMILY[o["family"]]["col"] if o["family"] in S.FAMILY else INK2
        mk = o["morph"]["key"]
        cv.d.ellipse([x + 2, yy + 5, x + 10, yy + 13], fill=col)
        cv.txt(x + 17, yy + 9, "%d %s" % (o["num"], o["formula"]), 11, True, INK, "lm")
        cv.txt(x + 104, yy + 9, MORPH_ZH[mk][0], 10.5, False, MORPH_COL[mk], "lm")
        top = sorted(o["abilities"].items(), key=lambda kv: -kv[1])[:3]
        cv.txt(x + 164, yy + 9, " · ".join("%s%s" % (ABIL_ZH[a], LV.get(l, l)) for a, l in top),
               10, False, INK2, "lm")
        yy += 17
    yy += 12
    cv.txt(x, yy, "整体能力：", 11.5, True, INK, "lm")
    xx = x + 72
    for ab, lv in sorted(tr["abilities"].items(), key=lambda kv: -kv[1])[:5]:
        f = cv.f(9.5)
        wtxt = "%s %s" % (ABIL_ZH.get(ab, ab), LV.get(lv, lv))
        wch = int(cv.d.textlength(wtxt, font=f)) + 8
        if xx + wch > x + w - 10:
            break
        _chip(cv, xx, yy - 8, wtxt, size=9.5, padx=4, h=15)
        xx += wch + 5
    cv.txt(x, yy + 20, "生态位：" + _niche(tr), 10.8, False, INK2, "lm", wrap=w)

if __name__ == "__main__":
    main()
