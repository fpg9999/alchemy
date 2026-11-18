# -*- coding: utf-8 -*-
"""T70b：把一个大分子画成"一个整体"。

思路：先把所有部件（骨架块、桥、端帽、支臂）画进同一张蒙版，取并集得到一个**单一外轮廓**；
然后只给这个并集填色、描边，内部用很淡的分区色与接缝线提示"由哪些骨架块组成"。
于是整张图是一个完整的生物/晶体，而不是一堆零件拼起来。
"""
import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter

import t68_shapes as S
import t69_pieces as P
import t69_draw as D
import t70_glyphs as G

SS = 2
INK = (36, 50, 64)
DARK = (26, 38, 50)


def _mask_poly(d, pts, fill=255):
    d.polygon([(x * SS, y * SS) for (x, y) in pts], fill=fill)


def _mask_thick(d, a, b, w, fill=255):
    d.line([(a[0] * SS, a[1] * SS), (b[0] * SS, b[1] * SS)], fill=fill, width=max(2, int(w * SS)))
    r = max(1.0, w * 0.5)
    for p in (a, b):
        d.ellipse([(p[0] - r) * SS, (p[1] - r) * SS, (p[0] + r) * SS, (p[1] + r) * SS], fill=fill)


def _mask_spike(d, base, u, L, w0):
    n = (-u[1], u[0])
    tip = (base[0] + u[0] * L, base[1] + u[1] * L)
    pts = [tip, (base[0] + n[0] * w0, base[1] + n[1] * w0), (base[0] - n[0] * w0, base[1] - n[1] * w0)]
    _mask_poly(d, pts)


def _mask_ribbon(d, base, u, L, wmax, waves):
    n = (-u[1], u[0])
    up, dn = [], []
    steps = 40
    for i in range(steps + 1):
        t = i / float(steps)
        p = (base[0] + u[0] * L * t, base[1] + u[1] * L * t)
        w = (0.22 + 0.34 * math.sin(math.pi * min(1.0, t * 1.15))) * wmax * (1.0 - 0.35 * t)
        wob = math.sin(math.pi * waves * t) * wmax * 0.55 * t
        up.append((p[0] + n[0] * (w + wob) + u[0] * wob * 0.4,
                   p[1] + n[1] * (w + wob) + u[1] * wob * 0.4))
        dn.append((p[0] - n[0] * (w - wob) + u[0] * wob * 0.4,
                   p[1] - n[1] * (w - wob) + u[1] * wob * 0.4))
    _mask_poly(d, up + list(reversed(dn)))


def _mask_helix(d, base, u, L, amp, turns):
    n = (-u[1], u[0])
    steps = 120
    for phase in (0.0, math.pi):
        pts = []
        for i in range(steps + 1):
            t = i / float(steps)
            p = (base[0] + u[0] * L * t, base[1] + u[1] * L * t)
            w = amp * math.sin(math.pi * t) ** 0.4
            off = w * math.sin(TAU * (turns + 0.5) * t + phase)
            pts.append((p[0] + n[0] * off, p[1] + n[1] * off))
        d.line([(x * SS, y * SS) for (x, y) in pts], fill=255, width=max(2, int(2.2 * SS)))


TAU = math.pi * 2.0


def _band(mask, thick):
    """在 3 倍分辨率上做膨胀取环，再降采样 → 平滑的抗锯齿描边带。"""
    W, H = mask.size
    B = 3
    big = mask.resize((W * B, H * B), Image.LANCZOS).point(lambda v: 255 if v > 128 else 0)
    outer = big.filter(ImageFilter.MaxFilter(2 * max(1, thick * B) + 1))
    band = ImageChops.subtract(outer, big)
    return band.resize((W, H), Image.LANCZOS)


def _band_inner(mask, thick):
    W, H = mask.size
    B = 3
    big = mask.resize((W * B, H * B), Image.LANCZOS).point(lambda v: 255 if v > 128 else 0)
    inner = big.filter(ImageFilter.MinFilter(2 * max(1, thick * B) + 1))
    band = ImageChops.subtract(inner, inner.filter(ImageFilter.MinFilter(5)))
    return band.resize((W, H), Image.LANCZOS)


def _smooth_mask(mask, W, H, close_r, blur_r, thresh=120):
    """把多个块并成一个圆润的整体外轮廓：降采样 + 模糊 + 重阈值（等价于大半径闭运算，但快得多）。"""
    f = 4
    sw, sh = max(8, W // f), max(8, H // f)
    sm = mask.resize((sw, sh), Image.LANCZOS)
    sm = sm.filter(ImageFilter.GaussianBlur(max(0.6, blur_r / f)))
    sm = sm.point(lambda v: 255 if v > thresh else 0)
    sm = sm.resize((W, H), Image.LANCZOS)
    return sm.point(lambda v: 255 if v > 128 else 0)


def draw_body_molecule(cv, mol, box, max_s=52, show_badges=True):
    bodies, bridges, fusion, idx_of, adj, skel_of, kinds = D.build(mol)
    s, ox, oy = D.fit_scale(bodies, box, max_s=max_s)
    W, H = cv.img.size

    def to_px(b):
        return [(x * s + ox, y * s + oy) for (x, y) in b.poly()]

    polys = [to_px(b) for b in bodies]
    poly_by_block = {b.k: polys[i] for i, b in enumerate(bodies)}
    center = lambda b: (b.cx * s + ox, b.cy * s + oy)

    # ---------- 1) 身体蒙版：骨架块 + 桥 + 融合（不含端帽）
    body_mask = Image.new("L", (W * SS, H * SS), 0)
    d = ImageDraw.Draw(body_mask)
    for b, pts in zip(bodies, polys):
        _mask_poly(d, pts)
    seg = {}
    for key, items in kinds.items():
        ka, kb = key
        if bodies[ka].block["sk"] == bodies[kb].block["sk"]:
            continue
        gk = (min(bodies[ka].block["sk"], bodies[kb].block["sk"]),
              max(bodies[ka].block["sk"], bodies[kb].block["sk"]))
        seg.setdefault(gk, []).extend(items)
    bridge_geo = []
    for gk, items in seg.items():
        rep = max(items, key=lambda it: (len(it.get("elems") or []), it["br"].get("k", 0)))
        ka, kb = rep["ka"], rep["kb"]
        ca, cb = center(bodies[ka]), center(bodies[kb])
        a = S.ray_exit(poly_by_block[ka], ca, cb)
        b = S.ray_exit(poly_by_block[kb], cb, ca)
        sp = min(bodies[ka].r, bodies[kb].r) * s * 0.62
        L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
        u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        elems = rep.get("elems") or []
        bridge_geo.append((a, b, sp, elems, u, L))
        _mask_thick(d, a, b, sp * 1.05)
    for (ka, kb, fu) in fusion:
        _mask_thick(d, center(bodies[ka]), center(bodies[kb]), min(bodies[ka].r, bodies[kb].r) * s * 1.15)

    # 闭运算 + 模糊：得到一整块身体（全部在 SS 高分辨率上做，边缘才平滑）
    BW, BH = W * SS, H * SS
    kclose = max(9, int(min(b.r for b in bodies) * s * 0.95))
    f = 4
    sb = body_mask.resize((max(8, BW // f), max(8, BH // f)), Image.LANCZOS)
    sb = sb.filter(ImageFilter.GaussianBlur(max(1.0, kclose * 0.45 / f)))
    sb = sb.point(lambda v: 255 if v > 100 else 0)
    body_big = sb.resize((BW, BH), Image.LANCZOS).point(lambda v: 255 if v > 128 else 0)

    # ---------- 2) 端帽 / 支臂：加到身体上（成为刺与触须）
    term_mask = Image.new("L", (W * SS, H * SS), 0)
    dt = ImageDraw.Draw(term_mask)
    geoms = D.attach_geoms(mol, bodies, idx_of, adj, skel_of)
    term_geo = []
    for m in geoms["mono"]:
        kb = m["kb"]
        if kb is None:
            continue
        pb = bodies[kb]
        c = center(pb)
        dv = m["dir"]
        far = (c[0] + dv[0] * pb.r * s * 3.0, c[1] + dv[1] * pb.r * s * 3.0)
        base = S.ray_exit(poly_by_block[kb], c, far)
        sz = max(5.0, pb.r * s * 0.26)
        el = mol["atoms"][m["atom"]]
        term_geo.append((el, base, dv, sz))
        if el == "C":
            _mask_spike(dt, base, dv, sz * 2.0, sz * 0.34)
            for t in (0.45, 0.7):
                p2 = (base[0] + dv[0] * sz * 2.0 * t, base[1] + dv[1] * sz * 2.0 * t)
                for sgn in (1.0, -1.0):
                    ang = sgn * 0.95
                    ca_, sa_ = math.cos(ang), math.sin(ang)
                    ddv = (dv[0] * ca_ - dv[1] * sa_, dv[0] * sa_ + dv[1] * ca_)
                    _mask_spike(dt, p2, ddv, sz * 0.8, sz * 0.16)
        elif el == "F":
            _mask_ribbon(dt, base, dv, sz * 2.1, sz * 0.55, 2)
        else:
            _mask_helix(dt, base, dv, sz * 2.4, sz * 0.30, 1)
    arm_geo = []
    for arm in geoms["arms"]:
        pb = bodies[arm["kb"]]
        c = center(pb)
        dv = arm["dir"]
        far = (c[0] + dv[0] * pb.r * s * 3.0, c[1] + dv[1] * pb.r * s * 3.0)
        base = S.ray_exit(poly_by_block[arm["kb"]], c, far)
        nn = len(arm["comp"])
        L = s * (1.2 + 0.18 * nn)
        tip = (base[0] + dv[0] * L, base[1] + dv[1] * L)
        arm_geo.append((base, dv, L, nn))
        _mask_thick(dt, base, tip, s * 0.5)
    full_big = ImageChops.lighter(body_big, term_mask)
    full = full_big.resize((W, H), Image.LANCZOS)
    solid = full.point(lambda v: 255 if v > 128 else 0)

    # ---------- 3) 一个外轮廓 + 一层身体色
    # 阴影
    sh = full_big.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(9))
    cv.img.paste(Image.new("RGB", (W, H), (146, 158, 172)), (0, 0),
                 sh.resize((W, H), Image.LANCZOS).point(lambda v: int(v * 0.38)))
    grad = Image.new("RGB", (1, H))
    gd = ImageDraw.Draw(grad)
    for yy in range(H):
        t = yy / float(max(1, H - 1))
        c = (int(250 - 36 * t), int(252 - 30 * t), int(254 - 22 * t))
        gd.point((0, yy), fill=c)
    cv.img.paste(grad.resize((W, H)), (0, 0), full)
    # 身体色偏：按各块家族色，非常淡
    for b, pts in zip(bodies, polys):
        bm = Image.new("L", (W * SS, H * SS), 0)
        ImageDraw.Draw(bm).polygon([(x * SS, y * SS) for (x, y) in pts], fill=255)
        bms = bm.resize((W, H), Image.LANCZOS).point(lambda v: 255 if v > 90 else 0)
        cv.img.paste(Image.new("RGB", (W, H), S.FAMILY[b.key]["col"]), (0, 0),
                     ImageChops.multiply(bms, full).point(lambda v: int(v * 0.13)))
    # 外轮廓
    band = ImageChops.subtract(full_big.filter(ImageFilter.MaxFilter(9)), full_big)
    cv.img.paste(Image.new("RGB", (W, H), DARK), (0, 0), band.resize((W, H), Image.LANCZOS))

    # 内层膜：整体内缩一圈的浅线，给身体"厚皮"的层次
    inner = full_big.filter(ImageFilter.MinFilter(15))
    ring2 = ImageChops.subtract(inner, inner.filter(ImageFilter.MinFilter(7)))
    cv.img.paste(Image.new("RGB", (W, H), (170, 186, 202)), (0, 0),
                 ring2.resize((W, H), Image.LANCZOS).point(lambda v: int(v * 0.55)))

    d = cv.d

    # ---------- 4) 体内细节：分区接缝 / 器官晕 / 脉络 / 桥骨纹
    for b in bodies:
        c = center(b)
        rr = b.r * s * 0.42
        d.ellipse([c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr],
                  fill=(228, 234, 241), outline=(150, 164, 180))
    # 脉络：块心之间、块心到端帽根部
    for (a, b, sp, elems, u, L) in bridge_geo:
        d.line([a, b], fill=(150, 166, 182), width=3)
    for (el, base, dv, sz) in term_geo:
        tip = (base[0] + dv[0] * sz * 1.6, base[1] + dv[1] * sz * 1.6)
        d.line([base, tip], fill=(150, 166, 182), width=2)
    # 桥的"件"：楔块 / 编织 / 膜褶（画在体内，作为器官）
    for (a, b, sp, elems, u, L) in bridge_geo:
        n = (-u[1], u[0])
        mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        if "X" in elems:
            half = min(0.50 * sp, 0.24 * L + 0.2 * sp)
            tri = [(mid[0] - u[0] * half * 1.05, mid[1] - u[1] * half * 1.05),
                   (mid[0] + u[0] * half * 0.65 + n[0] * half * 0.86,
                    mid[1] + u[1] * half * 0.65 + n[1] * half * 0.86),
                   (mid[0] + u[0] * half * 0.65 - n[0] * half * 0.86,
                    mid[1] + u[1] * half * 0.65 - n[1] * half * 0.86)]
            d.polygon(tri, fill=(208, 220, 232), outline=(58, 74, 94))
        if "W" in elems:
            steps = 60
            amp = sp * 0.34
            for phase in (0.0, math.pi):
                pts = []
                for i in range(steps + 1):
                    t = i / float(steps)
                    p2 = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                    e = math.sin(math.pi * t) ** 0.45
                    off = amp * e * math.sin(TAU * 1.0 * t + phase)
                    pts.append((p2[0] + n[0] * off, p2[1] + n[1] * off))
                d.line(pts, fill=(30, 86, 130), width=3, joint="curve")
        if "A" in elems:
            half = min(1.10 * sp, 0.5 * L + 0.6 * sp)
            th = sp * 0.22
            for k in range(1, 5):
                t = -0.7 + 1.4 * k / 5.0
                p2 = (mid[0] + n[0] * t * half, mid[1] + n[1] * t * half)
                d.line([(p2[0] + u[0] * th, p2[1] + u[1] * th),
                        (p2[0] - u[0] * th, p2[1] - u[1] * th)], fill=(96, 164, 150), width=2)
    # 融合焊纹
    for (ka, kb, fu) in fusion:
        ca, cb = center(bodies[ka]), center(bodies[kb])
        mid = ((ca[0] + cb[0]) / 2.0, (ca[1] + cb[1]) / 2.0)
        u = D.norm((cb[0] - ca[0], cb[1] - ca[1]))
        n = (-u[1], u[0])
        Lw = min(bodies[ka].r, bodies[kb].r) * s * 0.55
        for i in range(-2, 3):
            px, py = mid[0] + n[0] * i * Lw * 0.34, mid[1] + n[1] * i * Lw * 0.34
            d.line([(px + u[0] * Lw * 0.22, py + u[1] * Lw * 0.22),
                    (px - u[0] * Lw * 0.22, py - u[1] * Lw * 0.22)], fill=(70, 86, 104), width=3)
    # 徽章
    if show_badges:
        for b in bodies:
            c = center(b)
            P.badge(cv, (c[0] + b.r * s * 0.45, c[1] - b.r * s * 0.45), str(b.k + 1),
                    r=max(9, int(0.20 * s)), size=max(10, int(0.24 * s)))
    return {"s": s, "bodies": bodies, "ox": ox, "oy": oy}


def page_bodies(picks=("G13", "G24", "G16", "G26")):
    data = P.load_data()
    by = {m["mid"]: m for m in data["molecules"]}
    W, H = 1600, 1500
    cv = S.Canvas(W, H, (255, 255, 255))
    cv.txt(40, 46, "T70b 大分子整体图 · 一个分子 = 一个完整形体", 26, True, INK, "lm")
    cv.txt(40, 76, "骨架块、桥、端帽先并进同一张蒙版 → 只取一个外轮廓；内部只用淡分区色、接缝与骨纹提示结构，不再分件描边。",
           12.5, False, (96, 112, 128), "lm")
    cells = [(40, 120, 740, 640), (820, 120, 740, 640), (40, 790, 740, 640), (820, 790, 740, 640)]
    for mid, (x, y, w, h) in zip(picks, cells):
        cv.d.rectangle([x, y, x + w, y + h], outline=(224, 230, 236), width=2)
        draw_body_molecule(cv, by[mid], (x + 16, y + 46, w - 32, h - 76))
        cv.txt(x + 16, y + 22, by[mid]["mid"], 20, True, INK, "lm")
        S.draw_formula(cv.d, x + 80, y + 22, by[mid]["formula"], 17, INK, True, center=False)
    cv.save("images/t70b_bodies.png")




def page_all(picks=None, cols=6, rows=6, cw=256, ch=262):
    data = P.load_data()
    mols = [m for m in data["molecules"]]
    if picks:
        want = set(picks)
        mols = [m for m in mols if m["mid"] in want]
    else:
        mols = mols[:cols * rows]
    W = 40 + cols * cw
    H = 150 + rows * ch
    cv = S.Canvas(W, H, (255, 255, 255))
    cv.txt(40, 44, "T70b 大分子整体图 · 36 个稳定大分子（每个都是一个完整形体）", 26, True, INK, "lm")
    cv.txt(40, 74, "每一格：骨架块并成一个身体，桥在体内成为骨纹/器官，端帽长在体表；元素字形与字母都已隐去。",
           12.5, False, (96, 112, 128), "lm")
    for i, mol in enumerate(mols):
        r, c = i // cols, i % cols
        x = 40 + c * cw
        y = 110 + r * ch
        cv.d.rectangle([x, y, x + cw - 10, y + ch - 12], outline=(228, 234, 240), width=1)
        draw_body_molecule(cv, mol, (x + 6, y + 30, cw - 24, ch - 44), max_s=13, show_badges=False)
        cv.txt(x + 6, y + 14, mol["mid"], 13, True, INK, "lm")
        cv.txt(x + 40, y + 14, G.short_comp if hasattr(G, "short_comp") else mol["formula"], 11, False, (110, 126, 142), "lm")
    cv.save("images/t70b_all36.png")
    print("all36 ok")


def main():
    page_bodies()
    page_all()
    print("bodies ok")


if __name__ == "__main__":
    main()
