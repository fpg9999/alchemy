# -*- coding: utf-8 -*-
"""T73b 器官 = 分化形态本身。

不再“在家族容器旁边贴一个小形态”，而是让每个骨架块**整个变成**它分化出来的形态：
所有器官形态先并成一个身体蒙版（外露的朝外推），得到唯一外轮廓；体内再用细线和淡色
把每个器官的分化形态画出来。于是身体上的每个突起就是那个器官本身。
"""
import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter

import t68_shapes as S
import t69_bodies as B
import t70b_body as BODY
import t69_draw as D
import t69_pieces as P
import t72_morphs as M
import t73_organs as O73

SS = 2
INK = (36, 48, 62)
INK2 = (104, 120, 136)
DARK = (26, 36, 48)


def morph_mask(key, fam, px):
    """把 28 形态里的一个画成实心剪影（L 蒙版），px 为最终像素边长。"""
    tmp = S.Canvas(int(px), int(px), (255, 255, 255))
    M.draw_morph(tmp, px / 2.0, px / 2.0, px * 0.78, px * 0.78, key, fam)
    g = tmp.img.convert("L").point(lambda v: 255 if v < 250 else 0)
    g = g.filter(ImageFilter.MaxFilter(5))
    return g


def morph_art(key, fam, px):
    """器官的线稿（用于体内画分区线）。"""
    tmp = S.Canvas(int(px), int(px), (255, 255, 255))
    M.draw_morph(tmp, px / 2.0, px / 2.0, px * 0.78, px * 0.78, key, fam)
    return tmp.img


def draw_organ_body(cv, mol, box, max_s=52, show_badges=True, auto_organs=True):
    bodies, bridges, fusion, idx_of, adj, skel_of, kinds = D.build(mol)
    s, ox, oy = D.fit_scale(bodies, box, max_s=max_s)
    W, H = cv.img.size
    center = lambda b: (b.cx * s + ox, b.cy * s + oy)

    geoms = D.attach_geoms(mol, bodies, idx_of, adj, skel_of)
    organs = O73.analyze(mol, bodies, [b.poly() for b in bodies], geoms, fusion, adj)
    by_k = {og["k"]: og for og in organs}

    # ---------- 每个器官的剪影与位置
    org = []  # (k, key, fam, Rpx, cx, cy, outer)
    for i, b in enumerate(bodies):
        R = b.r * s
        px = max(36, int(R * 4.05))
        og = by_k.get(i, {"morph": None})
        key = og.get("morph") or "ball"
        cx, cy = center(b)
        outer = bool(og.get("on_hull"))
        if outer and len(bodies) > 1:
            dv = og.get("out_dir") or (0.0, 0.0)
            cx += dv[0] * R * 0.20
            cy += dv[1] * R * 0.20
        org.append((i, key, b.key, R, cx, cy, outer, px))

    # ---------- 器官打包：桥接/融合的器官必须互相压叠，才会连成一整块身体
    rr = [max(1.05 * e[3], e[7] * 0.56) for e in org]
    pos = [[e[4], e[5]] for e in org]
    orig = [[e[4], e[5]] for e in org]
    link = {}
    for key, items in kinds.items():
        ka, kb = key
        link[(min(ka, kb), max(ka, kb))] = 0.56
    for (ka, kb, fu) in fusion:
        link[(min(ka, kb), max(ka, kb))] = 0.42
    for _ in range(420):
        for i in range(len(org)):
            for j in range(i + 1, len(org)):
                ax, ay = pos[i]
                bx, by = pos[j]
                vx, vy = bx - ax, by - ay
                d = math.hypot(vx, vy) or 1.0
                k = link.get((i, j))
                if k is not None:
                    need = k * (rr[i] + rr[j])
                    if d > need:
                        push = (d - need) / d * 0.5
                        pos[i][0] += vx * push
                        pos[i][1] += vy * push
                        pos[j][0] -= vx * push
                        pos[j][1] -= vy * push
                else:
                    need = 1.02 * (rr[i] + rr[j])
                    if d < need:
                        push = (need - d) / d * 0.5
                        pos[i][0] -= vx * push
                        pos[i][1] -= vy * push
                        pos[j][0] += vx * push
                        pos[j][1] += vy * push
        # 轻微回拉，保持和原布局相似
        for i in range(len(org)):
            pos[i][0] += (orig[i][0] - pos[i][0]) * 0.004
            pos[i][1] += (orig[i][1] - pos[i][1]) * 0.004
    # 收进 box
    xs = [p[0] for p in pos]
    ys = [p[1] for p in pos]
    pad = 0.6 * s
    bw = max(xs) - min(xs) + 2 * max(rr) + 2 * pad
    bh = max(ys) - min(ys) + 2 * max(rr) + 2 * pad
    sc = min(1.0, box[2] / max(1.0, bw), box[3] / max(1.0, bh))
    cxm = (max(xs) + min(xs)) / 2.0
    cym = (max(ys) + min(ys)) / 2.0
    tx = box[0] + box[2] / 2.0
    ty = box[1] + box[3] / 2.0
    org2 = []
    for i, e in enumerate(org):
        nx = tx + (pos[i][0] - cxm) * sc
        ny = ty + (pos[i][1] - cym) * sc
        org2.append((e[0], e[1], e[2], e[3] * sc, nx, ny, e[6], max(26, int(e[7] * sc))))
    org = org2

    # ---------- 身体蒙版：器官剪影 + 桥 + 焊带
    BW, BH = W * SS, H * SS
    body = Image.new("L", (BW, BH), 0)
    for (i, key, fam, R, cx, cy, outer, px) in org:
        g = morph_mask(key, fam, px)
        g = g.resize((px * SS, px * SS), Image.LANCZOS)
        body.paste(g, (int(cx * SS - px * SS / 2.0), int(cy * SS - px * SS / 2.0)), g)
    dm = ImageDraw.Draw(body)
    # 桥：把相邻器官用胶囊连起来
    for key, items in kinds.items():
        ka, kb = key
        rep = max(items, key=lambda it: (len(it.get("elems") or []), it["br"].get("k", 0)))
        ca = (org[rep["ka"]][4], org[rep["ka"]][5])
        cb = (org[rep["kb"]][4], org[rep["kb"]][5])
        BODY._mask_thick(dm, ca, cb, 0.26 * s)
    # 融合：加厚焊带
    for (ka, kb, fu) in fusion:
        ca = (org[ka][4], org[ka][5])
        cb = (org[kb][4], org[kb][5])
        BODY._mask_thick(dm, ca, cb, 0.60 * s)

    # ---------- 端帽触肢 / 支臂也长在体表
    def cell_px(cell):
        cx0, cy0 = S.center_of(cell, s)
        return (cx0 + ox, cy0 + oy)

    kb_center = {i: (org[i][4], org[i][5]) for i in range(len(org))}
    for m in geoms.get("mono", []):
        kb = m.get("kb")
        if kb is None or kb >= len(org):
            continue
        u = m.get("dir") or (0.0, -1.0)
        c0 = kb_center[kb]
        base = (c0[0] + u[0] * org[kb][3] * 0.72, c0[1] + u[1] * org[kb][3] * 0.72)
        el = mol["atoms"][m.get("atom", 0)]
        sz = 0.42 * s
        if el == "C":
            BODY._mask_spike(dm, base, u, sz * 2.0, sz * 0.34)
        elif el == "F":
            BODY._mask_ribbon(dm, base, u, sz * 2.0, sz * 0.50, 2)
        elif el == "L":
            spine = []
            for kk in range(41):
                tt = kk / 40.0
                qx = base[0] + u[0] * sz * 2.1 * tt
                qy = base[1] + u[1] * sz * 2.1 * tt
                off = sz * 0.24 * math.sin(math.pi * tt) * math.sin(math.pi * 2 * tt)
                spine.append((qx - u[1] * off, qy + u[0] * off))
            dm.line([(x * SS, y * SS) for (x, y) in spine], fill=255,
                    width=max(4, int(0.13 * s * SS)), joint="curve")

    # ---------- 轻闭运算 → 单一外轮廓
    f = 4
    k = max(9, int(0.62 * s))
    sb = body.resize((max(8, BW // f), max(8, BH // f)), Image.LANCZOS)
    sb = sb.filter(ImageFilter.GaussianBlur(max(0.8, k * 0.45 / f)))
    sb = sb.point(lambda v: 255 if v > 110 else 0)
    big = sb.resize((BW, BH), Image.LANCZOS).point(lambda v: 255 if v > 128 else 0)
    full = big.resize((W, H), Image.LANCZOS)
    solid = full.point(lambda v: 255 if v > 128 else 0)

    # ---------- 阴影 + 渐变 + 器官淡色
    sh = big.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(9))
    cv.img.paste(Image.new("RGB", (W, H), (150, 162, 176)), (0, 0),
                 sh.resize((W, H), Image.LANCZOS).point(lambda v: int(v * 0.30)))
    grad = Image.new("RGB", (1, H))
    gd = ImageDraw.Draw(grad)
    for yy in range(H):
        t = yy / float(max(1, H - 1))
        gd.point((0, yy), fill=(int(249 - 30 * t), int(251 - 26 * t), int(254 - 18 * t)))
    cv.img.paste(grad.resize((W, H)), (0, 0), solid)
    # 每个器官按家族色极淡染（仍保持整体统一）
    for (i, key, fam, R, cx, cy, outer, px) in org:
        g = morph_mask(key, fam, px).resize((px, px), Image.LANCZOS)
        col = S.FAMILY.get(fam, {}).get("col", "#9aa7b4")
        cv.img.paste(Image.new("RGB", (W, H), S.lighten(col, 0.55)), (0, 0),
                     ImageChops.multiply(
                         Image.new("L", (W, H), 0) if False else _place_mask(g, W, H, cx, cy),
                         solid).point(lambda v: int(v * 0.16)))

    # ---------- 外轮廓 + 内膜
    band = ImageChops.subtract(big.filter(ImageFilter.MaxFilter(13)), big)
    cv.img.paste(Image.new("RGB", (W, H), DARK), (0, 0), band.resize((W, H), Image.LANCZOS))
    inner = big.filter(ImageFilter.MinFilter(15))
    ring = ImageChops.subtract(inner, inner.filter(ImageFilter.MinFilter(7)))
    cv.img.paste(Image.new("RGB", (W, H), (172, 188, 204)), (0, 0),
                 ring.resize((W, H), Image.LANCZOS).point(lambda v: int(v * 0.45)))

    # ---------- 体内：每个器官的分化形态线稿
    d = cv.d
    for (i, key, fam, R, cx, cy, outer, px) in org:
        art = morph_art(key, fam, px).convert("L").point(lambda v: 255 if v < 200 else 0)
        art = art.resize((px, px), Image.LANCZOS)
        cv.img.paste(Image.new("RGB", (W, H), (128, 144, 160)), (0, 0),
                     _place_mask(art.point(lambda v: int(v * 0.34)), W, H, cx, cy))
    # 融合焊纹
    for (ka, kb, fu) in fusion:
        ca = (org[ka][4], org[ka][5])
        cb = (org[kb][4], org[kb][5])
        for t in (0.35, 0.5, 0.65):
            px_ = ca[0] + (cb[0] - ca[0]) * t
            py_ = ca[1] + (cb[1] - ca[1]) * t
            d.line([(px_ - 0.12 * s, py_ - 0.12 * s), (px_ + 0.12 * s, py_ + 0.12 * s)],
                   fill=(70, 86, 104), width=2)

    if show_badges:
        for (i, key, fam, R, cx, cy, outer, px) in org:
            P.badge(cv, (cx + R * 0.55, cy - R * 0.60), str(i + 1),
                    r=max(9, int(0.20 * s)), size=max(10, int(0.23 * s)))
    return {"s": s, "organs": organs, "bodies": bodies}


def _place_mask(src, W, H, cx, cy):
    """把一张 L 小图贴到 (cx,cy) 中心，返回与画布同尺寸的掩版。"""
    out = Image.new("L", (W, H), 0)
    w, h = src.size
    out.paste(src, (int(cx - w / 2.0), int(cy - h / 2.0)))
    return out
