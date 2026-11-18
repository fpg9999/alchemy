# -*- coding: utf-8 -*-
"""T69 大分子剪影图册：元素字形/字母全部隐去，只留骨架外轮廓；
骨架之间用「融合焊缝 / 晶X 楔块 / 流W 腱 / 气A 膜」连接，端帽用 C・F・L 三种触肢。

用法: python t69_cards.py [G13 ...]   无参数则出全部 18 页 + 总览
"""
import math
import os
import sys
import json

from PIL import Image, ImageDraw, ImageFilter, ImageChops

import t68_shapes as S
import t69_pieces as P

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "images")

CARD_W, CARD_H = 1540, 620
PAGE_W, PAGE_H = 1600, 1440
CARDS_PER_PAGE = 2
N_PAGE = 18
CARD_X = 30

FAM_TXT = {"O": "纯秩", "P": "纯势", "K": "纯散", "OP": "秩势",
           "OK": "秩散", "PK": "势散", "OPK": "秩势散"}
KIND = {"X": "楔块", "W": "腱", "A": "膜"}
TERM = {"C": "尖三角", "F": "软四边形", "L": "细椭圆"}


def _lib_ids():
    with open(os.path.join(HERE, "t8_forms.json"), encoding="utf-8") as fh:
        forms = json.load(fh)
    return {f["formula"]: i + 1 for i, f in enumerate(forms)}


LIBIDX = _lib_ids()


# ------------------------------------------------------------------ 几何
def build_geom(mol, box):
    """返回 (s, pos, seams_px)。骨架内部的融合位移直接写进 pos。"""
    place = [tuple(x) for x in mol["place"]]
    cells = list(place)
    seams_u = []
    for sk in mol["skeletons"]:
        blocked = set()
        for other in mol["skeletons"]:
            if other is sk:
                continue
            for i in other["idx"]:
                blocked.add(tuple(place[i]))
        cur = {}
        for bi, blk in enumerate(sk["blocks"]):
            mem = blk["mem"]
            if bi == 0:
                cur = {tuple(place[i]): i for i in mem}
            else:
                blk_cells = [tuple(place[i]) for i in mem]
                dq, dr, segs = P.flush_shift(list(cur.keys()), blk_cells,
                                             blocked=blocked, s=1.0)
                for i in mem:
                    cells[i] = (place[i][0] + dq, place[i][1] + dr)
                seams_u.extend(segs)
                for i in mem:
                    cur[cells[i]] = i
    s, ox, oy = S.fit_layout(cells, box, margin=0.55, max_s=40)
    pos = []
    for cell in cells:
        c = S.center_of(cell, s)
        pos.append((c[0] + ox, c[1] + oy))
    seams = [((a[0] * s + ox, a[1] * s + oy),
              (b[0] * s + ox, b[1] * s + oy)) for (a, b) in seams_u]
    return s, pos, seams


def skel_polys(sk, mol, pos, s, bosses=None):
    atoms = [mol["atoms"][i] for i in sk["idx"]]
    kc = max(1, atoms.count("K"))
    idxs = set(sk["idx"])
    polys = [S.atom_poly(mol["atoms"][i], pos[i][0], pos[i][1],
                         s * P.GLYPH_SCALE, kc) for i in sk["idx"]]
    if bosses:
        polys = list(polys) + list(bosses)
    caps = []
    for (a, b, m) in mol["edges"]:
        if a in idxs and b in idxs:
            caps.append((pos[a], pos[b], s * P.BOND_W))
    return polys, caps, atoms


def adjacency(mol):
    adj = {}
    for (a, b, m) in mol["edges"]:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    return adj


def order_chain(atoms, adj):
    if len(atoms) <= 1:
        return list(atoms)
    st = set(atoms)
    ends = [a for a in atoms if len([b for b in adj.get(a, []) if b in st]) <= 1]
    if not ends:
        return list(atoms)
    out = [ends[0]]
    prev, cur = None, ends[0]
    while True:
        nxt = [b for b in adj.get(cur, []) if b in st and b != prev]
        if not nxt:
            break
        prev, cur = cur, nxt[0]
        out.append(cur)
    return out


def bridge_geom(mol, adj, skel_of):
    """每条桥：(chain, (ca_atom, cb_atom), elems)。接触原子取自 edges 真实邻接。"""
    out = []
    for br in mol["bridges"]:
        bidx = br["idx"]
        st = set(bidx)
        chain = order_chain(bidx, adj) or list(bidx)

        def skel_nbs(atom):
            return [y for y in adj.get(atom, []) if y not in st and y in skel_of]

        nb0 = skel_nbs(chain[0])
        nb1 = skel_nbs(chain[-1]) if len(chain) > 1 else nb0
        ca = nb0[0] if nb0 else None
        cb = None
        for y in nb1:
            if ca is None or skel_of[y] != skel_of[ca]:
                cb = y
                break
        if cb is None and len(nb1) > 1:
            cb = nb1[1]
        out.append({"br": br, "chain": chain, "elems": [mol["atoms"][i] for i in chain],
                    "ca": ca, "cb": cb})
    return out


def arm_groups(mol, adj):
    arms = set(mol["decoration"]["arms"])
    if not arms:
        return []
    mono = set(mol["decoration"]["mono"])
    out, seen = [], set()
    for a in sorted(arms):
        if a in seen:
            continue
        comp, stack = [], [a]
        seen.add(a)
        while stack:
            x = stack.pop()
            comp.append(x)
            for y in adj.get(x, []):
                if y in arms and y not in seen:
                    seen.add(y)
                    stack.append(y)
        skel_end = None
        for x in comp:
            for y in adj.get(x, []):
                if y not in arms and y not in mono:
                    skel_end = y
                    break
            if skel_end is not None:
                break
        if skel_end is None:
            continue
        order = [skel_end]
        nxts = [y for y in adj.get(skel_end, []) if y in arms]
        if not nxts:
            continue
        prev, cur = skel_end, nxts[0]
        order.append(cur)
        while True:
            cand = [y for y in adj.get(cur, [])
                    if y in arms and y != prev and y not in order]
            prev, cur = cur, None
            if not cand:
                break
            cur = cand[0]
            order.append(cur)
        out.append({"path": order,
                    "elems": [mol["atoms"][i] for i in order[1:]]})
    return out


# ------------------------------------------------------------------ 卡片
def card(cv, x0, y0, mol):
    fbox = (x0 + 14, y0 + 66, 930, 470)
    s, pos, seams = build_geom(mol, fbox)
    d = cv.d
    adj = adjacency(mol)
    skel_of = {}
    for sk in mol["skeletons"]:
        for i in sk["idx"]:
            skel_of[i] = sk["num"]
    bridges = bridge_geom(mol, adj, skel_of)
    arms = arm_groups(mol, adj)

    d.rectangle([x0, y0, x0 + CARD_W, y0 + CARD_H], outline="#d8dee2", width=1)
    cv.txt(x0 + 14, y0 + 8, mol["mid"], size=29, bold=True, fill="#1b262f")
    S.draw_formula(d, x0 + 106, y0 + 20, mol["formula"], 24, "#1b262f", True,
                   center=False)
    cv.txt(x0 + 16, y0 + 44,
           "%s · %d 原子 · %d 骨架 · %d 桥 · 元素字形与字母已隐去，只留骨架外轮廓"
           % (mol["exp"], mol["n_atoms"], len(mol["skeletons"]),
              len(mol["bridges"])),
           size=14, fill="#5c6b76")
    bx1 = x0 + CARD_W - 16
    d.rounded_rectangle([bx1 - 222, y0 + 12, bx1, y0 + 40], radius=8,
                        fill="#eafaf1", outline="#1e8449", width=2)
    cv.txt(bx1 - 111, y0 + 26, "稳定 F(v_M)={M} ✓ (pot_v4)", size=15,
           bold=True, fill="#1e8449", anchor="mm")
    cv.txt(bx1 - 12, y0 + 50, "来源 " + str(mol["exp"]), size=12,
           fill="#8a99a3", anchor="ra")

    # ---------- 1) 连接件与支臂（先画；两端会被骨架焊口盖住 → 看起来嵌进骨架）
    boss_polys = {sk["num"]: [] for sk in mol["skeletons"]}
    mid_groups = []
    for bg in bridges:
        br, chain, elems = bg["br"], bg["chain"], bg["elems"]
        ca, cb = bg["ca"], bg["cb"]
        if ca is None or cb is None:
            continue
        A, B = pos[ca], pos[cb]
        sa, sb = skel_of.get(ca), skel_of.get(cb)
        if sa == sb and len(chain) > 1:
            mid_groups.append((A, B, elems))
            continue
        h = P.boss_h(elems)
        for pa, pb, sn in ((A, B, sa), (B, A, sb)):
            poly = P.boss_poly(pa, pb, s, h)
            if poly is not None and sn is not None:
                boss_polys[sn].append(poly)
        At, _ = P.boss_geom(A, B, s, h)
        Bt, _ = P.boss_geom(B, A, s, h)
        if len(elems) == 1:
            e = elems[0]
            L = math.hypot(Bt[0] - At[0], Bt[1] - At[1])
            if e == "X":
                P.draw_x_wedge(cv, At, Bt, s, gap=max(L, 0.9 * s))
            elif e == "W":
                P.draw_w_tendon(cv, At, Bt, s)
            else:
                P.draw_a_membrane(cv, At, Bt, s)
        else:
            P.draw_link(cv, At, Bt, elems, s)
    for grp in arms:
        P.draw_arm(cv, [pos[i] for i in grp["path"]], grp["elems"], s)

    # ---------- 2) 骨架剪影（焊口并入剪影；浅填充 + 白色隔离晕 + 只留外轮廓）
    bands = []
    skel_atoms = {}
    for sk in mol["skeletons"]:
        polys, caps, atoms = skel_polys(sk, mol, pos, s,
                                        boss_polys.get(sk["num"], []))
        key, col = S.fam_tint(atoms)
        fm, band = P.draw_body(cv, polys, caps, S.lighten(col, 0.93),
                               S.lighten(col, 0.06))
        bands.append((band, S.lighten(col, 0.06)))
        skel_atoms[sk["num"]] = atoms

    # ---------- 3) 外轮廓压线 + 焊缝（融合：≥2 边贴死）
    if seams:
        P.draw_weld(cv, seams, s)
    for (A, B, elems) in mid_groups:
        P.draw_w_tendon(cv, A, B, s)

    # ---------- 4) 端帽触肢 / 铆钉
    mono = set(mol["decoration"]["mono"])
    arm_atoms = set(mol["decoration"]["arms"])
    n_ter = 0
    for i in sorted(mono):
        par = adj.get(i) or []
        if not par:
            continue
        p0 = par[0]
        u = P.norm(P.sub(pos[i], pos[p0]))
        base = P.add(pos[p0], P.mul(u, s * (0.20 if p0 in arm_atoms else 0.92)))
        P.draw_terminal(cv, base, u, mol["atoms"][i], s, n_ter)
        n_ter += 1
    for i in mol["decoration"]["intra"]:
        P.draw_rivet(cv, pos[i], s)

    # ---------- 5) 骨架徽章 + 元素组成小标签
    molc = P.centroid(pos)
    occ = []
    for sk in mol["skeletons"]:
        idxs = sk["idx"]
        c = P.centroid([pos[i] for i in idxs])
        cen = min(idxs, key=lambda i: math.hypot(pos[i][0] - c[0],
                                                 pos[i][1] - c[1]))
        P.badge(cv, pos[cen], str(sk["num"]), r=max(12, int(s * 0.40)),
                size=max(11, int(s * 0.30)))
        lab = P.short_comp([mol["atoms"][i] for i in idxs])
        xy = label_spot(pos, idxs, molc, occ, s)
        xy = (min(max(xy[0], x0 + 46), x0 + 880),
              min(max(xy[1], y0 + 82), y0 + 500))
        cv.txt_bg(xy[0], xy[1], lab, size=max(10, int(s * 0.27)),
                  bold=True, fill="#1b262f", anchor="mm")
        occ.append(xy)

    # 桥编号
    for bg in bridges:
        br = bg["br"]
        c = P.centroid([pos[i] for i in bg["chain"]])
        r = max(9, int(s * 0.28))
        d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r],
                  fill="#ffffff", outline=P.INK2, width=2)
        cv.txt(c[0], c[1], str(br["bid"] + 1), size=max(9, int(s * 0.24)),
               bold=True, fill=P.INK2, anchor="mm")

    # ---------- 6) 面板
    panel(cv, x0, y0, mol, bridges, skel_atoms)

    lx, ly = x0 + 16, y0 + CARD_H - 18
    for txt in ["剪影=骨架（元素隐去）", "白晕=骨架分离", "焊缝/刻痕=融合焊死",
                "楔块=晶X", "腱=流W", "膜=气A",
                "尖三角/软四边形/细椭圆=端帽", "铆钉=骨架内桥", "管=支臂"]:
        cv.txt(lx, ly, txt, size=11, fill="#93a1ab")
        lx += cv.d.textlength(txt, font=cv.f(11)) + 12


def label_spot(pos, idxs, molc, occ, s):
    c = P.centroid([pos[i] for i in idxs])
    R = max([math.hypot(pos[i][0] - c[0], pos[i][1] - c[1])
             for i in idxs] + [s])
    out = P.norm(P.sub(c, molc)) if molc != c else (1.0, 0.0)
    best, best_score = None, None
    for ang in [0, -35, 35, -70, 70, 110, -110, 180]:
        v = P.rot(out, math.radians(ang))
        p = P.add(c, P.mul(v, (R + s * 0.62)))
        score = 0.0
        for q in occ:
            score += max(0.0, 34 - math.hypot(p[0] - q[0], p[1] - q[1]))
        if best_score is None or score < best_score:
            best, best_score = p, score
    return best


# ------------------------------------------------------------------ 面板
def panel(cv, x0, y0, mol, bridges, skel_atoms):
    c1 = x0 + 986
    c2 = x0 + 1262
    y0p = y0 + 70

    cv.txt(c1, y0p, "骨架（剪影）", size=14, bold=True, fill="#1b262f")
    y = y0p + 20
    for sk in mol["skeletons"]:
        atoms = skel_atoms.get(sk["num"]) or []
        cv.d.ellipse([c1, y + 1, c1 + 16, y + 17], outline="#1b262f", width=2)
        cv.txt(c1 + 8, y + 9, str(sk["num"]), size=10, bold=True,
               fill="#1b262f", anchor="mm")
        cv.txt(c1 + 22, y - 1, P.elem_comp(atoms), size=12, bold=True,
               fill="#22303c")
        blk = sk["blocks"]
        forms = "、".join(b["formula"] for b in blk)
        ids = ["#%d" % LIBIDX[b["formula"]] for b in blk
               if b.get("in_lib") and b["formula"] in LIBIDX]
        line2 = "%d 原子 · 块 %s" % (len(atoms), forms)
        if ids:
            line2 += "（%s）" % "、".join(ids)
        cv.txt(c1 + 22, y + 13, line2, size=10, fill="#5c6b76")
        nf = len(sk.get("fusion") or [])
        if nf:
            fe = sk["fusion"][0].get("elements", "")
            cv.txt(c1 + 22, y + 25, "融合 %d 键 %s · 贴边焊死" % (nf, fe),
                   size=10, fill="#9a6b2f")
            y += 12
        y += 36

    yb = y0 + 468
    mono = mol["decoration"]["mono"]
    arms = mol["decoration"]["arms"]
    intra = mol["decoration"]["intra"]
    cnt = {}
    for i in mono:
        e = mol["atoms"][i]
        cnt[e] = cnt.get(e, 0) + 1
    cv.d.line([(c1, yb - 10), (x0 + CARD_W - 14, yb - 10)], fill="#e3e8ea",
              width=1)
    cv.txt(c1, yb, "端帽触肢", size=13, bold=True, fill="#1b262f")
    y = yb + 20
    parts = ["%s（%s）×%d" % (e, TERM[e], cnt[e]) for e in ("C", "F", "L")
             if cnt.get(e)]
    cv.txt(c1 + 10, y, "、".join(parts) if parts else "无", size=11,
           fill="#22303c")
    y += 18
    cv.txt(c1, y, "支臂 %d 原子（管状） · 骨架内桥 %d（铆钉）"
           % (len(arms), len(intra)), size=11, fill="#22303c")
    y += 18
    cv.txt(c1, y, "元素组成：", size=11, bold=True, fill="#1b262f")
    y += 16
    cv.txt(c1 + 8, y, P.elem_comp(mol["atoms"]), size=11, fill="#22303c")
    y += 16
    famk = S.fam_of_mol_atoms(mol["atoms"])
    tks = P.short_comp([a for a in mol["atoms"] if a in ("O", "P", "K")])
    cv.txt(c1 + 8, y, "分子家族 %s（%s）" % (FAM_TXT.get(famk, famk), tks),
           size=10, fill="#5c6b76")

    cv.txt(c2, y0p, "连接件（二价桥）", size=14, bold=True, fill="#1b262f")
    cv.txt(x0 + CARD_W - 14, y0p + 4, "%d 条" % len(bridges),
           size=11, fill="#8a99a3", anchor="ra")
    y = y0p + 20
    if not bridges:
        cv.txt(c2 + 8, y, "无（骨架各自独立 / 仅氢键无）", size=11,
               fill="#8a99a3")
    for bg in bridges:
        br, elems = bg["br"], bg["elems"]
        desc = " + ".join("%s%s" % (e, KIND.get(e, "")) for e in elems)
        ka, kb = bg["ca"], bg["cb"]
        if ka is None or kb is None:
            ends = "单端伸出（支臂）"
        else:
            sa, sb = skel_of_num(mol, ka), skel_of_num(mol, kb)
            ends = "骨架%s–骨架%s" % (sa, sb) if sa != sb else "骨架%s 内桥" % sa
        cv.d.ellipse([c2, y + 1, c2 + 16, y + 17], outline=P.INK2, width=2)
        cv.txt(c2 + 8, y + 9, str(br["bid"] + 1), size=9, bold=True,
               fill=P.INK2, anchor="mm")
        cv.txt(c2 + 22, y - 1, desc, size=12, bold=True, fill="#22303c")
        tps = "/".join(sorted(set(br.get("types") or [])))
        cv.txt(c2 + 22, y + 13, "%d 原子 · 键型 %s" % (len(elems), tps or "-"),
               size=10, fill="#5c6b76")
        cv.txt(c2 + 22, y + 25, ends, size=10, fill="#8a99a3")
        y += 38


def skel_of_num(mol, atom_i):
    for sk in mol["skeletons"]:
        if atom_i in sk["idx"]:
            return sk["num"]
    return "?"


# ------------------------------------------------------------------ 页面
def page_frame(cv, pi, n_page):
    cv.txt(26, 20, "T69 大分子剪影图册", size=31, bold=True, fill="#16212a")
    cv.txt(26, 66, "36 个稳定大分子 / 特大分子（≥14 原子）：元素字形与字母全部隐去，只留骨架外轮廓；"
                   "连接件与端帽触肢按形状语言绘制，元素组成以文字标注", size=14,
           fill="#5c6b76")
    cv.txt(PAGE_W - 26, 24, "第 %d / %d 页" % (pi + 1, n_page), size=15,
           fill="#5c6b76", anchor="ra")
    cv.d.line([(26, 92), (PAGE_W - 26, 92)], fill="#d8dee2", width=1)


GLYPH_LEGEND = ("剪影=骨架（元素隐去） · 白色隔离晕 · 焊缝/焊刻痕=骨架融合（≥2 边贴死） · "
                "楔块=晶X（最短最粗，嵌入骨架） · 腱=流W（可拉伸椭圆） · 膜=气A（横向长条） · "
                "尖三角=冰C端帽 · 软四边形=焰F端帽 · 细椭圆=电L端帽 · 管=支臂 · 铆钉=骨架内桥")


def one_page(pi, mols, out):
    cv = S.Canvas(PAGE_W, PAGE_H, "#ffffff")
    page_frame(cv, pi, N_PAGE)
    for j, mol in enumerate(mols):
        card(cv, CARD_X, 108 + j * (CARD_H + 18), mol)
    cv.txt(26, PAGE_H - 28, GLYPH_LEGEND, size=11, fill="#93a1ab")
    cv.txt(PAGE_W - 26, PAGE_H - 28, "t69_cards.py · t69_pieces.py",
           size=10, fill="#b9c3ca", anchor="ra")
    cv.save(out)
    print("saved", out)


def overview(data):
    cols, rows = 6, 6
    cw, ch = 258, 258
    W, H = cols * cw + 40, rows * ch + 126
    cv = S.Canvas(W, H, "#ffffff")
    cv.txt(22, 18, "T69 大分子剪影 · 总览（36 个稳定大分子）", size=29,
           bold=True, fill="#16212a")
    cv.txt(22, 60, "每格：编号 + 分子式 + 原子/骨架/桥数 + 剪影缩略图 + 家族色块；"
                   "细节见 t69_giants_01~18.png", size=13, fill="#5c6b76")
    for k, mol in enumerate(data["molecules"]):
        r, c = divmod(k, cols)
        x0 = 18 + c * cw
        y0 = 92 + r * ch
        box = (x0 + 6, y0 + 36, cw - 28, ch - 88)
        try:
            card_thumb(cv, box, mol)
        except Exception as exc:
            print("thumb fail", mol["mid"], exc)
        cv.txt(x0 + 8, y0 + 4, mol["mid"], size=16, bold=True, fill="#1b262f")
        cv.txt(x0 + 58, y0 + 8, P.short_comp(mol["atoms"]), size=13,
               fill="#22303c")
        cv.txt(x0 + 8, y0 + 24, "%d 原子 · %d 骨架 · %d 桥"
               % (mol["n_atoms"], len(mol["skeletons"]),
                  len(mol["bridges"])), size=10, fill="#5c6b76")
        key, col = S.fam_tint([a for a in mol["atoms"] if a in ("O", "P", "K")])
        cv.d.rounded_rectangle([x0 + cw - 60, y0 + 4, x0 + cw - 12, y0 + 26],
                               radius=5, fill=S.lighten(col, 0.82),
                               outline=S.lighten(col, 0.15))
        cv.txt(x0 + cw - 36, y0 + 15, FAM_TXT.get(key, key), size=10,
               fill="#1b262f", anchor="mm")
        if k % cols == cols - 1:
            cv.d.line([(18, y0 + ch - 6), (W - 18, y0 + ch - 6)],
                      fill="#eef1f2", width=1)
    out = os.path.join(IMG, "t69_overview.png")
    cv.save(out)
    print("saved", out)


def card_thumb(cv, box, mol):
    s, pos, seams = build_geom(mol, (box[0], box[1], box[2], box[3]))
    bands = []
    for sk in mol["skeletons"]:
        polys, caps, atoms = skel_polys(sk, mol, pos, s)
        key, col = S.fam_tint(atoms)
        fm, band = P.draw_body(cv, polys, caps, S.lighten(col, 0.93),
                               S.lighten(col, 0.10), halo=True)
    if seams:
        P.draw_weld(cv, seams, s)
    d = cv.d
    adj = adjacency(mol)
    for bg in bridge_geom(mol, adj, {i: sk["num"] for sk in mol["skeletons"]
                                     for i in sk["idx"]}):
        c = P.centroid([pos[i] for i in bg["chain"]])
        d.ellipse([c[0] - 2, c[1] - 2, c[0] + 2, c[1] + 2], fill=P.INK2)
    for i in mol["decoration"]["mono"]:
        par = adj.get(i)
        if not par:
            continue
        u = P.norm(P.sub(pos[i], pos[par[0]]))
        d.line([P.add(pos[par[0]], P.mul(u, s * 0.75)), pos[i]],
               fill=(130, 146, 158), width=2)
    for i in mol["decoration"]["intra"]:
        d.ellipse([pos[i][0] - 2, pos[i][1] - 2, pos[i][0] + 2, pos[i][1] + 2],
                  fill=P.INK2)


# ------------------------------------------------------------------ 入口
def main(argv):
    data = P.load_data()
    mols = data["molecules"]
    if len(argv) > 1:
        for mol in mols:
            if mol["mid"] in set(argv[1:]):
                cv = S.Canvas(CARD_W + 2 * CARD_X, CARD_H + 40, "#ffffff")
                card(cv, CARD_X, 20, mol)
                out = os.path.join(IMG, "t69_card_%s.png" % mol["mid"])
                cv.save(out)
                print("saved", out)
        return
    for pi in range(N_PAGE):
        chunk = mols[pi * CARDS_PER_PAGE:(pi + 1) * CARDS_PER_PAGE]
        if not chunk:
            break
        one_page(pi, chunk, os.path.join(IMG, "t69_giants_%02d.png" % (pi + 1)))
    overview(data)


if __name__ == "__main__":
    main(sys.argv)
