# -*- coding: utf-8 -*-
"""T69 渲染：几何容器版（块=骨架单元，融合焊死，桥=连接件，端帽=触肢）。"""
import math
import os
import json

from PIL import Image, ImageDraw, ImageFilter

import t68_shapes as S
import t69_pieces as P
import t69_bodies as B

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "images")

INK = (30, 42, 54)
INK2 = (96, 110, 122)
WELDC = (38, 50, 62)
WHITE = (255, 255, 255, 255)


def lighten(c, f):
    return S.lighten(c, f)


_LIBIDX = None


def lib_index():
    global _LIBIDX
    if _LIBIDX is None:
        forms = json.load(open(os.path.join(HERE, "t8_forms.json"), encoding="utf-8"))
        _LIBIDX = {}
        for i, f in enumerate(forms):
            _LIBIDX[f["formula"]] = i + 1
    return _LIBIDX


def norm(v):
    d = math.hypot(v[0], v[1])
    if d < 1e-6:
        return (1.0, 0.0)
    return (v[0] / d, v[1] / d)


def to_px(p, s, ox, oy):
    return (p[0] * s + ox, p[1] * s + oy)


def poly_px(poly, s, ox, oy):
    return [to_px(p, s, ox, oy) for p in poly]


def dir_of(mol, block_mem, atom, place):
    """块中心 -> 该原子（或原子组）的原布局方向，单位向量。"""
    pts = [place[i] for i in block_mem]
    cx = sum(p[0] for p in pts) / float(len(pts))
    cy = sum(p[1] for p in pts) / float(len(pts))
    if isinstance(atom, (list, tuple)):
        ax = sum(place[i][0] for i in atom) / float(len(atom))
        ay = sum(place[i][1] for i in atom) / float(len(atom))
    else:
        ax, ay = place[atom]
    return norm((ax - cx, ay - cy))


# ---------------------------------------------------------------- 布局编排
def build(mol):
    out = B.build_layout(mol)
    bodies, bridges, fusion, idx_of, adj, skel_of = out
    kinds = {}
    for it in bridges:
        if it.get("ka") is None or it.get("kb") is None:
            continue
        key = (min(it["ka"], it["kb"]), max(it["ka"], it["kb"]))
        kinds.setdefault(key, []).append(it)
    return bodies, bridges, fusion, idx_of, adj, skel_of, kinds


def fit_scale(bodies, box, margin=0.10, max_s=None):
    x0, y0, w, h = box
    xs, ys = [], []
    for b in bodies:
        for (x, y) in b.poly():
            xs.append(x)
            ys.append(y)
    if not xs:
        return 1.0, x0 + w / 2.0, y0 + h / 2.0
    mnx, mxx = min(xs), max(xs)
    mny, mxy = min(ys), max(ys)
    W = max(mxx - mnx, 1e-6)
    H = max(mxy - mny, 1e-6)
    s = min(w * (1 - 2 * margin) / W, h * (1 - 2 * margin) / H) * 0.94
    if max_s is not None:
        s = min(s, max_s)
    ox = x0 + w / 2.0 - (mnx + mxx) / 2.0 * s
    oy = y0 + h / 2.0 - (mny + mxy) / 2.0 * s
    return s, ox, oy


# ---------------------------------------------------------------- 绘制
def draw_halo(cv, poly, k=4):
    d = cv.d
    d.polygon(poly, fill=None, outline=WHITE, width=k * 2)


def draw_body(cv, b, s, ox, oy):
    poly = poly_px(b.poly(), s, ox, oy)
    draw_halo(cv, poly, 4)
    d = cv.d
    d.polygon(poly, fill=lighten(b.col, 0.93), outline=None)
    d.line(poly + [poly[0]], fill=b.col, width=max(3, int(s * 0.15)), joint="curve")


def inter(bodies, a, b):
    pa = poly_px(bodies[a].poly(), 1, 0, 0)
    pb = poly_px(bodies[b].poly(), 1, 0, 0)
    ca = (bodies[a].cx, bodies[a].cy)
    cb = (bodies[b].cx, bodies[b].cy)
    ea = S.ray_exit(pa, ca, cb)
    eb = S.ray_exit(pb, cb, ca)
    return ea, eb


def spread_offsets(items, bodies, ka, kb):
    """同一对块之间的多条桥，沿垂直方向错开。"""
    n = len(items)
    if n <= 1:
        return [0.0]
    return [(i - (n - 1) / 2.0) * 0.85 for i in range(n)]


def draw_x_block(cv, ca, cb, s):
    """晶 X：嵌入 A 骨架的三角块 + B 侧焊板（粗短，长度随间距拉长但不加粗）。"""
    d = cv.d
    u = norm((cb[0] - ca[0], cb[1] - ca[1]))
    n = (-u[1], u[0])
    apex = (ca[0] - u[0] * 0.50 * s, ca[1] - u[1] * 0.50 * s)
    base = (cb[0] + u[0] * 0.14 * s, cb[1] + u[1] * 0.14 * s)
    half = 0.40 * s
    tri = [apex, (base[0] + n[0] * half, base[1] + n[1] * half),
           (base[0] - n[0] * half, base[1] - n[1] * half)]
    d.polygon(tri, fill=(208, 218, 228), outline=WELDC)
    d.line(tri + [tri[0]], fill=WELDC, width=max(3, int(s * 0.12)))
    for f in (0.45, 0.70, 0.90):
        p = (apex[0] + (base[0] - apex[0]) * f, apex[1] + (base[1] - apex[1]) * f)
        d.line([(p[0] + n[0] * half * f, p[1] + n[1] * half * f),
                (p[0] - n[0] * half * f, p[1] - n[1] * half * f)],
               fill=(152, 166, 178), width=max(1, int(s * 0.03)))
    # B 侧焊板
    bc = (cb[0] + u[0] * 0.06 * s, cb[1] + u[1] * 0.06 * s)
    hh = half * 1.10
    plate = [(bc[0] + n[0] * hh + u[0] * 0.12 * s, bc[1] + n[1] * hh + u[1] * 0.12 * s),
             (bc[0] - n[0] * hh + u[0] * 0.12 * s, bc[1] - n[1] * hh + u[1] * 0.12 * s),
             (bc[0] - n[0] * hh - u[0] * 0.12 * s, bc[1] - n[1] * hh - u[1] * 0.12 * s),
             (bc[0] + n[0] * hh - u[0] * 0.12 * s, bc[1] + n[1] * hh - u[1] * 0.12 * s)]
    d.polygon(plate, fill=(178, 191, 204), outline=WELDC)
    d.line(plate + [plate[0]], fill=WELDC, width=max(2, int(s * 0.09)))
    for i in range(3):
        t = (i + 1) / 4.0
        p0 = (plate[0][0] + (plate[3][0] - plate[0][0]) * t,
              plate[0][1] + (plate[3][1] - plate[0][1]) * t)
        p1 = (plate[1][0] + (plate[2][0] - plate[1][0]) * t,
              plate[1][1] + (plate[2][1] - plate[1][1]) * t)
        d.line([p0, p1], fill=WELDC, width=max(1, int(s * 0.032)))


def draw_w_tendon2(cv, ca, cb, s):
    """流 W：可拉伸肌腱（粗细固定，长度随间距拉长）。"""
    d = cv.d
    u = norm((cb[0] - ca[0], cb[1] - ca[1]))
    n = (-u[1], u[0])
    st = (ca[0] - u[0] * 0.26 * s, ca[1] - u[1] * 0.26 * s)
    en = (cb[0] + u[0] * 0.26 * s, cb[1] + u[1] * 0.26 * s)
    span = math.hypot(en[0] - st[0], en[1] - st[1])
    up, dn = [], []
    steps = 20
    for i in range(steps + 1):
        t = i / float(steps)
        p = (st[0] + (en[0] - st[0]) * t, st[1] + (en[1] - st[1]) * t)
        w = (0.17 * s) * (0.52 + 0.48 * math.sin(math.pi * t))
        up.append((p[0] + n[0] * w, p[1] + n[1] * w))
        dn.append((p[0] - n[0] * w, p[1] - n[1] * w))
    poly = up + list(reversed(dn))
    d.polygon(poly, fill=(205, 227, 244), outline=(31, 91, 138))
    d.line(poly + [poly[0]], fill=(31, 91, 138), width=max(3, int(s * 0.09)))
    for k in (-0.40, 0.0, 0.40):
        p1 = (st[0] + u[0] * 0.12 * span + n[0] * 0.16 * s * k,
              st[1] + u[1] * 0.12 * span + n[1] * 0.16 * s * k)
        p2 = (en[0] - u[0] * 0.12 * span + n[0] * 0.16 * s * k,
              en[1] - u[1] * 0.12 * span + n[1] * 0.16 * s * k)
        mid = (p1[0] + (p2[0] - p1[0]) * 0.5 + n[0] * 0.06 * s,
               p1[1] + (p2[1] - p1[1]) * 0.5 + n[1] * 0.06 * s)
        d.line([p1, mid, p2], fill=(90, 143, 180), width=max(1, int(s * 0.03)))


def draw_a_slab(cv, ca, cb, s):
    """气 A：长条薄膜，长边贴着两侧骨架（尺寸固定，横置于两骨架之间）。"""
    d = cv.d
    u = norm((cb[0] - ca[0], cb[1] - ca[1]))
    n = (-u[1], u[0])
    mid = ((ca[0] + cb[0]) / 2.0, (ca[1] + cb[1]) / 2.0)
    hl = 1.00 * s
    ht = max(0.16 * s, 0.16 * math.hypot(cb[0] - ca[0], cb[1] - ca[1]))
    rect = [(mid[0] + n[0] * hl + u[0] * ht, mid[1] + n[1] * hl + u[1] * ht),
            (mid[0] - n[0] * hl + u[0] * ht, mid[1] - n[1] * hl + u[1] * ht),
            (mid[0] - n[0] * hl - u[0] * ht, mid[1] - n[1] * hl - u[1] * ht),
            (mid[0] + n[0] * hl - u[0] * ht, mid[1] + n[1] * hl - u[1] * ht)]
    d.polygon(rect, fill=(208, 238, 230), outline=(17, 100, 85))
    d.line(rect + [rect[0]], fill=(17, 100, 85), width=max(3, int(s * 0.09)))
    for f in (-0.42, 0.42):
        d.line([(mid[0] + n[0] * hl + u[0] * ht * f, mid[1] + n[1] * hl + u[1] * ht * f),
                (mid[0] - n[0] * hl + u[0] * ht * f, mid[1] - n[1] * hl + u[1] * ht * f)],
               fill=(104, 170, 152), width=max(1, int(s * 0.035)))


def draw_chain(cv, ca, cb, elems, s):
    """多元素桥：沿 ca→cb 按元素分组逐段放连接件（同元素合并）。"""
    groups = []
    for e in elems:
        if groups and groups[-1][0] == e:
            groups[-1][1] += 1
        else:
            groups.append([e, 1])
    u = norm((cb[0] - ca[0], cb[1] - ca[1]))
    n = len(groups)
    total = math.hypot(cb[0] - ca[0], cb[1] - ca[1])
    # 从两端各内缩 0.55s，按段数等分
    a0 = (ca[0] + u[0] * 0.55 * s, ca[1] + u[1] * 0.55 * s)
    b0 = (cb[0] - u[0] * 0.55 * s, cb[1] - u[1] * 0.55 * s)
    span = math.hypot(b0[0] - a0[0], b0[1] - a0[1])
    step = span / max(1, n)
    for i, (e, cnt) in enumerate(groups):
        p = (a0[0] + u[0] * step * i, a0[1] + u[1] * step * i)
        q = (a0[0] + u[0] * step * (i + 1), a0[1] + u[1] * step * (i + 1))
        if e == "X":
            draw_x_block(cv, p, q, s)
        elif e == "W":
            draw_w_tendon2(cv, p, q, s)
        elif e == "A":
            draw_a_slab(cv, p, q, s)


def draw_connections(cv, bodies, bridges, kinds, fusion, mol, s, ox, oy, kps=1.02):
    """每对骨架只画一个连接件（多条同类桥合并，标 ×N）。"""
    info = []
    groups = {}
    for key, items in kinds.items():
        ka, kb = key
        sa = bodies[ka].block["sk"]
        sb = bodies[kb].block["sk"]
        if sa == sb:
            continue
        gkey = (min(sa, sb), max(sa, sb))
        groups.setdefault(gkey, []).extend(items)
    for gkey, items in groups.items():
        # 代表件：原子数最多者（多元素桥优先）
        rep = max(items, key=lambda it: (len(it.get("elems") or []), it["br"].get("k", 0)))
        ka, kb = rep.get("ka"), rep.get("kb")
        if ka is None or kb is None:
            continue
        ea, eb = inter(bodies, ka, kb)
        A = to_px(ea, s, ox, oy)
        Bv = to_px(eb, s, ox, oy)
        ux, uy = norm((Bv[0] - A[0], Bv[1] - A[1]))
        nx, ny = -uy, ux
        sp = s * kps
        elems = rep.get("elems") or []
        if len(elems) == 1:
            if elems[0] == "X":
                draw_x_block(cv, A, Bv, sp)
            elif elems[0] == "W":
                draw_w_tendon2(cv, A, Bv, sp)
            elif elems[0] == "A":
                draw_a_slab(cv, A, Bv, sp)
        elif len(elems) > 1:
            draw_chain(cv, A, Bv, elems, sp)
        n = len(items)
        if n > 1:
            mx = (A[0] + Bv[0]) / 2.0
            my = (A[1] + Bv[1]) / 2.0
            P.text_bg(cv, mx + nx * s * 0.55, my + ny * s * 0.55, "x%d" % n,
                      max(11, int(0.26 * s)), True, INK, (255, 255, 255, 232), (5, 2), "mm")
        info.append({"bridge": rep, "A": A, "B": Bv, "n": n})
    return info


def draw_weld_seams(cv, bodies, fusion, s, ox, oy):
    """融合：两块边对边贴合，接缝画一条实心焊带 + 刻痕 + 两侧焊点。"""
    d = cv.d
    for (ka, kb, fu) in fusion:
        ca = to_px((bodies[ka].cx, bodies[ka].cy), s, ox, oy)
        cb = to_px((bodies[kb].cx, bodies[kb].cy), s, ox, oy)
        mx, my = (ca[0] + cb[0]) / 2.0, (ca[1] + cb[1]) / 2.0
        ux, uy = norm((cb[0] - ca[0], cb[1] - ca[1]))
        nx, ny = -uy, ux
        L = min(bodies[ka].r, bodies[kb].r) * s * 0.92
        th = s * 0.26
        band = [(mx + nx * L + ux * th, my + ny * L + uy * th),
                (mx + nx * L - ux * th, my + ny * L - uy * th),
                (mx - nx * L - ux * th, my - ny * L - uy * th),
                (mx - nx * L + ux * th, my - ny * L + uy * th)]
        d.polygon(band, fill=(58, 72, 86), outline=WELDC)
        d.line(band + [band[0]], fill=(20, 28, 36), width=max(2, int(s * 0.08)))
        for i in range(-2, 3):
            px = mx + nx * (i * L * 0.32)
            py = my + ny * (i * L * 0.32)
            d.line([(px + ux * th * 0.85, py + uy * th * 0.85),
                    (px - ux * th * 0.85, py - uy * th * 0.85)],
                   fill=(214, 222, 230), width=max(2, int(s * 0.05)))
        # 两侧焊点
        for f in (-1.0, 1.0):
            qx = mx + ux * th * 1.9 * f
            qy = my + uy * th * 1.9 * f
            rr = s * 0.13
            d.ellipse([qx - rr, qy - rr, qx + rr, qy + rr], fill=(58, 72, 86))


def attach_geoms(mol, bodies, idx_of, adj, skel_of):
    """把装饰原子（端帽/支臂/骨架内桥）分配到块，并算原布局方向。"""
    place = mol["place"]
    deco = mol.get("decoration") or {}
    monos = list(deco.get("mono") or [])
    arms = list(deco.get("arms") or [])
    intra = list(deco.get("intra") or [])
    out = {"mono": [], "arms": [], "intra": []}
    idx_of_sk = {i: sk["num"] for sk in mol["skeletons"] for i in sk["idx"]}

    # 端帽：沿邻接找到所属块
    def owner_block(atom):
        seen = {atom}
        stack = [atom]
        while stack:
            cur = stack.pop()
            for y in adj.get(cur, []):
                if y in idx_of:
                    return idx_of[y]
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
        return None

    for m in monos:
        kb = owner_block(m)
        out["mono"].append({"atom": m, "kb": kb,
                            "dir": dir_of(mol, bodies[kb].block["mem"], m, place) if kb is not None else (1, 0)})
    # 支臂：装饰原子子图分量
    arm_set = set(arms) | set(monos)
    seen = set()
    for a in arms:
        if a in seen:
            continue
        comp = []
        stack = [a]
        seen.add(a)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for y in adj.get(cur, []):
                if y in arm_set and y not in seen:
                    seen.add(y)
                    stack.append(y)
        kbs = [idx_of[y] for y in comp if y in idx_of]
        kb = kbs[0] if kbs else None
        if kb is None:
            continue
        ms = [m for m in comp if m in monos]
        out["arms"].append({"comp": comp, "kb": kb, "monos": ms,
                            "dir": dir_of(mol, bodies[kb].block["mem"], comp, place)})
    for it in intra:
        kbs = [idx_of[y] for y in adj.get(it, []) if y in idx_of]
        kb = kbs[0] if kbs else None
        if kb is None:
            continue
        out["intra"].append({"atom": it, "kb": kb,
                             "dir": dir_of(mol, bodies[kb].block["mem"], it, place)})
    return out


def rotv(v, ang):
    c = math.cos(ang)
    s = math.sin(ang)
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c)


def pick_exit(bodies, kb, atom_dir, s, ox, oy, others):
    """在容器边缘选一个"朝外且不压到别的体"的出口方向。"""
    b = bodies[kb]
    poly = poly_px(b.poly(), s, ox, oy)
    c = to_px((b.cx, b.cy), s, ox, oy)
    best = None
    for deg in (-90, -60, -30, 0, 30, 60, 90):
        d = rotv(atom_dir, math.radians(deg))
        q = S.ray_exit(poly, c, (c[0] + d[0], c[1] + d[1]))
        clear = 1e9
        for j in others:
            bj = bodies[j]
            cj = to_px((bj.cx, bj.cy), s, ox, oy)
            clear = min(clear, math.hypot(q[0] - cj[0], q[1] - cj[1]) - bj.r * s)
        score = clear + 0.35 * s * math.cos(math.radians(deg))
        if best is None or score > best[0]:
            best = (score, q, d)
    return best[1], best[2]


def draw_decoration(cv, bodies, geoms, mol, s, ox, oy):
    allb = list(range(len(bodies)))
    # 骨架内桥：容器边缘的小铆钉
    for it in geoms["intra"]:
        kb = it["kb"]
        b = bodies[kb]
        poly = poly_px(b.poly(), s, ox, oy)
        c = to_px((b.cx, b.cy), s, ox, oy)
        q, d = pick_exit(bodies, kb, it["dir"], s, ox, oy, [j for j in allb if j != kb])
        P.draw_rivet(cv, q, s)
    # 支臂：容器边缘伸出的管状触须
    for arm in geoms["arms"]:
        kb = arm["kb"]
        n = len(arm["comp"])
        q, d = pick_exit(bodies, kb, arm["dir"], s, ox, oy, [j for j in allb if j != kb])
        su = s * max(1.0, 0.32 * bodies[kb].r)
        ux, uy = d
        px, py = -uy, ux
        L = su * (0.80 + 0.28 * n)
        bend = su * 0.16 * (1 if n % 2 == 0 else -1)
        pts = [q,
               (q[0] + ux * L * 0.55 + px * bend, q[1] + uy * L * 0.55 + py * bend),
               (q[0] + ux * L + px * bend * 1.4, q[1] + uy * L + py * bend * 1.4)]
        P.draw_arm(cv, pts, [mol["atoms"][i] for i in arm["comp"]], su)
    # 端帽：沿容器边缘法向外伸
    for m in geoms["mono"]:
        kb = m["kb"]
        if kb is None:
            continue
        q, d = pick_exit(bodies, kb, m["dir"], s, ox, oy, [j for j in allb if j != kb])
        su = s * max(1.0, 0.34 * bodies[kb].r)
        P.draw_terminal(cv, q, d, mol["atoms"][m["atom"]], su, m["atom"])


def draw_molecule(cv, box, mol, halo=True, max_s=None):
    bodies, bridges, fusion, idx_of, adj, skel_of, kinds = build(mol)
    s, ox, oy = fit_scale(bodies, box, max_s=max_s)
    for b in bodies:
        draw_body(cv, b, s, ox, oy)
    draw_connections(cv, bodies, bridges, kinds, fusion, mol, s, ox, oy)
    # 再压一遍骨架轮廓：连接件看起来是"塞进"骨架里的
    for b in bodies:
        poly = poly_px(b.poly(), s, ox, oy)
        cv.d.line(poly + [poly[0]], fill=b.col, width=max(3, int(s * 0.15)), joint="curve")
    draw_weld_seams(cv, bodies, fusion, s, ox, oy)
    geoms = attach_geoms(mol, bodies, idx_of, adj, skel_of)
    draw_decoration(cv, bodies, geoms, mol, s, ox, oy)
    # 块标签：徽章 + 短组成（白底，避免压在轮廓上）
    for b in bodies:
        c = to_px((b.cx, b.cy), s, ox, oy)
        r = b.r * s
        P.badge(cv, (c[0] + r * 0.62, c[1] - r * 0.62), str(b.k + 1),
                r=max(10, int(0.24 * s)), size=max(11, int(0.27 * s)))
        txt = P.short_comp(b.atoms)
        P.text_bg(cv, c[0], c[1] + r * 0.34, txt, max(11, int(0.21 * s)), True,
                  INK, (255, 255, 255, 230), (5, 2), "mm")
    return {"s": s, "ox": ox, "oy": oy, "bodies": bodies, "kinds": kinds,
            "bridges": bridges, "fusion": fusion, "idx_of": idx_of,
            "adj": adj, "skel_of": skel_of, "geoms": geoms}
