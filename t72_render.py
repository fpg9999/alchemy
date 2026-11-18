# -*- coding: utf-8 -*-
"""T72 图集：能力总表 / 28 种分化形态 / 38 骨架的形态分化 / 大分子物种卡 / 小分子形态。"""
import json
import math
from collections import Counter

import t68_shapes as S
import t71_abilities as A
import t70b_body as B
import t72_abilities as AB
import t72_morphs as M
import pot_all as P

INK = (30, 42, 56)
INK2 = (98, 114, 130)
GRID = (232, 238, 244)
LV = {1: "Ⅰ", 2: "Ⅱ", 3: "Ⅲ"}
S3 = math.sqrt(3)
ELEM_COL = S.ELEMCOL


def _hx(c):
    if isinstance(c, str):
        return c
    return "#%02x%02x%02x" % tuple(c)


def _wrap(cv, x, y, text, size=11, fill=INK, maxw=300, lh=None, bold=False):
    f = cv.f(size, bold)
    lh = lh or (size + 4)
    lines, cur = [], ""
    for ch in text:
        if cv.d.textlength(cur + ch, font=f) <= maxw:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    lines.append(cur)
    for i, ln in enumerate(lines):
        cv.txt(x, y + i * lh, ln, size, bold, fill, "lm")
    return y + len(lines) * lh


# ------------------------------------------------------------------ 性状
def organ_traits(mol):
    out = []
    for sk in mol["skeletons"]:
        atoms = [mol["atoms"][i] for i in sk["idx"]]
        cnt = Counter(atoms)
        fam = AB.family_of_block(atoms)
        ab = AB.levels(cnt, AB.FAMILY_BONUS.get(fam, {}))
        n3 = len(sk["idx"])
        morphs = M.pick_morphs(fam, cnt, n3, seed=sk["num"])
        out.append({"num": sk["num"], "formula": sk["formula"], "fam": fam,
                    "counts": cnt, "abilities": ab, "n3": n3, "morphs": morphs,
                    "nbrs": len(sk.get("idx", [])), "zh": sk.get("family_zh", "")})
    return out


def molecule_traits(mol):
    counts = Counter(mol["atoms"])
    organs = organ_traits(mol)
    fams = Counter(o["fam"] for o in organs)
    fam0 = fams.most_common(1)[0][0] if fams else AB.family_of_block(mol["atoms"])
    ab_all = AB.levels(counts, AB.FAMILY_BONUS.get(fam0, {}))
    state, why = A.physical_state(counts)
    soft, _ = A.softness(mol)
    nint = sum(1 for k, v in ab_all.items() if AB.ABIL[k]["kind"] == "inorg")
    norg = sum(1 for k, v in ab_all.items() if AB.ABIL[k]["kind"] == "org")
    kind_zh = "有机体" if norg > nint * 1.25 else ("无机晶体" if nint > norg * 1.25 else "有机-无机杂合体")
    top = sorted(ab_all.items(), key=lambda kv: (-kv[1], kv[0]))[:6]
    m0 = organs[0]["morphs"][0] if organs else "column"
    mzh = next((mm[1] for mm in M.morph_list(organs[0]["fam"] if organs else "OPK") if mm[0] == m0), "基体")
    shape = "%s%s" % ("多器官" if len(organs) >= 3 else "", mzh + "体")
    feat = "·".join(AB.ABIL[k]["zh"] for k, lv in top[:3])
    name = "%s·%s %s·%s「%s」" % (state, soft, kind_zh, shape, feat)
    return {"mid": mol.get("mid", mol["formula"]), "formula": mol["formula"],
            "n_atoms": mol["n_atoms"], "counts": dict(counts), "organs": organs,
            "abilities": ab_all, "top": top, "state": state, "state_why": why,
            "softness": soft, "kind_zh": kind_zh, "name": name}


# ------------------------------------------------------------------ A 能力总表
def page_abilities(path="images/t72_abilities.png"):
    W, H = 1700, 1300
    cv = S.Canvas(W, H, (255, 255, 255))
    cv.txt(40, 52, "T72 能力总表 · 72 项能力（9 大类）", 26, True, INK, "lm")
    cv.txt(40, 82, "每项能力标注亲和元素与权重：元素越多、该能力越强（Ⅰ~Ⅲ）。构成本表的是“物质能做什么”，"
                   "具体某块骨架能长到几级，还要看它的元素计数与家族加成。", 12.3, False, INK2, "lm")
    cats = AB.CATS
    bw, bh = 532, 372
    for ci, (ck, czh, col, cdesc) in enumerate(cats):
        col_i, row_i = ci % 3, ci // 3
        x = 40 + col_i * (bw + 18)
        y = 118 + row_i * (bh + 16)
        cv.d.rounded_rectangle([x, y, x + bw, y + bh], radius=12,
                               fill=S.lighten(_hx(col), 0.95), outline=col)
        cv.d.rectangle([x, y, x + 8, y + bh], fill=col)
        cv.txt(x + 20, y + 20, czh, 17, True, col, "lm")
        cv.txt(x + 20, y + 42, cdesc, 10.8, False, INK2, "lm")
        items = [a for a in AB.ABILITY if a[2] == ck]
        for j, (key, zh, cat, kind, els, desc) in enumerate(items):
            yy = y + 66 + j * 38
            cv.d.ellipse([x + 20, yy + 3, x + 27, yy + 10],
                         fill=(70, 160, 120) if kind == "org" else (70, 108, 170))
            cv.txt(x + 34, yy + 7, zh, 12.5, True, INK, "lm")
            xx = x + 150
            for el, w in sorted(els.items(), key=lambda kv: -kv[1]):
                cv.d.polygon(S.atom_poly(el, xx + 7, yy + 7, 8, 2), fill=ELEM_COL[el], outline=INK)
                cv.txt(xx + 17, yy + 7, "%d" % w, 8, False, INK2, "lm")
                xx += 30
            cv.txt(x + 250, yy + 7, desc, 9.8, False, INK2, "lm")
    cv.txt(40, H - 44, "● = 有机向能力（生命体特征）　● = 无机向能力（晶体/材料特征）。同一家族的各骨架共享加成，"
                       "但元素配比不同 → 能力谱不同。", 11.5, False, INK2, "lm")
    cv.save(path)
    print("saved", path)


# ------------------------------------------------------------------ B 28 形态
def page_morphs(path="images/t72_morphs.png"):
    W = 1700
    rowh, cw = 200, 372
    H = 150 + 7 * rowh
    cv = S.Canvas(W, H, (255, 255, 255))
    cv.txt(40, 48, "T72 骨架分化形态库 · 7 家族 × 4 种具体形态（共 28 种）", 26, True, INK, "lm")
    cv.txt(40, 78, "每个家族都有 4 种可分化形态，各有明确功能（括号里是它对应的能力）。骨架在分子里长成哪一种，"
                   "由它的元素配比、三价原子数与所处环境决定。", 12.3, False, INK2, "lm")
    for ri, fam in enumerate(M.FAM_ORDER):
        y = 112 + ri * rowh
        col = S.FAMILY[fam]["col"]
        cv.d.rounded_rectangle([30, y, W - 30, y + rowh - 14], radius=10,
                               fill=S.lighten(_hx(col), 0.95), outline=S.lighten(_hx(col), 0.55))
        cv.d.rectangle([30, y, 38, y + rowh - 14], fill=col)
        cv.txt(56, y + 26, S.FAMILY[fam]["zh"], 18, True, col, "lm")
        cv.txt(56, y + 50, "家族 %s · 38 库内 %d 个形态" % (fam, sum(1 for f in json.load(open('t8_forms.json', encoding='utf-8'))
                                                         if S.fam_key([a for a in set(f['atoms']) if a in 'OPK']) == fam)), 10.5, False, INK2, "lm")
        for mi, (key, zh, fn, tags, desc) in enumerate(M.MORPHS[fam]):
            cx = 150 + mi * cw
            cy = y + 96
            fn(cv.d, cx, cy, 74, 66, S.lighten(col, 0.85), col)
            cv.txt(cx + 62, y + 44, zh, 14, True, INK, "lm")
            cv.txt(cx + 62, y + 64, "（%s）" % "、".join(AB.ABIL[t]["zh"] for t in tags[:3]), 9.5, False, col, "lm")
            _wrap(cv, cx + 62, y + 84, desc, 9.8, INK2, maxw=170, lh=12)
    cv.save(path)
    print("saved", path)


# ------------------------------------------------------------------ C 38 骨架
def _forms():
    return json.load(open("t8_forms.json", encoding="utf-8"))


def page_blocks38(path="images/t72_blocks38.png"):
    forms = _forms()
    cols, cw, ch = 3, 556, 150
    W = 40 + cols * cw + 10
    H = 150 + 13 * ch
    cv = S.Canvas(W, H, (255, 255, 255))
    cv.txt(40, 48, "T72 38 个骨架块的分化形态（每块 3 种可长成的具体形态）", 26, True, INK, "lm")
    cv.txt(40, 78, "列：编号 / 公式 / 家族 / 主要能力（Ⅰ~Ⅲ）/ 三种形态（按元素配比排序，第一种是最常长成的）", 12.3, False, INK2, "lm")
    for i, f in enumerate(forms):
        atoms = f["atoms"]
        cnt = Counter(atoms)
        fam = AB.family_of_block(atoms)
        ab = AB.levels(cnt, AB.FAMILY_BONUS.get(fam, {}))
        top = sorted(ab.items(), key=lambda kv: (-kv[1], kv[0]))[:4]
        n3 = sum(1 for a in atoms if a in "OPK")
        morphs = M.pick_morphs(fam, cnt, n3, seed=i)
        col = S.FAMILY[fam]["col"]
        c, r = i % cols, i // cols
        x = 40 + c * cw
        y = 104 + r * ch
        cv.d.rounded_rectangle([x, y, x + cw - 14, y + ch - 12], radius=9, fill=(252, 253, 255), outline=GRID)
        cv.d.rectangle([x, y, x + 5, y + ch - 12], fill=col)
        cv.txt(x + 16, y + 18, "#%d" % (i + 1), 11, True, INK2, "lm")
        cv.txt(x + 48, y + 18, f["formula"], 15, True, INK, "lm")
        cv.txt(x + 190, y + 18, S.FAMILY[fam]["zh"], 11, False, col, "lm")
        xx = x + 16
        for key, lv in top:
            label = "%s%s" % (AB.ABIL[key]["zh"], LV.get(lv, lv))
            fnt = cv.f(9.5)
            wch = int(cv.d.textlength(label, font=fnt)) + 10
            if xx + wch > x + cw - 30:
                break
            cv.d.rounded_rectangle([xx, y + 32, xx + wch, y + 48], radius=8,
                                   fill=S.lighten(_hx((70, 160, 120)), 0.92), outline=(206, 220, 214))
            cv.txt(xx + 5, y + 40, label, 9.5, False, INK, "lm")
            xx += wch + 5
        for mi, mk in enumerate(morphs):
            mzh = next((mm[1] for mm in M.morph_list(fam) if mm[0] == mk), mk)
            mx = x + 46 + mi * 132
            my = y + 88
            M.draw_morph(cv, mx, my, 66, 58, mk, fam)
            cv.txt(mx, y + 124, mzh, 10.5, True, INK, "mm")
            if mi == 0:
                cv.txt(mx, y + 138, "（常长成）", 8.5, False, INK2, "mm")
    cv.save(path)
    print("saved", path)


# ------------------------------------------------------------------ D 大分子物种卡
CHOICE = ["G33", "G14", "G13", "G16", "G24", "G07"]


def page_species(path="images/t72_species.png"):
    data = A.load_molecules()
    by = {m["mid"]: m for m in data}
    tra = [molecule_traits(by[mid]) for mid in CHOICE]
    W, H = 1600, 190 + len(tra) * 476
    cv = S.Canvas(W, H, (255, 255, 255))
    cv.txt(40, 46, "T72 大分子物种卡 · 器官按功能分化的形态", 26, True, INK, "lm")
    cv.txt(40, 76, "每个器官（骨架块）画成它实际长成的分化形态；右侧列它的形态名、功能能力，右侧标题是自动生成的物种名。",
           12.3, False, INK2, "lm")
    for i, tr in enumerate(tra):
        y = 104 + i * 476
        cv.d.rounded_rectangle([28, y, W - 28, y + 456], radius=12, fill=(252, 253, 255), outline=GRID)
        B.draw_body_molecule(cv, by[tr["mid"]], (40, y + 16, 500, 420), max_s=64, show_badges=False)
        x = 570
        cv.txt(x, y + 24, tr["name"], 18, True, INK, "lm", wrap=980) if False else _wrap(cv, x, y + 24, tr["name"], 18, INK, 960, 24, True)
        cv.txt(x, y + 50, "%s  ·  %d 原子  ·  %s  ·  %s  ·  %s" % (
            tr["formula"], tr["n_atoms"], tr["kind_zh"], tr["state"], tr["softness"]), 11.5, False, INK2, "lm")
        cv.txt(x, y + 74, "器官与形态", 11.5, True, INK, "lm")
        yy = y + 94
        for o in tr["organs"][:6]:
            fam = o["fam"]
            col = S.FAMILY.get(fam, S.FAMILY["OPK"])["col"]
            M.draw_morph(cv, x + 26, yy + 18, 44, 38, o["morphs"][0], fam)
            cv.txt(x + 60, yy + 6, "%d %s" % (o["num"], o["formula"]), 11.5, True, INK, "lm")
            mzh = next((mm[1] for mm in M.morph_list(fam) if mm[0] == o["morphs"][0]), "")
            cv.txt(x + 150, yy + 6, mzh, 10.8, False, col, "lm")
            tops = sorted(o["abilities"].items(), key=lambda kv: -kv[1])[:3]
            cv.txt(x + 220, yy + 6, " · ".join("%s%s" % (AB.ABIL[k]["zh"], LV.get(v, v)) for k, v in tops),
                   10, False, INK2, "lm")
            cv.txt(x + 60, yy + 24, "可用形态：" + " / ".join(
                next((mm[1] for mm in M.morph_list(fam) if mm[0] == mk), mk) for mk in o["morphs"]),
                   9.5, False, INK2, "lm")
            yy += 50
        cv.txt(x, y + 424, "整体能力：", 11.5, True, INK, "lm")
        xx = x + 80
        for key, lv in tr["top"][:6]:
            label = "%s%s" % (AB.ABIL[key]["zh"], LV.get(lv, lv))
            fnt = cv.f(9.5)
            wch = int(cv.d.textlength(label, font=fnt)) + 10
            if xx + wch > W - 60:
                break
            cv.d.rounded_rectangle([xx, y + 414, xx + wch, y + 432], radius=8, fill=(246, 249, 252), outline=(214, 224, 232))
            cv.txt(xx + 5, y + 423, label, 9.5, False, INK, "lm")
            xx += wch + 6
    cv.save(path)
    print("saved", path)


# ------------------------------------------------------------------ E 小分子
SMALL_PICK = ["OXC", "F2", "LF", "OK", "PK", "WA", "CL", "XA", "O2X2", "OP", "C2", "K3"]


def _norm_place(place):
    if isinstance(place, dict):
        return [tuple(place[str(i)]) for i in range(len(place))]
    return [tuple(p) for p in place]


def _draw_chain(cv, atoms, edges, place, box, max_s=34):
    """小分子：按真实几何画“元素字形 + 键带”（无字母），读起来就是它的外形。"""
    place = _norm_place(place)
    x0, y0, w, h = box
    qs = [p[0] for p in place]
    rs = [p[1] for p in place]
    cw = (max(qs) - min(qs)) * 1.5 + 2.2
    chh = (max(rs) - min(rs)) * S3 + (max(qs) - min(qs)) * 0.5 + 2.2
    sc = min((w - 20) / max(1e-6, cw), (h - 20) / max(1e-6, chh), max_s)
    cx0 = x0 + w / 2.0
    cy0 = y0 + h / 2.0
    mq = (min(qs) + max(qs)) / 2.0
    mr = (min(rs) + max(rs)) / 2.0
    pos = [S.center_of((q - mq, r - mr), sc) for (q, r) in place]
    pos = [(cx0 + x, cy0 + y) for (x, y) in pos]
    d = cv.d
    # 键带
    for (a, b, m) in edges:
        pa, pb = pos[a], pos[b]
        col = (60, 72, 86) if (a in range(len(atoms)) and b in range(len(atoms))) else (60, 72, 86)
        wdt = max(3, int(sc * (0.34 if m <= 1 else 0.44)))
        d.line([pa, pb], fill=(228, 234, 240), width=wdt + 5)
        d.line([pa, pb], fill=(58, 70, 84), width=wdt)
        d.ellipse([pa[0] - wdt / 2, pa[1] - wdt / 2, pa[0] + wdt / 2, pa[1] + wdt / 2], fill=(58, 70, 84))
        d.ellipse([pb[0] - wdt / 2, pb[1] - wdt / 2, pb[0] + wdt / 2, pb[1] + wdt / 2], fill=(58, 70, 84))
        if m >= 2:
            nx, ny = -(pb[1] - pa[1]), (pb[0] - pa[0])
            ln = math.hypot(nx, ny) or 1.0
            off = wdt * 0.85
            for k in range(1, m):
                o = (k - (m - 1) / 2.0) * off
                d.line([(pa[0] + nx / ln * o, pa[1] + ny / ln * o),
                        (pb[0] + nx / ln * o, pb[1] + ny / ln * o)],
                       fill=(58, 70, 84), width=max(2, int(wdt * 0.55)))
    # 原子字形
    cnt = {}
    for el in atoms:
        cnt[el] = cnt.get(el, 0) + 1
    for el, (px, py) in zip(atoms, pos):
        sca = sc * (0.95 if el in ("O", "P", "K") else 0.86)
        poly = S.atom_poly(el, px, py, sca, max(1, cnt.get("K", 1)))
        col = ELEM_COL.get(el, (120, 130, 140))
        d.polygon(poly, fill=S.lighten(_hx(col), 0.62), outline=_hx(col))
        d.line(poly + [poly[0]], fill=(34, 46, 60), width=2)


def page_small(path="images/t72_small.png"):
    items = json.load(open("t4_catalog_all_validated.json", encoding="utf-8"))
    by = {}
    for it in items:
        if it["formula"] in SMALL_PICK and it["formula"] not in by and it["natoms"] <= 8:
            by[it["formula"]] = it
    picks = [by[f] for f in SMALL_PICK if f in by]
    cols, cw, ch = 2, 780, 300
    W = 40 + cols * cw + 10
    H = 160 + ((len(picks) + 1) // 2) * ch
    cv = S.Canvas(W, H, (255, 255, 255))
    cv.txt(40, 48, "T72 小分子的形态（2~5 原子，按新形态语言画）", 26, True, INK, "lm")
    cv.txt(40, 78, "小分子没有多器官，形态就是“键带 + 节点形态 + 端帽”：秩O/势P/散K 用骨架形态，晶X/流W/气A 用连接件形态，"
                   "冰C/电L/焰F 用端帽形态。", 12.3, False, INK2, "lm")
    lt2 = {"O": "秩O", "P": "势P", "K": "沌K", "X": "晶X", "W": "流W", "A": "气A", "C": "冰C", "L": "电L", "F": "焰F"}
    for i, it in enumerate(picks):
        c, r = i % cols, i // cols
        x = 40 + c * cw
        y = 104 + r * ch
        cnt = Counter(it["atoms"])
        cv.d.rounded_rectangle([x, y, x + cw - 14, y + ch - 14], radius=10, fill=(252, 253, 255), outline=GRID)
        cv.txt(x + 16, y + 18, it["formula"], 18, True, INK, "lm")
        zh = "·".join("%s×%d" % (lt2[a], n) for a, n in cnt.items())
        cv.txt(x + 150, y + 18, zh, 11, False, INK2, "lm")
        _draw_chain(cv, list(it["atoms"]), [tuple(e) for e in it["edges"]],
                    it["place"], (x + 20, y + 40, 330, 230), max_s=32)
        # 右侧说明
        tx = x + 380
        ab = AB.levels(cnt, {})
        top = sorted(ab.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
        cv.txt(tx, y + 52, "形态构成（原子字形 + 键带）", 11.5, True, INK, "lm")
        GL = {"O": "三角形", "P": "圆形", "K": "多角多边形", "X": "尖六边形", "W": "圆角六边形",
              "A": "虚线六边形", "C": "菱形", "L": "小圆点", "F": "小三角形"}
        yy = y + 74
        for el, n in cnt.items():
            cv.txt(tx, yy, "%s ×%d  →  %s" % (lt2[el], n, GL.get(el, "字形")), 10.5, False, INK2, "lm")
            yy += 17
        # 键型统计
        pos = _norm_place(it["place"])
        bt = Counter()
        for (ea, eb, m) in it["edges"]:
            dq = pos[eb][0] - pos[ea][0]
            dr = pos[eb][1] - pos[ea][1]
            t = P.classify_offset((dq, dr))
            bt[t or "?"] += 1
        TB = {"S": "S 短键(刚)", "C": "C 角键(铰)", "L": "L 长键(软)", "?": "其他"}
        cv.txt(tx, yy, "键：" + "、".join("%s×%d" % (TB.get(k, k), v) for k, v in bt.items()),
               10.5, False, INK2, "lm")
        yy += 20
        cv.txt(tx, yy, "能力：" + " · ".join("%s%s" % (AB.ABIL[k]["zh"], LV.get(v, v)) for k, v in top),
               10.5, False, INK, "lm")
        # 命名
        state = A.physical_state(cnt)
        if isinstance(state, tuple):
            state = state[0]
        nd = len(it["atoms"])
        ring = (len(it["edges"]) >= nd)
        shape = "小环体" if ring else ("双原子体" if nd == 2 else ("三原子折线体" if nd == 3 else "短链体"))
        soft = "刚性" if bt.get("S", 0) >= max(bt.get("C", 0), bt.get("L", 0)) else (
            "粘性" if bt.get("C", 0) >= bt.get("L", 0) else "松散")
        cv.txt(tx, y + ch - 44, "物种名：%s·%s 小分子·%s「%s」" % (
            state, soft, shape, "·".join(AB.ABIL[k]["zh"] for k, v in top[:2])), 10.5, False, INK2, "lm")
    cv.save(path)
    print("saved", path)


def main():
    page_abilities()
    page_morphs()
    page_blocks38()
    page_species()
    page_small()


if __name__ == "__main__":
    main()
