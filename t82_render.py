"""T82 渲染：把最终环境按"切片"画出来。

* 世界 = 方格环面（W x H 格），每格最多 1 个分子（点粒子、真实落在格子里）；
* 每个分子按其骨架（t4_catalog_all_validated.json 的 place 轴向坐标）画成
  方块图像：原子 = 9 元素配色的方块，键 = S 实线 / C 虚线 / L 点线；
* 分子图像锚定在它占据的那一格，图像大小随骨架自适应（大分子略微缩小，
  以免完全遮住邻居）；
* 从最终快照里自动挑 4 个区域切片（最密 / 中等 / 最稀 / 最大分子所在），
  另画一张全环境密度图（标出切片位置）和一处原地放大图。
"""

from __future__ import annotations

import io
import json
import math
import os

from PIL import Image, ImageDraw, ImageFont

from alchemy.core.elements import classify_offset

BASE = os.path.dirname(os.path.abspath(__file__))
RESULT = os.path.join(BASE, "t82_env_result.json")
CATALOG = os.path.join(BASE, "t4_catalog_all_validated.json")
FONT_REG = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"

SQ3 = math.sqrt(3.0)
SPRITE_S = 0.55          # 轴向像素 -> 格子单位（相邻原子 ~0.95 格）
ATOM_FRAC = 0.42         # 原子方块边长 / 格子边长（基准值）

COL = {
    "O": (214, 69, 69),
    "K": (224, 142, 43),
    "P": (154, 168, 37),
    "X": (47, 111, 208),
    "W": (47, 168, 184),
    "A": (63, 163, 95),
    "F": (180, 79, 191),
    "L": (122, 92, 196),
    "C": (128, 128, 140),
}
BG = (250, 249, 246)
GRID = (228, 225, 218)
INK = (40, 40, 46)
SUB = (90, 90, 100)
LINE = (55, 55, 62)


def fnt(size, bold=False):
    path = FONT_BOLD if bold else FONT_REG
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def load_catalog():
    cat = json.load(io.open(CATALOG, encoding="utf-8"))
    return {r["formula"]: r for r in cat}


def sprite_for(rec):
    """返回 (atoms[(el,dx,dy)], bonds[(dx1,dy1,dx2,dy2,kind)], n)，单位=格。"""
    place = {int(k): (v[0], v[1]) for k, v in rec["place"].items()}
    xy = {i: (SQ3 * (q + r / 2.0), 1.5 * r) for i, (q, r) in place.items()}
    n = len(rec["atoms"])
    cx = sum(v[0] for v in xy.values()) / n
    cy = sum(v[1] for v in xy.values()) / n
    off = {i: ((x - cx) * SPRITE_S, (y - cy) * SPRITE_S) for i, (x, y) in xy.items()}
    atoms = [(rec["atoms"][i], off[i][0], off[i][1]) for i in range(n)]
    bonds = []
    for e in rec["edges"]:
        i, j = int(e[0]), int(e[1])
        q1, r1 = place[i]
        q2, r2 = place[j]
        kind = classify_offset((q2 - q1, r2 - r1))
        bonds.append((off[i][0], off[i][1], off[j][0], off[j][1], kind))
    return atoms, bonds, n


_sprite_cache = {}


def get_sprite(rec):
    key = rec["formula"]
    if key not in _sprite_cache:
        _sprite_cache[key] = sprite_for(rec)
    return _sprite_cache[key]


def draw_bond(d, x1, y1, x2, y2, kind, w, color=LINE):
    w = max(1, int(w))
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1.0
    ux, uy = dx / L, dy / L
    if kind == "S":
        d.line([(int(x1), int(y1)), (int(x2), int(y2))], fill=color, width=w)
    elif kind == "C":
        seg, gap = max(2.5, w * 2.2), max(2.0, w * 1.7)
        t = 0.0
        while t < L:
            t2 = min(L, t + seg)
            d.line([(int(x1 + ux * t), int(y1 + uy * t)),
                    (int(x1 + ux * t2), int(y1 + uy * t2))],
                   fill=color, width=w)
            t = t2 + gap
    else:  # L: dotted
        dot, gap = max(1.2, w * 0.8), max(2.8, w * 2.0)
        t = 0.0
        while t < L:
            d.ellipse([x1 + ux * t - dot / 2, y1 + uy * t - dot / 2,
                       x1 + ux * t + dot / 2, y1 + uy * t + dot / 2], fill=color)
            t += dot + gap


def draw_molecule(d, cx, cy, rec, cell, max_cells=2.6):
    """把一个分子的骨架方块画在 (cx,cy)；大分子自动缩小到 max_cells 格内。"""
    atoms, bonds, n = get_sprite(rec)
    ext = 0.0
    for (el, dx, dy) in atoms:
        ext = max(ext, abs(dx), abs(dy))
    if ext <= 0:
        s = 1.0
    else:
        s = min(1.0, (max_cells / 2.0) / ext)
    blk = max(3.2, cell * ATOM_FRAC * s)
    for (ax1, ay1, ax2, ay2, kind) in bonds:
        draw_bond(d, cx + ax1 * s * cell, cy + ay1 * s * cell,
                  cx + ax2 * s * cell, cy + ay2 * s * cell, kind,
                  max(1.0, cell * 0.13 * s))
    r = blk / 2.0
    wpx = 1 if blk < 9 else 2
    for (el, dx, dy) in atoms:
        x, y = cx + dx * s * cell, cy + dy * s * cell
        col = COL.get(el, (120, 120, 120))
        d.rectangle([int(round(x - r)), int(round(y - r)),
                     int(round(x + r)), int(round(y + r))],
                    fill=col, outline=(35, 35, 40), width=wpx)
    return n


def density_map(mols, W, H):
    dens = [[0] * W for _ in range(H)]
    for (r, c, f) in mols:
        dens[r % H][c % W] += 1
    return dens


def win_score(dens, H, W, ox, oy, sw, sh):
    s = 0
    for r in range(oy, oy + sh):
        row = dens[r % H]
        for c in range(ox, ox + sw):
            s += row[c % W]
    return s


def choose_windows(mols, W, H, sw, sh):
    dens = density_map(mols, W, H)
    cands = []
    for oy in range(0, H - sh + 1, max(1, sh // 4)):
        for ox in range(0, W - sw + 1, max(1, sw // 4)):
            cands.append((win_score(dens, H, W, ox, oy, sw, sh), ox, oy))
    cands.sort(reverse=True)
    picks = []
    min_dist = min(sw, sh) * 0.7

    def far(a, b):
        dx = min(abs(a[0] - b[0]), W - abs(a[0] - b[0]))
        dy = min(abs(a[1] - b[1]), H - abs(a[1] - b[1]))
        return math.hypot(dx, dy) >= min_dist

    picks.append(("A", "最密集区域", cands[0][1], cands[0][2], cands[0][0]))
    chosen = None
    for s, ox, oy in cands[len(cands) // 2:]:
        if far((ox, oy), (picks[0][2], picks[0][3])):
            chosen = (ox, oy, s)
            break
    chosen = chosen or (cands[len(cands) // 2][1], cands[len(cands) // 2][2],
                        cands[len(cands) // 2][0])
    picks.append(("B", "中等密度区域", chosen[0], chosen[1], chosen[2]))
    chosen = None
    for s, ox, oy in reversed(cands):
        if (far((ox, oy), (picks[0][2], picks[0][3]))
                and far((ox, oy), (picks[1][2], picks[1][3]))):
            chosen = (ox, oy, s)
            break
    chosen = chosen or (0, 0, 0)
    picks.append(("C", "最稀疏区域", chosen[0], chosen[1], chosen[2]))

    prev = [(p[2], p[3]) for p in picks]
    bigs = sorted(mols, key=lambda m: -natoms_cache.get(m[2], 0))[:300]
    chosen = None
    for (r, c, f) in bigs:
        ox = min(max(0, c - sw // 2), W - sw)
        oy = min(max(0, r - sh // 2), H - sh)
        if all(far((ox, oy), p) for p in prev):
            chosen = (ox, oy)
            break
    if chosen is None:
        chosen = (max(0, W - sw), max(0, H - sh))
    ox, oy = chosen
    picks.append(("D", "最大分子附近", ox, oy,
                  win_score(dens, H, W, ox, oy, sw, sh)))
    return picks, dens


natoms_cache = {}
_comp_cache = {}


def parse_comp(f):
    if f in _comp_cache:
        return _comp_cache[f]
    d = {}
    i = 0
    while i < len(f):
        ch = f[i]
        i += 1
        num = ""
        while i < len(f) and f[i].isdigit():
            num += f[i]
            i += 1
        d[ch] = d.get(ch, 0) + (int(num) if num else 1)
    _comp_cache[f] = d
    return d


def slice_stats(mols, W, H, ox, oy, sw, sh):
    sub = [(r, c, f) for (r, c, f) in mols
           if 0 <= (r - oy) % H < sh and 0 <= (c - ox) % W < sw]
    comp = {}
    for (r, c, f) in sub:
        comp[f] = comp.get(f, 0) + 1
    top = sorted(comp.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
    ecl = {e: 0 for e in "OXCKAPFWL"}
    atoms_total = 0
    for (r, c, f) in sub:
        cf = parse_comp(f)
        atoms_total += sum(cf.values())
        for e, k in cf.items():
            ecl[e] += k
    cell = {(r, c): f for (r, c, f) in sub}
    seen = set()
    sizes = []
    for p in cell:
        if p in seen:
            continue
        stack = [p]
        seen.add(p)
        k = 0
        while stack:
            q = stack.pop()
            k += 1
            r, c = q
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    nb = ((r + dr) % H, (c + dc) % W)
                    if nb in cell and nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
        sizes.append(k)
    sizes.sort(reverse=True)
    return {
        "window": [ox, oy, sw, sh],
        "n": len(sub),
        "density": round(len(sub) / float(sw * sh), 4),
        "n_distinct": len(comp),
        "top": top,
        "atoms": atoms_total,
        "mean_atoms": round(atoms_total / len(sub), 2) if sub else 0.0,
        "elements": ecl,
        "clusters": {"n_components": len(sizes),
                     "max": sizes[0] if sizes else 0,
                     "in_big": sum(s for s in sizes if s >= 3)},
        "mols": sub,
    }


def draw_slice_image(mols, W, H, ox, oy, sw, sh, cell, cat, max_cells=2.2):
    img = Image.new("RGB", (sw * cell, sh * cell), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for i in range(sw + 1):
        d.line([(i * cell, 0), (i * cell, sh * cell)], fill=GRID, width=1)
    for j in range(sh + 1):
        d.line([(0, j * cell), (sw * cell, j * cell)], fill=GRID, width=1)
    sub = [(r, c, f) for (r, c, f) in mols
           if 0 <= (r - oy) % H < sh and 0 <= (c - ox) % W < sw]
    sub.sort(key=lambda m: natoms_cache.get(m[2], 0))
    for (r, c, f) in sub:
        rec = cat.get(f)
        cx = ((c - ox) % W) * cell + cell / 2.0
        cy = ((r - oy) % H) * cell + cell / 2.0
        if rec:
            draw_molecule(d, cx, cy, rec, cell, max_cells)
        else:
            rr = cell * 0.2
            d.rectangle([cx - rr, cy - rr, cx + rr, cy + rr],
                        fill=(150, 150, 150), outline=(60, 60, 60))
    d.rectangle([0, 0, sw * cell - 1, sh * cell - 1], outline=(80, 80, 90), width=2)
    return img


def draw_zoom(mols, W, H, ox, oy, sw, sh, cell, cat, max_cells=2.4):
    img = Image.new("RGB", (sw * cell, sh * cell), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for i in range(sw + 1):
        d.line([(i * cell, 0), (i * cell, sh * cell)], fill=(236, 233, 226), width=1)
    for j in range(sh + 1):
        d.line([(0, j * cell), (sw * cell, j * cell)], fill=(236, 233, 226), width=1)
    sub = [(r, c, f) for (r, c, f) in mols
           if 0 <= (r - oy) % H < sh and 0 <= (c - ox) % W < sw]
    sub.sort(key=lambda m: natoms_cache.get(m[2], 0))
    labels = []
    for (r, c, f) in sub:
        rec = cat.get(f)
        cx = ((c - ox) % W) * cell + cell / 2.0
        cy = ((r - oy) % H) * cell + cell / 2.0
        if rec:
            draw_molecule(d, cx, cy, rec, cell, max_cells)
        else:
            rr = cell * 0.18
            d.rectangle([cx - rr, cy - rr, cx + rr, cy + rr],
                        fill=(150, 150, 150), outline=(60, 60, 60))
        n = natoms_cache.get(f, 0)
        if n >= 10:
            labels.append((cx, cy, f, n))
    labels.sort(key=lambda t: -t[3])
    placed = []
    lf = fnt(15)
    for (cx, cy, f, n) in labels:
        if len(placed) >= 6:
            break
        tw = d.textlength(f, font=lf)
        th = 18
        x = min(max(2.0, cx + cell * 0.45), sw * cell - 2 - tw)
        y = min(max(2.0, cy - cell * 0.72), sh * cell - 2 - th)
        box = (x, y, x + tw, y + th)
        if any(not (box[2] < b[0] or b[2] < box[0]
                    or box[3] < b[1] or b[3] < box[1]) for b in placed):
            continue
        placed.append(box)
        d.text((x, y), f, font=lf, fill=(25, 25, 35))
    d.rectangle([0, 0, sw * cell - 1, sh * cell - 1], outline=(80, 80, 90), width=2)
    return img


def main():
    result = json.load(io.open(RESULT, encoding="utf-8"))
    cat = load_catalog()
    for f in cat:
        natoms_cache[f] = cat[f]["natoms"]
    snap = result["snapshots"][-1]
    W = result["config"]["W"]
    H = result["config"]["H"]
    mols = [(r, c, f) for (r, c, f) in snap["mols"]]
    for (r, c, f) in mols:
        if f not in natoms_cache:
            natoms_cache[f] = sum(parse_comp(f).values())

    SW, SH = 40, 30
    CELL = 26
    picks, dens = choose_windows(mols, W, H, SW, SH)
    print("windows:", [(p[0], p[1], p[2], p[3], p[4]) for p in picks])

    panels = []
    for key, desc, ox, oy, score in picks:
        st = slice_stats(mols, W, H, ox, oy, SW, SH)
        img = draw_slice_image(mols, W, H, ox, oy, SW, SH, CELL, cat)
        panels.append((key, desc, ox, oy, img, st))
        print("[%s] %s window=(%d,%d) n=%d distinct=%d mean_atoms=%.1f "
              "max_cluster=%d top=%s"
              % (key, desc, ox, oy, st["n"], st["n_distinct"], st["mean_atoms"],
                 st["clusters"]["max"], st["top"][:4]))

    slice_w, slice_h = SW * CELL, SH * CELL
    pad = 22
    right_w = 960
    head_h = 100
    row_h = slice_h + 58
    right_h = 30 + int(round(right_w * H / float(W))) + 28 + 30 + 12 * 60 + 34 + 150
    left_h = head_h + row_h * 2 + 10
    H_IMG = max(left_h, head_h + right_h) + 150
    W_IMG = pad + (slice_w * 2 + pad * 3) + right_w + pad

    canvas = Image.new("RGB", (W_IMG, H_IMG), BG)
    d = ImageDraw.Draw(canvas)
    cfg = result["config"]
    d.text((pad, 24), "T82 九元素环境：最终状态的骨架方块切片",
           font=fnt(42, True), fill=INK)
    d.text((pad, 78),
           "方格环面 %dx%d · 每格 1 分子 · T62 九元素投料 1600 分子 · %d 拍 · "
           "三素力（聚吸引/散半径/动排斥）驱动 + 规则 1~11 反应 · 终态 N=%d"
           % (W, H, cfg["ticks"], snap["n"]),
           font=fnt(19), fill=SUB)

    positions = [(pad, head_h), (pad * 2 + slice_w, head_h),
                 (pad, head_h + row_h), (pad * 2 + slice_w, head_h + row_h)]
    for (key, desc, ox, oy, img, st), (x, y) in zip(panels, positions):
        d.text((x, y), "%s  %s  窗口 (%d,%d) %dx%d 格" %
               (key, desc, ox, oy, SW, SH), font=fnt(22, True), fill=INK)
        d.text((x, y + 30),
               "N=%d 种数=%d 平均 %.1f 原子 局部最大团=%d 顶: %s" %
               (st["n"], st["n_distinct"], st["mean_atoms"],
                st["clusters"]["max"],
                ", ".join("%s×%d" % (f, k) for f, k in st["top"][:4])),
               font=fnt(16), fill=SUB)
        canvas.paste(img, (x, y + 56))
        d.rectangle([x, y + 56, x + slice_w, y + 56 + slice_h],
                    outline=(60, 60, 70), width=2)

    # ---------------- 全环境密度图 ----------------
    mx = pad * 2 + slice_w * 2 + pad
    y0 = head_h
    mapw, maph = right_w, int(round(right_w * H / float(W)))
    d.text((mx, y0), "全环境地图（密度：越红越密；蓝框=四个切片）",
           font=fnt(22, True), fill=INK)
    mimg = Image.new("RGB", (W, H), (255, 255, 255))
    mp = mimg.load()
    for r in range(H):
        for c in range(W):
            v = dens[r][c]
            t = min(1.0, v / 1.5)
            base = (250, 248, 242)
            hot = (196, 74, 44)
            mp[c, r] = tuple(int(base[i] + (hot[i] - base[i]) * t) for i in range(3))
    mimg = mimg.resize((mapw, maph), Image.BILINEAR)
    canvas.paste(mimg, (mx, y0 + 32))
    d.rectangle([mx, y0 + 32, mx + mapw, y0 + 32 + maph],
                outline=(60, 60, 70), width=2)
    for (key, desc, ox, oy, img, st) in panels:
        sx = mx + ox * mapw / float(W)
        sy = y0 + 32 + oy * maph / float(H)
        sx2 = mx + (ox + SW) * mapw / float(W)
        sy2 = y0 + 32 + (oy + SH) * maph / float(H)
        d.rectangle([sx, sy, sx2, sy2], outline=(20, 90, 160), width=3)
        d.text((sx + 4, sy + 3), key, font=fnt(20, True), fill=(20, 90, 160))

    # ---------------- 放大细节 ----------------
    zy0 = y0 + 32 + maph + 26
    d.text((mx, zy0), "E 原地放大（16×12 格）：每个分子的骨架方块",
           font=fnt(22, True), fill=INK)
    big = max(mols, key=lambda m: natoms_cache.get(m[2], 0))
    zox = min(max(0, big[1] - 8), W - 16)
    zoy = min(max(0, big[0] - 6), H - 12)
    zimg = draw_zoom(mols, W, H, zox, zoy, 16, 12, 60, cat)
    canvas.paste(zimg, (mx, zy0 + 34))
    d.rectangle([mx, zy0 + 34, mx + zimg.size[0], zy0 + 34 + zimg.size[1]],
                outline=(60, 60, 70), width=2)
    d.text((mx, zy0 + 38 + zimg.size[1]),
           "窗口 (%d,%d) 16×12 格；≥8 原子的分子标了分子式" % (zox, zoy),
           font=fnt(16), fill=SUB)

    # ---------------- 图例 ----------------
    ly = zy0 + 38 + zimg.size[1] + 26
    d.text((mx, ly), "元素配色（原子方块）", font=fnt(20, True), fill=INK)
    ex = mx
    ey = ly + 32
    for e in "OXCKAPFWL":
        d.rectangle([ex, ey, ex + 24, ey + 24], fill=COL[e], outline=(40, 40, 40))
        d.text((ex + 30, ey + 2), e, font=fnt(19), fill=INK)
        ex += 58
    d.text((mx, ey + 40), "键型：S 实线 · C 虚线 · L 点线（骨架来自目录 place 坐标）",
           font=fnt(17), fill=SUB)
    d.text((mx, ey + 66), "分子图像锚定在它占据的那一格；大分子会自动缩小，",
           font=fnt(17), fill=SUB)
    d.text((mx, ey + 92), "所以相邻格子里的分子仍能分辨——这就是环境的真实样貌。",
           font=fnt(17), fill=SUB)

    # 页脚
    fy = H_IMG - 62
    d.text((pad, fy),
           "读图：每格至多 1 个分子；原子方块颜色 = 9 元素；键线 = 分子骨架；"
           "A/B/C/D 为同一终态环境的 4 个切片，E 为原地放大。",
           font=fnt(18), fill=SUB)
    d.text((pad, fy + 28),
           "诚实注：模拟中分子是点粒子，骨架图按目录结构绘制并锚定在格子中心；"
           "反应产物不在目录中时画成灰色小方块（本图 %d 种）。"
           % sum(1 for (r, c, f) in mols if f not in cat),
           font=fnt(18), fill=SUB)

    out = os.path.join(BASE, "images", "t82_slices.png")
    canvas.save(out)
    print("saved", out, canvas.size)

    for (key, desc, ox, oy, img, st) in panels:
        img.save(os.path.join(BASE, "images", "t82_slice_%s.png" % key.lower()))
    zimg.save(os.path.join(BASE, "images", "t82_slice_zoom.png"))

    out2 = os.path.join(BASE, "t82_slices.json")
    data = {
        "config": cfg,
        "final_summary": result["summary"],
        "windows": [{"key": key, "desc": desc, "ox": ox, "oy": oy,
                     "sw": SW, "sh": SH,
                     "stats": {k: v for k, v in st.items() if k != "mols"}}
                    for (key, desc, ox, oy, img, st) in panels],
        "zoom": {"ox": zox, "oy": zoy, "sw": 16, "sh": 12},
    }
    with io.open(out2, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    print("saved", out2)


if __name__ == "__main__":
    main()
