# -*- coding: utf-8 -*-
"""T75 方块世界：每个骨架 = 地图上的 1 个单位方块。

- 骨架块（6 级块）合起来的那个三价连通块 = 1 个方块；
- 方块之间的桥 / 融合画在共用的边上；
- 一价端帽 = 方块外缘上的小方钉；
- 物质属性：硬度（三价）/ 粘性（二价）/ 温度（一价），值由 t75_attrs 计算。
"""
import math
from collections import Counter, defaultdict

import t68_shapes as S
import t69_pieces as P
import t75_attrs as AT
import t75b_attrs as SA

INK = (38, 50, 64)
INK2 = (104, 120, 136)
FAM_COL = {k: v["col"] for k, v in S.FAMILY.items()}

UP, DOWN, LEFT, RIGHT = (0, -1), (0, 1), (-1, 0), (1, 0)


def _hx(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ---------------------------------------------------------------- 图结构
def skeleton_graph(mol):
    """返回 {sk_i: [(sk_j, [bridge dict...]), ...]} 与融合对。"""
    n = len(mol["skeletons"])
    g = defaultdict(list)
    pair_br = defaultdict(list)
    for br in mol["bridges"]:
        c = br.get("comps") or []
        if len(c) < 2:
            continue
        a, b = c[0], c[1]
        if a == b:
            continue
        key = (min(a, b), max(a, b))
        pair_br[key].append(br)
    for (a, b), brs in pair_br.items():
        g[a].append((b, brs))
        g[b].append((a, brs))
    return g, pair_br


def grid_embed(mol):
    """把骨架排成方块阵列（4 邻接）。返回 {sk_i: (q, r)}。"""
    n = len(mol["skeletons"])
    g, _ = skeleton_graph(mol)
    if n == 1:
        return {0: (0, 0)}
    # 从连接最多的骨架开始 BFS
    start = max(range(n), key=lambda i: len(g[i]))
    cell = {start: (0, 0)}
    used = {(0, 0)}
    order = [start]
    queue = [start]
    while queue:
        cur = queue.pop(0)
        for nb, _brs in g[cur]:
            if nb in cell:
                continue
            q0, r0 = cell[cur]
            cands = []
            for dq, dr in (RIGHT, DOWN, LEFT, UP):
                c = (q0 + dq, r0 + dr)
                if c in used:
                    continue
                # 偏好：靠近已放好的其他邻居、总体紧凑
                score = 0.0
                for nb2, _ in g[nb]:
                    if nb2 in cell:
                        c2 = cell[nb2]
                        score += abs(c[0] - c2[0]) + abs(c[1] - c2[1])
                score += 0.15 * (abs(c[0]) + abs(c[1]))
                cands.append((score, c))
            if not cands:
                # 兜底：向外找空位
                for rr in range(-8, 9):
                    for qq in range(-8, 9):
                        c = (qq, rr)
                        if c not in used:
                            cands.append((abs(qq) + abs(rr), c))
                            break
                    if cands:
                        break
            cands.sort()
            c = cands[0][1]
            cell[nb] = c
            used.add(c)
            order.append(nb)
            queue.append(nb)
    # 归一化到非负
    qs = [c[0] for c in cell.values()]
    rs = [c[1] for c in cell.values()]
    mq, mr = min(qs), min(rs)
    return {i: (q - mq, r - mr) for i, (q, r) in cell.items()}


# ---------------------------------------------------------------- 方块细节
def fam_motif(d, fam, x0, y0, s, col):
    """方块内部的家族纹样（7 种，各不相同）。"""
    c = _hx(col)
    light = _mix(c, (255, 255, 255), 0.55)
    cx, cy = x0 + s / 2.0, y0 + s * 0.42
    m = s * 0.27
    if fam == "O":            # 三角（秩序）
        d.polygon([(cx, cy - m), (cx + m * 0.92, cy + m * 0.7), (cx - m * 0.92, cy + m * 0.7)],
                  fill=light, outline=c, width=max(1, int(s * 0.02)))
    elif fam == "P":          # 圆（势能）
        d.ellipse([cx - m, cy - m, cx + m, cy + m], fill=light, outline=c, width=max(1, int(s * 0.02)))
    elif fam == "K":          # 多角（沌）
        pts = [(cx + m * math.cos(-math.pi / 2 + i * math.pi * 2 / 5),
                cy + m * math.sin(-math.pi / 2 + i * math.pi * 2 / 5)) for i in range(5)]
        d.polygon(pts, fill=light, outline=c, width=max(1, int(s * 0.02)))
    elif fam == "OP":         # 拱（秩+势）
        d.arc([cx - m, cy - m, cx + m, cy + m], 180, 360, fill=c, width=max(2, int(s * 0.03)))
        d.line([(cx - m, cy), (cx - m, cy + m * 0.7)], fill=c, width=max(2, int(s * 0.03)))
        d.line([(cx + m, cy), (cx + m, cy + m * 0.7)], fill=c, width=max(2, int(s * 0.03)))
    elif fam == "OK":         # 盾（秩+沌）
        pts = [(cx, cy - m), (cx + m, cy - m * 0.2), (cx + m * 0.6, cy + m),
               (cx, cy + m * 0.7), (cx - m * 0.6, cy + m), (cx - m, cy - m * 0.2)]
        d.polygon(pts, fill=light, outline=c, width=max(1, int(s * 0.02)))
    elif fam == "PK":         # 圆角方（势+沌）
        d.rounded_rectangle([cx - m, cy - m, cx + m, cy + m], radius=m * 0.55,
                            fill=light, outline=c, width=max(1, int(s * 0.02)))
    else:                     # OPK 六边形
        pts = [(cx + m * math.cos(math.pi / 6 + i * math.pi / 3),
                cy + m * math.sin(math.pi / 6 + i * math.pi / 3)) for i in range(6)]
        d.polygon(pts, fill=light, outline=c, width=max(1, int(s * 0.02)))
    # 中心小点 = 该块三价原子数
    n3 = 0
    for _ in range(1):
        pass
    return n3



def draw_attr_bars(cv, x0, y0, s, a, rng):
    """在方块右下角画三条小条：硬度(红)/粘性(绿)/温度(紫)。"""
    d = cv.d
    hrs, vrs, trs = rng
    def fr(v, r):
        lo, hi = r
        return max(0.0, min(1.0, (v - lo) / max(1e-6, hi - lo)))
    vals = [(a["hardness"], fr(a["hardness"], hrs), (0xC0, 0x39, 0x2B)),
            (a["viscosity"], fr(a["viscosity"], vrs), (0x1E, 0x84, 0x49)),
            (a["temperature"], fr(a["temperature"], trs), (0x8E, 0x44, 0xAD))]
    bx = x0 + s * 0.80
    by = y0 + s * 0.13
    bh = s * 0.045
    bw = s * 0.13
    for k, (v, f, col) in enumerate(vals):
        yy = by + k * (bh + s * 0.03)
        d.rectangle([bx, yy, bx + bw, yy + bh], fill=(238, 242, 246), outline=(208, 216, 224))
        d.rectangle([bx, yy, bx + max(2, bw * f), yy + bh], fill=col)

def draw_tile(cv, x0, y0, s, sk, col, labels=True):
    d = cv.d
    c = _hx(col)
    fill = _mix(c, (255, 255, 255), 0.90)
    d.rectangle([x0, y0, x0 + s - 1, y0 + s - 1], fill=fill, outline=c, width=max(2, int(s * 0.035)))
    fam_motif(d, sk.get("family", "OPK"), x0, y0, s, col)
    # 6 级块数：右上角小方点
    nb = len(sk.get("blocks") or [])
    for i in range(nb):
        d.rectangle([x0 + s - 12 - i * 9, y0 + 7, x0 + s - 6 - i * 9, y0 + 13],
                    fill=_mix(c, (255, 255, 255), 0.25), outline=None)
    if not labels:
        return
    # 块形态标签
    form = sk.get("block_forms") or []
    txt = (form[0] if form else (sk.get("formula") or ""))[:6]
    cv.txt(x0 + s / 2.0, y0 + int(s * 0.86), txt, max(8, int(s * 0.11)), True, _mix(c, INK, 0.35), "mm")
    cv.txt(x0 + s / 2.0, y0 + int(s * 0.13), "%d 原子" % (sk.get("n") or 0), max(7, int(s * 0.08)),
           False, INK2, "mm")


# ---------------------------------------------------------------- 连接件
def draw_bridge_on_edge(cv, x0, y0, s, side, elems):
    """side: 'h'（水平共用边，横跨左右）或 'v'（垂直共用边，横跨上下）；(x0,y0) 为共用边起点。"""
    d = cv.d
    els = sorted(set(elems))
    if "X" in els:      # 晶：最硬——短粗的双焊块
        if side == "h":
            w = s * 0.46
            d.rectangle([x0 - w / 2, y0 - s * 0.10, x0 + w / 2, y0 + s * 0.10],
                        fill=(186, 194, 204), outline=(62, 74, 88), width=2)
            for i in (-1, 1):
                d.rectangle([x0 - s * 0.05, y0 + i * s * 0.16 - s * 0.045,
                             x0 + s * 0.05, y0 + i * s * 0.16 + s * 0.045],
                            fill=(96, 106, 120), outline=(40, 50, 62))
        else:
            h = s * 0.46
            d.rectangle([x0 - s * 0.10, y0 - h / 2, x0 + s * 0.10, y0 + h / 2],
                        fill=(186, 194, 204), outline=(62, 74, 88), width=2)
    elif "W" in els:    # 流：可拉伸的椭圆肌腱
        if side == "h":
            d.ellipse([x0 - s * 0.07, y0 - s * 0.21, x0 + s * 0.07, y0 + s * 0.21],
                      fill=(198, 228, 238), outline=(38, 110, 132), width=2)
            d.line([(x0, y0 - s * 0.19), (x0, y0 + s * 0.19)], fill=(38, 110, 132), width=1)
        else:
            d.ellipse([x0 - s * 0.21, y0 - s * 0.07, x0 + s * 0.21, y0 + s * 0.07],
                      fill=(198, 228, 238), outline=(38, 110, 132), width=2)
            d.line([(x0 - s * 0.19, y0), (x0 + s * 0.19, y0)], fill=(38, 110, 132), width=1)
    else:               # 气：长条薄膜（沿共用边的细长条）
        if side == "h":
            d.rectangle([x0 - s * 0.022, y0 - s * 0.30, x0 + s * 0.022, y0 + s * 0.30],
                        fill=(200, 236, 224), outline=(28, 108, 92), width=2)
            for k in range(-2, 3):
                d.line([(x0 - s * 0.02, y0 + k * s * 0.10), (x0 + s * 0.02, y0 + k * s * 0.10)],
                       fill=(40, 120, 104), width=1)
        else:
            d.rectangle([x0 - s * 0.30, y0 - s * 0.022, x0 + s * 0.30, y0 + s * 0.022],
                        fill=(200, 236, 224), outline=(28, 108, 92), width=2)


def draw_weld(cv, x0, y0, s, side):
    d = cv.d
    if side == "h":
        for i in range(6):
            yy = y0 + (i - 2.5) * s * 0.075
            d.line([(x0 - s * 0.10, yy - s * 0.02), (x0 + s * 0.10, yy + s * 0.02)],
                   fill=(60, 74, 88), width=max(2, int(s * 0.018)))
    else:
        for i in range(6):
            xx = x0 + (i - 2.5) * s * 0.075
            d.line([(xx - s * 0.02, y0 - s * 0.10), (xx + s * 0.02, y0 + s * 0.10)],
                   fill=(60, 74, 88), width=max(2, int(s * 0.018)))


# ---------------------------------------------------------------- 端帽/支臂
def draw_stud(cv, x, y, s, u, el):
    """方块外缘的小方钉（一价端帽）。u=朝外单位向量（轴对齐）。"""
    d = cv.d
    L = s * 0.15
    w = s * 0.26
    cx, cy = x + u[0] * L * 0.5, y + u[1] * L * 0.5
    if u[0]:
        box = [x - L, cy - w / 2, x + L, cy + w / 2]
    else:
        box = [cx - w / 2, y - L, cx + w / 2, y + L]
    col = {"C": (150, 206, 236), "F": (240, 168, 120), "L": (188, 158, 226)}.get(el, (200, 200, 200))
    edge = {"C": (34, 96, 140), "F": (150, 66, 24), "L": (86, 52, 150)}.get(el, (90, 90, 90))
    d.rectangle(box, fill=col, outline=edge, width=2)
    if el == "C":      # 冰：尖三角 → 方块里画个三角
        cx0, cy0 = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        r = w * 0.30
        d.polygon([(cx0, cy0 - r), (cx0 + r, cy0 + r * 0.8), (cx0 - r, cy0 + r * 0.8)], fill=edge)
    elif el == "F":    # 焰：四边形内画波浪
        cx0, cy0 = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        d.line([(cx0 - w * 0.28, cy0 + w * 0.10), (cx0, cy0 - w * 0.12), (cx0 + w * 0.28, cy0 + w * 0.10)],
               fill=edge, width=2)
    else:              # 电：细椭圆 → 小圆点
        cx0, cy0 = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        d.ellipse([cx0 - w * 0.16, cy0 - w * 0.16, cx0 + w * 0.16, cy0 + w * 0.16], fill=edge)


# ---------------------------------------------------------------- 整分子
def draw_molecule(cv, box, mol, show_attrs=True, max_tile=None, pad=18, attr_rng=None):
    cell = grid_embed(mol)
    nq = max(c[0] for c in cell.values()) + 1
    nr = max(c[1] for c in cell.values()) + 1
    W, H = box[2], box[3]
    s = min((W - 2 * pad) / nq, (H - 2 * pad) / nr)
    if max_tile:
        s = min(s, max_tile)
    ox = box[0] + (W - nq * s) / 2.0
    oy = box[1] + (H - nr * s) / 2.0
    # 骨架 → 方块
    for i, sk in enumerate(mol["skeletons"]):
        q, r = cell[i]
        draw_tile(cv, ox + q * s, oy + r * s, s, sk, FAM_COL.get(sk.get("family", "OPK"), "#2c3e50"), labels=False)
    # 桥：画在共用的边上
    _, pair_br = skeleton_graph(mol)
    for (a, b), brs in pair_br.items():
        if a not in cell or b not in cell:
            continue
        qa, ra = cell[a]
        qb, rb = cell[b]
        elems = sorted({mol["atoms"][i] for br in brs for i in br["idx"]
                        if mol["atoms"][i] in ("X", "W", "A")})
        if (qa, ra) == (qb, rb):
            continue
        if ra == rb and abs(qa - qb) == 1:      # 水平相邻 → 垂直共用边
            x = ox + max(qa, qb) * s
            y = oy + ra * s
            draw_bridge_on_edge(cv, x, y + s / 2.0, s, "h", elems)
        elif qa == qb and abs(ra - rb) == 1:    # 垂直相邻 → 水平共用边
            x = ox + qa * s
            y = oy + max(ra, rb) * s
            draw_bridge_on_edge(cv, x + s / 2.0, y, s, "v", elems)
    # 融合：同一骨架内部的块（画在方块内部边界的焊纹）
    for sk in mol["skeletons"]:
        if sk.get("n_fusion_bonds"):
            q, r = cell[sk["num"] - 1] if (sk["num"] - 1) in cell else (0, 0)
            x0, y0 = ox + q * s, oy + r * s
            d = cv.d
            for k in range(4):
                d.line([(x0 + s * 0.14 + k * s * 0.18, y0 + s * 0.62),
                        (x0 + s * 0.14 + k * s * 0.18, y0 + s * 0.86)], fill=(70, 84, 98), width=2)
    # 端帽：方块外缘的方钉
    atom2sk = {}
    for sk in mol["skeletons"]:
        for a in sk["idx"]:
            atom2sk[a] = sk["num"] - 1
    place = mol["place"]
    def cell_of(i):
        c = place[i] if isinstance(place, list) else place[str(i)]
        return (c[0], c[1]) if isinstance(c, (list, tuple)) else (c["q"], c["r"])
    nb = {}
    for (a, b, m) in mol["edges"]:
        nb.setdefault(a, []).append(b)
        nb.setdefault(b, []).append(a)
    cnt = Counter()
    for idx in mol["decoration"].get("mono", []):
        kb = None
        for j in nb.get(idx, []):
            if j in atom2sk:
                kb = atom2sk[j]
                break
        if kb is None or kb not in cell:
            continue
        q, r = cell[kb]
        x0, y0 = ox + q * s, oy + r * s
        # 方向：端帽原子相对所在方块中心的方向（按轴对齐取最大分量）
        pc = cell_of(idx)
        cen = (q, r)
        dvx, dvy = pc[0] - cen[0], pc[1] - cen[1]
        if abs(dvx) >= abs(dvy):
            u = (1 if dvx >= 0 else -1, 0)
        else:
            u = (0, 1 if dvy >= 0 else -1)
        # 若该方向已有方块，换一个空边
        occ = set(cell.values())
        if (q + u[0], r + u[1]) in occ:
            free_dirs = [d for d in ((1, 0), (-1, 0), (0, 1), (0, -1))
                         if (q + d[0], r + d[1]) not in occ]
            if not free_dirs:
                continue
            # 取与期望方向最接近的空边
            free_dirs.sort(key=lambda d: -(d[0] * u[0] + d[1] * u[1]))
            u = free_dirs[0]
        k_edge = (kb, u)
        cnt[("stud", k_edge)] += 1
        off = (cnt[("stud", k_edge)] - 0.5) * s * 0.22
        if u[0]:
            px, py = (x0 + s if u[0] > 0 else x0), y0 + s / 2.0 + off
        else:
            px, py = x0 + s / 2.0 + off, (y0 + s if u[1] > 0 else y0)
        draw_stud(cv, px, py, s, u, mol["atoms"][idx])
    # 文字最后画，避免被连接件/端帽压住
    for i, sk in enumerate(mol["skeletons"]):
        q, r = cell[i]
        col = FAM_COL.get(sk.get("family", "OPK"), "#2c3e50")
        c = _hx(col)
        form = sk.get("block_forms") or []
        txt = (form[0] if form else (sk.get("formula") or ""))[:6]
        cv.txt(ox + q * s + s / 2.0, oy + r * s + int(s * 0.86), txt,
               max(8, int(s * 0.11)), True, _mix(c, INK, 0.35), "mm")
        cv.txt(ox + q * s + s / 2.0, oy + r * s + int(s * 0.13), "%d 原子" % (sk.get("n") or 0),
               max(7, int(s * 0.08)), False, INK2, "mm")
    attrs = SA.skeleton_attrs(mol)
    if attr_rng:
        for i, sk in enumerate(mol["skeletons"]):
            q, r = cell[i]
            draw_attr_bars(cv, ox + q * s, oy + r * s, s, attrs[i], attr_rng)
    return {"cell": cell, "s": s, "ox": ox, "oy": oy, "attrs": attrs}


def draw_attr_box(cv, box, mol):
    pass  # 属性由卡片负责
